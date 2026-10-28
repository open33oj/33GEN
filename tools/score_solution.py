#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""给一份选手代码按测试点打分（验数据强度用）。

用法：

    python3 tools/score_solution.py --problem d1s3 --source /path/to/wrong.cpp

做什么：

  1. 用与 `tools/_common.py` 完全相同的编译选项编译这份代码（零警告要求不适用，
     选手代码有警告照跑）；
  2. 逐个测试点运行：文件 IO 题在临时目录里按 `<filename>.in` / `<filename>.out` 跑，
     标准 IO 题把 `.in` 喂给 stdin；
  3. 判分：
     - 答案唯一（`checker_type: default`）→ 与 `.ans` 逐行比对，
       忽略行末空格与文件末尾空行（与 Hydro 默认比较器口径一致）；
     - SPJ 题（`checker_type: testlib`）→ 把输出与 `.ans` 交给 `src/checker.cpp` 判；
  4. 打印每个测试点的结果、三个子任务的小计与总分（每点 5 分）。

它只读 `problems/<pid>/data/`，不会改动任何正式数据；用来回答
"这份错解现在能拿多少分 / 数据能不能区分它"（见 `docs/rules.md` K6）。
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import (  # noqa: E402
    CXXFLAGS, EXTRA_LDFLAGS, TESTLIB_DIR, Problem, compile_source, die, log, temp_dir,
)

POINTS_PER_CASE = 5


def time_limit_seconds(p: Problem) -> float:
    """从 config.yaml 的 `time`（如 `1s` / `500ms`）取单点时限，用于模拟 TLE。"""
    raw = str(p.hydro_config.get("time") or "1s").strip().lower()
    try:
        if raw.endswith("ms"):
            return float(raw[:-2]) / 1000.0
        if raw.endswith("s"):
            return float(raw[:-1])
        return float(raw)
    except ValueError:
        return 1.0


def norm_output(raw: bytes) -> str:
    """Hydro 默认比较器口径：忽略行末空格与文件末尾空行。"""
    text = raw.decode("utf-8", "replace").replace("\r\n", "\n").replace("\r", "\n")
    lines = [ln.rstrip(" \t") for ln in text.split("\n")]
    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines)


def build(p: Problem, source: Path, out_dir: Path) -> Path:
    """编译选手代码：允许警告，但语法/链接错误要报出来。"""
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / ("solution-" + re.sub(r"[^A-Za-z0-9_.-]", "_", source.stem)
                        + (".exe" if os.name == "nt" else ""))
    cmd = ["g++"] + CXXFLAGS + ["-I", str(TESTLIB_DIR)] + list(EXTRA_LDFLAGS) + \
          [str(source), "-o", str(target)]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if proc.returncode != 0:
        sys.stderr.write(proc.stdout.decode("utf-8", "replace"))
        die("选手代码编译失败：%s" % source)
    return target


def run_case(p: Problem, exe_path: Path, in_path: Path, work: Path, timeout: float):
    """运行一份测试点，返回 (选手输出, 退出码)。超时按 -1 处理。"""
    fname = p.hydro_config.get("filename")
    try:
        if fname:
            shutil.copyfile(str(in_path), str(work / (fname + ".in")))
            proc = subprocess.run([str(exe_path)], cwd=str(work), timeout=timeout,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            produced = work / (fname + ".out")
            out = produced.read_bytes() if produced.is_file() else b""
        else:
            proc = subprocess.run([str(exe_path)], input=in_path.read_bytes(), timeout=timeout,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            out = proc.stdout
    except subprocess.TimeoutExpired:
        return b"", -1
    return out, proc.returncode


def judge(p: Problem, checker, in_path: Path, out: bytes, ans_path: Path, work: Path):
    """返回 (是否通过, 说明)。"""
    if checker is not None:
        user_out = work / "user.out"
        user_out.write_bytes(out)
        proc = subprocess.run([str(checker), str(in_path), str(user_out), str(ans_path)],
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        if proc.returncode == 0:
            return True, "ok"
        msg = proc.stdout.decode("utf-8", "replace").strip().split("\n")[-1][:60]
        return False, msg or "checker 判错"
    want = norm_output(ans_path.read_bytes())
    got = norm_output(out)
    if got == want:
        return True, "ok"
    if not out:
        return False, "没有输出 / 崩溃（exit）"
    return False, "第 %d 行起与答案不同" % next(
        (i for i, (x, y) in enumerate(zip(got.split("\n"), want.split("\n")), 1) if x != y),
        min(len(got.split("\n")), len(want.split("\n"))) + 1)


def main() -> int:
    ap = argparse.ArgumentParser(description="给一份选手代码按测试点打分（验数据强度）")
    ap.add_argument("--problem", required=True, help="题目编号（problems/ 下的目录名）")
    ap.add_argument("--source", required=True, help="选手代码 .cpp 路径")
    ap.add_argument("--quiet-cases", action="store_true", help="只打印挂掉的测试点")
    args = ap.parse_args()

    p = Problem(args.problem)
    source = Path(args.source)
    if not source.is_file():
        die("找不到选手代码：%s" % source)
    exe_path = build(p, source, p.build / "score")

    has_checker = bool(p.hydro_config.get("checker")) and \
        p.hydro_config.get("checker_type") == "testlib"
    checker = None
    if has_checker:
        checker = compile_source(p.src / "checker.cpp", p.build / "score")

    subtasks = p.hydro_config.get("subtasks") or []
    limit = time_limit_seconds(p)
    log("题目 %s（%s），选手代码 %s，单点时限 %.2fs"
        % (p.pid, p.meta.get("title"), source.name, limit))
    total = 0
    per_sub = []
    for si, (s_si, ci, in_name, out_name) in enumerate(p.cases()):
        in_path, ans_path = p.data / in_name, p.data / out_name
        if not (in_path.is_file() and ans_path.is_file()):
            die("缺少数据 %s；请先运行 python3 tools/build.py all --problem %s"
                % (in_name, p.pid))
        with temp_dir("score-%s-" % p.pid) as td:
            work = Path(td)
            out, code = run_case(p, exe_path, in_path, work, limit)
            ok, why = judge(p, checker, in_path, out, ans_path, work)
        if code == -1 and not ok:
            why = "超时（> %.2fs）" % limit
        elif code != 0 and not ok:
            why = "运行崩溃（exit %d）" % code
        total += POINTS_PER_CASE if ok else 0
        while len(per_sub) <= s_si:
            per_sub.append(0)
        per_sub[s_si] += POINTS_PER_CASE if ok else 0
        if ok and args.quiet_cases:
            continue
        log("  %-8s %s%s" % (in_name, "AC" if ok else "WA", "" if ok else "   " + why))

    log("")
    for si, st in enumerate(subtasks):
        log("  子任务 %d（%s）：%d / %d"
            % (si + 1, st.get("name", ""), per_sub[si] if si < len(per_sub) else 0,
               int(st.get("score", 0))))
    log("  总分：%d / 100" % total)
    return 0


if __name__ == "__main__":
    sys.exit(main())
