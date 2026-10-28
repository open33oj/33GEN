#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成下发到 `down/` 的样例数据：**题面小样例 + 满规模大样例**。

    python3 tools/samples.py --problem d1j1     # 一道题
    python3 tools/samples.py --all              # 全部题目（跳过 _template）

产物（不进 git，见 .gitignore）：

    problems/<pid>/data/samples/<英文名><编号>.in
    problems/<pid>/data/samples/<英文名><编号>.ans

编号规则：

    1 .. S      题面里「## 样例 k 输入 / ## 样例 k 输出」的原样抽取（S 通常为 1~2）
    S+1 .. S+B  大样例，来自 `meta.yaml` 的 `samples` 表：

        samples:
          - case: t13      # 借用这个测试点的规模与形状
            seed: 0x5A13   # 换一个 seed —— 样例不是正式测试点，不能直接泄题

为什么单独一个工具：

  * 样例是**下发材料**，要能随题面与数据一起重建，所以和测试数据一样不进 git；
  * 小样例必须与题面逐字节一致（直接从 `statement/zh_CN.md` 抽取，不手抄）；
  * 大样例必须"有一定强度"（满规模、能压时间与内存），
    但又**不能是 20 个正式测试点之一**，因此统一换 seed 重新生成；
  * 所有样例都要过一遍 `valid.cpp`，与正式测试点同一把尺子；
  * 题面小样例的**输出**也要验一次：非 SPJ 题与 `std.cpp` 的输出逐行比对，
    SPJ 题交给 `checker.cpp` 判定 —— 题面里的样例答案是人手写的，
    这一步专门拦「样例输出与题目判定标准不一致」的锅。

打包：`tools/pack_lemon.py` 会把这些文件复制到 `down/<英文名>/`。
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import (  # noqa: E402
    PROBLEMS, SRC_CHECKER, SRC_GEN, SRC_STD, SRC_VALID,
    Problem, compile_source, die, exe, log, read_text, temp_dir, warn,
)
from build import normalize_lf, run_std  # noqa: E402

RE_SAMPLE_HEADING = re.compile(r"^#{1,6}\s*样例\s*(\d+)\s*(输入|输出)\s*$")
RE_FENCE = re.compile(r"^\s*(`{3,}|~{3,})\s*$")


# ---------------------------------------------------------------- 题面小样例

def extract_small_samples(md: str) -> list:
    """从题面 Markdown 里抽出小样例，返回按编号排好的 [(编号, 输入, 输出)]。

    只认「## 样例 k 输入」/「## 样例 k 输出」小节后面紧跟的代码块（见 docs/statement.md）。
    """
    lines = md.replace("\r\n", "\n").split("\n")
    got = {}
    i = 0
    while i < len(lines):
        m = RE_SAMPLE_HEADING.match(lines[i])
        if not m:
            i += 1
            continue
        idx, kind = int(m.group(1)), m.group(2)
        j = i + 1
        while j < len(lines) and not lines[j].strip():
            j += 1
        fm = RE_FENCE.match(lines[j]) if j < len(lines) else None
        if not fm:
            die("题面第 %d 行「样例 %d %s」后面没有代码块" % (i + 1, idx, kind))
        fence = fm.group(1)
        body = []
        j += 1
        while j < len(lines) and not RE_FENCE.match(lines[j]):
            body.append(lines[j])
            j += 1
        if j >= len(lines):
            die("题面第 %d 行的代码块没有闭合" % (i + 1))
        got.setdefault(idx, {})[kind] = "\n".join(body) + "\n"
        i = j + 1

    out = []
    for idx in sorted(got):
        both = got[idx]
        if "输入" not in both or "输出" not in both:
            die("题面的样例 %d 只有%s，缺另一半"
                % (idx, "输入" if "输入" in both else "输出"))
        out.append((idx, both["输入"], both["输出"]))
    if not out:
        warn("题面里没有找到「## 样例 k 输入 / 输出」小节")
    return out


# ---------------------------------------------------------------- 编译辅助

def ensure_exe(p: Problem, fname: str):
    """按需编译 p.src/<fname>，返回可执行文件路径（源文件不存在时返回 None）。"""
    src = p.src / fname
    if not src.is_file():
        return None
    bin_dir = p.build / "bin"
    target = bin_dir / exe(src.stem)
    if target.is_file() and target.stat().st_mtime >= src.stat().st_mtime:
        return target
    return compile_source(src, bin_dir)


def validate_input(p: Problem, valid_exe, in_path: Path) -> None:
    """用 valid.cpp 校验一个样例输入（testlib 校验器从 stdin 读）。"""
    proc = subprocess.run([str(valid_exe)], input=in_path.read_bytes(),
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if proc.returncode != 0:
        sys.stderr.write(proc.stdout.decode("utf-8", "replace"))
        die("%s 没通过 valid.cpp 校验——样例必须满足题面里的数据范围" % in_path.name)


def _norm_output(raw: bytes) -> str:
    """按 Hydro 默认比较器的口径归一化：忽略行末空格与文件末尾空行。"""
    text = raw.decode("utf-8", "replace").replace("\r\n", "\n").replace("\r", "\n")
    lines = [ln.rstrip(" \t") for ln in text.split("\n")]
    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines)


def validate_sample_output(p: Problem, std_exe, checker_exe,
                           in_path: Path, ans_path: Path) -> None:
    """校验题面小样例的**输出**（题面里的这一段是手写的，谁也没验过）。

    - 非 SPJ 题：与 `std.cpp` 的输出逐行比对（忽略行末空格 / 末尾空行）；
    - SPJ 题：把题面的答案当"选手输出"、标程的答案当"标准答案"交给 `checker.cpp` 判定，
      checker 必须认为题面答案合法。

    这一步专门拦「样例输出与题目判定标准不一致」这类锅（例如三进制天平曾经给出的
    样例 1 其实不平衡）。大样例是 std 现算的，不需要再比。
    """
    with temp_dir("sampchk-%s-" % p.pid) as td:
        produced = Path(td) / "std.ans"
        run_std(p, std_exe, in_path, produced)
        if checker_exe is not None:
            proc = subprocess.run(
                [str(checker_exe), str(in_path), str(ans_path), str(produced)],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            if proc.returncode != 0:
                sys.stderr.write(proc.stdout.decode("utf-8", "replace"))
                die("%s：题面样例 %s 没通过 checker.cpp —— 题面里的样例答案与判定标准不一致"
                    % (p.pid, in_path.name))
            return
        want = _norm_output(produced.read_bytes())
        got = _norm_output(ans_path.read_bytes())
        if want != got:
            die("%s：题面样例 %s 的输出与标程不一致\n"
                "        题面写的是：%r\n"
                "        标程算出来：%r\n"
                "        请修正题面里的样例输出（或标程）"
                % (p.pid, in_path.name, got[:200], want[:200]))


# ---------------------------------------------------------------- 主流程

def build_samples(p: Problem) -> list:
    meta = p.meta
    name = meta.get("name") or p.pid
    out_dir = p.data / "samples"
    if out_dir.exists():
        for old in sorted(out_dir.glob("*")):
            old.unlink()
    out_dir.mkdir(parents=True, exist_ok=True)

    md = read_text(p.statement / "zh_CN.md")
    small = extract_small_samples(md)

    valid_exe = ensure_exe(p, SRC_VALID)
    if valid_exe is None:
        warn("%s 没有 valid.cpp，样例不做范围校验" % p.pid)

    made = []
    number = 0
    for _idx, in_text, ans_text in small:
        number += 1
        in_path = out_dir / ("%s%d.in" % (name, number))
        ans_path = out_dir / ("%s%d.ans" % (name, number))
        in_path.write_bytes(in_text.encode("utf-8"))
        ans_path.write_bytes(ans_text.encode("utf-8"))
        made.append((number, "题面样例 %d" % _idx, in_path, ans_path))

    big = meta.get("samples") or []
    gen_exe = ensure_exe(p, SRC_GEN) if big else None
    std_exe = ensure_exe(p, SRC_STD)
    if std_exe is None:
        die("%s 缺少 %s，无法校验样例输出" % (p.pid, SRC_STD))
    if big and gen_exe is None:
        die("%s 声明了 samples，但缺少 %s" % (p.pid, SRC_GEN))
    # SPJ 题的样例输出交给 checker 判定（见 validate_sample_output）
    has_checker = bool(p.hydro_config.get("checker")) and \
        p.hydro_config.get("checker_type") == "testlib"
    checker_exe = ensure_exe(p, SRC_CHECKER) if has_checker else None

    for entry in big:
        if not isinstance(entry, dict) or not entry.get("case"):
            die("%s 的 samples 项必须写成 {case: <测试点名>, seed: <整数>}" % p.pid)
        case = str(entry["case"])
        seed = entry.get("seed")
        if seed is None:
            die("%s 的 samples 项 %s 缺少 seed（大样例必须换种子，不能直接用测试点）"
                % (p.pid, case))
        number += 1
        in_path = out_dir / ("%s%d.in" % (name, number))
        ans_path = out_dir / ("%s%d.ans" % (name, number))
        with temp_dir("sample-%s-" % p.pid) as td:
            tmp_in = Path(td) / "in.txt"
            proc = subprocess.run(
                [str(gen_exe), "--case", case, "--seed", str(int(seed)),
                 "--out", str(tmp_in)],
                cwd=td, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            if proc.returncode != 0:
                sys.stderr.write(proc.stdout.decode("utf-8", "replace"))
                die("%s：gen --case %s --seed %s 失败" % (p.pid, case, seed))
            if not tmp_in.is_file():
                die("%s：gen 没有产出大样例输入（gen.cpp 需要支持 --seed）" % p.pid)
            in_path.write_bytes(tmp_in.read_bytes())
        normalize_lf(in_path)
        run_std(p, std_exe, in_path, ans_path)
        made.append((number, "大样例（%s，seed %s）" % (case, hex(int(seed))), in_path, ans_path))

    # 统一校验 + 报告
    for number, source, in_path, ans_path in made:
        if valid_exe is not None:
            validate_input(p, valid_exe, in_path)
        if source.startswith("题面样例"):
            validate_sample_output(p, std_exe, checker_exe, in_path, ans_path)
        log("  [ok  ] %-28s %-7s %6.1f KiB  %5d 行  -> %s"
            % (in_path.name, source, in_path.stat().st_size / 1024.0,
               in_path.read_bytes().count(b"\n"), ans_path.name))
    return made


def main() -> int:
    ap = argparse.ArgumentParser(
        description="生成下发到 down/ 的样例数据（题面小样例 + 大样例）",
        epilog="产物在 problems/<pid>/data/samples/，由 tools/pack_lemon.py 复制进 down/")
    ap.add_argument("--problem", help="题目编号")
    ap.add_argument("--all", action="store_true", help="全部题目（跳过 _template）")
    args = ap.parse_args()

    if not args.problem and not args.all:
        ap.error("请给出 --problem <pid> 或 --all")

    if args.all:
        pids = [d.name for d in sorted(PROBLEMS.iterdir())
                if d.is_dir() and not d.name.startswith("_")
                and (d / "meta.yaml").is_file()]
    else:
        pids = [args.problem]

    total = 0
    for pid in pids:
        log("═══ %s ═══" % pid)
        p = Problem(pid)
        made = build_samples(p)
        small = sum(1 for _n, s, _i, _a in made if s.startswith("题面样例"))
        log("  %s：%d 个样例（题面小样例 %d + 大样例 %d）"
            % (pid, len(made), small, len(made) - small))
        total += len(made)
    log("完成：%d 道题、共 %d 个样例文件对" % (len(pids), total))
    return 0


if __name__ == "__main__":
    sys.exit(main())
