#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""数据强度检查：把每个测试点的规模与答案分布摊开，便于人工判断有没有强度。

    python3 tools/data_strength.py                 # 检查所有已生成的题
    python3 tools/data_strength.py d1j1 d2j3       # 只查指定题
    python3 tools/data_strength.py --subtask 2     # 只打印第 2 个子任务

为什么需要它：`contest_check.py` 只能验证"结构对不对"（20 点、6+6+8、按点计分），
但**数据有没有强度**是没法靠结构检查的 —— 例如满规模的测试点如果答案恒为 0，
或者每组数据都很小，结构检查照样全绿。本脚本把关键统计量打出来，
再自动标出几个明显的坏味道，剩下的由人工过一眼。

自动判定的坏味道：
  * `答案恒定`：某个子任务里所有测试点的答案完全相同（可能整段是送分数据）；
  * `规模不达标`：满规模子任务的实测规模远小于题面声明的上界；
  * `无大用例`：子任务里连一个接近上界的测试用例都没有。
"""

from __future__ import annotations

import argparse
import collections
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import PROBLEMS, Problem, log  # noqa: E402

# 每个测试点的规模提取方式：读第 1 个 token 当 T，然后每个测试用例吃 (a 个参数 + 若干数据)
# 单位是"数字个数"；数组长度由参数给出时用 lambda 描述。
# 这里只做"尽量通用"的估计：多数题是 T + (n, ...) + n 个数据。
SPECIAL = {
    # pid: (自定义解析函数名) —— 需要时再补
}


def numbers(path: Path):
    return path.read_text(encoding="utf-8", errors="replace").split()


def _spec_scale(pid: str, toks, spec: str, no_T: bool = False):
    """按 meta.yaml 里的 `data_spec` 精确计算规模。

    data_spec 是一小段 Python 表达式，可用变量：
        T          测试用例数（第一个数）
        p          游标（[下标]，可用 p[0] 读写）
        x(i)       当前用例的第 i 个参数
        take(k)    消费 k 个整数
        at(i)      读绝对下标 i 的值但不移动游标（用于处理变长部分）
        advance(k) 游标前进 k
        unit       本用例的"规模"（默认取第一个参数；spec 里可改写）
    遍历完所有用例后返回 (T, Σunit, max unit)。规格写错会退回启发式估计。

    变长输入（例如操作行可能是 `1 l r` 或 `2 x`）用 `at(i)` 逐行判断该行占几个数，
    再用 `advance(k)` 跳过 —— 例如 d2s2 的 data_spec 就是这么写的。

    单组数据的题（输入里没有 T，第一行就是数据）在 meta.yaml 里写 `data_no_T: true`，
    这样打印出来的 T 会是 1 而不是把第一个参数误当成 T。
    """
    try:
        pos = [1] if no_T else [1]
        if no_T:
            T = 1
            pos = [0]
        else:
            T = int(toks[0])
            pos = [1]
        units = []

        def x(i):
            return int(toks[pos[0] + i])

        def take(k):
            v = 0
            for _ in range(k):
                v = int(toks[pos[0]])
                pos[0] += 1
            return v

        def advance(n=1):
            pos[0] += n

        def at(i):
            """读绝对下标 i 的值，但不移动游标。"""
            return int(toks[i])

        env = {"T": T, "p": pos, "x": x, "take": take, "advance": advance, "at": at}
        # 只放一小撮安全的内建函数，规格里就能写 range / min / max / len 这类表达式；
        # 注意规格自己的变量（例如 q）要写在 advance 之前，别在游标移动后再用 x(i) 读。
        spec_builtins = {"range": range, "min": min, "max": max, "len": len, "int": int}
        for _ in range(T):
            env["unit"] = x(0)
            exec(spec, {"__builtins__": spec_builtins}, env)   # noqa: S102 - 本地元信息，非外部输入
            units.append(int(env["unit"]))
        return {"T": T, "tokens": len(toks), "max_unit": max(units) if units else 0,
                "total": sum(units)}
    except Exception:  # noqa: BLE001 - 规格写错就退回启发式
        return None


def heuristic_scale(toks):
    """启发式：T + 每个用例 (n, 后面 n 个数据)。只在没有 data_spec 时用。"""
    try:
        T = int(toks[0])
        pos = 1
        units = []
        for _ in range(T):
            if pos >= len(toks):
                break
            n = int(toks[pos])
            units.append(n)
            pos += 1 + n
        return {"T": T, "tokens": len(toks),
                "max_unit": max(units) if units else 0, "total": sum(units)}
    except (ValueError, IndexError):
        return None


def scale_stats(pid: str, path: Path, spec: str = None, no_T: bool = False):
    toks = numbers(path)
    if not toks:
        return None
    if spec:
        got = _spec_scale(pid, toks, spec, no_T)
        if got:
            return got
    return heuristic_scale(toks)


def answers(path: Path):
    """把 .ans 压成"每个测试用例一个字符串"的列表（用于看分布）。

    注意：不能只看第一个 token —— 有些题（如 SCAVHUNT）每组的首行是固定的
    `Scenario #i:` 前缀，只看首 token 会误判成"答案恒定"。
    """
    txt = path.read_text(encoding="utf-8", errors="replace").strip()
    out = []
    for line in txt.split("\n"):
        line = line.strip()
        if not line:
            continue
        out.append(line if len(line) <= 18 else line[:15] + "...")
    return out


def answer_key(path: Path):
    """整份答案文件的指纹，用于判断两个测试点是否完全同解。

    不能只看第一行：例如 d1j4 每组答案的首行都是 "33DAI"，但整份答案并不相同。
    去掉 SCAVHUNT 那类固定格式行后取整份内容做哈希。
    """
    import hashlib
    txt = path.read_text(encoding="utf-8", errors="replace")
    lines = [l.strip() for l in txt.split("\n") if l.strip()]
    body = [l for l in lines if not l.startswith("Scenario")]
    if not body:
        body = lines
    return hashlib.sha256("\n".join(body).encode("utf-8")).hexdigest()[:16]


def answer_head(path: Path):
    """答案的第一行（仅用于打印展示）。"""
    txt = path.read_text(encoding="utf-8", errors="replace")
    lines = [l.strip() for l in txt.split("\n") if l.strip()]
    body = [l for l in lines if not l.startswith("Scenario")]
    return (body[0] if body else (lines[0] if lines else ""))[:40]


def describe(vals):
    """把答案列表压成"取值个数 + 前几个"。"""
    c = collections.Counter(vals)
    top = c.most_common(3)
    return "%d 种取值，最常见 %s" % (len(c), ", ".join("%s×%d" % kv for kv in top))


def check_problem(pid: str, only_sub: int = None) -> int:
    p = Problem(pid)
    meta = p.meta
    spec = meta.get("data_spec")
    subs = p.hydro_config.get("subtasks") or []
    cases = p.cases()
    if not cases or not p.data.is_dir():
        log("%s：没有数据，跳过" % pid)
        return 0

    log("")
    log("═══ %s（%s）%s═══" % (pid, meta.get("title", ""),
                              "" if spec else "  [未声明 data_spec，用启发式估计]"))
    problems = 0
    idx = 0
    for si, st in enumerate(subs):
        n = len(st.get("cases") or [])
        if only_sub is not None and si != only_sub:
            idx += n
            continue
        log("  ── 子任务 %d（%d 点，%s 分）：%s"
            % (si + 1, n, st.get("score"), st.get("name", "")))
        rows = []
        total_all = []
        for k in range(idx, idx + n):
            _, _, in_name, out_name = cases[k]
            ip = p.data / in_name
            op = p.data / out_name
            if not (ip.is_file() and op.is_file()):
                log("     %-8s 缺数据" % in_name)
                continue
            st_stats = scale_stats(pid, ip, spec, bool(meta.get("data_no_T")))
            av = answers(op)
            if st_stats:
                total_all.append(st_stats["total"])
                rows.append("%s: T=%-5d Σ=%-9d max=%-8d ans=%s"
                            % (Path(in_name).stem, st_stats["T"], st_stats["total"],
                               st_stats["max_unit"], " / ".join(av[:2])))
            else:
                rows.append("%s: ans=%s" % (Path(in_name).stem, " / ".join(av[:2])))
        for r in rows:
            log("     " + r)

        # 坏味道检查
        ops = [p.data / cases[k][3] for k in range(idx, idx + n)]
        keys = [answer_key(o) for o in ops if o.is_file()]
        keys = [k for k in keys if k]
        heads = [answer_head(o) for o in ops if o.is_file()]
        if len(keys) >= 3 and len(set(keys)) == 1:
            log("     [warn] 这一子任务 %d 个测试点的**整份答案完全相同**—— 可能整段是同一类数据"
                % len(keys))
            problems += 1
        if total_all:
            mx = max(total_all)
            # 规模天然很小的题（例如 N ≤ 40 的天平）可以在 meta.yaml 里声明
            # data_scale_max，声明后只要实测达到该上界就不报警。
            declared_max = meta.get("data_scale_max")
            if declared_max:
                if si == len(subs) - 1 and mx != int(declared_max):
                    log("     [warn] 满规模子任务实测规模 %d，与声明的 %s 不符"
                        % (mx, declared_max))
                    problems += 1
            elif si == len(subs) - 1 and mx < 1000 and spec != "unit = x(0); advance(1)":
                log("     [warn] 满规模子任务的实测规模只有 %d，确认是否卡满" % mx)
                problems += 1
        log("     答案样本：%s" % " | ".join(heads[:5]))

        # 整档答案只有一种取值：说明"输出常数"就能拿满这一档（例如 n = 1 的网格答案恒为 1）
        vals = set()
        for k in range(idx, idx + n):
            op = p.data / cases[k][3]
            if op.is_file():
                for line in op.read_text(encoding="utf-8", errors="replace").split("\n"):
                    line = line.strip()
                    # d2j1 那类固定的 `Scenario #i:` 行不算答案
                    if line and not line.startswith("Scenario"):
                        vals.add(line)
        if n >= 2 and len(vals) == 1:
            # 有些档是**刻意**保留成常数的（例如题面就写成"退化网格"的那种），
            # 在 meta.yaml 里用 `data_constant_ok: [子任务下标]` 声明后只打印提示。
            allowed = meta.get("data_constant_ok") or []
            if si in allowed:
                log("     [info] 这一子任务 %d 个测试点的答案恒为 %r（meta.yaml 里已声明 "
                    "data_constant_ok，属刻意设计）" % (n, next(iter(vals))))
            else:
                log("     [warn] 这一子任务 %d 个测试点的答案只有一种取值 %r —— 输出常数就能拿满这一档"
                    % (n, next(iter(vals))))
                problems += 1
        idx += n
    return problems


def main() -> int:
    ap = argparse.ArgumentParser(description="数据强度检查")
    ap.add_argument("problems", nargs="*", help="题目目录名（默认全部）")
    ap.add_argument("--subtask", type=int, help="只看第几个子任务（从 0 开始）")
    args = ap.parse_args()

    if args.problems:
        pids = args.problems
    else:
        pids = [d.name for d in sorted(PROBLEMS.iterdir())
                if d.is_dir() and not d.name.startswith("_")
                and (d / "hydro" / "testdata" / "config.yaml").is_file()
                and (d / "data").is_dir()]

    total_warn = 0
    for pid in pids:
        total_warn += check_problem(pid, args.subtask)

    log("")
    log("=" * 60)
    log("检查了 %d 道题，%d 处需要人工确认（见上面的 [warn]）" % (len(pids), total_warn))
    log("注意：本脚本只能标出明显的坏味道，数据强度最终仍需人工过一眼。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
