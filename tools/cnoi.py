#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CNOI 题面工具的命令行入口。

    python3 tools/cnoi.py build --problem aplusb --preview -o build/statement/aplusb

实现见 tools/cnoi/（md.py 解析渲染、typst.py 调用编译器、cli.py 命令）。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from cnoi.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
