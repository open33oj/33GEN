#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""编译 C++ 源文件、生成与校验测试数据。

用法：
    python3 tools/build.py <命令> --problem <pid> [选项]

命令：
    build      编译 std.cpp / 子任务程序 / gen.cpp / valid.cpp / checker.cpp / interactor.cpp
    gen        运行 gen.cpp 生成全部测试点（.in 与 .ans）
    validate   用 valid.cpp 校验全部 .in
    check      校验全部 .ans 的格式（能读开、行尾规范、非空），SPJ 题再用 checker 自校
    all        依次执行 build -> gen -> validate -> check
    clean      删除 build/<pid>/
    list       列出 config.yaml 里声明的测试点

选项：
    --problem <pid>     题目编号（目录名），必填
    --case <name>       只处理某个测试点的 input 文件名（如 a1.in）
    --skip <步骤>       在 all 中跳过某一步，可重复（如 --skip check）
    --jobs <n>          并行编译数（默认 1，Windows 下建议 <= 4）

约定（详见 AGENTS.md）：
  * 数据生成器 gen.cpp 使用 testlib，且通过命令行参数接收随机种子与数据规模。
  * 每个测试点调用一次生成器：`gen --case <input名> <args...>`，
    生成器把该测试点的输入写到 stdout，答案由标程 std 生成（要求题目不是 SPJ 型）。
  * 若题目是 SPJ/交互题，请设置 config.yaml 中该测试点的 `answer: external`，
    此时 `.ans` 由 gen 自行写盘（约定写 `<input基本名>.ans`），不再运行标程。
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import (  # noqa: E402
    SRC_GEN, SRC_STD, SRC_VALID, SRC_CHECKER, SRC_INTERACTOR,
    Problem, compile_source, die, exe, log, run, temp_dir, warn,
)

ALL_STEPS = ["build", "gen", "validate", "check"]


# ---------------------------------------------------------------- build

def step_build(p: Problem, jobs: int = 1) -> dict:
    """编译题目目录下所有 C++ 程序，返回 {类别: 可执行文件路径}。"""
    log("[1/1] 编译 %s 的源文件" % p.pid)
    out_dir = p.build / "bin"
    built = {}
    names = [("std", SRC_STD), ("gen", SRC_GEN), ("valid", SRC_VALID),
             ("checker", SRC_CHECKER), ("interactor", SRC_INTERACTOR)]
    # 函数式交互题（grader 型）：src/std.cpp 是"选手参考实现"，
    # 它 #include grader 下发的头文件、且没有 main，不能单独编译，也不参与评测。
    grader_style = bool(p.hydro_config.get("user_extra_files"))
    if grader_style:
        names = [(k, f) for k, f in names if k != "std"]
    # 子任务程序：30.cpp / 60.cpp ...
    for score, path in p.subtask_sources():
        names.append(("sub%d" % score, path.name))
    for key, fname in names:
        src = p.src / fname
        if src.is_file():
            built[key] = compile_source(src, out_dir)
        elif key in ("std",):
            warn("%s 缺少 %s" % (p.pid, fname))
    if not built:
        die("%s 下没有任何 .cpp 源文件" % p.src)
    log("  编译完成：%s" % ", ".join(sorted(built)))
    return built


# ---------------------------------------------------------------- gen

def normalize_lf(path: Path) -> bool:
    """把 CRLF / 孤立 CR 统一成 LF。返回是否发生过修改。

    Windows 上 C 的文本模式写文件会把 \\n 变成 \\r\\n，而评测机在 Linux 上
    需要 LF，所以生成/收集数据后统一归一化（见 AGENTS.md 第 9 条：
    数据格式由 python3 统一把关）。
    """
    raw = path.read_bytes()
    fixed = raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    if fixed != raw:
        path.write_bytes(fixed)
        return True
    return False


def run_std(p: Problem, std_exe, in_path: Path, out_path: Path) -> None:
    """用标程从 in_path 算出 out_path。

    全程使用二进制管道：Windows 下 text 模式会把 \\n 转成 \\r\\n，
    而测试数据必须统一为 LF。若 config.yaml 里配置了 `filename: foo`，
    则按文件 IO 方式运行（在临时目录里以 foo.in / foo.out 交互）。
    """
    import subprocess

    fname = p.hydro_config.get("filename")
    if fname:
        with temp_dir("std-%s-" % p.pid) as td:
            td = Path(td)
            shutil.copyfile(str(in_path), str(td / (fname + ".in")))
            r = subprocess.run([str(std_exe)], cwd=str(td),
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if r.returncode != 0:
                print(r.stderr.decode("utf-8", "replace"), file=sys.stderr)
                die("std 在 %s 上崩溃（exit %d，文件 IO 模式）" % (in_path.name, r.returncode))
            produced = td / (fname + ".out")
            if not produced.is_file():
                die("std 未生成 %s（题目声明了 filename: %s）" % (produced.name, fname))
            out_path.write_bytes(produced.read_bytes())
            if normalize_lf(out_path):
                warn("%s 含 CRLF，已归一化为 LF（标程写文件未用二进制模式）" % out_path.name)
        return

    r = subprocess.run([str(std_exe)], input=in_path.read_bytes(),
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if r.returncode != 0:
        print(r.stderr.decode("utf-8", "replace"), file=sys.stderr)
        die("std 在 %s 上崩溃（exit %d）" % (in_path.name, r.returncode))
    out_path.write_bytes(r.stdout)
    if normalize_lf(out_path):
        warn("%s 含 CRLF，已归一化为 LF" % out_path.name)


def gen_case_names(gen_exe) -> list:
    """问生成器要它支持的测试点名单（`gen --list`）。

    生成器可以不实现 --list：此时返回空列表，调用方跳过一致性检查。
    """
    proc = run([gen_exe, "--list"], check=False, capture=True)
    if proc.returncode != 0:
        return []
    names = [x.strip() for x in (proc.stdout or "").split("\n") if x.strip()]
    # 只有每行都像测试点名才认（避免把帮助/报错当名单）
    if names and all(re.match(r"^[A-Za-z0-9_.-]+$", n) for n in names):
        return names
    return []


def step_gen(p: Problem, built: dict, only_case: str = None) -> list:
    """运行生成器产出全部测试点，返回生成的文件列表。

    生成器接口（见 docs/workflow.md §3）：

        gen --case <测试点名> [--list]

    其中 `<测试点名>` 是 `config.yaml` 里 `input` 去掉 `.in` 后的名字，
    生成器**自己把输入写到 `<测试点名>.in`**（在当前工作目录，即被调用的目录）。
    随机种子与数据规模由生成器内部维护的配置表决定，不通过命令行传入。
    """
    if "gen" not in built:
        die("%s 缺少 %s，无法生成数据" % (p.pid, SRC_GEN))
    cfg = p.hydro_config
    spj = bool(cfg.get("checker") and cfg.get("checker_type") != "default")
    p.data.mkdir(parents=True, exist_ok=True)
    gen_exe = built["gen"]
    std_exe = built.get("std")
    made = []

    cases = p.cases()
    if only_case:
        cases = [c for c in cases if c[2] == only_case]
        if not cases:
            die("config.yaml 中没有测试点 %s" % only_case)

    # 一致性检查：config.yaml 的测试点 vs 生成器声明的测试点
    declared = gen_case_names(gen_exe)
    wanted = [Path(c[2]).stem for c in cases]
    if declared:
        unknown = [n for n in wanted if n not in declared]
        unused = [n for n in declared if n not in [Path(c[2]).stem for c in p.cases()]]
        if unknown:
            die("生成器不认识这些测试点：%s\n"
                "        gen.cpp 的 CASES 表里只声明了：%s"
                % (", ".join(unknown), ", ".join(declared)))
        if unused:
            warn("gen.cpp 声明了但 config.yaml 里没用的测试点：%s" % ", ".join(unused))

    log("[2] 生成 %d 个测试点" % len(cases))
    for si, ci, in_name, out_name in cases:
        in_path = p.data / in_name
        out_path = p.data / out_name
        case_name = Path(in_name).stem
        if in_path.exists():
            # 先删掉旧文件，这样"生成器没写出文件"能被发现。
            # Windows 上文件可能被杀毒/索引/编辑器短暂占用，重试几次而不是直接崩。
            for attempt in range(5):
                try:
                    in_path.unlink()
                    break
                except PermissionError:
                    if attempt == 4:
                        warn("%s 被其他程序占用，先跳过删除（生成器会覆盖它）" % in_name)
                    else:
                        time.sleep(0.2)
        cmd = [gen_exe, "--case", case_name]
        log("  $ %s" % " ".join(str(c) for c in cmd))
        # 生成器按相对路径写文件，所以用 data/ 作为工作目录
        proc = run(cmd, cwd=p.data, check=False, capture=True)
        if proc.returncode != 0:
            if proc.stdout:
                print(proc.stdout, file=sys.stderr)
            die("生成器在测试点 %s 上失败（exit %d）" % (case_name, proc.returncode))
        if not in_path.is_file():
            # 兼容旧写法：生成器把输入写到了 stdout（老约定）。
            if (proc.stdout or "").strip():
                warn("%s：生成器把数据写到了 stdout，已按旧约定收下。"
                     "建议改为 `gen --case %s` 自己写 %s（见 docs/workflow.md §3）"
                     % (p.pid, case_name, in_name))
                with open(in_path, "w", encoding="utf-8", newline="\n") as f:
                    f.write(proc.stdout)
            else:
                die("生成器没有产出 %s\n"
                    "        生成器约定：`gen --case %s` 应把输入写到 %s（当前工作目录）"
                    % (in_name, case_name, in_name))
        # Windows 上生成器用 fopen(..., "w") 会写出 CRLF；评测机要 LF，
        # 所以这里统一归一化（与标程输出同样处理，见 docs/workflow.md §0）。
        if normalize_lf(in_path):
            warn("%s 含 CRLF，已归一化为 LF（生成器写文件未用二进制模式）" % in_name)
        made.append(in_path)

        # 答案：统一用标程生成。
        #
        # 即使题目是 SPJ（答案不唯一），这样做也是对的：testlib checker 判定的是
        # "选手答案相对输入是否合法"，标准答案只起参照作用，标程给出一组合法解即可。
        # 这样还让"标程必须能跑通全部数据"成为一条硬性检查。
        # 只有交互题（有 interactor）不存在 .ans。
        # 函数式交互题（grader 型：config.yaml 里用 user_extra_files 下发 grader.cpp/头文件）
        # 同样没有"标程独立运行"这回事，答案也必须由 gen 提供。
        grader_style = bool(p.hydro_config.get("user_extra_files"))
        if "interactor" in built or grader_style:
            if out_path.is_file():
                log("    [交互] 答案由 gen 提供：%s" % out_name)
            else:
                log("    [交互] 无答案文件（交互题）")
        else:
            if std_exe is None:
                # 函数式交互题没有可独立运行的 std（选手代码要与 grader 一起编译），
                # 答案由 gen 提供；其它题缺 std 则是错误。
                if grader_style:
                    log("    [交互] 无独立标程，答案由 gen 提供：%s" % out_name)
                else:
                    die("缺少 std.cpp，无法生成 %s" % out_name)
            else:
                run_std(p, std_exe, in_path, out_path)
        made.append(out_path)
    return made


# ---------------------------------------------------------------- validate

def step_validate(p: Problem, built: dict, only_case: str = None) -> int:
    if "valid" not in built:
        warn("%s 没有 valid.cpp，跳过校验（强烈建议补上，见 docs/workflow.md）" % p.pid)
        return 0
    log("[3] 校验测试点")
    bad = 0
    files = sorted(p.data.glob("*.in"))
    if only_case:
        files = [f for f in files if f.name == only_case]
    if not files:
        die("%s 下没有 .in 文件，请先运行 gen" % p.data)
    for f in files:
        # testlib 校验器从 stdin 读输入（不能把文件名当参数传）
        import subprocess
        proc = subprocess.run([str(built["valid"])], input=f.read_bytes(),
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        if proc.returncode != 0:
            bad += 1
            sys.stderr.write(proc.stdout.decode("utf-8", "replace"))
            warn("校验失败：%s" % f.name)
        else:
            log("  [ok  ] %s" % f.name)
    if bad:
        die("%d 个测试点校验失败" % bad)
    return 0


# ---------------------------------------------------------------- check

def step_check(p: Problem, built: dict, only_case: str = None) -> int:
    """对答案做基本健全性检查：存在、非空、行尾为\\n、无 \\r；
    SPJ 题再用 checker.cpp 自校一遍（checker <in> <ans> <ans> 必须判 ok）。"""
    import subprocess

    log("[4] 检查答案文件")
    bad = 0
    cases = [c for c in p.cases()
             if not only_case or c[2] == only_case]
    for si, ci, in_name, out_name in cases:
        in_path = p.data / in_name
        out_path = p.data / out_name
        if not in_path.is_file():
            warn("缺少输入：%s" % in_name)
            bad += 1
            continue
        if not out_path.is_file():
            warn("缺少答案：%s" % out_name)
            bad += 1
            continue
        if in_path.stat().st_size == 0:
            warn("输入为空：%s" % in_name)
            bad += 1
        raw = out_path.read_bytes()
        if not raw:
            warn("答案为空：%s" % out_name)
            bad += 1
        if b"\r" in raw:
            warn("答案含 CR（应为 LF 换行）：%s" % out_name)
            bad += 1
        if raw and not raw.endswith(b"\n"):
            warn("答案末尾缺少换行：%s" % out_name)
            bad += 1
    if bad:
        die("%d 处答案文件问题" % bad)

    # SPJ 题：checker 必须接受标程给出的答案（否则 checker 自身就写错了）
    if "checker" in built:
        for si, ci, in_name, out_name in cases:
            in_path = p.data / in_name
            out_path = p.data / out_name
            if not (in_path.is_file() and out_path.is_file()):
                continue
            proc = subprocess.run(
                [str(built["checker"]), str(in_path), str(out_path), str(out_path)],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            if proc.returncode != 0:
                sys.stderr.write(proc.stdout.decode("utf-8", "replace"))
                warn("checker 认为 %s 的标准答案不合法（exit %d）"
                     % (out_name, proc.returncode))
                bad += 1
        if bad:
            die("checker 自校失败：%d 个测试点" % bad)
        log("  checker 自校通过（%d 个测试点）" % len(cases))
    log("  全部答案文件正常")
    return 0


# ---------------------------------------------------------------- main

def main() -> int:
    ap = argparse.ArgumentParser(description="编译与数据生成工具（见 AGENTS.md）")
    ap.add_argument("command", choices=["build", "gen", "validate", "check", "all", "clean", "list"])
    ap.add_argument("--problem", required=True, help="题目编号（problems/ 下的目录名）")
    ap.add_argument("--case", help="只处理指定 input 文件名")
    ap.add_argument("--skip", action="append", default=[], choices=ALL_STEPS,
                    help="all 命令中跳过的步骤，可重复")
    ap.add_argument("--jobs", type=int, default=1, help="并行编译数（保留参数）")
    args = ap.parse_args()

    p = Problem(args.problem)
    t0 = time.time()

    if args.command == "list":
        declared = None
        gen_src = p.src / SRC_GEN
        if gen_src.is_file():
            exe_path = p.build / "bin" / exe(gen_src.stem)
            if exe_path.is_file():
                declared = gen_case_names(exe_path)
            else:
                declared = "(未编译；先跑 build)"
        for si, ci, in_name, out_name in p.cases():
            case_name = Path(in_name).stem
            mark = ""
            if isinstance(declared, list) and declared:
                mark = "  [gen.cpp 已声明]" if case_name in declared else "  [gen.cpp 未声明!]"
            log("subtask%d case%d  %-14s -> %-14s（gen --case %s）%s"
                % (si, ci, in_name, out_name, case_name, mark))
        if declared is None:
            warn("%s 没有 %s，无法核对测试点声明" % (p.pid, SRC_GEN))
        elif isinstance(declared, str):
            warn(declared)
        elif declared:
            unused = [n for n in declared
                      if n not in [Path(c[2]).stem for c in p.cases()]]
            if unused:
                warn("gen.cpp 声明了但 config.yaml 没用到的测试点：%s" % ", ".join(unused))
        return 0

    if args.command == "clean":
        if p.build.exists():
            shutil.rmtree(str(p.build))
            log("已删除 %s" % p.build)
        return 0

    if args.command == "build":
        step_build(p, args.jobs)
        return 0

    built = step_build(p, args.jobs)

    if args.command in ("gen", "all") and "gen" not in args.skip:
        step_gen(p, built, args.case)
    if args.command in ("validate", "all") and "validate" not in args.skip:
        step_validate(p, built, args.case)
    if args.command in ("check", "all") and "check" not in args.skip:
        step_check(p, built, args.case)

    log("完成，用时 %.1fs" % (time.time() - t0))
    return 0


if __name__ == "__main__":
    sys.exit(main())
