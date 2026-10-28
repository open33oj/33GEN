#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 resources/source/ 里的原始素材落地成构建真正需要的资源。

    python3 tools/setup_resources.py [--only testlib|cnoi|typst-packages] [--check]

本脚本是"新克隆一个仓库后第一条要跑的命令"：它把快照变成可用的构建环境。

落地内容：

  1. `resources/source/testlib/testlib.h`                  -> `resources/testlib/testlib.h`
  2. `resources/source/cnoi-statement-generator-*.zip`     -> `resources/cnoi/{typst,fonts}/`
     （只解出编译期真正需要的模板与字体，不解压整个 52 MiB 前端工程）
  3. Typst 包 `@preview/oxifmt:1.0.0`、`@preview/mitex:0.2.5`
                                                            -> `resources/typst-packages/preview/...`

Windows 注意：本环境下 Typst CLI 无法自行下载 @preview 包
（native-tls 报"安全包中没有可用的凭证"），因此第 3 步用 Python 的
urllib + tarfile 手动下载并解包，再用 `--package-path resources/typst-packages`
让 Typst 读取本地包目录。首次执行需要联网。

升级原始素材的流程见 resources/source/README.md。
"""

from __future__ import annotations

import argparse
import io
import os
import shutil
import subprocess
import sys
import tarfile
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RES = ROOT / "resources"
SOURCE = RES / "source"

# ---------------------------------------------------------------- 常量

TYPST_PACKAGES = [
    # (包名, 版本) —— 版本必须与 resources/cnoi/typst/*.typ 中的 import 一致
    ("oxifmt", "1.0.0"),
    ("mitex", "0.2.5"),
]
TYPST_PACKAGE_REGISTRY = "https://packages.typst.org/preview/{name}-{version}.tar.gz"

CNOI_ZIP_PREFIX = "cnoi-statement-generator-"
CNOI_TEMPLATE = "templates/cnoi/typst"
CNOI_ASSET_FONTS = "assets/typst/fonts"

# CNOI 模板（main.typ）实际用到的字体家族：
#   Latin Modern Roman / LM Roman 10|12|17  正文与标题（含粗体、斜体）
#   New Computer Modern Math                数学公式
#   SimSun / SimHei / KaiTi                 中文正文 / 粗体标题 / 场次
#   Fira Mono                               代码块
# 上游把整个 assets/typst/fonts 打包进前端，其中有 6 个文件模板从未引用
# （Alibaba PuHuiTi 两个字重、JetBrains Mono、New CMSansMath、
#   Fira Mono 的 Bold/Medium 两个字重，共 15.5 MiB）。
# 实测：只装下面这些字体，渲染结果与"全量字体"**逐字节一致**，且零字体回退警告
# （见 docs/workflow.md §9）。所以默认不再安装那 6 个。
# 万一上游模板改用了新字体，`python3 tools/selftest.py` 的字体检查会报出来。
# 仓库只带自由字体；中文用系统字体（见 CNOI_SYSTEM_FONTS）。
CNOI_REQUIRED_FONTS = [
    # 正文与标题：10pt / 12pt / 17pt 三个光学尺寸，各含需要的字重
    "lmroman10-regular.otf", "lmroman10-bold.otf",
    "lmroman10-italic.otf", "lmroman10-bolditalic.otf",
    "lmroman12-regular.otf", "lmroman12-bold.otf", "lmroman12-italic.otf",
    "lmroman17-regular.otf",
    # 数学
    "NewCMMath-Regular.otf", "NewCMMath-Bold.otf", "NewCMMath-Book.otf",
    # 等宽（代码块）
    "FiraMono-Regular.ttf",
]

# 中文字体：SimSun / SimHei / KaiTi 是商业字体，**不进仓库**（公开再分发有授权风险）。
# 出 PDF 时由 Typst 去系统字体里找；找不到就会缺字，所以 --check 会主动检测并提示。
CNOI_SYSTEM_FONTS = ["SimSun", "SimHei", "KaiTi"]


# ---------------------------------------------------------------- 工具

def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def _copy_if_changed(src: Path, dst: Path) -> bool:
    """返回是否真的写入了文件。"""
    if dst.is_file() and dst.read_bytes() == src.read_bytes():
        return False
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)
    return True


def _find_cnoi_zip() -> Path:
    cands = sorted(SOURCE.glob(CNOI_ZIP_PREFIX + "*.zip"))
    if not cands:
        raise SystemExit(
            "[error] 在 %s 下找不到 %s*.zip；请先放入 CNOI 题面生成器发布包（见该目录 README）。"
            % (SOURCE, CNOI_ZIP_PREFIX)
        )
    if len(cands) > 1:
        print("[warn ] %s 下有多个 CNOI 生成器压缩包，使用最新的：%s"
              % (SOURCE.relative_to(ROOT), cands[-1].name))
    return cands[-1]


def detect_cjk_fonts() -> tuple:
    """检测三个中文字体能不能用：仓库里没有，只能靠系统。

    返回 (可直接使用的家族, 缺失的家族, 检测方式说明)。
    检测顺序：resources/cnoi/fonts/ 里有 → 用 `typst fonts` 查 → Windows 字体目录。
    """
    fonts_dir = RES / "cnoi" / "fonts"
    have = {name for name in CNOI_SYSTEM_FONTS
            if (fonts_dir / (name + ".ttf")).is_file()
            or (fonts_dir / (name.lower() + ".ttf")).is_file()}

    how = "本地 resources/cnoi/fonts/"
    if len(have) < len(CNOI_SYSTEM_FONTS):
        listed = set()
        typst = shutil.which("typst")
        if typst:
            try:
                out = subprocess.run([typst, "fonts"], stdout=subprocess.PIPE,
                                     stderr=subprocess.DEVNULL, timeout=30)
                listed = {line.strip() for line in
                          out.stdout.decode("utf-8", "replace").split("\n") if line.strip()}
                how = "`typst fonts`"
            except Exception:  # noqa: BLE001 - 检测失败就退回文件系统
                listed = set()
        if not typst:
            how = "文件系统（未安装 typst）"
        have |= {name for name in CNOI_SYSTEM_FONTS if name in listed}
        if os.name == "nt":
            win = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
            alias = {"SimSun": ["simsun.ttc", "simsun.ttf"],
                     "SimHei": ["simhei.ttf"],
                     "KaiTi": ["simkai.ttf"]}
            for name, files in alias.items():
                if any((win / f).is_file() for f in files):
                    have.add(name)

    missing = [name for name in CNOI_SYSTEM_FONTS if name not in have]
    return sorted(have), missing, how


def _report_cjk_fonts() -> None:
    """把中文字体的检测结果打出来（缺了不影响 --check 的退出码，但必须提示）。"""
    have, missing, how = detect_cjk_fonts()
    if missing:
        print("[warn ] 中文字体缺失：%s（检测方式：%s）" % (", ".join(missing), how))
        print("        出 PDF 会缺字：Windows 一般自带这三个；Linux 请安装，")
        print("        或把同名 .ttf 放进 resources/cnoi/fonts/。")
    else:
        print("[info ] 中文字体可用：%s（检测方式：%s）" % (", ".join(have), how))


def _cnoi_zip_optional():
    cands = sorted(SOURCE.glob(CNOI_ZIP_PREFIX + "*.zip"))
    if not cands:
        return None
    if len(cands) > 1:
        print("[warn ] %s 下有多个 CNOI 生成器压缩包，使用最新的：%s"
              % (SOURCE.relative_to(ROOT), cands[-1].name))
    return cands[-1]


def _check_landed_cnoi(check: bool) -> list:
    """没有发布包 zip 时，只校验已经落地的 resources/cnoi。"""
    cnoi = RES / "cnoi"
    need = [cnoi / "typst" / "main.typ"] + [cnoi / "fonts" / f for f in CNOI_REQUIRED_FONTS]
    changed = [str(p) for p in need if not p.is_file()]
    if changed:
        print("[warn ] resources/cnoi 不完整，且没有可用的发布包 zip")
    else:
        print("[ok   ] resources/cnoi/ 已就绪（未发现 zip，使用已落地的模板与自由字体）")
    _report_cjk_fonts()
    return changed


# ---------------------------------------------------------------- 1. testlib

TESTLIB_README = """# testlib

`testlib.h` 是本工程数据生成器（`gen.cpp`）、校验器（`valid.cpp`）、
交互器（`interactor.cpp`）以及 testlib 型 `checker.cpp` 的唯一依赖。

- 文件位置：`resources/testlib/testlib.h`（版本见文件内 `#define VERSION`）
- 来源：`resources/source/testlib/testlib.h`，由 `python3 tools/setup_resources.py` 同步；
  上游 <https://github.com/MikeMirzayanov/testlib>
- 本工程固定使用 testlib，以保证所有随机数据可复现（见 `docs/workflow.md`）。

编译时统一加 `-I resources/testlib`（`tools/build.py` 已内置）。
需要手动编译时：

```bash
g++ -std=c++14 -O2 -Wall -I resources/testlib gen.cpp -o build/gen
```

## 使用约定

- `gen.cpp`：`registerGen(argc, argv, 1)`，seed 只来自生成器内部的 `CASES` 表。
- `valid.cpp`：`registerValidation(argc, argv)`，用带范围的 `readInt(l, r, "name")` 读取。
- `interactor.cpp`：`registerInteraction(argc, argv)`。
- `checker.cpp`：`registerTestlibCmd(argc, argv)`，用 `quitf(_ok/_wa/_pe/_fail/...)` 返回。

不要修改本目录下的 `testlib.h`；要升级请换 `resources/source/testlib/testlib.h` 后重跑同步脚本。
"""


def sync_testlib(check: bool) -> list:
    src = SOURCE / "testlib" / "testlib.h"
    dst = RES / "testlib" / "testlib.h"
    if not src.is_file():
        raise SystemExit("[error] 找不到 %s（原始素材应放在 resources/source/）" % src)
    changed = []
    if check:
        if not dst.is_file() or dst.read_bytes() != src.read_bytes():
            changed.append(str(dst))
    else:
        if _copy_if_changed(src, dst):
            print("[copy ] resources/source/testlib/testlib.h -> resources/testlib/testlib.h")
            changed.append(str(dst))
        else:
            print("[ok   ] resources/testlib/testlib.h 已是最新")
        if not (RES / "testlib" / "README.md").is_file():
            _write_text(RES / "testlib" / "README.md", TESTLIB_README)
            print("[write] resources/testlib/README.md")
            changed.append(str(RES / "testlib" / "README.md"))
    return changed


# ---------------------------------------------------------------- 2. CNOI 模板与字体

CNOI_README = """# CNOI 题面生成器（编译期资源）

这里存放 [cnoi-statement-generator](https://github.com/Mr-Python-in-China/cnoi-statement-generator)
中**编译 PDF 真正需要的文件**。上游项目本体是浏览器端 React 单页应用
（Markdown -> Typst -> PDF），本工程不引入其前端依赖，而是用 Typst CLI 编译同一套模板。

```
resources/cnoi/
├── typst/       # main.typ / header.typ / 代码高亮主题
├── fonts/       # 模板需要的自由字体（Latin Modern、New CM Math、Fira Mono）
└── VERSION      # 版本标记
```

**中文字体不在仓库里**：SimSun / SimHei / KaiTi 是商业字体，公开再分发有授权风险。
出 PDF 时 Typst 会去系统字体里找；Windows 一般自带这三个，Linux 需要自己安装。
检测方式：

```bash
python tools/setup_resources.py --check
```

它会用 `typst fonts` 检查这三个家族，缺失时给出提示。也可以把同名 `.ttf`
放进 `resources/cnoi/fonts/` 覆盖。

`tools/cnoi.py build` 的工作方式：把 `typst/` 复制到构建目录，生成 `content.json`、
`extra-precaution.typ`、`problem-<i>.typ`，然后运行

```bash
typst compile --font-path resources/cnoi/fonts --font-path <系统字体目录> \\
              --package-path resources/typst-packages \\
              --root <仓库根目录> main.typ out/statement.pdf
```

不要手工修改本目录下的文件；要跟随上游升级请把新的发布包放到 `resources/source/`
后重跑同步脚本，再跑 `python3 tools/selftest.py`。
"""


def sync_cnoi(check: bool, all_fonts: bool = False) -> list:
    zpath = _cnoi_zip_optional()
    if zpath is None:
        return _check_landed_cnoi(check)
    changed = []
    with zipfile.ZipFile(zpath) as z:
        names = z.namelist()
        root = names[0].split("/")[0] + "/"

        def extract(member: str, dst: Path, data=None) -> None:
            data = z.read(root + member) if data is None else data
            if check:
                if not dst.is_file() or dst.read_bytes() != data:
                    changed.append(str(dst))
                return
            if dst.is_file() and dst.read_bytes() == data:
                return
            dst.parent.mkdir(parents=True, exist_ok=True)
            with open(dst, "wb") as f:
                f.write(data)
            changed.append(str(dst))

        # 模板
        for m in [n[len(root):] for n in names if n.startswith(root + CNOI_TEMPLATE + "/")]:
            if m.endswith("/"):
                continue
            extract(m, RES / "cnoi" / "typst" / Path(m).name)

        # 字体：默认只装模板真正用到的（见 CNOI_REQUIRED_FONTS 的说明）
        font_members = [n[len(root):] for n in names
                        if n.startswith(root + CNOI_ASSET_FONTS + "/") and not n.endswith("/")]
        kept = []
        for m in font_members:
            fname = Path(m).name
            if not all_fonts and fname not in CNOI_REQUIRED_FONTS:
                continue
            extract(m, RES / "cnoi" / "fonts" / fname)
            kept.append(fname)
        if not all_fonts:
            missing = [f for f in CNOI_REQUIRED_FONTS if f not in kept]
            if missing:
                raise SystemExit(
                    "[error] 上游包里缺少模板需要的字体：%s\n"
                    "        可能是上游改了模板，请检查 %s 并更新 CNOI_REQUIRED_FONTS。"
                    % (", ".join(missing), zpath.name))
            # 清掉之前装多余字体留下的残留（例如曾用 --all-fonts 跑过）
            if not check:
                for old in (RES / "cnoi" / "fonts").glob("*"):
                    if old.name not in CNOI_REQUIRED_FONTS:
                        old.unlink()
                        print("[del  ] 移除模板未使用的字体：%s" % old.name)
        extra_note = "（全量 %d 个）" % len(kept) if all_fonts else \
            "（模板必需 %d 个，已跳过 %d 个未使用）" % (len(kept), len(font_members) - len(kept))
        print("[info ] 字体%s" % extra_note)

        # 版本标记
        if not check:
            marker = RES / "cnoi" / "VERSION"
            text = "source: resources/source/%s\nfonts: %s\n" % (
                zpath.name, "all" if all_fonts else "required")
            if not marker.is_file() or marker.read_text(encoding="utf-8") != text:
                _write_text(marker, text)
        if not check and not (RES / "cnoi" / "README.md").is_file():
            _write_text(RES / "cnoi" / "README.md", CNOI_README)

    if changed:
        print("[copy ] CNOI 模板与字体 -> resources/cnoi/（%d 个文件）" % len(changed))
    else:
        print("[ok   ] resources/cnoi/ 已是最新（来源 %s）" % zpath.name)
    _report_cjk_fonts()
    return changed


# ---------------------------------------------------------------- 3. Typst 包

def sync_typst_packages(check: bool) -> list:
    changed = []
    for name, version in TYPST_PACKAGES:
        dst = RES / "typst-packages" / "preview" / name / version
        marker = dst / "typst.toml"
        if marker.is_file():
            print("[ok   ] @preview/%s:%s 已存在" % (name, version))
            continue
        if check:
            changed.append(str(dst))
            continue
        url = TYPST_PACKAGE_REGISTRY.format(name=name, version=version)
        print("[net  ] 下载 %s" % url)
        try:
            with urllib.request.urlopen(url, timeout=180) as r:
                blob = r.read()
        except Exception as exc:  # noqa: BLE001
            raise SystemExit(
                "[error] 下载 @preview/%s:%s 失败：%s\n"
                "        请检查网络，或手动解包到 %s" % (name, version, exc, dst)
            )
        dst.mkdir(parents=True, exist_ok=True)
        with tarfile.open(fileobj=io.BytesIO(blob), mode="r:gz") as tf:
            tf.extractall(str(dst))
        print("[write] @preview/%s:%s -> resources/typst-packages/preview/%s/%s"
              % (name, version, name, version))
        changed.append(str(dst))
    return changed


# ---------------------------------------------------------------- main

def main() -> int:
    ap = argparse.ArgumentParser(
        description="把 resources/source/ 里的原始素材落地成构建资源")
    ap.add_argument("--only", choices=["testlib", "cnoi", "typst-packages"],
                    help="只同步指定部分")
    ap.add_argument("--all-fonts", action="store_true",
                    help="连模板没用到的字体一起装（+15.5 MiB，一般不需要）")
    ap.add_argument("--check", action="store_true",
                    help="只检查是否已落地（不写文件），有缺失时退出码为 1")
    args = ap.parse_args()

    changed = []
    if args.only in (None, "testlib"):
        changed += sync_testlib(args.check)
    if args.only in (None, "cnoi"):
        changed += sync_cnoi(args.check, all_fonts=args.all_fonts)
    if args.only in (None, "typst-packages"):
        changed += sync_typst_packages(args.check)

    if args.check and changed:
        print("[fail ] 以下资源缺失或过期：")
        for c in changed:
            print("         " + c)
        return 1
    if args.check:
        print("[pass ] resources/ 已全部就绪")
    return 0


if __name__ == "__main__":
    sys.exit(main())
