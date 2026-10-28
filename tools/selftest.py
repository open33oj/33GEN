#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""工具链自检：在模板题上把整条流水线跑一遍，并断言关键性质。

    python3 tools/selftest.py

检查内容（全部通过才算工具链健康）：

  1. 资源就绪（testlib / CNOI 模板字体 / Typst 包）；
  2. config.yaml 声明的测试点与 gen.cpp 的 CASES 表一致；
  3. 编译 → 生成数据 → 校验 → 检查答案 全绿；
  4. **可复现性**：删掉数据重新生成，逐字节与上一次相同；
  5. 题面方言校验（cnoi.py check --strict）；
  6. 题面 PDF + PNG 预览生成成功；
  7. 样例数据（samples.py）能从题面与大样例配置生成；
  8. 两个打包器都能产出（Hydro zip / LemonLime cdf+data+down），
     且 data/ 与 down/ 的目录与文件名都用题目的英文短名。

用法上它只依赖 problems/_template，不会碰你正在出的题。
"""

from __future__ import annotations

import argparse
import hashlib
import re
import shutil
import struct
import subprocess
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
sys.path.insert(0, str(TOOLS))

from _common import BUILD, WORK, Problem, log, warn  # noqa: E402

PY = sys.executable or "python"


class Checker(object):
    def __init__(self):
        self.failed = 0
        self.passed = 0

    def ok(self, title, detail=""):
        self.passed += 1
        log("[ok  ] %s%s" % (title, ("  " + detail) if detail else ""))

    def bad(self, title, detail=""):
        self.failed += 1
        log("[FAIL] %s%s" % (title, ("  " + detail) if detail else ""))

    def step(self, title, argv, cwd=None, show_tail=6):
        log("")
        log("── %s" % title)
        proc = subprocess.run(argv, cwd=str(cwd) if cwd else None,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                              encoding="utf-8", errors="replace")
        tail = "\n".join((proc.stdout or "").strip().split("\n")[-show_tail:])
        if tail:
            print("   " + tail.replace("\n", "\n   "))
        if proc.returncode != 0:
            self.bad(title, "exit %d" % proc.returncode)
        else:
            self.ok(title)
        return proc


def hash_dir(path: Path) -> dict:
    got = {}
    for f in sorted(path.glob("*")):
        if f.is_file():
            got[f.name] = hashlib.sha256(f.read_bytes()).hexdigest()
    return got


# ---------------------------------------------------------------- 静态检查

def lint_unused_imports() -> list:
    """找出 tools/ 下未被使用的 import（纯 AST，不依赖第三方库）。

    只报"确实没用到"的：跳过 `from __future__`，以及带 `__all__` 的包
    `__init__.py`（那里的 import 是刻意的再导出）。
    """
    import ast

    problems = []
    for path in sorted(TOOLS.rglob("*.py")):
        src = path.read_text(encoding="utf-8")
        if path.name == "__init__.py" and "__all__" in src:
            continue
        try:
            tree = ast.parse(src, filename=str(path))
        except SyntaxError as exc:
            problems.append("%s 语法错误：%s" % (path.relative_to(ROOT), exc))
            continue
        used = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                used.add(node.id)
            elif isinstance(node, ast.Attribute):
                root = node
                while isinstance(root, ast.Attribute):
                    root = root.value
                if isinstance(root, ast.Name):
                    used.add(root.id)
        imported = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for a in node.names:
                    if a.name != "__future__":
                        imported.append((a.asname or a.name.split(".")[0], node.lineno))
            elif isinstance(node, ast.ImportFrom):
                if node.module == "__future__":
                    continue
                for a in node.names:
                    if a.name != "*":
                        imported.append((a.asname or a.name, node.lineno))
        for name, lineno in imported:
            if name not in used:
                problems.append("%s:%d 未使用的 import: %s"
                                % (path.relative_to(ROOT), lineno, name))
    return problems


def font_families(path: Path) -> set:
    """读 TrueType/OpenType 的 name 表，取出字体家族名（1 与 16 号记录）。"""
    data = path.read_bytes()
    off = struct.unpack(">I", data[12:16])[0] if data[:4] == b"ttcf" else 0
    num = struct.unpack(">H", data[off + 4:off + 6])[0]
    tables = {}
    for i in range(num):
        p = off + 12 + 16 * i
        tag = data[p:p + 4].decode("latin1", "replace")
        o, l = struct.unpack(">II", data[p + 8:p + 16])
        tables[tag] = (o, l)
    o, _l = tables["name"]
    _fmt, cnt, so = struct.unpack(">HHH", data[o:o + 6])
    fams = set()
    for i in range(cnt):
        p = o + 6 + 12 * i
        pid, _eid, _lid, nid, ln, offset = struct.unpack(">HHHHHH", data[p:p + 12])
        if nid not in (1, 16):
            continue
        raw = data[o + so + offset: o + so + offset + ln]
        try:
            fams.add(raw.decode("utf-16-be") if pid == 3 else raw.decode("latin1"))
        except Exception:  # noqa: BLE001
            continue
    return fams


def system_font_families() -> set:
    """`typst fonts` 能看到的系统字体家族；没有 typst 或执行失败就返回空集。"""
    typst = shutil.which("typst")
    if not typst:
        return set()
    try:
        out = subprocess.run([typst, "fonts"], stdout=subprocess.PIPE,
                             stderr=subprocess.DEVNULL, timeout=30)
        text = out.stdout.decode("utf-8", "replace")
        return {line.strip() for line in text.split("\n") if line.strip()}
    except Exception:  # noqa: BLE001 - 检测失败按"没有系统字体"处理
        return set()


def check_fonts(problem) -> tuple:
    """确认模板引用的每个字体家族都能拿到。

    仓库只带自由字体；SimSun / SimHei / KaiTi 是商业字体，改由系统提供
    （见 setup_resources.py 的 CNOI_SYSTEM_FONTS）。所以除了看
    `resources/cnoi/fonts/`，还要问一遍 `typst fonts`，两边都没有才算缺失。
    """
    fonts_dir = ROOT / "resources" / "cnoi" / "fonts"
    typst_dir = ROOT / "resources" / "cnoi" / "typst"
    if not fonts_dir.is_dir() or not typst_dir.is_dir():
        return None, "resources/cnoi 未落地"

    wanted = set()
    for f in sorted(typst_dir.glob("*.typ")):
        src = f.read_text(encoding="utf-8")
        for m in re.finditer(r'font:\s*\(?"([^"]+)"', src):
            wanted.add(m.group(1).strip())
        for m in re.finditer(r'font:\s*\(([^)]*)\)', src):
            for name in re.findall(r'"([^"]+)"', m.group(1)):
                wanted.add(name.strip())
    if not wanted:
        return None, "模板里没解析出 font: 声明（模板结构可能变了）"

    have = {}
    for p in sorted(fonts_dir.glob("*")):
        for fam in font_families(p):
            have.setdefault(_norm_font(fam), p.name)

    missing = []
    sys_fams = {_norm_font(x) for x in system_font_families()}
    for name in sorted(wanted):
        n = _norm_font(name)
        if n in have or n in sys_fams:
            continue
        missing.append(name)
    return sorted(wanted), missing


def _norm_font(name: str) -> str:
    """把字体家族名归一化，便于比对。

    模板里写 `New Computer Modern Math`，字体内部叫 `NewComputerModern Math`；
    标题用 `Latin Modern Roman 12`，内部是 `LM Roman 12`。所以：
    去掉空格/连字符等分隔符并转小写，再把 `latinmodern` 缩成 `lm`。
    """
    low = re.sub(r"[\s\-_]+", "", name).lower()
    return low.replace("latinmodern", "lm")


def main() -> int:
    ap = argparse.ArgumentParser(description="工具链自检（在模板题上跑通全流程）")
    ap.add_argument("--problem", default="_template", help="用哪道题做自检")
    ap.add_argument("--keep", action="store_true", help="保留自检产生的数据与产物")
    args = ap.parse_args()

    c = Checker()
    p = Problem(args.problem)
    log("自检题目：%s" % p.dir)

    # 0. 静态检查（不需要题目，不需要编译，最快）
    log("")
    log("── 工具代码静态检查（未使用的 import）")
    problems = lint_unused_imports()
    if problems:
        for item in problems:
            log("   %s" % item)
        c.bad("静态检查", "%d 处问题" % len(problems))
    else:
        c.ok("静态检查", "tools/ 下无未使用的 import")

    # 1. 资源
    c.step("资源就绪 (setup_resources --check)",
           [PY, str(TOOLS / "setup_resources.py"), "--check"], cwd=WORK)

    # 1b. 字体覆盖
    log("")
    log("── 模板字体覆盖检查")
    wanted, missing = check_fonts(p)
    if wanted is None:
        c.bad("字体覆盖", str(missing))
    elif missing:
        c.bad("字体覆盖", "模板用到但没装的字体：%s（上游可能改了模板，"
                          "见 setup_resources.py 的 CNOI_REQUIRED_FONTS）"
                          % ", ".join(missing))
    else:
        c.ok("字体覆盖", "模板引用的 %d 个字体家族都有对应文件" % len(wanted))

    # 2. config 与 gen.cpp 的一致性
    log("")
    log("── config.yaml 与 gen.cpp 的一致性")
    c.step("编译生成器", [PY, str(TOOLS / "build.py"), "build", "--problem", p.pid],
           cwd=WORK, show_tail=2)
    gen_exe = p.build / "bin" / ("gen.exe" if sys.platform == "win32" else "gen")
    declared = []
    if gen_exe.is_file():
        proc = subprocess.run([str(gen_exe), "--list"], stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, encoding="utf-8", errors="replace")
        declared = [x.strip() for x in (proc.stdout or "").split("\n") if x.strip()]
    wanted = [Path(x[2]).stem for x in p.cases()]
    if not declared:
        warn("生成器没有实现 --list，跳过一致性检查")
    elif declared == wanted:
        c.ok("测试点声明一致", "%d 个：%s" % (len(declared), ", ".join(declared)))
    else:
        c.bad("测试点声明不一致", "config=%s gen.cpp=%s" % (wanted, declared))

    # 3. 全流程
    c.step("编译 + 生成 + 校验 + 检查 (build.py all)",
           [PY, str(TOOLS / "build.py"), "all", "--problem", p.pid], cwd=WORK)

    # 4. 可复现性
    log("")
    log("── 数据可复现性（重新生成后逐字节比对）")
    first = hash_dir(p.data)
    if not first:
        c.bad("可复现性", "data/ 为空，上一步可能没生成数据")
    else:
        shutil.rmtree(str(p.data))
        proc = subprocess.run([PY, str(TOOLS / "build.py"), "gen", "--problem", p.pid],
                              cwd=str(WORK), stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, encoding="utf-8", errors="replace")
        second = hash_dir(p.data)
        if proc.returncode != 0:
            c.bad("可复现性", "重新生成失败")
        elif first == second:
            c.ok("可复现性", "%d 个文件逐字节相同" % len(first))
        else:
            diff = sorted(set(first) ^ set(second)) or \
                [k for k in first if first.get(k) != second.get(k)]
            c.bad("可复现性", "以下文件不一致：%s" % ", ".join(diff))

    # 5. 题面校验
    c.step("题面方言校验 (cnoi.py check --strict)",
           [PY, str(TOOLS / "cnoi.py"), "check", "--problem", p.pid,
            "-o", str(BUILD / "selftest" / "check"), "--strict"], cwd=WORK)

    # 6. 题面 PDF + 预览
    out = BUILD / "selftest" / "statement"
    c.step("题面 PDF + PNG 预览 (cnoi.py build --preview)",
           [PY, str(TOOLS / "cnoi.py"), "build", "--problem", p.pid,
            "-o", str(out), "--preview"], cwd=WORK, show_tail=4)
    pdf = out / "statement.pdf"
    pngs = sorted((out / "preview").glob("page-*.png")) if (out / "preview").is_dir() else []
    if pdf.is_file() and pngs:
        c.ok("产物检查", "PDF %.1f KiB + %d 张预览图" % (pdf.stat().st_size / 1024.0, len(pngs)))
    else:
        c.bad("产物检查", "缺少 statement.pdf 或预览图")

    # 7. 样例数据与打包
    c.step("样例数据 (samples.py)",
           [PY, str(TOOLS / "samples.py"), "--problem", p.pid], cwd=WORK, show_tail=3)
    sample_dir = p.data / "samples"
    name = str(p.meta.get("name") or p.pid)
    sample_ins = sorted(sample_dir.glob("%s*.in" % name)) if sample_dir.is_dir() else []
    if sample_ins and all(f.with_suffix(".ans").is_file() for f in sample_ins):
        c.ok("样例数据", "%d 对：%s" % (len(sample_ins), ", ".join(f.name for f in sample_ins)))
    else:
        c.bad("样例数据", "data/samples/ 下没有成对的 %s<编号>.in/.ans" % name)

    c.step("Hydro 题包 (pack_hydro)",
           [PY, str(TOOLS / "pack_hydro.py"), "--problem", p.pid], cwd=WORK, show_tail=1)
    c.step("LemonLime 包 (pack_lemon)",
           [PY, str(TOOLS / "pack_lemon.py"), "--contest", "selftest",
            "--problem", p.pid], cwd=WORK, show_tail=1)

    # down/ 结构与命名：data/<英文名>/<英文名><n>.in、down/<英文名>/<英文名><k>.in
    lemon = BUILD / "lemon" / "selftest"
    ok_layout = ((lemon / "data" / name / ("%s1.in" % name)).is_file()
                 and (lemon / "down" / name / ("%s1.ans" % name)).is_file())
    if ok_layout:
        c.ok("LemonLime 目录命名", "data/%s/%s1.in 与 down/%s/%s1.ans 都在" % (name, name, name, name))
    else:
        c.bad("LemonLime 目录命名", "应存在 data/%s/%s1.in 与 down/%s/%s1.ans" % (name, name, name, name))

    log("")
    log("=" * 56)
    log("自检结果：%d 项通过，%d 项失败" % (c.passed, c.failed))
    if c.failed:
        log("自检产物保留在 %s，便于排查" % (BUILD / "selftest"))
        return 1

    if args.keep:
        log("已保留自检产物（--keep）：%s" % (BUILD / "selftest"))
    else:
        # 只清理**本次自检自己产生**的东西，绝不碰别的工具的输出：
        #   build/selftest/   自检的题面与预览
        #   build/_template/  自检编译出来的可执行文件
        #   build/hydro、build/lemon 是打包器正常产物，保留
        shutil.rmtree(str(BUILD / "selftest"), ignore_errors=True)
        shutil.rmtree(str(p.build), ignore_errors=True)
        log("已清理自检中间产物（build/selftest、build/%s）" % p.pid)
    return 0


if __name__ == "__main__":
    sys.exit(main())
