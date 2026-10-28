#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CNOI 题面工具（Python 版的 cnoi-statement-generator 命令行工具）。

它是上游浏览器端生成器 `Mr-Python-in-China/cnoi-statement-generator` 的
Python/CLI 对应实现：同一套 Typst 模板、同一套 Markdown 方言，
但把「Markdown -> Typst -> PDF」的过程搬到命令行，便于出题流程自动化。

典型用法：

    # 单文件：Markdown -> Typst（只看产物）
    python3 tools/cnoi.py convert problems/_template/statement/zh_CN.md -o build/x

    # 单文件：直接出 PDF
    python3 tools/cnoi.py build problems/_template/statement/zh_CN.md --title "A + B Problem"

    # 题目目录：自动读 meta.yaml / contest.yaml
    python3 tools/cnoi.py build --problem _template --preview

    # 只校验
    python3 tools/cnoi.py check --problem _template --strict

子命令：
    convert   Markdown -> Typst 源码（可导出上游网页版生成器用的 markdown）
    build     Markdown -> Typst -> PDF（可选 PNG 预览）
    check     不编译，只做方言校验
    info      打印文档树统计（小节、脚注、块类型计数）
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import uuid
from pathlib import Path

# 让 `python tools/cnoi.py ...`、`python -m cnoi.cli` 与包内导入都能工作：
# 先把 tools/ 放进 sys.path，再用绝对导入拿公共库，避免依赖包层级。
_TOOLS_DIR = str(Path(__file__).resolve().parent.parent)
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)

from _common import (  # noqa: E402
    CONTESTS, RESOURCES, ROOT, Problem, die, log, read_text, read_yaml,
    subtask_table, warn, write_text,
)

from . import md as cnoi_md  # noqa: E402
from . import typst as cnoi_typst  # noqa: E402

CNOI_FONTS = RESOURCES / "cnoi" / "fonts"
CNOI_TYPST = RESOURCES / "cnoi" / "typst"
CNOI_PKGS = RESOURCES / "typst-packages"

DEFAULT_PRECAUTION = """**注意事项（请仔细阅读）**

1. 文件名（程序名和输入输出文件名）必须使用英文小写。
2. `main` 函数的返回值类型必须是 `int`，程序正常结束时的返回值必须是 0。
3. 若无特殊说明，结果的比较方式为全文比较（过滤行末空格及文末回车）。
4. 程序可使用的栈空间内存限制与题目的内存限制一致。
5. 只提供 Linux 格式附加样例文件。
"""

STABLE_NS = uuid.uuid5(uuid.NAMESPACE_URL, "33gen/cnoi-statement")


# ---------------------------------------------------------------- 辅助

def stable_uuid(seed: str) -> str:
    return str(uuid.uuid5(STABLE_NS, seed))


def norm_seconds(raw, default="1.0 秒") -> str:
    if raw is None:
        return default
    m = re.match(r"^\s*([\d.]+)\s*(ms|s)?\s*$", str(raw))
    if not m:
        return str(raw)
    val = float(m.group(1))
    if m.group(2) == "ms":
        val /= 1000.0
    return "%.1f 秒" % val


def norm_mebibytes(raw, default="512 MiB") -> str:
    if raw is None:
        return default
    m = re.match(r"^\s*([\d.]+)\s*([mMgG]?)", str(raw))
    if not m:
        return str(raw)
    val = float(m.group(1))
    if m.group(2).lower() == "g":
        val *= 1024
    return "%d MiB" % int(val)


def make_typst(verbose: bool, work_root: Path, resource_dir: Path = None) -> "cnoi_typst.Typst":
    if not CNOI_FONTS.is_dir():
        die("缺少 %s；请先运行 python3 tools/setup_resources.py" % CNOI_FONTS)
    if not (CNOI_PKGS / "preview" / "oxifmt").is_dir():
        die("缺少 %s；请先运行 python3 tools/setup_resources.py" % CNOI_PKGS)
    fonts = [CNOI_FONTS] + list(cnoi_typst.system_font_dirs())
    # --root 必须同时包含「工程目录」与「题面引用的资源目录」（图片常写成
    # resources/xxx/fig.png 这种仓库相对路径），所以取两者的公共父目录。
    # Typst 的约束是：主文件必须位于 --root 之内。
    cands = [Path(resource_dir)] if resource_dir else []
    cands.append(RESOURCES)
    for cand in cands:
        if cand.is_dir() and _is_within(Path(work_root), cand):
            root = cand
            break
    else:
        root = ROOT          # 兜底：仓库根一定能同时包住两边
    return cnoi_typst.Typst(font_dirs=fonts, package_dir=CNOI_PKGS,
                            root=root, verbose=verbose)


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def report(errors, warnings, strict: bool) -> int:
    for w in warnings:
        warn("题面检查：%s" % w)
    for e in errors:
        print("[error] 题面检查：%s" % e, file=sys.stderr)
    if errors:
        return 1
    if strict and warnings:
        print("[error] --strict：%d 条警告被当作错误" % len(warnings), file=sys.stderr)
        return 1
    return 0


# ---------------------------------------------------------------- 模板补丁

# 上游模板 main.typ 属于第三方快照，不能直接改（AGENTS.md 铁律 11：
# resources/cnoi/ 由 tools/setup_resources.py 从 zip 落地，改了会被覆盖）。
# 本工程对封面/页眉有明确要求，所以在**复制到构建目录之后**按锚点打补丁。
# 每个补丁必须恰好命中一次，否则直接报错——上游升级后会立刻暴露，
# 而不是悄悄生成一份版式不对的 PDF。
TIME_DEF_RE = re.compile(r"#let time = \(\n.*?\n\)\n\n", re.S)
TIME_RENDER_RE = re.compile(r"  #if time != none \{\n.*?\n  \}\n", re.S)

STAGE_PATCHES = [
    # 1) 封面不显示「时间：…~…」（比赛时间由比赛系统展示，题面上不写）
    (TIME_DEF_RE, ""),
    (TIME_RENDER_RE, ""),
    # 2) 页眉三段之间补空格：上游是直接拼接，换成新短名后会粘成一串
    (re.compile(r"        #data\.title\n        #data\.subtitle\n"
                r"        #h\(1fr\)\n        #data\.dayname\n"),
     "        #data.title\n        #h(0.6em)\n        #data.subtitle\n"
     "        #h(0.6em)\n        #data.dayname\n        #h(1fr)\n"),
    # 3) PDF 元数据标题：上游只写 #set document(title: data.title)，
    #    浏览器标签页只会显示「三三信奥国庆模拟赛」，看不到组别与场次。
    #    这里补成「比赛名 组别 场次」（空字段自动跳过）。
    (re.compile(r"#set document\(title: data\.title\)\n"),
     "#set document(title: (data.title, data.subtitle, data.dayname)\n"
     "  .filter(x => x != none and x != \"\").join(\" \"))\n"),
]


def stage_template(typst_dir: Path) -> None:
    """把 CNOI 模板复制到构建目录，并打上本工程的补丁。"""
    for f in sorted(CNOI_TYPST.glob("*")):
        shutil.copyfile(str(f), str(typst_dir / f.name))
    main = typst_dir / "main.typ"
    text = read_text(main)
    for i, (pattern, repl) in enumerate(STAGE_PATCHES, start=1):
        text, hits = pattern.subn(repl, text)
        if hits != 1:
            die("题面模板补丁 #%d 命中 %d 次（应为 1 次）：%s 可能已被上游改动，"
                "请核对 tools/cnoi/cli.py 的 STAGE_PATCHES"
                % (i, hits, (CNOI_TYPST / "main.typ").relative_to(ROOT)))
    write_text(main, text)


# ---------------------------------------------------------------- 输入解析

class Input(object):
    """把「一个 md 文件」或「一道题的目录」统一成一份输入。"""

    def __init__(self, md_text, name, title, subtitle, dayname, date_range,
                 languages, precaution, noi_style, file_io, fname,
                 time_limit, memory_limit, testcase, point_equal, submit, src,
                 pid=None, pname=None):
        self.md_text = md_text
        self.name = name
        self.title = title           # 封面第一行：比赛名（或单题时的题目名）
        self.pname = pname or title  # 本题题目名（封面表格与页眉用）
        self.subtitle = subtitle
        self.dayname = dayname
        self.date_range = date_range
        self.languages = languages
        self.precaution = precaution
        self.noi_style = noi_style
        self.file_io = file_io
        self.fname = fname
        self.time_limit = time_limit
        self.memory_limit = memory_limit
        self.testcase = testcase
        self.point_equal = point_equal
        self.submit = submit
        self.src = src
        self.pid = pid

    @property
    def typst_name(self) -> str:
        return "problem-0"

    def subtask_table(self, index) -> str:
        """按本题的 hydro/testdata/config.yaml 生成「子任务」小节 Markdown。

        这样题面里的子任务表与评测配置**同源**，不会各写一份而漂移；
        Hydro 题面（tools/pack_hydro.py）用的是同一个 `_common.subtask_table()`。
        """
        if not self.pid:
            return ""
        return subtask_table(Problem(self.pid).hydro_config)


def input_from_problem(pid: str, args, contest: dict = None) -> "Input":
    """从 problems/<pid>/ 组装一份题面输入。

    contest 是**调用方传入**的比赛级信息：
      * `build_contest` 传该场比赛的配置；
      * 单题命令没给 `--contest` 时，才回退到 meta.yaml 里的 `contest` 字段。
    注意：同一道题可能被两场比赛复用（例如第 2 天的 S 组复用 J3/J4），
    此时只能靠调用方决定用哪一场的封面信息，不能只看 meta.yaml。
    """
    p = Problem(pid)
    md_path = p.statement / "zh_CN.md"
    if not md_path.is_file():
        die("找不到题面：%s" % md_path)
    meta = p.meta
    if contest is None and meta.get("contest"):
        cpath = CONTESTS / (meta["contest"] + ".yaml")
        if cpath.is_file():
            contest = read_yaml(cpath)
    contest = contest or {}
    cfg = p.hydro_config
    fname = cfg.get("filename")
    cases = p.cases()
    precaution_path = p.statement / "precaution.md"
    precaution = read_text(precaution_path) if precaution_path.is_file() \
        else DEFAULT_PRECAUTION
    date = contest.get("date") or {}
    date_range = None
    if date.get("start"):
        start = list(date["start"])
        end = list(date.get("end") or start[:3] + [12, 0, 0])
        date_range = (start, end)
    langs = contest.get("languages") or [
        {"name": "C++", "compile_options": "-O2 -std=c++14 -static"}]
    return Input(
        md_text=read_text(md_path),
        name=meta.get("name") or p.pid,
        # 封面第一行用比赛名（contest 的 title），没有才退回题目名；
        # 本题题目名放进 pname，用于封面表格与页眉。
        title=getattr(args, "title", None) or contest.get("title") or meta.get("title") or p.pid,
        pname=meta.get("title") or p.pid,
        subtitle=contest.get("subtitle", ""),
        dayname=contest.get("dayname", ""),
        date_range=date_range,
        languages=langs,
        precaution=precaution,
        noi_style=bool(contest.get("noi_style", True)),
        # file_io：比赛配置里开了（封面列「输入文件名 / 输出文件名」两行），
        # 或者本题自己声明了 filename（真的用文件 IO）时为真。
        file_io=bool(contest.get("file_io")) or bool(fname),
        fname=fname,
        time_limit=norm_seconds(meta.get("time") or cfg.get("time")),
        memory_limit=norm_mebibytes(meta.get("memory") or cfg.get("memory")),
        testcase=str(len(cases)),
        # 「测试点是否等分」看的是**每个测试点**的分值，不是子任务的总分：
        # 本批比赛 6+6+8 个点、30+30+40 分，每点都是 5 分，所以封面显示「是」
        # （按测试点得分，见 docs/rules.md）。
        point_equal="是" if len({int(st.get("score", 0)) // max(1, len(st.get("cases") or [1]))
                                for st in (cfg.get("subtasks") or [])}) <= 1
        else "否",
        submit=[meta.get("submit_filename") or (fname or p.pid) + ".cpp"],
        src=md_path,
        pid=pid,
    )


def contest_entries(cfg: dict) -> list:
    """把 contests/<id>.yaml 的 problems 归一化成 [(folder, pos)]。"""
    out = []
    for item in cfg.get("problems") or []:
        if isinstance(item, dict):
            folder = item.get("folder") or item.get("problem")
            if not folder:
                die("contests 里的 problems 项缺少 folder：%r" % item)
            out.append((folder, item.get("pos") or folder))
        else:
            out.append((item, item))
    return out


def load_contest(cid: str) -> dict:
    path = CONTESTS / (cid + ".yaml")
    if not path.is_file():
        die("找不到比赛配置：%s（contests/<id>.yaml）" % path)
    cfg = read_yaml(path)
    if not cfg.get("problems"):
        die("%s 里没有列出 problems" % path)
    return cfg


def load_input(args) -> "Input":
    if getattr(args, "contest", None):
        # 单题命令借比赛配置取封面信息（取第一题或指定题目）
        cfg = load_contest(args.contest)
        entries = contest_entries(cfg)
        folder = args.problem or entries[0][0]
        return input_from_problem(folder, args, cfg)
    if args.problem:
        # 单题模式：优先用 --contest 指定的比赛，否则回退到 meta.yaml 的 contest
        return input_from_problem(args.problem, args, None)

    src = Path(args.markdown)
    if not src.is_file():
        die("找不到 Markdown 文件：%s" % src)
    text = read_text(src)
    title = args.title or _first_heading(text) or src.stem
    return Input(
        md_text=text,
        name=args.name or src.stem,
        title=title,
        subtitle=args.subtitle or "",
        dayname=args.day or "",
        date_range=None,
        languages=[{"name": "C++", "compile_options": "-O2 -std=c++14 -static"}],
        precaution=DEFAULT_PRECAUTION,
        noi_style=True,
        file_io=False,
        fname=None,
        time_limit="1.5 秒",
        memory_limit="512 MiB",
        testcase="20",
        point_equal="是",
        submit=[src.stem + ".cpp"],
        src=src,
        pid=None,
    )


def _first_heading(text: str) -> str:
    for line in text.split("\n"):
        m = re.match(r"^#{1,2}\s+(.*?)\s*$", line)
        if m and m.group(1) not in ("题目描述", "输入格式", "输出格式"):
            return m.group(1)
    return ""


# ---------------------------------------------------------------- content.json

def _problem_entry(inp: Input, index: int) -> dict:
    # 「目录 / 可执行文件名 / 输入输出文件名」用同一套短名：
    # 题目声明了 filename 就用它（文件 IO 题），否则用英文短名 name。
    stem = inp.fname or inp.name
    return {
        "uuid": stable_uuid("problem-%s-%d" % (inp.name, index)),
        "name": inp.name,
        "title": inp.pname,          # 封面上这一列显示的是本题题目名
        "type": "传统型",
        "dir": stem,
        "exec": stem,
        "input": (stem + ".in") if inp.file_io else "stdin",
        "output": (stem + ".out") if inp.file_io else "stdout",
        "time_limit": inp.time_limit,
        "memory_limit": inp.memory_limit,
        "testcase": inp.testcase,
        "point_equal": inp.point_equal,
        "submit_filename": inp.submit,
        "pretestcase": "",
        "markdown": _problem_markdown(inp, index),
    }


def build_content(inp: Input, extra: list = None) -> dict:
    """生成 content.json。extra 是多题场景下除第一题以外的题目。"""
    problems = [_problem_entry(inp, 0)]
    for k, other in enumerate(extra or [], start=1):
        problems.append(_problem_entry(other, k))
    content = {
        "title": inp.title,
        "subtitle": inp.subtitle,
        "dayname": inp.dayname,
        "use_pretest": False,
        "noi_style": inp.noi_style,
        "file_io": inp.file_io,
        "support_languages": [
            {"uuid": stable_uuid("lang-" + l["name"]), "name": l["name"],
             "compile_options": l.get("compile_options", "")} for l in inp.languages],
        "problems": problems,
        "extraContents": {"precaution": {"markdown": inp.precaution}},
        "images": [],
    }
    # 比赛时间：本工程不把它印在题面上（模板补丁已去掉「时间：…」一行），
    # 所以只有比赛配置里真的写了 date 才放进 content.json。
    if inp.date_range:
        start, end = inp.date_range
        content["date"] = {"start": list(start), "end": list(end)}
    return content


# ---------------------------------------------------------------- 子命令

def cmd_convert(args) -> int:
    inp = load_input(args)
    errors, warnings = cnoi_md.check(inp.md_text)
    if errors:
        return report(errors, warnings, args.strict)
    report(errors, warnings, args.strict)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    typst_src = cnoi_md.render(inp.md_text)
    write_text(out_dir / "problem-0.typ", typst_src)
    write_text(out_dir / "problem-0.md", inp.md_text)
    log("已写出 Typst 源码：%s" % (out_dir / "problem-0.typ"))

    if args.roundtrip:
        back = cnoi_md.typst_to_markdown(typst_src)
        write_text(out_dir / "roundtrip.md", back)
        log("已写出回写结果：%s" % (out_dir / "roundtrip.md"))

    if args.content_json:
        write_text(out_dir / "content.json",
                   json.dumps(build_content(inp), ensure_ascii=False, indent=2) + "\n")
        write_text(out_dir / "extra-precaution.md", inp.precaution)
        log("已写出网页版生成器输入：%s" % (out_dir / "content.json"))
    return 0


def cmd_check(args) -> int:
    inp = load_input(args)
    errors, warnings = cnoi_md.check(inp.md_text)
    code = report(errors, warnings, args.strict)
    if code == 0:
        log("题面校验通过（%d 条警告）" % len(warnings))
    return code


def cmd_info(args) -> int:
    inp = load_input(args)
    doc = cnoi_md.parse(inp.md_text)
    info = cnoi_md.ast_summary(doc)
    log("来源：%s" % inp.src)
    log("标题：%s（短名 %s）" % (inp.title, inp.name))
    log("块级节点：%d" % info["blocks"])
    log("节点计数：" + ", ".join("%s=%d" % kv for kv in sorted(info["counts"].items())))
    if info["headings"]:
        log("小节：")
        for depth, title in info["headings"]:
            log("  %s%s" % ("  " * (depth - 2) if depth >= 2 else "", title))
    if info["footnotes"]:
        log("脚注定义：%s" % ", ".join(info["footnotes"]))
    return 0


def _problem_markdown(inp: "Input", index: int) -> str:
    """题面正文 + 自动生成的「子任务」小节（与 config.yaml 同源）。"""
    md = inp.md_text.rstrip() + "\n"
    table = inp.subtask_table(index)
    if not table:
        return md
    if "子任务" in md:
        # 题面自己（或原题）已经写了子任务相关内容：以题面为准，不重复追加
        return md
    return md + "\n## 子任务\n\n本题共 " + inp.testcase + " 个测试点，按测试点计分：\n\n" \
        + table + "\n每个测试点单独评分，全部测试点的得分之和即为本题得分。\n"


def cmd_build(args) -> int:
    if getattr(args, "contest", None):
        return build_contest(args)

    inp = load_input(args)
    errors, warnings = cnoi_md.check(inp.md_text)
    if report(errors, warnings, args.strict):
        return 1

    out_dir = Path(args.out)
    typst_dir = out_dir / "typst"
    if typst_dir.exists() and not args.keep:
        shutil.rmtree(str(typst_dir))
    typst_dir.mkdir(parents=True, exist_ok=True)

    # 1) 模板 + content.json + markdown
    stage_template(typst_dir)
    write_text(typst_dir / "content.json",
               json.dumps(build_content(inp), ensure_ascii=False, indent=2) + "\n")
    write_text(typst_dir / "problem-0.md", inp.md_text)
    write_text(typst_dir / "extra-precaution.md", inp.precaution)
    write_text(typst_dir / "problem-0.typ", cnoi_md.render(_problem_markdown(inp, 0)))
    write_text(typst_dir / "extra-precaution.typ", _precaution_typst(inp.precaution))
    log("Typst 工程：%s" % typst_dir)

    if args.no_compile:
        log("已跳过编译（--no-compile）")
        return 0

    # 2) PDF
    runner = make_typst(args.verbose, typst_dir, args.resource_dir)
    if args.verbose:
        log("Typst：%s" % runner.version())
    pdf = out_dir / "statement.pdf"
    runner.pdf(typst_dir / "main.typ", pdf)
    pages = runner.page_count(pdf)
    log("PDF：%s（%d 页，%.1f KiB）" % (pdf, pages, pdf.stat().st_size / 1024.0))

    # 3) PNG 预览
    if args.preview:
        png_dir = out_dir / "preview"
        made = runner.pages_png(typst_dir / "main.typ", png_dir, ppi=args.ppi,
                                first=args.pages_from, last=args.pages_to,
                                count=pages)
        log("预览：%s（%d 张，ppi=%d）" % (png_dir, len(made), args.ppi))
        for p in made:
            log("  %s" % p.name)
    return 0


def build_contest(args) -> int:
    """把一整场比赛（多道题）出成一份 CNOI 题面 PDF。"""
    cfg = load_contest(args.contest)
    entries = contest_entries(cfg)
    inputs = [input_from_problem(folder, args, cfg) for folder, _pos in entries]

    bad = 0
    for inp in inputs:
        errors, warnings = cnoi_md.check(inp.md_text)
        for w in warnings:
            warn("%s：%s" % (inp.name, w))
        for e in errors:
            print("[error] %s：%s" % (inp.name, e), file=sys.stderr)
        bad += len(errors)
    if bad:
        print("[error] 有 %d 处题面错误，已中止" % bad, file=sys.stderr)
        return 1

    out_dir = Path(args.out)
    typst_dir = out_dir / "typst"
    if typst_dir.exists() and not args.keep:
        shutil.rmtree(str(typst_dir))
    typst_dir.mkdir(parents=True, exist_ok=True)

    stage_template(typst_dir)
    write_text(typst_dir / "content.json",
               json.dumps(build_content(inputs[0], inputs[1:]),
                          ensure_ascii=False, indent=2) + "\n")
    for k, inp in enumerate(inputs):
        md = _problem_markdown(inp, k)
        write_text(typst_dir / ("problem-%d.md" % k), md)
        write_text(typst_dir / ("problem-%d.typ" % k), cnoi_md.render(md))
    write_text(typst_dir / "extra-precaution.md", inputs[0].precaution)
    write_text(typst_dir / "extra-precaution.typ",
               _precaution_typst(inputs[0].precaution))
    log("比赛：%s（%s），共 %d 题" % (args.contest, inputs[0].title, len(inputs)))
    log("Typst 工程：%s" % typst_dir)

    if args.no_compile:
        log("已跳过编译（--no-compile）")
        return 0

    runner = make_typst(args.verbose, typst_dir, args.resource_dir)
    pdf = out_dir / "statement.pdf"
    runner.pdf(typst_dir / "main.typ", pdf)
    pages = runner.page_count(pdf)
    log("PDF：%s（%d 页，%.1f KiB）" % (pdf, pages, pdf.stat().st_size / 1024.0))
    if args.preview:
        png_dir = out_dir / "preview"
        made = runner.pages_png(typst_dir / "main.typ", png_dir, ppi=args.ppi,
                                first=args.pages_from, last=args.pages_to, count=pages)
        log("预览：%s（%d 张）" % (png_dir, len(made)))
    return 0


def _precaution_typst(text: str) -> str:
    """注意事项单独渲染成 Typst。

    走与题面正文同一套渲染器（`md.render`），列表才能拿到正确的项目符号排版；
    早先这里手写 `#par[• ...]`，会把有序列表也画成实心点。
    """
    return cnoi_md.render(text, with_header_import=False)


# ---------------------------------------------------------------- CLI

def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="cnoi.py",
        description="CNOI 题面工具：Markdown -> Typst -> PDF（Python 版生成器）",
        epilog="详见 docs/statement.md",
    )
    sub = ap.add_subparsers(dest="command", required=True)

    def common(p):
        p.add_argument("markdown", nargs="?", help="题面 Markdown 文件")
        p.add_argument("--problem", help="题目编号（读 problems/<pid>/ 下的题面与元信息）")
        p.add_argument("--contest", help="比赛编号（读 contests/<id>.yaml，出整场题面 PDF）")
        p.add_argument("--out", "-o", required=True, help="输出目录")
        p.add_argument("--title", help="覆盖封面标题")
        p.add_argument("--name", help="覆盖英文短名")
        p.add_argument("--subtitle", help="封面副标题")
        p.add_argument("--day", help="封面场次（如“提高组”）")
        p.add_argument("--resource-dir", default=str(RESOURCES),
                       help="题面里相对路径引用的资源根目录（默认 resources/）")
        p.add_argument("--strict", action="store_true",
                       help="把校验警告也当作错误")
        p.add_argument("--verbose", "-v", action="store_true", help="打印实际执行的命令")

    p = sub.add_parser("convert", help="Markdown -> Typst 源码")
    common(p)
    p.add_argument("--content-json", action="store_true",
                   help="同时写出 content.json（可导入网页版生成器）")
    p.add_argument("--roundtrip", action="store_true",
                   help="额外写一份 Typst 回写成 Markdown 的结果，便于核对")
    p.set_defaults(func=cmd_convert)

    p = sub.add_parser("build", help="Markdown -> Typst -> PDF")
    common(p)
    p.add_argument("--no-compile", action="store_true", help="只生成 Typst 工程")
    p.add_argument("--preview", action="store_true", help="额外渲染 PNG 预览")
    p.add_argument("--ppi", type=int, default=110, help="预览分辨率（默认 110）")
    p.add_argument("--pages-from", type=int, help="预览起始页（从 1 开始）")
    p.add_argument("--pages-to", type=int, help="预览结束页")
    p.add_argument("--keep", action="store_true", help="保留上一次的 Typst 工程目录")
    p.set_defaults(func=cmd_build)

    p = sub.add_parser("check", help="只校验 Markdown 方言")
    common(p)
    p.set_defaults(func=cmd_check)

    p = sub.add_parser("info", help="打印文档树统计")
    common(p)
    p.set_defaults(func=cmd_info)
    return ap


def main(argv=None) -> int:
    ap = build_parser()
    args = ap.parse_args(argv)
    if not args.problem and not args.markdown and not getattr(args, "contest", None):
        ap.error("请给出 Markdown 文件，或用 --problem <pid> / --contest <id>")
    try:
        return args.func(args)
    except cnoi_md.CnoiError as e:
        print("[error] %s" % e, file=sys.stderr)
        return 2
    except cnoi_typst.TypstError as e:
        print("[error] %s" % e, file=sys.stderr)
        return 3


if __name__ == "__main__":
    sys.exit(main())
