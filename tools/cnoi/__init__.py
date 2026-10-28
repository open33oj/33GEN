#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CNOI 题面工具包。

    md.py   Markdown 解析与 Typst 渲染（上游 remarkTypst 的 Python 对应实现）
    typst.py Typst CLI 调用（PDF / PNG 预览）
    cli.py  命令行入口

直接运行：`python3 tools/cnoi.py <子命令>`（这是推荐的用法，见 docs/statement.md）。
"""

from . import md, typst  # noqa: F401

__all__ = ["md", "typst"]
