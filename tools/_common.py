#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""本工程 Python 工具的公共库。

只依赖标准库 + PyYAML。所有路径都相对于仓库根目录解析。
"""

from __future__ import annotations

import contextlib
import hashlib
import os
import re
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

# ---------------------------------------------------------------- 路径

# 仓库根：tools/ 与 resources/ 的锚点，永远不变
ROOT = Path(__file__).resolve().parent.parent


def _resolve_work() -> Path:
    """本次任务的工作根（日期目录）。

    优先级：环境变量 GEN_WORK > 当前目录（含 problems/ 或 contests/）> 仓库根。
    每个任务都在 runs/<开始日期>/ 里做，见 AGENTS.md K7；
    在该目录里直接跑 `python ../../tools/build.py ...` 即可自动认到。
    """
    env = os.environ.get("GEN_WORK")
    if env:
        return Path(env).resolve()
    cwd = Path.cwd().resolve()
    if (cwd / "problems").is_dir() or (cwd / "contests").is_dir():
        return cwd
    return ROOT


WORK = _resolve_work()
RESOURCES = ROOT / "resources"
PROBLEMS = WORK / "problems"
BUILD = WORK / "build"
CONTESTS = WORK / "contests"

TESTLIB_DIR = RESOURCES / "testlib"
CNOI_DIR = RESOURCES / "cnoi"
CNOI_TYPST_DIR = CNOI_DIR / "typst"
CNOI_FONTS_DIR = CNOI_DIR / "fonts"
TYPST_PACKAGES_DIR = RESOURCES / "typst-packages"

# ---------------------------------------------------------------- 编译选项

# 见 AGENTS.md 第 3 条：C++ 编译选项固定为 -std=c++14 -O2 -Wall
CXXFLAGS = ["-std=c++14", "-O2", "-Wall"]

# 评测机（Hydro / LemonLime）运行在 Linux 上，数据统一使用 LF 换行。
# testlib 的 eoln() 在 Windows 上默认要求 CRLF，因此必须定义 FOR_LINUX，
# 否则 valid.cpp 会对合法的 LF 数据报 "Expected EOLN"。
CXXFLAGS += ["-DFOR_LINUX"] if os.name == "nt" else []

# 本机（Windows / MinGW-w64 9.3.0 posix-dwarf）缺少 libgcc_s 的导入库
# （只有 bin/libgcc_s_seh-1.dll，链接时报 "cannot find -lgcc_s"），
# 因此本地编译额外加上 -static-libgcc。若换成完整工具链可自行去掉。
EXTRA_LDFLAGS = ["-static-libgcc"] if os.name == "nt" else []

# 源文件类别 -> 固定文件名（见 AGENTS.md 第 5 条）
SRC_STD = "std.cpp"
SRC_GEN = "gen.cpp"
SRC_VALID = "valid.cpp"
SRC_CHECKER = "checker.cpp"
SRC_INTERACTOR = "interactor.cpp"
SOLUTION = "sol.md"
SUBTASK_RE = re.compile(r"^(\d+)\.cpp$")  # 30.cpp / 60.cpp ... 按目标分数命名


# ---------------------------------------------------------------- 基础工具


@contextlib.contextmanager
def temp_dir(prefix: str):
    """建一个临时目录，**落在 build/tmp/ 下**，用完忽略错误地删掉。

    不用 `tempfile.TemporaryDirectory`：它在 Windows 上退出时会 chmod 目录，
    本机 / 沙箱环境会报 WinError 5；放在 build/ 里本来就可以随 build 一起删。
    """
    base = BUILD / "tmp"
    base.mkdir(parents=True, exist_ok=True)
    path = base / (prefix + uuid.uuid4().hex[:8])
    path.mkdir(parents=True, exist_ok=True)
    try:
        yield path
    finally:
        shutil.rmtree(str(path), ignore_errors=True)


def log(msg: str) -> None:
    print(msg, flush=True)


def warn(msg: str) -> None:
    print("[warn ] " + msg, flush=True)


def die(msg: str, code: int = 1):
    print("[error] " + msg, file=sys.stderr, flush=True)
    sys.exit(code)


def run(cmd: list, cwd: Path = None, check: bool = True, capture: bool = False):
    """运行外部命令。cmd 为列表，避免 shell 引号问题。"""
    log("  $ " + " ".join(str(c) for c in cmd))
    proc = subprocess.run(
        [str(c) for c in cmd],
        cwd=str(cwd) if cwd else None,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.STDOUT if capture else None,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if check and proc.returncode != 0:
        if capture and proc.stdout:
            print(proc.stdout, file=sys.stderr)
        die("命令失败（exit %d）：%s" % (proc.returncode, " ".join(str(c) for c in cmd)))
    return proc


def exe(name: str) -> str:
    """给可执行文件名加上平台后缀。"""
    return name + (".exe" if os.name == "nt" else "")


def read_yaml(path: Path) -> dict:
    if yaml is None:
        die("需要 PyYAML：pip install pyyaml")
    if not path.is_file():
        die("找不到配置文件：%s" % path)
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if data is None:
        die("配置文件为空：%s" % path)
    return data


def write_yaml(path: Path, data: dict) -> None:
    if yaml is None:
        die("需要 PyYAML：pip install pyyaml")
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def read_text(path: Path) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


# ---------------------------------------------------------------- 题目解析

class Problem(object):
    """一道题的目录结构。"""

    def __init__(self, pid: str):
        self.pid = pid
        self.dir = PROBLEMS / pid
        if not self.dir.is_dir():
            die("找不到题目目录：%s" % self.dir)
        self.src = self.dir / "src"
        self.data = self.dir / "data"
        self.hydro = self.dir / "hydro"
        self.statement = self.dir / "statement"
        self.build = BUILD / pid

    # -- 元信息 --------------------------------------------------

    @property
    def meta(self) -> dict:
        return read_yaml(self.dir / "meta.yaml")

    @property
    def hydro_config(self) -> dict:
        return read_yaml(self.hydro / "testdata" / "config.yaml")

    @property
    def has_file_io(self) -> bool:
        return bool(self.hydro_config.get("filename"))

    # -- 测试点列表 ----------------------------------------------

    def cases(self) -> list:
        """返回 [(子任务下标, 测试点下标, input 名, output 名)]。

        以 hydro/testdata/config.yaml 的 subtasks 为唯一事实来源。
        seed 与数据规模不在这里——它们由 src/gen.cpp 的配置表维护（见 docs/workflow.md §3）。
        """
        cfg = self.hydro_config
        subtasks = cfg.get("subtasks") or []
        if not subtasks:
            die("%s 未配置 subtasks；请先在 hydro/testdata/config.yaml 中声明测试点"
                % (self.hydro / "testdata" / "config.yaml"))
        out = []
        for si, st in enumerate(subtasks):
            for ci, case in enumerate(st.get("cases") or []):
                if "input" not in case or "output" not in case:
                    die("subtasks[%d].cases[%d] 缺少 input/output" % (si, ci))
                out.append((si, ci, case["input"], case["output"]))
        return out

    def subtask_names(self) -> list:
        names = []
        for si, st in enumerate(self.hydro_config.get("subtasks") or []):
            names.append(st.get("name") or "subtask%d" % si)
        return names

    # -- 源文件 --------------------------------------------------

    def source(self, name: str) -> Path:
        return self.src / name

    def subtask_sources(self) -> list:
        """按分数排序的子任务程序 [(分数, 路径)]。"""
        got = []
        for p in sorted(self.src.glob("*.cpp")):
            m = SUBTASK_RE.match(p.name)
            if m:
                got.append((int(m.group(1)), p))
        return sorted(got)


# ---------------------------------------------------------------- 单源编译

def compile_source(src: Path, out_dir: Path, name: str = None,
                   extra: list = None) -> Path:
    """用固定选项编译一个 C++ 源文件，返回可执行文件路径。

    编译选项固定为 `-std=c++14 -O2 -Wall`（AGENTS.md 铁律 2/3），
    并且**零警告**才算通过：出现 `warning:` 直接报错，避免"数据能跑但警告一堆"。
    """
    if not src.is_file():
        die("找不到源文件：%s" % src)
    if not TESTLIB_DIR.is_dir():
        die("resources/testlib 不存在；请先运行 python3 tools/setup_resources.py")
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / exe(name or src.stem)
    cmd = ["g++"] + CXXFLAGS + ["-I", str(TESTLIB_DIR)] + list(EXTRA_LDFLAGS)
    if extra:
        cmd += list(extra)
    cmd += [str(src), "-o", str(target)]
    proc = run(cmd, check=False, capture=True)
    output = proc.stdout or ""
    if proc.returncode != 0:
        sys.stderr.write(output)
        die("编译失败（exit %d）：%s" % (proc.returncode, src))
    warns = [line.strip() for line in output.split("\n") if "warning:" in line]
    if warns:
        for line in warns:
            print("  " + line, file=sys.stderr)
        die("%s 编译出现 %d 条警告（铁律 2：编译零警告，请修掉；"
            "确需抑制请说明理由并写进 docs/）" % (src.name, len(warns)))
    return target


def find_testlib_programs(problem: Problem) -> dict:
    """返回 {类别: 源文件路径}，只包含真实存在的文件。"""
    got = {}
    for key, fname in (("gen", SRC_GEN), ("valid", SRC_VALID),
                       ("checker", SRC_CHECKER), ("interactor", SRC_INTERACTOR),
                       ("std", SRC_STD)):
        p = problem.source(fname)
        if p.is_file():
            got[key] = p
    return got


# ---------------------------------------------------------------- 题面子任务表

# 题面的「## 子任务」小节由 config.yaml 生成，PDF（tools/cnoi.py）与
# Hydro 题面（tools/pack_hydro.py）共用这两个函数，保证两处同源、不会各写一份。
# 最后一列是「特殊性质」而不是「特殊限制」：子任务既可能用限制划分（n ≤ 10），
# 也可能用性质划分（不含空格），统称「特殊性质」才不会被写窄。
SUBTASK_TABLE_HEAD = [
    "| 测试点 | 分值 | 每个测试点 | 特殊性质 |",
    "| :---: | :---: | :---: | :--- |",
]

# 表格单元格里的 `|` 会被 GFM 当成列分隔符。数学里的 `|`（如 $|s|$）换成
# `\vert`，正文里的 `|` 转义成 `\|`，否则整张子任务表会错位。
_TABLE_MATH_RE = re.compile(r"\$[^$\n]*\$")


def escape_table_cell(text: str) -> str:
    """转义 GFM 表格单元格里的竖线。"""
    def math(match):
        return match.group(0).replace("|", r"\vert ")

    text = _TABLE_MATH_RE.sub(math, text)
    return re.sub(r"(?<!\\)\|", r"\\|", text)


def subtask_table(cfg: dict) -> str:
    """按 `hydro/testdata/config.yaml` 的 subtasks 生成子任务表；没有 subtasks 时返回空串。"""
    subtasks = (cfg or {}).get("subtasks") or []
    if not subtasks:
        return ""
    rows = list(SUBTASK_TABLE_HEAD)
    first = 1
    for st in subtasks:
        n = len(st.get("cases") or [])
        last = first + n - 1
        # 注意：rng 自己带 $...$，所以拼进单元格时不能再套一层 $
        rng = "$%d$" % first if n == 1 else "$%d \\sim %d$" % (first, last)
        score = int(st.get("score", 0))
        per_s = "%g" % (score / n if n else 0)
        lim = []
        if st.get("time"):
            lim.append("$%s$" % st["time"])
        if st.get("memory"):
            lim.append("$%s$" % st["memory"])
        desc = "；".join(x for x in ([st.get("name") or ""] + lim) if x)
        desc = escape_table_cell(desc) if desc else "无"
        rows.append("| %s | $%d$ | $%s$ | %s |" % (rng, score, per_s, desc))
        first = last + 1
    return "\n".join(rows) + "\n"


def subtask_section(cfg: dict, testcase: str = None) -> str:
    """整段「## 子任务」小节（含前后说明）；config.yaml 没有 subtasks 时返回空串。"""
    table = subtask_table(cfg)
    if not table:
        return ""
    if testcase is None:
        testcase = str(sum(len(st.get("cases") or []) for st in (cfg.get("subtasks") or [])))
    return ("\n## 子任务\n\n本题共 %s 个测试点，按测试点计分：\n\n" % testcase) \
        + table + "\n每个测试点单独评分，全部测试点的得分之和即为本题得分。\n"


def files_equal(a: Path, b: Path) -> bool:
    if not (a.is_file() and b.is_file()):
        return False
    if a.stat().st_size != b.stat().st_size:
        return False
    return hashlib.sha256(a.read_bytes()).digest() == hashlib.sha256(b.read_bytes()).digest()


def reset_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(str(path))
    path.mkdir(parents=True, exist_ok=True)
