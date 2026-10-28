#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""导出 Hydro OJ 题目压缩包（Hydro Problem Format）。

用法：
    python3 tools/pack_hydro.py --problem <pid> [--out <zip>] [--no-zip]
    python3 tools/pack_hydro.py --day d1            # 一天的 6 道题打成一个包

产出的 zip 结构（见 docs/formats.md）：

    <Hydro 题号>.zip                     # 单题：build/hydro/C0141.zip
    └── C0141/
        ├── problem.yaml                 # pid = meta.yaml 的 hydro_pid
        ├── problem_zh.md                # 小样例为 ```inputk / ```outputk，
        │                                # 大样例为 additional_file 里的下载链接
        ├── testdata/
        │   ├── config.yaml
        │   ├── *.in / *.ans
        │   ├── std.cc / gen.cc / valid.cc / checker.cc / interactor.cc
        │   └── sol.md
        └── additional_file/
            └── <英文短名><k>.in / .ans  # 下发的大样例（k 从「小样例个数 + 1」开始）

    d1.zip                               # 场次级：--day d1，一个包 6 题
    ├── C0141/  C0142/  …  C0146/        # 解压后就直接是 6 个题目文件夹（不多套一层）

注意：Hydro 默认要求 C++ 源文件扩展名为 .cc，因此这里统一把 .cpp 重命名为 .cc，
并同步改写 config.yaml 中的 checker / interactor 路径。
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import (  # noqa: E402
    BUILD, CONTESTS, SOLUTION, SRC_CHECKER, SRC_GEN, SRC_INTERACTOR, SRC_STD, SRC_VALID,
    Problem, die, log, read_text, read_yaml, subtask_section, write_text, write_yaml,
)

# 打进 testdata/ 的源码：源文件名 -> 包内文件名
SRC_MAP = [
    (SRC_STD, "std.cc"),
    (SRC_GEN, "gen.cc"),
    (SRC_VALID, "valid.cc"),
    (SRC_CHECKER, "checker.cc"),
    (SRC_INTERACTOR, "interactor.cc"),
]

# config.yaml 里理论上是干净的（生成参数写在 gen.cpp 的 CASES 表里，见
# docs/workflow.md §3.2）；这里仍然做一次清洗，防止手工加的私有键漏进交付包。
PRIVATE_KEYS = ("args", "name", "gen")

# Hydro 题面的样例写法（见 docs/formats.md）：
# 题面源文件用的是 CNOI/PDF 方言（「## 样例 k 输入」+ 普通代码块），
# 打包时转成 Hydro 认识的 ```inputk / ```outputk，两者自动并排显示。
# 标题级别取 1~6：题面里两个小样例常写成 `### 样例 1 输入`（与 tools/samples.py 的
# RE_SAMPLE_HEADING 保持同一口径，漏掉 `###` 会让样例在 Hydro 里退化成普通代码块）。
RE_SAMPLE_HEAD = re.compile(r"^#{1,6}\s*样例\s*(\d+)\s*(输入|输出)\s*$")
RE_FENCE = re.compile(r"^\s*(`{3,}|~{3,})\s*$")
# 大样例在题面里写成「见选手目录下的 <短名>/<短名>k.in 与 <短名>/<短名>k.ans。」
# 打包时改写成 additional_file 里的下载链接（file:// 是 Hydro 的附加文件协议）。
RE_BIG_SAMPLE_POINTER = re.compile(
    r"见选手目录下的\s*`?([^`\s]+?)`?\s*与\s*`?([^`\s]+?)`?\s*。")


def hydro_statement(md: str):
    """把 CNOI 风格的题面转成 Hydro 题面。

    返回 (题面文本, 大样例文件基本名列表)。列表里的文件需要放进 `additional_file/`，
    题面里的链接就是指向它们的。
    """
    lines = md.replace("\r\n", "\n").split("\n")
    extras = []

    def pointer(m):
        a = Path(m.group(1)).name
        b = Path(m.group(2)).name
        extras.extend([a, b])
        return "见 [%s](file://%s) 与 [%s](file://%s)。" % (a, a, b, b)

    out = []
    i = 0
    while i < len(lines):
        head = RE_SAMPLE_HEAD.match(lines[i])
        if head is None:
            out.append(RE_BIG_SAMPLE_POINTER.sub(pointer, lines[i]))
            i += 1
            continue
        # 「## 样例 k 输入 / 输出」后面紧跟代码块 -> ```inputk / ```outputk
        idx, kind = head.group(1), head.group(2)
        j = i + 1
        while j < len(lines) and not lines[j].strip():
            j += 1
        fm = RE_FENCE.match(lines[j]) if j < len(lines) else None
        if fm is None:                      # 没有代码块：原样保留，交给人工检查
            out.append(lines[i])
            i += 1
            continue
        fence = fm.group(1)
        j += 1
        body = []
        while j < len(lines) and not RE_FENCE.match(lines[j]):
            body.append(lines[j])
            j += 1
        out.append("```%s%s" % ("input" if kind == "输入" else "output", idx))
        out.extend(body)
        out.append("```")
        i = j + 1

    # 自检：转换完之后题面里不该再出现"样例 k 输入/输出"标题 + 普通代码块
    # （标题级别写错、代码块没闭合都会走到这里，宁可报错也不要交出一个样例退化的包）。
    for n, line in enumerate(out, 1):
        stale = RE_SAMPLE_HEAD.match(line)
        if stale:
            die("打包题面时第 %d 行「%s」没有被转换成 ```input%s / ```output%s"
                % (n, line.strip(), stale.group(1), stale.group(1)))
    return "\n".join(out), list(dict.fromkeys(extras))


def clean_config(cfg: dict) -> dict:
    """去掉本工程私有的键（如测试点的 args、子任务的 name）。"""
    out = {}
    for k, v in cfg.items():
        if k in PRIVATE_KEYS:
            continue
        if k == "subtasks" and isinstance(v, list):
            new_st = []
            for st in v:
                nst = {kk: vv for kk, vv in st.items() if kk not in PRIVATE_KEYS}
                if isinstance(nst.get("cases"), list):
                    nst["cases"] = [{kk: vv for kk, vv in c.items() if kk not in PRIVATE_KEYS}
                                    for c in nst["cases"]]
                new_st.append(nst)
            out[k] = new_st
        else:
            out[k] = v
    return out


def hydro_pid(p: Problem) -> str:
    """题目在 Hydro 里的 pid：meta.yaml 的 `hydro_pid`（如 C0141），没写才退回目录名。"""
    return str(p.meta.get("hydro_pid") or p.meta.get("pid") or p.pid)


def build_tree(p: Problem, root: Path) -> Path:
    if root.exists():
        shutil.rmtree(str(root))
    (root / "testdata").mkdir(parents=True, exist_ok=True)

    meta = p.meta
    cfg = clean_config(p.hydro_config)

    # problem.yaml
    problem_yaml = {
        "title": meta.get("title") or p.pid,
        "tag": meta.get("tag") or [],
        "pid": hydro_pid(p),
    }
    write_yaml(root / "problem.yaml", problem_yaml)

    # problem_zh.md（Hydro 题面）：样例改成 ```inputk / ```outputk，
    # 大样例改成 additional_file 的下载链接（见 docs/formats.md），
    # 末尾补上与 config.yaml 同源的「## 子任务」小节（说明每个测试点的特点与分值）
    md, big_samples = hydro_statement(read_text(p.statement / "zh_CN.md"))
    # 题面自己（或原题）已经写了子任务相关内容时，一律不再追加，避免出现两份子任务说明
    # （例如公益赛导入的题目，子任务表本来就在题面的「数据规模与约定」里）。
    if "子任务" not in md:
        md = md.rstrip() + "\n" + subtask_section(p.hydro_config)
    write_text(root / "problem_zh.md", md)

    # 测试数据
    data_dir = root / "testdata"
    cases = p.cases()
    written = 0
    for _, _, in_name, out_name in cases:
        for name in (in_name, out_name):
            src = p.data / name
            if not src.is_file():
                die("缺少数据文件 %s；请先运行 python3 tools/build.py gen --problem %s"
                    % (src, p.pid))
            shutil.copyfile(str(src), str(data_dir / name))
            written += 1

    # 题解
    sol = p.dir / SOLUTION
    if sol.is_file():
        shutil.copyfile(str(sol), str(data_dir / SOLUTION))

    # 源码（.cpp -> .cc）
    for src_name, dst_name in SRC_MAP:
        src = p.src / src_name
        if not src.is_file():
            continue
        dst = data_dir / dst_name
        if dst.is_file():
            # 已经有 testdata/<dst_name>（函数式交互题的选手参考实现放在这里），
            # 不要用 src/ 下的同名文件覆盖它。
            log("  [skip] src/%s 不覆盖 testdata/%s" % (src_name, dst_name))
            continue
        shutil.copyfile(str(src), str(dst))

    # config.yaml 中的 C++ 路径同步改名
    def fix_path(v):
        if isinstance(v, str) and v.endswith(".cpp"):
            return v[:-4] + ".cc"
        return v
    for key in ("checker", "interactor"):
        if key in cfg:
            fixed = fix_path(cfg.get(key))
            if fixed:
                cfg[key] = fixed
            else:
                cfg.pop(key)   # 不要写出 checker: null 这种空键
    if cfg.get("checker") and cfg.get("checker_type") in (None, "default", "strict"):
        die("配置了 checker 但 checker_type 是 default/strict；"
            "请改为 checker_type: testlib（见 docs/formats.md）")
    write_yaml(data_dir / "config.yaml", cfg)

    # user_extra_files / judge_extra_files 里列出的文件也要放进 testdata/，
    # 否则评测机取不到（函数式交互题下发 grader.cpp / 头文件 / compile.sh 就靠这个）。
    for key in ("user_extra_files", "judge_extra_files"):
        for rel in (cfg.get(key) or []):
            if not isinstance(rel, str):
                continue
            dst = data_dir / rel
            if dst.is_file():
                continue
            src = p.hydro / "testdata" / rel
            if not src.is_file():
                die("config.yaml 的 %s 列了 %s，但 %s 不存在" % (key, rel, src))
            shutil.copyfile(str(src), str(dst))

    # 附加文件：静态的（图片/PDF）+ 本次生成的大样例
    add_root = root / "additional_file"
    add_src = p.hydro / "additional_file"
    if add_src.is_dir():
        for f in sorted(add_src.rglob("*")):
            if f.is_file():
                dst = add_root / f.relative_to(add_src)
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(str(f), str(dst))
    for base in big_samples:
        src = p.data / "samples" / base
        if not src.is_file():
            die("%s 缺少下发样例 %s；请先运行 python3 tools/samples.py --problem %s"
                % (p.pid, src, p.pid))
        add_root.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(str(src), str(add_root / base))
    if add_root.is_dir():
        log("  附加文件：%d 个（含大样例 %d 个）"
            % (len([f for f in add_root.rglob('*') if f.is_file()]), len(big_samples)))

    log("已组装 Hydro 题包目录：%s（%d 个数据文件）" % (root, written))
    return root


def make_zip(root: Path, out: Path, base: Path = None) -> Path:
    """把 root 下的文件打包。

    base 是"包内路径的参照点"：默认 root.parent，于是 zip 里带一层 `root.name/`；
    场次级题包传 base=root，这样**解压后直接就是每题的文件夹**（不再多套一层）。
    """
    base = base or root.parent
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()
    with zipfile.ZipFile(str(out), "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(root.rglob("*")):
            if f.is_file():
                z.write(str(f), str(f.relative_to(base)))
    log("已生成压缩包：%s（%.1f KiB）" % (out, out.stat().st_size / 1024.0))
    return out


def day_problems(day: str) -> list:
    """一天的 6 道题：`contests/<day>-j.yaml` 的 4 题 + `<day>-s.yaml` 里新增的题（按顺序去重）。

    例：`d1` → d1j1 d1j2 d1j3 d1j4 d1s2 d1s3（第 1 天 J 组 4 题 + S 组新增 2 题）。
    """
    got = []
    for suffix in ("-j", "-s"):
        path = CONTESTS / (day + suffix + ".yaml")
        if not path.is_file():
            die("找不到比赛配置：%s" % path)
        for item in (read_yaml(path).get("problems") or []):
            folder = item.get("folder") if isinstance(item, dict) else item
            if folder and folder not in got:
                got.append(folder)
    if not got:
        die("%s 的两场比赛里都没有题目" % day)
    return got


def main() -> int:
    ap = argparse.ArgumentParser(description="导出 Hydro 题目压缩包")
    ap.add_argument("--problem", action="append", default=[],
                    help="题目编号（problems/ 下的目录名），可重复")
    ap.add_argument("--day", help="场次级题包：把 contests/<day>-j/-s.yaml 里的 6 道题打成一个 zip")
    ap.add_argument("--batch", help="批量题包：把 --problem 列出的题打成一个 zip（解压后直接是各题文件夹）")
    ap.add_argument("--out", help="输出 zip 路径（默认 build/hydro/<Hydro 题号>.zip）")
    ap.add_argument("--no-zip", action="store_true", help="只组装目录，不打包")
    args = ap.parse_args()

    if not args.problem and not args.day:
        ap.error("请给出 --problem <pid>（可重复）、--day <id> 或 --batch <名称>")
    if args.problem and args.day:
        ap.error("--problem 与 --day 只能用一个")
    if args.day and args.batch:
        ap.error("--day 与 --batch 只能用一个")

    # 批量题包：把任意多道题放进同一个 zip，解压后直接是各题的 Hydro 题号文件夹
    if args.batch:
        root = BUILD / "hydro" / args.batch
        if root.exists():
            shutil.rmtree(str(root))
        for pid in args.problem:
            p = Problem(pid)
            build_tree(p, root / hydro_pid(p))
            log("  %s -> %s" % (pid, hydro_pid(p)))
        if args.no_zip:
            return 0
        out = Path(args.out) if args.out else (BUILD / "hydro" / (args.batch + ".zip"))
        # base=root：解压出来直接是 D0997/ … D1006/，不再多套一层 batch 目录
        make_zip(root, out, base=root)
        return 0

    # 场次级：一个 zip 里放当天的 6 个题目文件夹（文件夹名 = Hydro 题号）
    if args.day:
        pids = day_problems(args.day)
        root = BUILD / "hydro" / args.day
        if root.exists():
            shutil.rmtree(str(root))
        for pid in pids:
            p = Problem(pid)
            build_tree(p, root / hydro_pid(p))
            log("  %s -> %s" % (pid, hydro_pid(p)))
        if args.no_zip:
            return 0
        out = Path(args.out) if args.out else (BUILD / "hydro" / (args.day + ".zip"))
        # base=root：解压出来直接是 C0141/ … C0146/，不再多套一层 d1/
        make_zip(root, out, base=root)
        return 0

    for pid in args.problem:
        p = Problem(pid)
        root = BUILD / "hydro" / pid / hydro_pid(p)
        build_tree(p, root)
        if not (root / "problem.yaml").is_file():
            die("组装失败：%s 下没有 problem.yaml，拒绝打包" % root)
        if args.no_zip:
            continue
        out = Path(args.out) if (args.out and len(args.problem) == 1) \
            else (BUILD / "hydro" / (hydro_pid(p) + ".zip"))
        make_zip(root, out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
