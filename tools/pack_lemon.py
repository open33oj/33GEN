#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""导出 LemonLime 评测包（<contest>.cdf + data/ + down/）。

用法：
    python3 tools/pack_lemon.py --contest d1-j
    python3 tools/pack_lemon.py --contest demo --problem aplusb [--problem ...]
    python3 tools/pack_lemon.py --contest demo --all --time-limit 1000 --memory-limit 512

产出（见 docs/formats.md）：

    build/lemon/<contest>/
    ├── <contest>.cdf                       # JSON 比赛配置
    ├── data/<英文名>/<英文名><n>.in        # 评测数据（n = 1..20，按测试点顺序）
    ├── data/<英文名>/<英文名><n>.ans
    ├── data/<英文名>/std.cpp  sol.md       # 标程与题解（LemonLime 不会当测试点）
    ├── data/<英文名>/checker.cpp           # 有 SPJ 时
    └── down/                               # 下发给选手（不是 LemonLime 的概念）
        ├── <比赛名>-<组别>-<场次>.pdf      # **整场比赛合并**的完整试题
        └── <英文名>/<英文名><k>.in / .ans  # 该题的样例（题面小样例 + 满规模大样例）

命名约定：题目目录与数据文件都用 `meta.yaml` 的英文短名 `name`（≤6 个小写英文字母），
不用题目编号 `pid`——这样选手与评测机看到的文件名是一致的、自解释的。
样例数据由 `tools/samples.py` 生成到 `problems/<pid>/data/samples/`。
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import (  # noqa: E402
    BUILD, CONTESTS, PROBLEMS, SRC_CHECKER, SRC_STD, SOLUTION,
    Problem, die, log, read_text, read_yaml, warn, write_text,
)
from samples import extract_small_samples  # noqa: E402

# LemonLime 枚举（src/core/task.h）
TASK_TRADITIONAL = 0
TASK_INTERACTION = 2

COMPARISON_LINE_BY_LINE = 0
COMPARISON_IGNORE_SPACES = 1
COMPARISON_REAL_NUMBER = 3
COMPARISON_TESTLIB = 5

DEP_SUFFIX = "_lemon_SUbtaskDEPENDENCE_fLAg"


def parse_time_ms(value):
    """'1s' / '0.5s' / '1000ms' / None -> 毫秒整数。"""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value)
    m = re.match(r"^\s*([\d.]+)\s*(ms|s)?\s*$", str(value))
    if not m:
        return None
    v = float(m.group(1))
    return int(v) if m.group(2) == "ms" else int(v * 1000)


def parse_mem_mb(value):
    """'256m' / '512 MB' / None -> MB 整数。"""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value)
    m = re.match(r"^\s*([\d.]+)\s*([mMgG]?)", str(value))
    if not m:
        return None
    v = float(m.group(1))
    return int(v * 1024) if m.group(2).lower() == "g" else int(v)


def collect_problems(contest: str, only: list, use_all: bool) -> list:
    """决定这场比赛包含哪些题。

    优先读 `contests/<contest>.yaml`（那里有权威的题目清单与顺序）；
    找不到配置时退回"按 meta.yaml 的 contest 字段筛选"。
    这样即使一道题被两场比赛复用（第 2 天 S 组复用 J3/J4），顺序也不会错。
    """
    cpath = CONTESTS / (contest + ".yaml")
    if cpath.is_file() and not only:
        cfg = read_yaml(cpath)
        folders = []
        for item in cfg.get("problems") or []:
            folders.append(item.get("folder") if isinstance(item, dict) else item)
        got = []
        for f in folders:
            if f:
                got.append(Problem(f))
        if got:
            print("按 contests/%s.yaml 组包：%s"
                  % (contest, ", ".join(p.pid for p in got)))
            return got

    got = []
    for d in sorted(PROBLEMS.iterdir()):
        if not d.is_dir() or not (d / "meta.yaml").is_file():
            continue
        if only:
            if d.name not in only:
                continue        # 显式指定时不再跳过 _template
        else:
            if d.name.startswith("_"):
                continue
            meta = read_yaml(d / "meta.yaml")
            if not use_all and meta.get("contest") != contest:
                continue
        got.append(Problem(d.name))
    missing = [x for x in only if x not in [p.pid for p in got]]
    if missing:
        die("找不到题目：%s" % ", ".join(missing))
    if not got:
        die("没有匹配的题目（contest=%s, problems=%s）" % (contest, only or "全部"))
    return got


def problem_name(p: Problem) -> str:
    """题目的英文短名：目录名、数据文件名、样例文件名的前缀都用它。"""
    return str(p.meta.get("name") or p.pid)


def sample_files(p: Problem) -> list:
    """返回该题样例的 [(序号, .in 路径, .ans 路径)]，按序号排序。

    优先用 `problems/<pid>/data/samples/`（`tools/samples.py` 生成：题面小样例 + 大样例）；
    找不到时退回到"直接从题面抽小样例"（没有大样例），并提示去跑 samples.py。
    """
    name = problem_name(p)
    src = p.data / "samples"
    got = []
    for in_path in sorted(src.glob("%s*.in" % name)) if src.is_dir() else []:
        m = re.match(r"^%s(\d+)\.in$" % re.escape(name), in_path.name)
        if not m:
            continue
        ans_path = in_path.with_suffix(".ans")
        if not ans_path.is_file():
            die("%s 缺少配对的 %s" % (in_path, ans_path.name))
        got.append((int(m.group(1)), in_path, ans_path))
    if got:
        return got

    warn("%s 没有 data/samples/，down/ 里只有题面小样例（没有大样例）。"
         "请先运行：python3 tools/samples.py --problem %s" % (p.pid, p.pid))
    md = p.statement / "zh_CN.md"
    if not md.is_file():
        return []
    tmp = p.build / "samples-fallback"
    if tmp.exists():
        shutil.rmtree(str(tmp))
    tmp.mkdir(parents=True, exist_ok=True)
    for k, (idx, in_text, ans_text) in enumerate(extract_small_samples(read_text(md)), start=1):
        in_path = tmp / ("%s%d.in" % (name, k))
        ans_path = tmp / ("%s%d.ans" % (name, k))
        in_path.write_bytes(in_text.encode("utf-8"))
        ans_path.write_bytes(ans_text.encode("utf-8"))
        got.append((k, in_path, ans_path))
    return got


def build_problem_task(p: Problem, data_root: Path, down_root: Path,
                       time_default, memory_default) -> dict:
    meta = p.meta
    cfg = p.hydro_config
    fname = cfg.get("filename")
    cases = p.cases()
    name = problem_name(p)

    pdir = data_root / name
    pdir.mkdir(parents=True, exist_ok=True)
    down_pdir = down_root / name
    down_pdir.mkdir(parents=True, exist_ok=True)

    # 子任务 -> 该子任务第一个测试点在 LemonLime 里的下标（1-based）
    subtask_first = {}
    test_cases = []
    for idx, (si, ci, in_name, out_name) in enumerate(cases, start=1):
        src_in = p.data / in_name
        src_out = p.data / out_name
        if not (src_in.is_file() and src_out.is_file()):
            die("%s 缺少 %s / %s；请先运行 tools/build.py gen" % (p.pid, in_name, out_name))
        dst_in = pdir / ("%s%d.in" % (name, idx))
        dst_out = pdir / ("%s%d.ans" % (name, idx))
        shutil.copyfile(str(src_in), str(dst_in))
        shutil.copyfile(str(src_out), str(dst_out))

        # 子任务依赖：写入哨兵字符串（见 docs/formats.md）
        input_files = ["%s/%s%d.in" % (name, name, idx)]
        st = (cfg.get("subtasks") or [])[si]
        if st.get("if"):
            for dep in st["if"]:
                dep_first = subtask_first.get(str(dep))
                if dep_first is None:
                    warn("%s 的 subtask%d 依赖 subtask%s，但后者没有更早的测试点，跳过依赖标记"
                         % (p.pid, si, dep))
                    continue
                input_files.append("%d%s" % (dep_first, DEP_SUFFIX))
        subtask_first.setdefault(str(si), idx)

        test_cases.append({
            "fullScore": int(st.get("score", 0)) // max(1, len(st.get("cases") or [1])),
            # 时限/内存优先级：测试点 -> 子任务 -> 题目 config.yaml -> meta.yaml -> 命令行默认值。
            # meta.yaml 是每题时限内存的事实来源（与题面封面一致），不能只用命令行默认值。
            "timeLimit": (parse_time_ms(st.get("time"))
                          or parse_time_ms(cfg.get("time"))
                          or parse_time_ms(meta.get("time"))
                          or time_default),
            "memoryLimit": (parse_mem_mb(st.get("memory"))
                            or parse_mem_mb(cfg.get("memory"))
                            or parse_mem_mb(meta.get("memory"))
                            or memory_default),
            "inputFiles": input_files,
            "outputFiles": ["%s/%s%d.ans" % (name, name, idx)],
        })

    # 下发样例：题面小样例 + 大样例（见 tools/samples.py）
    for k, in_path, ans_path in sample_files(p):
        shutil.copyfile(str(in_path), str(down_pdir / in_path.name))
        shutil.copyfile(str(ans_path), str(down_pdir / ans_path.name))

    # 子任务分值无法整除时把余数补给最后一个测试点
    for si, st in enumerate(cfg.get("subtasks") or []):
        n = len(st.get("cases") or [])
        if not n:
            continue
        total = int(st.get("score", 0))
        base = total // n
        if base * n != total:
            warn("%s 的 subtask%d 分值 %d 无法被 %d 个测试点整除，已按 %d 分配"
                 % (p.pid, si, total, n, base))

    if "checker" in cfg and cfg.get("checker_type") == "testlib":
        comparison = COMPARISON_TESTLIB
        src_checker = p.src / SRC_CHECKER
        if not src_checker.is_file():
            die("%s 声明了 testlib checker，但缺少 %s" % (p.pid, SRC_CHECKER))
        shutil.copyfile(str(src_checker), str(pdir / "checker.cpp"))
        special_judge = "%s/checker" % name
    else:
        comparison = COMPARISON_IGNORE_SPACES
        special_judge = ""

    if cfg.get("type") == "interactive":
        task_type = TASK_INTERACTION
        warn("%s 是交互题：请手工在 .cdf 中补 interactor / interactorName / grader 字段" % p.pid)
    else:
        task_type = TASK_TRADITIONAL

    # 标程与题解放进 data/（LemonLime 不会把它们当测试点）
    src_std = p.src / SRC_STD
    if src_std.is_file():
        shutil.copyfile(str(src_std), str(pdir / SRC_STD))
    sol = p.dir / SOLUTION
    if sol.is_file():
        shutil.copyfile(str(sol), str(pdir / SOLUTION))

    return {
        "problemTitle": meta.get("title") or p.pid,
        "sourceFileName": name,
        "inputFileName": (fname + ".in") if fname else "%s.in" % name,
        "outputFileName": (fname + ".out") if fname else "%s.out" % name,
        "standardInputCheck": not bool(fname),
        "standardOutputCheck": not bool(fname),
        "taskType": task_type,
        "subFolderCheck": False,
        "comparisonMode": comparison,
        "diffArguments": "--ignore-space-change --text --brief",
        "realPrecision": 3,
        "specialJudge": special_judge,
        "answerFileExtension": "ans",
        "compilerConfiguration": {"g++": "default", "python": "default"},
        "testCases": test_cases,
    }


def contest_statement(contest: str):
    """整场合并的试题 PDF（`tools/cnoi.py build --contest <id>` 的产物）。"""
    pdf = BUILD / "contests" / contest / "statement.pdf"
    return pdf if pdf.is_file() else None


def contest_pdf_name(contest: str) -> str:
    """下发给选手的试题文件名：`<比赛名>-<组别>-<场次>.pdf`（读 contests/<id>.yaml）。"""
    path = CONTESTS / (contest + ".yaml")
    parts = []
    if path.is_file():
        cfg = read_yaml(path)
        parts = [str(cfg.get(k) or "") for k in ("title", "subtitle", "dayname")]
    parts = [re.sub(r"\s+", "", p) for p in parts if p.strip()]
    if not parts:
        return "%s.pdf" % contest
    return re.sub(r"-{2,}", "-", "-".join(parts)).strip("-") + ".pdf"


def main() -> int:
    ap = argparse.ArgumentParser(description="导出 LemonLime 评测包")
    ap.add_argument("--contest", default="contest", help="比赛名（输出目录与 .cdf 名）")
    ap.add_argument("--problem", action="append", default=[], help="题目编号，可重复")
    ap.add_argument("--all", action="store_true", help="导出全部题目（忽略 meta.yaml 的 contest）")
    ap.add_argument("--time-limit", type=int, default=1000, help="默认时限（毫秒）")
    ap.add_argument("--memory-limit", type=int, default=512, help="默认内存（MB）")
    args = ap.parse_args()

    problems = collect_problems(args.contest, args.problem, args.all)
    out_root = BUILD / "lemon" / args.contest
    if out_root.exists():
        shutil.rmtree(str(out_root))
    data_root = out_root / "data"
    down_root = out_root / "down"
    data_root.mkdir(parents=True, exist_ok=True)
    down_root.mkdir(parents=True, exist_ok=True)

    # 下发给选手的**整场试题**（4 题合并成一份，不是每题分开）
    if (CONTESTS / (args.contest + ".yaml")).is_file():
        pdf = contest_statement(args.contest)
        if pdf is None:
            die("找不到整场试题 PDF：%s\n"
                "        请先运行 python3 tools/cnoi.py build --contest %s -o build/contests/%s"
                % (BUILD / "contests" / args.contest / "statement.pdf",
                   args.contest, args.contest))
        target = down_root / contest_pdf_name(args.contest)
        shutil.copyfile(str(pdf), str(target))
        log("下发试题：down/%s（整场合并，%.0f KiB）"
            % (target.name, target.stat().st_size / 1024.0))
    else:
        warn("没有 contests/%s.yaml，down/ 里只有各题样例、没有合并试题；"
             "整场比赛请用 --contest <contests 里的 id>" % args.contest)

    tasks = []
    for p in problems:
        log("处理 %s ..." % p.pid)
        tasks.append(build_problem_task(p, data_root, down_root,
                                        args.time_limit, args.memory_limit))

    cdf = {
        "contestTitle": args.contest,
        "version": "1.0",
        "contestants": [],
        "tasks": tasks,
    }
    cdf_path = out_root / (args.contest + ".cdf")
    write_text(cdf_path, json.dumps(cdf, ensure_ascii=False, indent=1) + "\n")
    log("已生成 %s（%d 道题）" % (cdf_path, len(tasks)))
    log("提醒：contestants 为空，请在 LemonLime 里添加选手；"
        "选手名单也可以手工写进 .cdf 的 contestants 字段。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
