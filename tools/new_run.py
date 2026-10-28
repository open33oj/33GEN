#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""为一次出题任务建立日期目录（AGENTS.md K7）。

    python tools/new_run.py              # 建 runs/<今天>/，已存在则复用
    python tools/new_run.py --date 2026-11-03
    python tools/new_run.py --list       # 列出已有任务目录

目录结构：

    runs/2026-10-28/
    ├── batch.md        本批的 P1–P7 取值（首次创建时生成模板）
    ├── problems/       每道题（problems/<pid>/...）
    ├── contests/       比赛配置
    ├── notes/          对拍、草稿等临时材料
    └── build/          产物（可随时删）

之后在该目录里工作即可：
    cd runs/2026-10-28
    python ..\\..\\tools\\build.py all --problem <pid>
"""

from __future__ import annotations

import argparse
import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import ROOT, log  # noqa: E402

RUNS = ROOT / "runs"

BATCH_TEMPLATE = """# 本批参数（P1–P7）

> 每批重新确认，不要沿用上一批。填完再开始建题。

- [ ] P1 人物与世界观：
- [ ] P2 比赛结构：
- [ ] P3 测试点规格：
- [ ] P4 题号与命名：
- [ ] P5 样例策略：
- [ ] P6 交付物：
- [ ] P7 题面形式：

## 本批启用模块

- 题型（M）：M8、M9、…
- 交付（D）：D1、…

## 题目清单

| pid | 英文短名 | 标题 | 来源 | 状态 |
| --- | --- | --- | --- | --- |
"""


def main() -> int:
    ap = argparse.ArgumentParser(description="建立日期任务目录")
    ap.add_argument("--date", help="YYYY-MM-DD，默认今天")
    ap.add_argument("--list", action="store_true", help="列出已有任务目录")
    args = ap.parse_args()

    if args.list:
        if not RUNS.is_dir():
            log("还没有任务目录（%s）" % RUNS)
            return 0
        for d in sorted(p for p in RUNS.iterdir() if p.is_dir()):
            n = len(list((d / "problems").glob("*/meta.yaml"))) if (d / "problems").is_dir() else 0
            log("%s  %d 道题" % (d.name, n))
        return 0

    if args.date:
        try:
            datetime.date.fromisoformat(args.date)
        except ValueError:
            log("日期格式应为 YYYY-MM-DD：%s" % args.date)
            return 1
        day = args.date
    else:
        day = datetime.date.today().isoformat()

    run = RUNS / day
    existed = run.is_dir()
    for sub in ("problems", "contests", "notes", "build"):
        (run / sub).mkdir(parents=True, exist_ok=True)

    batch = run / "batch.md"
    if not batch.is_file():
        batch.write_text(BATCH_TEMPLATE, encoding="utf-8", newline="\n")

    log(("复用" if existed else "新建") + "任务目录：%s" % run)
    log("  在仓库根执行：set GEN_WORK=%s" % run)
    log("  （或 cd 进去，用 ..\\..\\tools\\build.py 这样的路径）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
