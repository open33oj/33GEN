#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CNOI 题面 Markdown 的解析与 Typst 渲染（纯标准库）。

这是 cnoi-statement-generator 里 remarkTypst 编译器在 Python 侧的对应实现：

    Markdown --parse()--> 文档树 --to_typst()--> Typst 源码

对照关系（上游 `src/compiler/remarkTypst/compiler.ts`）：

    paragraph -> #par[...]              heading -> #heading(depth: n, [...])
    code      -> #raw(block: true, ...) inlineCode -> #raw(block: false, ...)
    emphasis  -> #emph[...]             strong -> #strong[...]
    delete    -> #strike[...]           blockquote -> #quote(block: true)[...]
    list      -> #list([...],)          enum -> #enum(start: n, [...]),
    link      -> #link("url", [...])    image -> #box(image("...", ...))
    math      -> #mi(block: true, ...)  inlineMath -> #mi(block: false, ...)
    table     -> #figure(table(...))    thematicBreak -> #thematic-break
    footnote  -> #footnote[label(...)]  figure 容器 -> #figure(caption: ...)[...]

上游用 mdast，这里用一个等价的轻量文档树（dict，键 `type` + 自有字段）。
支持范围见 README；不支持的结构会给出**明确报错**，而不是静默产出坏 Typst。
"""

from __future__ import annotations

import re

__all__ = [
    "CnoiError", "CnoiWarning", "parse", "to_typst", "typst_to_markdown",
    "render", "check", "ast_summary", "TYPST_VALUE_RE",
]

# ---------------------------------------------------------------- 常量与正则

# 图片尺寸只接受相对单位（与上游 TYPST_RELATIVE_VALUE_REGEX 等价）
TYPST_VALUE_RE = re.compile(
    r"^(?: *[+-]? *(?:\d+(?:\.\d+)?|\.\d+)(?:pt|mm|cm|in|em|%))"
    r"(?: *[+-] *(?:\d+(?:\.\d+)?|\.\d+)(?:pt|mm|cm|in|em|%))* *$"
)

# Typst 0.14 在 #par[...] 正文里必须转义的字符（见 docs/statement.md §4）
# 特别注意 @：`CPU @3.70GHz` 会被当成引用而报 "label <3.70GHz> does not exist"。
RE_ESCAPE = re.compile(r"([\\#`$@])")

# 上游 cnoi 模板的硬限制：代码块里单个"词"不得超过 63 列
MAX_CODE_WIDTH = 63

RE_FENCE = re.compile(r"^(\s*)(`{3,}|~{3,})\s*([^`]*?)\s*$")
RE_HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
RE_THEMATIC = re.compile(r"^\s*(?:-{3,}|\*{3,}|_{3,})\s*$")
RE_TABLE_ROW = re.compile(r"^\s*\|.*\|\s*$")
RE_SEP_CELL = re.compile(r"^:?-{2,}:?$")
RE_LIST_ITEM = re.compile(r"^(\s*)([-*+]|\d{1,9}[.)])\s+(.*)$")
RE_BLOCKQUOTE = re.compile(r"^\s*>\s?(.*)$")
RE_DIRECTIVE_OPEN = re.compile(r"^\s*:::\s*([a-zA-Z][\w-]*)\s*(\{[^}]*\})?\s*$")
RE_DIRECTIVE_CLOSE = re.compile(r"^\s*:::\s*$")
RE_FOOTNOTE_DEF = re.compile(r"^\[\^([^\]]+)\]:\s*(.*)$")
RE_FOOTNOTE_REF = re.compile(r"\[\^([^\]]+)\]")

RE_CODE_SPAN = re.compile(r"(`+)(.+?)\1", re.S)
RE_MATH_BLOCK = re.compile(r"\$\$(.+?)\$\$", re.S)
RE_MATH_INLINE = re.compile(r"\$([^$\n]+?)\$")
RE_IMAGE = re.compile(r"!\[([^\]]*)\]\(([^)\s]*)\)(\{[^}\n]*\})?")
RE_LINK = re.compile(r"\[([^\]]*)\]\(([^)\s]*)\)")
RE_STRONG = re.compile(r"\*\*(?=\S)(.+?)(?<=\S)\*\*", re.S)
RE_EMPH = re.compile(r"(?<!\*)\*(?=\S)([^*]+?)(?<=\S)\*(?!\*)", re.S)
RE_DELETE = re.compile(r"~~(?=\S)(.+?)(?<=\S)~~", re.S)

MAX_LIST_DEPTH = 3


# ---------------------------------------------------------------- 异常

class CnoiError(Exception):
    """解析/渲染失败。带行号与提示，给命令行直接展示。"""

    def __init__(self, message: str, line: int = 0, hint: str = ""):
        self.message = message
        self.line = line
        self.hint = hint
        super().__init__(message)

    def __str__(self) -> str:
        loc = "第 %d 行" % self.line if self.line else "文档"
        text = "%s：%s" % (loc, self.message)
        if self.hint:
            text += "\n  提示：%s" % self.hint
        return text


class CnoiWarning(object):
    def __init__(self, message: str, line: int = 0, hint: str = ""):
        self.message = message
        self.line = line
        self.hint = hint

    def __str__(self) -> str:
        loc = "第 %d 行" % self.line if self.line else "文档"
        text = "%s：%s" % (loc, self.message)
        if self.hint:
            text += "（%s）" % self.hint
        return text


# ---------------------------------------------------------------- 文档树小工具

def _node(type_: str, **kw) -> dict:
    node = {"type": type_}
    node.update(kw)
    return node


def _text(value: str) -> dict:
    return _node("text", value=value)


def _walk(nodes):
    """深度优先遍历文档树，只产出节点（dict），跳过 list 之类的容器。"""
    for n in nodes:
        if not isinstance(n, dict):
            continue
        yield n
        for child in n.get("children") or []:
            for x in _walk([child]):
                yield x


# ---------------------------------------------------------------- 解析：块级

def parse(md: str) -> dict:
    """把 Markdown 解析成文档树（mdast 的等价轻量表示）。"""
    lines = md.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    footnotes = {}
    blocks = _parse_blocks(lines, 0, len(lines), footnotes, depth=0)
    return _node("root", children=blocks, footnotes=footnotes)


def _parse_blocks(lines, start, end, footnotes, depth):
    nodes = []
    i = start
    while i < end:
        raw = lines[i]

        # 脚注定义（块级，先摘出去）
        m = RE_FOOTNOTE_DEF.match(raw)
        if m:
            label = m.group(1).strip()
            body = [m.group(2)]
            i += 1
            while i < end and lines[i].strip() and not _starts_block(lines, i):
                body.append(lines[i].strip())
                i += 1
            footnotes[label] = " ".join(x for x in body if x)
            continue

        # 围栏代码块
        m = RE_FENCE.match(raw)
        if m:
            fence, info = m.group(2), m.group(3)
            close_re = re.compile(r"^\s*%s{%d,}\s*$"
                                  % (re.escape(fence[0]), len(fence)))
            body = []
            i += 1
            closed = False
            while i < end:
                if close_re.match(lines[i]):
                    closed = True
                    i += 1
                    break
                body.append(lines[i])
                i += 1
            if not closed:
                raise CnoiError("代码块没有闭合（缺少结尾的 %s）" % fence, i,
                                "检查是否漏写了结束围栏")
            nodes.append(_node("code", lang=info or "", value="\n".join(body),
                               line=i - len(body) - 1))
            continue

        # 空行
        if not raw.strip():
            i += 1
            continue

        # 标题
        m = RE_HEADING.match(raw)
        if m:
            nodes.append(_node("heading", depth=len(m.group(1)),
                               children=_parse_inlines(m.group(2), i + 1), line=i + 1))
            i += 1
            continue

        # 分隔线
        if RE_THEMATIC.match(raw):
            nodes.append(_node("thematicBreak", line=i + 1))
            i += 1
            continue

        # 表格
        if RE_TABLE_ROW.match(raw) and i + 1 < end and _is_sep_row(lines[i + 1]):
            j = i + 2
            while j < end and RE_TABLE_ROW.match(lines[j]):
                j += 1
            nodes.append(_parse_table(lines[i:j], i + 1))
            i = j
            continue

        # ::: 容器指令
        m = RE_DIRECTIVE_OPEN.match(raw)
        if m:
            name, attrs = m.group(1), _parse_attrs(m.group(2) or "")
            i += 1
            body = []
            closed = False
            while i < end:
                if RE_DIRECTIVE_CLOSE.match(lines[i]):
                    closed = True
                    i += 1
                    break
                body.append(lines[i])
                i += 1
            if not closed:
                raise CnoiError("容器指令 ::: %s 没有闭合" % name, i,
                                "补一行单独的 ::: 作为结束")
            children = _parse_blocks(body, 0, len(body), footnotes, depth + 1)
            nodes.append(_node("container", name=name, attributes=attrs,
                               children=children, line=i))
            continue

        # 引用块
        m = RE_BLOCKQUOTE.match(raw)
        if m:
            body = []
            while i < end:
                bm = RE_BLOCKQUOTE.match(lines[i])
                if bm:
                    body.append(bm.group(1))
                    i += 1
                elif lines[i].strip() == "":
                    break
                else:
                    break
            nodes.append(_node("blockquote", line=i,
                               children=_parse_blocks(body, 0, len(body),
                                                      footnotes, depth + 1)))
            continue

        # 列表
        m = RE_LIST_ITEM.match(raw)
        if m:
            items, ordered, i = _parse_list(lines, i, end, footnotes, depth)
            nodes.append(_node("list", ordered=ordered, children=items))
            continue

        # 段落（连续非空行直到下一个块起始）
        buf = [raw.strip()]
        i += 1
        while i < end and lines[i].strip() and not _starts_block(lines, i):
            buf.append(lines[i].strip())
            i += 1
        nodes.append(_node("paragraph", children=_parse_inlines(" ".join(buf), i),
                           line=i - len(buf) + 1))
    return nodes


def _starts_block(lines, i) -> bool:
    line = lines[i]
    if not line.strip():
        return True
    if RE_FENCE.match(line) or RE_HEADING.match(line) or RE_THEMATIC.match(line):
        return True
    if RE_DIRECTIVE_OPEN.match(line) or RE_BLOCKQUOTE.match(line):
        return True
    if RE_LIST_ITEM.match(line) or RE_FOOTNOTE_DEF.match(line):
        return True
    if RE_TABLE_ROW.match(line) and i + 1 < len(lines) and _is_sep_row(lines[i + 1]):
        return True
    return False


def _parse_list(lines, i, end, footnotes, depth):
    """解析一个列表；返回 (items, ordered, next_index)。"""
    if depth > MAX_LIST_DEPTH:
        raise CnoiError("列表嵌套超过 %d 层" % MAX_LIST_DEPTH, i + 1,
                        "题面里的多层列表本来就难读，建议改成小标题或拆段")
    first = RE_LIST_ITEM.match(lines[i])
    ordered = first.group(2)[0].isdigit()
    base_indent = len(first.group(1))
    start = int(re.match(r"\d+", first.group(2)).group()) if ordered else None
    items = []
    cur = None
    loose = False
    while i < end:
        line = lines[i]
        if not line.strip():
            # 空行：可能是松散列表，也可能列表结束
            j = i + 1
            while j < end and not lines[j].strip():
                j += 1
            if j < end and RE_LIST_ITEM.match(lines[j]) and \
                    len(RE_LIST_ITEM.match(lines[j]).group(1)) == base_indent:
                loose = True
                i = j
                continue
            break
        m = RE_LIST_ITEM.match(line)
        if m and len(m.group(1)) == base_indent:
            cur = [m.group(3)]
            items.append(cur)
            i += 1
            continue
        if m and len(m.group(1)) > base_indent:
            # 嵌套子列表：交给 _parse_blocks 处理整段
            if cur is None:
                break
            sub_start = i
            sub_end = i
            while sub_end < end:
                sm = RE_LIST_ITEM.match(lines[sub_end])
                if sm and len(sm.group(1)) == base_indent:
                    break
                if not lines[sub_end].strip():
                    break
                sub_end += 1
            cur.append("\n" + "\n".join(lines[sub_start:sub_end]))
            i = sub_end
            continue
        if len(line) - len(line.lstrip()) > base_indent and cur is not None:
            cur.append(line.strip())          # 续行
            i += 1
            continue
        break

    nodes = []
    for raw_item in items:
        buf = []
        for chunk in raw_item:
            if chunk.startswith("\n"):
                buf.append(chunk)
            else:
                buf.append(" " + chunk if buf else chunk)
        nodes.append(_parse_blocks("".join(buf).split("\n"), 0,
                                   len("".join(buf).split("\n")), footnotes, depth + 1))
    return nodes, ordered, i


def _is_sep_row(line: str) -> bool:
    cells = _split_row(line)
    return bool(cells) and all(RE_SEP_CELL.match(c) for c in cells)


def _split_row(line: str):
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return [c.strip() for c in s.split("|")]


def _parse_table(lines, start_line) -> dict:
    header = [_parse_inlines(c, start_line) for c in _split_row(lines[0])]
    align = []
    for c in _split_row(lines[1]):
        if c.startswith(":") and c.endswith(":"):
            align.append("center")
        elif c.endswith(":"):
            align.append("right")
        elif c.startswith(":"):
            align.append("left")
        else:
            align.append("none")
    rows = [[_parse_inlines(c, start_line + k) for c in _split_row(l)]
            for k, l in enumerate(lines[2:], start=2)]
    ncol = max([len(header)] + [len(r) for r in rows]) if rows else len(header)
    align += ["none"] * (ncol - len(align))

    # 合并：^ 向上 rowspan，< 向左 colspan（先算 colspan 再算 rowspan）
    grid = [header] + rows
    source = [[_cell_source(grid[r][c]) if c < len(grid[r]) else "" for c in range(ncol)]
              for r in range(len(grid))]
    colspan = [[1] * ncol for _ in grid]
    rowspan = [[1] * ncol for _ in grid]
    removed = [[False] * ncol for _ in grid]
    for r in range(len(grid)):
        for c in range(ncol - 1, -1, -1):
            if source[r][c] == "<" and c > 0:
                removed[r][c] = True
                k = c - 1
                while k >= 0 and removed[r][k]:
                    k -= 1
                if k >= 0:
                    colspan[r][k] += colspan[r][c]
    for r in range(len(grid) - 1, -1, -1):
        for c in range(ncol):
            if removed[r][c]:
                continue
            if source[r][c] == "^" and r > 0:
                removed[r][c] = True
                k = r - 1
                while k >= 0 and removed[k][c]:
                    k -= 1
                if k >= 0:
                    rowspan[k][c] += rowspan[r][c]
    return _node("table", align=align, colspan=colspan, rowspan=rowspan,
                 removed=removed, rows=grid, line=start_line)


def _cell_source(cell):
    """单元格是否为合并标记（`^` / `<`）：要求整格只有一个文本节点。"""
    if len(cell) == 1 and cell[0]["type"] == "text":
        return cell[0]["value"].strip()
    return ""


def _parse_attrs(raw: str) -> dict:
    """解析 `{caption="...", width=50%}` 这类属性串。"""
    attrs = {}
    if not raw:
        return attrs
    body = raw.strip().lstrip("{").rstrip("}")
    for part in re.split(r",(?![^\"']*[\"'][^\"']*$)", body):
        if "=" not in part:
            key = part.strip()
            if key:
                attrs[key] = ""
            continue
        k, v = part.split("=", 1)
        attrs[k.strip()] = v.strip().strip("\"'")
    return attrs


# ---------------------------------------------------------------- 解析：行内

def _parse_inlines(text: str, line: int = 0, slots: list = None):
    """把一段行内 Markdown 解析成节点列表。

    `slots` 在递归解析（粗体/斜体/链接里的内容）时共用同一份：外层先抽出来的
    行内数学/代码会用 `\\x00k\\x00` 占位，如果内层换一份新的 slots，就会去查
    一个不存在的下标（`**乘 $2$**` 这类写法曾因此抛 IndexError）。
    """
    if text == "":
        return []
    if slots is None:
        slots = []

    def hold(node):
        slots.append(node)
        return "\x00%d\x00" % (len(slots) - 1)

    # 1. 行内代码（反引号数量要匹配）
    text = RE_CODE_SPAN.sub(lambda m: hold(_node("inlineCode", value=m.group(2))), text)
    # 2. 行间数学 -> 3. 行内数学
    text = RE_MATH_BLOCK.sub(lambda m: hold(_node("math", value=m.group(1))), text)
    text = RE_MATH_INLINE.sub(lambda m: hold(_node("inlineMath", value=m.group(1))), text)
    # 4. 图片（可带 {width=..}）
    text = RE_IMAGE.sub(lambda m: hold(_node(
        "image", alt=m.group(1), url=m.group(2), attr=_parse_attrs(m.group(3) or ""))), text)
    # 5. 链接
    text = RE_LINK.sub(lambda m: hold(_node(
        "link", url=m.group(2), children=_parse_inlines(m.group(1), line, slots))), text)
    # 6. 粗体 / 斜体 / 删除线
    text = RE_STRONG.sub(lambda m: hold(_node(
        "strong", children=_parse_inlines(m.group(1), line, slots))), text)
    text = RE_DELETE.sub(lambda m: hold(_node(
        "delete", children=_parse_inlines(m.group(1), line, slots))), text)
    text = RE_EMPH.sub(lambda m: hold(_node(
        "emph", children=_parse_inlines(m.group(1), line, slots))), text)
    # 7. 脚注引用
    text = RE_FOOTNOTE_REF.sub(lambda m: hold(_node("footnoteRef", label=m.group(1).strip())), text)

    out = []
    pos = 0
    for m in re.finditer(r"\x00(\d+)\x00", text):
        if m.start() > pos:
            out.append(_text(text[pos:m.start()]))
        out.append(slots[int(m.group(1))])
        pos = m.end()
    if pos < len(text):
        out.append(_text(text[pos:]))
    return out


# ---------------------------------------------------------------- 渲染：Typst

def escape_typst_string(s: str) -> str:
    """Typst 字符串字面量的转义（对应上游 escapeTypstString）。"""
    return (s.replace("\\", "\\\\").replace('"', '\\"')
            .replace("\n", "\\n").replace("\t", "\\t").replace("\r", "\\r"))


def escape_typst_text(s: str) -> str:
    """Typst 正文的转义；见 docs/statement.md §4 的实测清单。"""
    return RE_ESCAPE.sub(r"\\\1", s)


_ALIGN_TYPST = {
    "none": "center + horizon",
    "center": "center + horizon",
    "left": "left + horizon",
    "right": "right + horizon",
}


def to_typst(doc: dict, *, with_header_import: bool = True) -> str:
    """把文档树渲染成 Typst 源码。"""
    out = []
    if with_header_import:
        out.append('#import "header.typ": *')
        out.append("")
    for node in doc.get("children") or []:
        _render_block(node, out)
    refs = {n["label"] for n in _walk(doc.get("children") or [])
            if n["type"] == "footnoteRef"}
    footnotes = doc.get("footnotes") or {}
    used = [(k, v) for k, v in footnotes.items() if k in refs]
    if used:
        out.append("#hide(place(top+left, [")
        for label, value in used:
            out.append('#footnote[%s]#label("user-footnote: %s")'
                       % (_render_inline_nodes(_parse_inlines(value)), escape_typst_string(label)))
        out.append("]))")
    return "\n".join(out).rstrip("\n") + "\n"


def _render_block(node, out) -> None:
    t = node["type"]
    if t == "paragraph":
        _emit_paragraph(node["children"], out)
    elif t == "heading":
        out.append("#heading(depth: %d, [%s])"
                   % (node["depth"], _render_inline_nodes(node["children"])))
        out.append("")
    elif t == "code":
        lang = node["lang"] or "txt"
        lang = {"plain": "txt", "markdown": "md"}.get(lang, lang)
        out.append('#raw(block: true, lang: "%s", "%s")'
                   % (lang, escape_typst_string(node["value"])))
        out.append("")
    elif t == "thematicBreak":
        out.append("#thematic-break")
        out.append("")
    elif t == "blockquote":
        out.append("#quote(block: true)[")
        for child in node["children"]:
            _render_block(child, out)
        out.append("]")
        out.append("")
    elif t == "list":
        head = "#enum(" + ("start: %d," % node["start"] if node.get("start") else "") \
            if node["ordered"] else "#list("
        out.append(head)
        for item in node["children"]:
            out.append("[%s]," % _render_list_item(item))
        out.append(")")
        out.append("")
    elif t == "table":
        out.append(_render_table(node))
        out.append("")
    elif t == "container":
        if node["name"] == "figure":
            cap = node["attributes"].get("caption")
            head = '#figure(caption: "%s", ' % escape_typst_string(cap) if cap else "#figure("
            out.append(head + "[")
            for child in node["children"]:
                _render_block(child, out)
            out.append("])")
            out.append("")
        else:
            # 未知容器：内容照常渲染，不报错（与上游 fallback 行为一致）
            for child in node["children"]:
                _render_block(child, out)
    else:  # pragma: no cover - 解析器不会产出其它类型
        raise CnoiError("无法渲染的块类型：%s" % t)


# 行间公式的占位标记：先当行内内容放进 #par[...]，再在渲染段落时提升为独立块。
_DISPLAY_MATH = "\x01DM%s\x01"


def _emit_paragraph(nodes, out) -> None:
    """渲染一个段落；如果里面有行间公式，就把段落按公式切开。

    Typst 不允许 `math.equation(block: true)` 出现在段落内部
    （`#par[#mi(block: true, ...)]` 会被忽略并给出警告），所以行间公式必须
    作为独立的顶层内容输出。这里把段落拆成 [文本段, 公式, 文本段, ...] 依次输出。
    """
    buf = []            # 当前累积的行内节点
    pending = []        # 待输出的 (kind, payload)

    def flush():
        if buf:
            pending.append(("par", _render_inline_nodes(list(buf))))
            del buf[:]

    for n in nodes:
        if n["type"] == "math":
            flush()
            pending.append(("math", n["value"]))
        else:
            buf.append(n)
    flush()

    # 只有一个公式、没有文字：直接输出块级公式，不套 #par
    if len(pending) == 1 and pending[0][0] == "math":
        out.append('#mi(block: true, "%s")' % escape_typst_string(pending[0][1]))
        out.append("")
        return

    for kind, payload in pending:
        if kind == "math":
            out.append('#mi(block: true, "%s")' % escape_typst_string(payload))
        else:
            out.append("#par[%s]" % payload)
        out.append("")


def _render_list_item(item) -> str:
    """渲染一个列表项。

    **列表项的正文必须是行内内容，不能是 `#par[...]`。**
    CNOI 模板重写了 `show list`：它把项目符号与 `it.body` 拼成一个段落来排
    （见 resources/cnoi/typst/main.typ 的 correctly-indent-list-and-enum-items）。
    一旦 body 里出现块级段落 `#par[...]`，符号就会自己占一行、正文另起一行缩进
    ——这就是"实心点排版错位"的原因。
    """
    parts = []
    for child in item:
        if child["type"] == "paragraph":
            parts.append(_render_item_paragraph(child["children"]))
        else:
            sub = []
            _render_block(child, sub)
            parts.append("\n".join(sub).strip())
    return "\n\n".join(p for p in parts if p)


def _render_item_paragraph(nodes) -> str:
    """列表项里的段落 -> 行内内容；行间公式降级为块级公式（列表项里允许块级内容）。"""
    chunks = []
    for n in nodes:
        if n["type"] == "math":
            chunks.append('#mi(block: true, "%s")' % escape_typst_string(n["value"]))
        else:
            chunks.append(_render_inline_nodes([n]))
    return "".join(chunks)


def _render_table(node) -> str:
    cols = len(node["align"])
    out = ["#figure(table(",
           "  columns: %d," % cols,
           "  align: (%s)," % ", ".join(_ALIGN_TYPST[a] for a in node["align"])]
    for r, row in enumerate(node["rows"]):
        for c in range(cols):
            if node["removed"][r][c]:
                continue
            opts = ""
            if node["colspan"][r][c] > 1:
                opts += "colspan: %d, " % node["colspan"][r][c]
            if node["rowspan"][r][c] > 1:
                opts += "rowspan: %d, " % node["rowspan"][r][c]
            cell = row[c] if c < len(row) else []
            out.append("  table.cell(%s)[%s]," % (opts, _render_inline_nodes(cell)))
        out.append("  ")
    out.append("))")
    return "\n".join(out)


def _render_inline_nodes(nodes) -> str:
    parts = []
    for n in nodes:
        t = n["type"]
        if t == "text":
            parts.append(escape_typst_text(n["value"]))
        elif t == "inlineCode":
            parts.append('#raw(block: false, lang: "txt", "%s")'
                         % escape_typst_string(n["value"]))
        elif t == "math":
            # 行间公式不应该走到这里：_emit_paragraph 会在渲染段落前把它挑出来，
            # 作为独立的块级公式输出（放进 #par[...] 会被 Typst 忽略）。
            raise CnoiError("行间公式必须由 _emit_paragraph 处理")
        elif t == "inlineMath":
            parts.append('#mi(block: false, "%s")' % escape_typst_string(n["value"]))
        elif t == "image":
            opts = ""
            for key in ("width", "height"):
                val = (n["attr"] or {}).get(key)
                if isinstance(val, str) and TYPST_VALUE_RE.match(val):
                    opts += ", %s: %s" % (key, val)
            alt = n.get("alt") or ""
            if alt:
                opts += ', alt: "%s"' % escape_typst_string(alt)
            parts.append('#box(image("%s"%s))' % (escape_typst_string(n["url"]), opts))
        elif t == "link":
            parts.append('#link("%s", [%s])'
                         % (escape_typst_string(n["url"]),
                            _render_inline_nodes(n["children"])))
        elif t == "strong":
            parts.append("#strong[%s]" % _render_inline_nodes(n["children"]))
        elif t == "emph":
            parts.append("#emph[%s]" % _render_inline_nodes(n["children"]))
        elif t == "delete":
            parts.append("#strike[%s]" % _render_inline_nodes(n["children"]))
        elif t == "footnoteRef":
            parts.append('#footnote(label("user-footnote: %s"))'
                         % escape_typst_string(n["label"]))
        else:  # pragma: no cover
            raise CnoiError("无法渲染的行内类型：%s" % t)
    return "".join(parts)


# ---------------------------------------------------------------- 渲染：回写 Markdown

# 回写用的块识别标签（用单字符标记，避免和 `#` 前缀混淆）
_TAG_PAR = "P"
_TAG_HEAD = "H"
_TAG_CODE = "C"
_TAG_RAW = "R"
_TAG_QUOTE = "Q"
_TAG_LIST = "L"
_TAG_ENUM = "E"
_TAG_FIGURE = "F"
_TAG_TABLE = "B"
_TAG_HIDE = "X"
_TAG_FOOTNOTE = "N"


def _split_inline_tokens(s: str):
    """把行内 Typst 拆成 (前缀, 文本, 后缀) 三段；不匹配时返回 None。"""
    for pat in (
        (r'^#raw\(block: false, lang: "txt", "', r'"\)$'),
        (r'^#mi\(block: true, "', r'"\)$'),
        (r'^#mi\(block: false, "', r'"\)$'),
        (r'^#strong\[', r'\]$'),
        (r'^#emph\[', r'\]$'),
        (r'^#strike\[', r'\]$'),
    ):
        m = re.match(pat[0], s)
        if m and re.search(pat[1], s):
            end = re.search(pat[1], s)
            return m.end(), s[m.end():end.start()], pat[0]
    return None


def _restore_inlines(s: str) -> str:
    """把一行 Typst 行内结构换回 Markdown（#raw/#mi/#strong/#emph/#strike/图片/链接）。"""
    s = _restore_matched(s)
    s = re.sub(r'#raw\(block: false, lang: "txt", "((?:[^"\\]|\\.)*)"\)',
               lambda m: "`%s`" % _unescape(m.group(1)), s)
    s = re.sub(r'#mi\(block: true, "((?:[^"\\]|\\.)*)"\)',
               lambda m: "$$%s$$" % _unescape(m.group(1)), s)
    s = re.sub(r'#mi\(block: false, "((?:[^"\\]|\\.)*)"\)',
               lambda m: "$%s$" % _unescape(m.group(1)), s)
    s = re.sub(r'#strong\[(.*?)\]', lambda m: "**%s**" % m.group(1), s)
    s = re.sub(r'#emph\[(.*?)\]', lambda m: "*%s*" % m.group(1), s)
    s = re.sub(r'#strike\[(.*?)\]', lambda m: "~~%s~~" % m.group(1), s)
    s = re.sub(r'#box\(image\("((?:[^"\\]|\\.)*)"[^)]*\)\)',
               lambda m: "![%s](%s)" % (_img_alt(m.group(0)), _unescape(m.group(1))), s)
    s = re.sub(r'#link\("((?:[^"\\]|\\.)*)", \[(.*?)\]\)',
               lambda m: "[%s](%s)" % (m.group(2), _unescape(m.group(1))), s)
    s = re.sub(r'#footnote\(label\("user-footnote: ((?:[^"\\]|\\.)*)"\)\)',
               lambda m: "[^%s]" % _unescape(m.group(1)), s)
    s = re.sub(r"\\([\\#`$@])", r"\1", s)
    return s


def _img_alt(full: str) -> str:
    m = re.search(r'alt: "((?:[^"\\]|\\.)*)"', full)
    return _unescape(m.group(1)) if m else ""


def _restore_matched(s: str) -> str:
    """处理嵌套的 #strong[...] / #emph[...]，从最内层开始替换。"""
    while True:
        m = re.search(r"#(strong|emph|strike)\[([^\[\]]*)\]", s)
        if not m:
            return s
        kind, body = m.group(1), m.group(2)
        mark = {"strong": "**%s**", "emph": "*%s*", "strike": "~~%s~~"}[kind]
        s = s[:m.start()] + (mark % body) + s[m.end():]


def typst_to_markdown(typst: str, *, title: str = "", problemtitle: str = "") -> str:
    """把 to_typst() 的产物转回 Markdown（用于导出上游生成器的 Markdown 源）。

    只处理 to_typst() 会产出的结构；模板指令（#import / #set / #show …）
    与 `extra-precaution` 之类的 include 会被跳过。
    """
    out = []
    i = 0

    def push_block(md_text, blank=True):
        if md_text is None:
            return
        if blank and out and out[-1] != "":
            out.append("")
        out.append(md_text)
        if blank:
            out.append("")

    def take_balanced(start, opener, closer):
        """从 start 处读入配平的一段，返回 (内容, 结束位置)。"""
        depth = 0
        j = start
        while j < len(typst):
            c = typst[j]
            if c == '"':                      # 跳过字符串
                j += 1
                while j < len(typst) and typst[j] != '"':
                    j += 2 if typst[j] == "\\" else 1
                j += 1
                continue
            if c == opener:
                depth += 1
            elif c == closer:
                depth -= 1
                if depth == 0:
                    return typst[start + 1:j], j + 1
            j += 1
        raise CnoiError("回写失败：括号不配平")

    while i < len(typst):
        rest = typst[i:]
        if rest.startswith("#par["):
            body, i = take_balanced(i + len("#par"), "[", "]")
            push_block(_restore_inlines(body))
            continue
        m = re.match(r'#heading\(depth: (\d), \[', rest)
        if m:
            body, i = take_balanced(i + m.end() - 1, "[", "]")
            push_block("#" * int(m.group(1)) + " " + _restore_inlines(body))
            continue
        if rest.startswith("#thematic-break"):
            i += len("#thematic-break")
            push_block("---")
            continue
        m = re.match(r'#raw\(block: true, lang: "([^"]*)", "', rest)
        if m:
            j = i + m.end()
            buf = []
            while j < len(typst):
                if typst[j] == "\\":
                    buf.append(typst[j:j + 2])
                    j += 2
                    continue
                if typst[j] == '"':
                    break
                buf.append(typst[j])
                j += 1
            j += 1
            if j < len(typst) and typst[j] == ")":
                j += 1
            while j < len(typst) and typst[j] == "\n":
                j += 1
            lang = {"txt": "", "md": "markdown"}.get(m.group(1), m.group(1))
            push_block("```%s\n%s\n```" % (lang, _unescape("".join(buf))))
            i = j
            continue
        if rest.startswith("#quote(block: true)["):
            body, i = take_balanced(i + len("#quote(block: true)"), "[", "]")
            inner = typst_to_markdown(body)
            push_block("\n".join("> " + l if l else ">" for l in inner.split("\n")).rstrip())
            continue
        if rest.startswith("#hide("):
            # 脚注定义块：整段跳过
            depth, j = 0, i
            while j < len(typst):
                if typst[j] == "(":
                    depth += 1
                elif typst[j] == ")":
                    depth -= 1
                    if depth == 0:
                        break
                j += 1
            i = j + 1
            continue
        m = re.match(r"#figure\(table\(", rest)
        if m:
            body, i = take_balanced(i + len("#figure("), "(", ")")
            push_block(_table_to_markdown(body))
            continue
        m = re.match(r'#figure\(caption: "((?:[^"\\]|\\.)*)", \[', rest)
        if m:
            body, i = take_balanced(i + m.end() - 1, "[", "]")
            push_block(':::figure{caption="%s"}\n%s\n:::' % (m.group(1), typst_to_markdown(body)))
            continue
        if rest.startswith("#figure(table"):
            body, i = take_balanced(i + len("#figure("), "(", ")")
            push_block(_table_to_markdown(body))
            continue
        if rest.startswith("#list(") or rest.startswith("#enum("):
            start = re.match(r"#(list|enum)\(", rest)
            ordered = start.group(1) == "enum"
            body, i = take_balanced(i + start.end() - 1, "(", ")")
            items = [x for x in re.findall(r"\[(.*?)\],", body, flags=re.S)]
            lines = []
            for k, item in enumerate(items, start=1):
                content = typst_to_markdown(item).strip().replace("\n", " ")
                lines.append(("%d. " % k if ordered else "- ") + content)
            push_block("\n".join(lines))
            continue
        if rest.startswith("#import") or rest.startswith("#set ") or \
                rest.startswith("#show ") or rest.startswith("#include") or \
                rest.startswith("//"):
            i = typst.find("\n", i)
            i = len(typst) if i < 0 else i + 1
            continue
        # 其它内容（模板代码等）直接跳过一行
        i = typst.find("\n", i)
        i = len(typst) if i < 0 else i + 1

    text = "\n".join(out)
    text = re.sub(r"\n{3,}", "\n\n", text).strip() + "\n"
    if problemtitle and not text.lstrip().startswith("#"):
        text = "# " + problemtitle + "\n\n" + text
    return text


def _table_to_markdown(body: str) -> str:
    """把 table(...) 的内容还原成 Markdown 表格（保留 ^ / < 合并标记）。

    to_typst() 会把 rowspan 单元格只写在首行，后续行根本不产出该格，
    所以这里不能按"每行恰好 cols 个格"来切行，必须按列槽位回填。
    """
    cols = 0
    m = re.search(r"columns:\s*(\d+)", body)
    if m:
        cols = int(m.group(1))
    if cols <= 0:
        return ""
    cells = []
    for opts, content in re.findall(r"table\.cell\(([^)]*)\)\[(.*?)\]", body, flags=re.S):
        cs = re.search(r"colspan:\s*(\d+)", opts)
        rs = re.search(r"rowspan:\s*(\d+)", opts)
        cells.append({"text": _restore_inlines(content).strip(),
                      "cs": int(cs.group(1)) if cs else 1,
                      "rs": int(rs.group(1)) if rs else 1})

    # 按列槽位回填：rowspan 留下的空槽用 ^ 占位
    grid = []
    active = {}                      # 列 -> 还需要的续行数
    idx = 0
    while idx < len(cells):
        row = [None] * cols
        for c in range(cols):
            if active.get(c, 0) > 0:
                row[c] = ("^", 1, 1)
                active[c] -= 1
                if active[c] == 0:
                    del active[c]
                continue
            if idx >= len(cells):
                break
            cell = cells[idx]
            idx += 1
            row[c] = (cell["text"], cell["cs"], cell["rs"])
            if cell["rs"] > 1:
                active[c] = cell["rs"] - 1
            for k in range(1, cell["cs"]):
                if c + k < cols:
                    row[c + k] = ("<", 1, 1)
        grid.append(row)
        if all(x is None for x in row):
            break

    lines = []
    for r, row in enumerate(grid):
        rendered = []
        for c, cell in enumerate(row):
            if cell is None:
                rendered.append(" ")
            elif cell[0] == "^":
                rendered.append("^")
            elif cell[0] == "<":
                rendered.append("<")
            else:
                rendered.append(cell[0])
        lines.append("| " + " | ".join(rendered) + " |")
        if r == 0:
            lines.append("| " + " | ".join(["---"] * cols) + " |")
    return "\n".join(lines)


def _unescape(s: str) -> str:
    return (s.replace("\\n", "\n").replace("\\t", "\t")
            .replace('\\"', '"').replace("\\\\", "\\"))


# ---------------------------------------------------------------- 校验与摘要

def check(md: str) -> tuple:
    """校验题面；返回 (errors, warnings)，元素是 CnoiError / CnoiWarning。

    宁可报错也不要产出坏 PDF，所以这里的检查偏严格。
    """
    errors, warnings = [], []

    # 1. 能否解析
    try:
        doc = parse(md)
    except CnoiError as e:
        return [e], []

    # 2. 代码块宽度（上游硬限制 63 列）
    for n in _walk(doc["children"]):
        if n["type"] == "code":
            for ln, line in enumerate(n["value"].split("\n"), start=1):
                for word in re.split(r"[\s\u200b]", line):
                    if len(word) > MAX_CODE_WIDTH:
                        errors.append(CnoiError(
                            "代码块里有超过 %d 列的长串（约 %d 列）"
                            % (MAX_CODE_WIDTH, len(word)), n.get("line", 0),
                            "为了可读性请把完整代码放进 down/ 下发，不要塞进题面"))
                        break

    # 3. 结构检查
    sections = [n for n in doc["children"] if n["type"] == "heading"]
    if not any(h["depth"] == 2 for h in sections):
        warnings.append(CnoiWarning("题面里没有二级标题（## 题目描述 这类）", 0,
                                    "CNOI 模板只把 ## 渲染成【】小节，一级标题由模板自己输出"))
    if not any(_plain(h) == "题目描述" for h in sections):
        warnings.append(CnoiWarning("没有找到“## 题目描述”小节", 0,
                                    "按 docs/statement.md 的章节顺序书写"))

    # 4. 图片尺寸属性
    for n in _walk(doc["children"]):
        if n["type"] == "image":
            for key, val in (n["attr"] or {}).items():
                if key in ("width", "height") and not TYPST_VALUE_RE.match(val or ""):
                    warnings.append(CnoiWarning(
                        "图片 %s 的 %s=%s 不是相对单位，会被忽略"
                        % (n["url"], key, val), 0,
                        "只支持 pt/mm/cm/in/em/%，例如 width=50%"))

    # 5. 数学定界符是否成对
    body = re.sub(r"```.*?```", "", md, flags=re.S)
    body = re.sub(r"`[^`\n]*`", "", body)
    if body.count("$$") % 2 != 0:
        errors.append(CnoiError("行间数学 $$...$$ 没有成对出现", 0, "检查是否漏写了 $$"))
    stripped = body.replace("$$", "")
    if len(re.findall(r"(?<!\\)\$", stripped)) % 2 != 0:
        warnings.append(CnoiWarning("行内数学 $...$ 的 $ 数量是奇数", 0,
                                    "如果本来就想输出 $ 符号，请写成 \\$"))

    # 5b. 公式被「吃掉 $」：$n$ 会被写成 1n1 这种样子（历史上真出现过）
    eaten = re.search(r"1[a-zA-Z]1", stripped)
    if eaten:
        warnings.append(CnoiWarning(
            "疑似公式被破坏：出现了 %s 这样的写法" % eaten.group(0), 0,
            r"检查是不是 $n$ 这类公式两侧的 $ 被误删了"))

    # 6. HTML（模板不支持，会当 inline code 显示）
    for ln, line in enumerate(md.split("\n"), start=1):
        if re.search(r"</?[a-zA-Z][\w-]*(\s[^>]*)?/?>", line):
            warnings.append(CnoiWarning("出现 HTML 标签，模板会把它当普通代码显示", ln,
                                        "改用 Markdown 语法"))

    # 7. YAML front matter 会被忽略
    if md.lstrip().startswith("---\n"):
        warnings.append(CnoiWarning("文档开头的 YAML front matter 会被忽略", 1,
                                    "元信息请写进 meta.yaml / contest.yaml"))

    # 8. 引用了但没定义的脚注
    refs = {n["label"] for n in _walk(doc["children"]) if n["type"] == "footnoteRef"}
    for label in sorted(refs - set(doc["footnotes"])):
        warnings.append(CnoiWarning("脚注 [^%s] 没有定义" % label, 0,
                                    "补一行 [^%s]: 内容" % label))
    return errors, warnings


def _plain(node) -> str:
    return "".join(n["value"] for n in node.get("children") or [] if n["type"] == "text")


def ast_summary(doc: dict) -> dict:
    """给 --info 用的统计摘要。"""
    counts = {}
    headings = []
    for n in _walk(doc["children"]):
        counts[n["type"]] = counts.get(n["type"], 0) + 1
        if n["type"] == "heading":
            headings.append((n["depth"], _plain(n)))
    return {
        "blocks": len(doc["children"]),
        "counts": counts,
        "headings": headings,
        "footnotes": sorted((doc.get("footnotes") or {}).keys()),
    }


def render(md: str, *, with_header_import: bool = True) -> str:
    """一步到位：Markdown -> Typst 源码（等价于上游 processor.processSync）。"""
    doc = parse(md)
    typst = to_typst(doc, with_header_import=with_header_import)
    return typst
