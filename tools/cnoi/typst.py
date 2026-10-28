#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""调用 Typst 编译器：编译 PDF、渲染 PNG 预览。

本工程不使用 typst.ts（上游生成器在浏览器里跑的 WASM 版本），而是调用本机
Typst CLI —— 见 docs/statement.md §7。本环境有两个必须处理的点：

  * Typst 自己下载 @preview 包会因 TLS 证书问题失败
    → 统一加 `--package-path resources/typst-packages`；
  * 字体必须显式给出 `--font-path`（模板用的是自带的 LM Roman / SimSun 等）
    → 加 `resources/cnoi/fonts`，再补系统字体目录兜底。
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

__all__ = ["TypstError", "Typst", "find_typst", "system_font_dirs"]


class TypstError(Exception):
    pass


def find_typst() -> str:
    exe = shutil.which("typst")
    if not exe:
        raise TypstError("找不到 typst 命令；请安装 Typst 并加入 PATH（本工程需要 0.14+）")
    return exe


def system_font_dirs():
    if os.name == "nt":
        win = Path(os.environ.get("WINDIR", r"C:\Windows"))
        yield win / "Fonts"
        local = os.environ.get("LOCALAPPDATA")
        if local:
            yield Path(local) / "Microsoft" / "Windows" / "Fonts"
        return
    if sys.platform == "darwin":
        for p in ("/System/Library/Fonts", "/Library/Fonts",
                  os.path.expanduser("~/Library/Fonts")):
            yield Path(p)
        return
    for p in ("/usr/share/fonts", "/usr/local/share/fonts",
              os.path.expanduser("~/.local/share/fonts"),
              os.path.expanduser("~/.fonts")):
        yield Path(p)


class Typst(object):
    """一个已配置好的 Typst 调用器。"""

    def __init__(self, font_dirs=(), package_dir: Path = None, root: Path = None,
                 verbose: bool = False):
        self.exe = find_typst()
        self.font_dirs = [Path(p) for p in font_dirs if Path(p).is_dir()]
        self.package_dir = Path(package_dir) if package_dir else None
        self.root = Path(root) if root else None
        self.verbose = verbose

    # -- 参数 --------------------------------------------------------

    def _base_args(self):
        args = [self.exe, "compile"]
        for d in self.font_dirs:
            args += ["--font-path", str(d)]
        if self.package_dir:
            args += ["--package-path", str(self.package_dir)]
        if self.root:
            args += ["--root", str(self.root)]
        return args

    def _run(self, args):
        if self.verbose:
            print("  $ " + " ".join(args), flush=True)
        proc = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                              encoding="utf-8", errors="replace")
        return proc.returncode, proc.stdout or ""

    @staticmethod
    def _clean_output(output: str) -> str:
        """Typst 的 stderr 带源码位置与 ┌─ 框线；原样保留但对使用者太吵，做轻度裁剪。"""
        lines = [l for l in output.split("\n") if l.strip()]
        return "\n".join(lines)

    # -- 公开接口 ----------------------------------------------------

    def version(self) -> str:
        proc = subprocess.run([self.exe, "--version"], stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, encoding="utf-8", errors="replace")
        return (proc.stdout or "").strip()

    def pdf(self, main_typ: Path, out_pdf: Path) -> Path:
        out_pdf.parent.mkdir(parents=True, exist_ok=True)
        code, output = self._run(self._base_args() + [str(main_typ), str(out_pdf)])
        if code != 0:
            raise TypstError("Typst 编译失败（exit %d）\n%s"
                             % (code, self._clean_output(output)))
        return out_pdf

    def page_count(self, pdf: Path) -> int:
        """数出 PDF 页数。

        先按页对象计数（Typst 生成的 PDF 结构固定），失败再用二分探测兜底。
        """
        data = pdf.read_bytes()
        n = len(re.findall(rb"/Type\s*/Page[^s]", data))
        if n > 0:
            return n
        # 兜底：逐页试编译，直到 --pages 越界
        page = 1
        while page <= 999:
            code, _ = self._run(self._base_args() + [
                "--format", "png", "--pages", str(page),
                str(pdf.with_suffix(".typ")), str(pdf.with_suffix(".probe.png"))])
            if code != 0:
                break
            page += 1
        probe = pdf.with_suffix(".probe.png")
        if probe.is_file():
            probe.unlink()
        return max(1, page - 1)

    def pages_png(self, main_typ: Path, out_dir: Path, *, ppi: int = 110,
                  stem: str = "page", first: int = None, last: int = None,
                  count: int = None) -> list:
        """把 main_typ 逐页渲染成 PNG，返回生成的文件列表。

        逐页渲染（而不是用 `{p}` 模板）是为了避免 Windows 命令行把花括号
        当成参数展开，也便于只导出部分页面。

        `count` 是已知总页数时给出的上界。Typst 对越界的 --pages **不报错**
        （只是不产出文件），所以不传 count 就必须靠"某页没有产物"来判断结束，
        否则会一直试下去；调用方应优先传 count。
        """
        out_dir.mkdir(parents=True, exist_ok=True)
        for old in out_dir.glob("%s-*.png" % stem):
            old.unlink()
        base = self._base_args() + ["--format", "png", "--ppi", str(ppi)]
        made = []
        lo = first or 1
        hi = last if last is not None else (count if count is not None else lo + 499)
        if count is not None:
            hi = min(hi, count)
        for page in range(lo, hi + 1):
            target = out_dir / ("%s-%d.png" % (stem, page))
            code, output = self._run(base + ["--pages", str(page),
                                             str(main_typ), str(target)])
            if code != 0:
                raise TypstError("Typst 预览渲染失败（第 %d 页，exit %d）\n%s"
                                 % (page, code, self._clean_output(output)))
            if not target.is_file():
                break          # 页码越界：Typst 静默跳过
            made.append(target)
        if not made:
            raise TypstError("预览渲染没有产出任何图片（起始页 %d 可能超出范围）" % lo)
        return made
