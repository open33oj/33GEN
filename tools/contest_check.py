#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""比赛级验收：检查一场比赛（或全部比赛）的题目是否满足硬性要求。

    python3 tools/contest_check.py                 # 检查 contests/ 下全部比赛
    python3 tools/contest_check.py d1-j d1-s       # 只查指定比赛
    python3 tools/contest_check.py --no-build      # 跳过需要编译的检查

检查项（数值规格属于批次参数 P2/P3，可用命令行覆盖，不是硬编码规则）：

  1. contests/<id>.yaml 里的题目目录都存在，每场题数 = --per-contest；
  2. 每题测试点数 = --points，config 的 cases 数与 data/ 下的 .in/.ans 数一致；
  3. 子任务划分 = --split、分值 = --scores，合计 100，按测试点得分（type: sum）；
  4. gen.cpp 声明的测试点（--list）与 config.yaml 完全一致；
  5. src/ 下有 std.cpp / gen.cpp / valid.cpp（答案不唯一的题还应有 checker.cpp）；
  6. 数据能被 valid.cpp 全部通过，且 .ans 存在、非空、为 LF；
  7. 题面过 `cnoi.py check --strict`；第一小节是「## 题目描述」、没有「## 题目背景」；
     含本批主角（--hero，默认 33DAI，传空串则跳过）；
     「提示」不涉及做法、样例解释不解释"为什么无解/最优"、异或要写规则与 `^`；
  8. 命名：英文短名 `^[a-z]{1,6}$`、同场不重；中文题名 ≤12 列；
     `hydro_pid` 是「字母 + 数字」且全局唯一。

注意：主角名与废弃人名（HERO / FORBIDDEN_NAMES）属于批次参数 P1，
换一批时用 --hero 指定，或改这两个常量。
"""

from __future__ import annotations

import argparse
import collections
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import CONTESTS, PROBLEMS, WORK, Problem, log, read_yaml  # noqa: E402

PY = sys.executable or "python"
TOOLS = Path(__file__).resolve().parent
WANT_COUNT = 20
WANT_SPLIT = [6, 6, 8]
WANT_SCORES = [30, 30, 40]
WANT_PER_CONTEST = 4
# 以上是「上一批」的规格，属于批次参数（docs/rules.md P2/P3），**不是硬编码规则**：
# 换一批用 --points / --split / --scores / --per-contest 覆盖。
HERO = "33DAI"
SHORT_NAME_RE = re.compile(r"^[a-z]{1,6}$")
# 题目名的显示宽度上限（列）：封面表格是 4 题并排，实测 12 列（= 6 个汉字）单行放得下，
# 13 列（如旧名「传送阵·简单版」）就会折行。见 docs/rules.md。
TITLE_MAX_WIDTH = 12
# 废弃的人物名：`三七` 只算人名，不算「第三十七」里的数字
FORBIDDEN_NAMES = [re.compile(r"Alice"), re.compile(r"Bob"),
                   re.compile(r"(?<![第十百千万零一二三四五六七八九])三七(?![十百千万])")]
# 「提示」小节里禁止出现的词：只要出现，基本就是把做法写进题面了
# （见 docs/statement.md）。提示只允许写读入/格式/判分说明。
HINT_FORBIDDEN = ["策略", "贪心", "二分", "复杂度", "不变量", "单调", "前缀和", "只需",
                  "只取决于", "溢出", "卡常", "结论", "性质", "注意到", "无论如何"]
# 样例解释里禁止出现的词：解释只说明"给出的输出是可达/合规的"，
# 不得解释"为什么无解 / 为什么最优"，也不得暴露任何结论。
EXPLAIN_FORBIDDEN = ["策略", "不变量", "奇偶性总是", "是完全平方数", "只取决于",
                     "无论如何都", "永远不可能", "始终是", "结论"]


def display_width(text: str) -> int:
    """显示宽度：中日韩等宽字符算 2 列，其余算 1 列。"""
    return sum(2 if ord(c) > 0x1100 else 1 for c in str(text))


def section_text(md: str, keyword: str) -> str:
    """取出标题里含 keyword 的所有小节的正文（拼起来）。"""
    out = []
    cur = None
    for line in md.split("\n"):
        m = re.match(r"^##\s+(.*?)\s*$", line)
        if m:
            cur = [] if keyword in m.group(1) else None
            if cur is not None:
                out.append(cur)
        elif cur is not None:
            cur.append(line)
    return "\n".join("\n".join(b) for b in out)


class Report(object):
    def __init__(self):
        self.errors = []
        self.warnings = []

    def err(self, where, msg):
        self.errors.append("%s：%s" % (where, msg))
        log("  [FAIL] %-26s %s" % (where, msg))

    def warn(self, where, msg):
        self.warnings.append("%s：%s" % (where, msg))
        log("  [warn] %-26s %s" % (where, msg))

    def ok(self, where, msg=""):
        log("  [ok  ] %-26s %s" % (where, msg))


def contest_files(only):
    d = CONTESTS
    if not d.is_dir():
        return []
    got = sorted(d.glob("*.yaml"))
    if only:
        got = [p for p in got if p.stem in only]
    return got


def check_config(r, p: Problem):
    """测试点数量、子任务划分与分值。"""
    cfg = p.hydro_config
    subs = cfg.get("subtasks") or []
    counts = [len(s.get("cases") or []) for s in subs]
    scores = [int(s.get("score", 0)) for s in subs]

    if sum(counts) != WANT_COUNT:
        r.err(p.pid, "测试点总数 %d，应为 %d" % (sum(counts), WANT_COUNT))
    elif counts != WANT_SPLIT:
        r.err(p.pid, "子任务划分 %s，应为 %s" % (counts, WANT_SPLIT))
    else:
        r.ok(p.pid, "子任务 %s" % "+".join(map(str, counts)))

    if scores != WANT_SCORES:
        r.err(p.pid, "子任务分值 %s，应为 %s" % (scores, WANT_SCORES))
    elif sum(scores) != 100:
        r.err(p.pid, "总分 %d，应为 100" % sum(scores))

    # 按点计分：每个子任务的分值要能被它的测试点数整除，且所有点分值相同
    per = []
    for s, n in zip(subs, counts):
        if n and int(s.get("score", 0)) % n:
            r.err(p.pid, "子任务分值 %s 不能被 %d 个测试点整除（无法按点计分）"
                  % (s.get("score"), n))
        if n:
            per.append(int(s.get("score", 0)) // n)
    if per and len(set(per)) != 1:
        r.warn(p.pid, "各子任务每点分值不同：%s" % per)
    elif per:
        r.ok(p.pid, "按点计分：每点 %d 分" % per[0])

    # 每个子任务都要有名字（会渲染到题面）
    for i, s in enumerate(subs):
        if not s.get("name"):
            r.warn(p.pid, "subtask%d 没有 name（题面子任务表会是空的）" % i)
        # 按点得分：Hydro 只有在 type: sum 时才按每个测试点分别给分
        if str(s.get("type", "min")) != "sum":
            r.err(p.pid, "subtask%d 的 type 是 %r，本批比赛按测试点得分，应为 sum"
                  "（type: min 会变成整个子任务全对才给分，见 docs/rules.md）"
                  % (i, s.get("type")))


def check_files(r, p: Problem):
    cfg = p.hydro_config
    cases = p.cases()
    n_in = len(list(p.data.glob("*.in")))
    n_ans = len(list(p.data.glob("*.ans")))

    if not p.data.is_dir() or n_in == 0:
        r.err(p.pid, "data/ 下没有 .in（先跑 tools/build.py gen）")
        return
    if n_in != len(cases):
        r.err(p.pid, "data/ 有 %d 个 .in，config.yaml 声明 %d 个" % (n_in, len(cases)))
    if n_ans != n_in:
        r.err(p.pid, "data/ 有 %d 个 .in 但只有 %d 个 .ans" % (n_in, n_ans))
    else:
        r.ok(p.pid, "%d 个测试点、%d 对数据文件" % (n_in, n_ans))

    # .ans 非空 + LF
    bad = []
    for f in sorted(p.data.glob("*.ans")):
        raw = f.read_bytes()
        if not raw.strip():
            bad.append("%s 为空" % f.name)
        elif b"\r" in raw:
            bad.append("%s 含 CR" % f.name)
        elif not raw.endswith(b"\n"):
            bad.append("%s 末尾缺换行" % f.name)
    if bad:
        r.err(p.pid, "答案文件问题：%s" % "；".join(bad[:4]))

    # 源码齐全
    for name in ("std.cpp", "gen.cpp", "valid.cpp"):
        if not (p.src / name).is_file():
            r.err(p.pid, "缺少 src/%s" % name)
    if cfg.get("checker") and not (p.src / "checker.cpp").is_file():
        r.err(p.pid, "声明了 checker，但缺少 src/checker.cpp")


def check_gen_declared(r, p: Problem, exe: Path):
    if not exe.is_file():
        return
    proc = subprocess.run([str(exe), "--list"], stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT, encoding="utf-8", errors="replace")
    declared = [x.strip() for x in (proc.stdout or "").split("\n") if x.strip()]
    wanted = [Path(c[2]).stem for c in p.cases()]
    if not declared:
        r.warn(p.pid, "gen.cpp 未实现 --list，无法核对测试点声明")
    elif declared != wanted:
        r.err(p.pid, "gen.cpp 声明 %s 与 config.yaml %s 不一致"
              % (declared[:6], wanted[:6]))
    else:
        r.ok(p.pid, "gen 声明的 %d 个测试点与 config 一致" % len(declared))


def check_io_and_big_samples(r, p: Problem, md: str):
    """文件 IO（`filename` + 题面 + 标程）与大样例位置说明（见 §4.2/§6）。"""
    meta = p.meta
    cfg = p.hydro_config
    name = str(meta.get("name") or p.pid)

    if cfg.get("filename") != name:
        r.err(p.pid, "config.yaml 的 filename 应为 %r（本批题统一文件 IO，"
              "见 docs/rules.md）" % name)
    for f in ("%s.in" % name, "%s.out" % name):
        if f not in md:
            r.err(p.pid, "题面「输入/输出格式」里没有出现文件名 %s" % f)
    std = p.src / "std.cpp"
    if std.is_file() and ("%s.in" % name) not in std.read_text(encoding="utf-8"):
        r.err(p.pid, "src/std.cpp 没有按文件 IO 打开 %s.in" % name)

    # 大样例位置：编号 = 小样例个数 + 1 开始，与 meta.yaml 的 samples 一一对应
    n_small = len({int(m.group(1)) for m in
                   re.finditer(r"^##\s*样例\s*(\d+)\s*输入\s*$", md, re.M)})
    samples = meta.get("samples") or []
    if not samples:
        r.warn(p.pid, "meta.yaml 没有 samples：没有下发大样例")
        return
    missing = []
    for k in range(n_small + 1, n_small + 1 + len(samples)):
        pat = re.compile(r"见选手目录下的\s*`?%s/%s%d\.in`?\s*与\s*`?%s/%s%d\.ans`?\s*。"
                         % (re.escape(name), re.escape(name), k,
                            re.escape(name), re.escape(name), k))
        if not pat.search(md):
            missing.append(k)
    if missing:
        r.err(p.pid, "题面缺少大样例位置说明：样例 %s（写法：「见选手目录下的 "
              "`%s/%s<k>.in` 与 `%s/%s<k>.ans`。」）"
              % ("、".join(map(str, missing)), name, name, name, name))
    else:
        r.ok(p.pid, "文件 IO 与 %d 个大样例位置均已写明" % len(samples))


def check_statement(r, p: Problem):
    proc = subprocess.run(
        [PY, str(TOOLS / "cnoi.py"), "check", "--problem", p.pid,
         "-o", str(p.build / "check"), "--strict"],
        cwd=str(WORK), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        r.err(p.pid, "题面未过 --strict 校验：%s"
              % (proc.stdout or "").strip().split("\n")[-1][:80])
        return
    md = (p.statement / "zh_CN.md").read_text(encoding="utf-8")
    if HERO and HERO not in md:
        r.err(p.pid, "题面里没有出现主角「%s」" % HERO)
    else:
        r.ok(p.pid, "题面通过（含主角%s）" % HERO)
    # 题面结构：第一个小节就是题目描述，不要单独的「题目背景」小节
    if "## 题目背景" in md:
        r.err(p.pid, "题面里不该有「## 题目背景」小节（人物与设定直接写进题目描述）")
    if not md.lstrip().startswith("## 题目描述"):
        r.err(p.pid, "题面的第一个小节必须是「## 题目描述」")
    for pat in FORBIDDEN_NAMES:
        m = pat.search(md)
        if m:
            r.err(p.pid, "题面里出现了废弃的人物名「%s」" % m.group(0))

    # 提示小节：只允许写读入/格式/判分说明，出现做法词直接报错
    hint = section_text(md, "提示")
    bad = [w for w in HINT_FORBIDDEN if w in hint]
    if bad:
        r.err(p.pid, "「## 提示」里出现疑似做法提示的词：%s"
              "（提示只能写读入、格式与判分说明）" % "、".join(bad))

    # 样例解释：只解释"给出的输出是可达/合规的"，不得解释为什么无解/为什么最优
    explain = section_text(md, "解释")
    bad = [w for w in EXPLAIN_FORBIDDEN if w in explain]
    if bad:
        r.err(p.pid, "样例解释里出现疑似做法提示的词：%s"
              "（样例解释只说明输出为什么是正确的，不讲做法）" % "、".join(bad))

    # 异或：必须解释运算规则并给出 C++ 运算符（硬性要求，见 docs/statement.md）
    if re.search(r"\\oplus|按位异或", md):
        missing = []
        if "逐位" not in md:
            missing.append("运算规则（写成二进制后逐位比较）")
        if "C++" not in md or "`^`" not in md:
            missing.append("C++ 里的运算符 `^`")
        if missing:
            r.err(p.pid, "题面用到异或，但缺少：%s" % "；".join(missing))

    # 文件 IO 与大样例位置（本批竞赛题的硬性要求）
    check_io_and_big_samples(r, p, md)


def main() -> int:
    global WANT_COUNT, WANT_SPLIT, WANT_SCORES, WANT_PER_CONTEST, HERO

    ap = argparse.ArgumentParser(description="比赛级验收检查")
    ap.add_argument("contests", nargs="*", help="比赛 id（默认全部）")
    ap.add_argument("--no-build", action="store_true",
                    help="跳过需要编译生成器的检查")
    ap.add_argument("--points", type=int, default=WANT_COUNT,
                    help="每题测试点数（P3，默认 %d）" % WANT_COUNT)
    ap.add_argument("--split", default=",".join(map(str, WANT_SPLIT)),
                    help="子任务点数划分（P3，默认 %s）" % "+".join(map(str, WANT_SPLIT)))
    ap.add_argument("--scores", default=",".join(map(str, WANT_SCORES)),
                    help="子任务分值（P3，默认 %s）" % "+".join(map(str, WANT_SCORES)))
    ap.add_argument("--per-contest", type=int, default=WANT_PER_CONTEST,
                    help="每场题数（P2，默认 %d）" % WANT_PER_CONTEST)
    ap.add_argument("--hero", default=HERO,
                    help="本批主角名（P1，默认 %s；传空串跳过检查）" % HERO)
    args = ap.parse_args()

    WANT_COUNT = args.points
    WANT_SPLIT = [int(x) for x in str(args.split).split(",") if x.strip()]
    WANT_SCORES = [int(x) for x in str(args.scores).split(",") if x.strip()]
    WANT_PER_CONTEST = args.per_contest
    HERO = args.hero

    files = contest_files(args.contests)
    if not files:
        log("没有找到比赛配置（contests/*.yaml）")
        return 1

    # 先把所有比赛涉及的题目收集起来（去重，因为一道题可能被两场复用）
    r = Report()
    per_contest = {}
    all_pids = []
    for f in files:
        cfg = read_yaml(f)
        folders = []
        for item in cfg.get("problems") or []:
            folders.append(item.get("folder") if isinstance(item, dict) else item)
        per_contest[f.stem] = (cfg, folders)
        for x in folders:
            if x not in all_pids:
                all_pids.append(x)

    # 1) 比赛配置的完整性
    log("═══ 1. 比赛配置 ═══")
    for cid, (cfg, folders) in per_contest.items():
        missing = [x for x in folders if not (PROBLEMS / x / "meta.yaml").is_file()]
        if missing:
            r.err(cid, "题目目录不存在：%s" % ", ".join(missing))
        else:
            r.ok(cid, "%s（%s）共 %d 题" % (cfg.get("subtitle", cid), cid, len(folders)))
        if len(folders) != WANT_PER_CONTEST:
            r.err(cid, "一场比赛应有 %d 题，实际 %d 题（P2；可用 --per-contest 覆盖）"
                  % (WANT_PER_CONTEST, len(folders)))

    # 2) 逐题检查
    existing = [x for x in all_pids if (PROBLEMS / x / "meta.yaml").is_file()]
    log("")
    log("═══ 2. 测试点与子任务（%d 题）═══" % len(existing))
    for pid in existing:
        p = Problem(pid)
        check_config(r, p)

    log("")
    log("═══ 3. 数据文件与源码 ═══")
    for pid in existing:
        p = Problem(pid)
        check_files(r, p)

    log("")
    log("═══ 4. 生成器声明与题面 ═══")
    for pid in existing:
        p = Problem(pid)
        exe = p.build / "bin" / ("gen.exe" if sys.platform == "win32" else "gen")
        if not args.no_build:
            check_gen_declared(r, p, exe)
        check_statement(r, p)

    # 5) 主角、题目名、英文短名与 Hydro 题号（跨题）
    log("")
    log("═══ 5. 命名与跨题一致性 ═══")
    names = collections.Counter()
    hydro_pids = collections.Counter()
    for pid in existing:
        meta = Problem(pid).meta
        title = str(meta.get("title", ""))
        short = str(meta.get("name", ""))
        submit = str(meta.get("submit_filename", ""))
        names[title or pid] += 1
        if display_width(title) > TITLE_MAX_WIDTH:
            r.err(pid, "题目名「%s」宽 %d 列，超过 %d 列（= %d 个汉字）："
                  "封面表格会折行，请改短"
                  % (title, display_width(title), TITLE_MAX_WIDTH,
                     TITLE_MAX_WIDTH // 2))
        if not SHORT_NAME_RE.match(short):
            r.err(pid, "英文短名「%s」不合规：只能用 1~6 个小写英文字母"
                  "（封面「目录」列，见 docs/rules.md）" % short)
        if submit != short + ".cpp":
            r.warn(pid, "提交源程序文件名「%s」与英文短名「%s」不一致" % (submit, short))
        # Hydro 题号：导入 Hydro 后 problem.yaml 的 pid（pack_hydro 用它做题目文件夹名）
        hid = str(meta.get("hydro_pid", ""))
        if not hid:
            r.err(pid, "meta.yaml 缺少 hydro_pid（Hydro 题号，如 C0141）")
        elif not re.match(r"^[A-Za-z]+[0-9]+$", hid):
            r.err(pid, "hydro_pid「%s」不合规：必须是「字母 + 数字」且不能全为数字" % hid)
        else:
            hydro_pids[hid] += 1
    dup = [k for k, v in names.items() if v > 1]
    if dup:
        r.warn("全局", "题目名重复：%s" % ", ".join(dup))
    else:
        r.ok("全局", "%d 道题题目名互不相同" % len(existing))
    dup = [k for k, v in hydro_pids.items() if v > 1]
    if dup:
        r.err("全局", "Hydro 题号重复：%s" % ", ".join(sorted(dup)))
    elif hydro_pids:
        r.ok("全局", "%d 个 Hydro 题号互不相同（%s ~ %s）"
             % (len(hydro_pids), min(hydro_pids), max(hydro_pids)))

    for cid, (_cfg, folders) in per_contest.items():
        shorts = [str(Problem(x).meta.get("name", "")) for x in folders
                  if (PROBLEMS / x / "meta.yaml").is_file()]
        dup = [k for k, v in collections.Counter(shorts).items() if v > 1]
        if dup:
            r.err(cid, "同一场比赛里英文短名重复：%s" % ", ".join(dup))
        else:
            r.ok(cid, "4 题的英文短名互不相同：%s" % " ".join(shorts))

    log("")
    log("=" * 60)
    log("检查了 %d 场比赛、%d 道题：%d 个错误，%d 个警告"
        % (len(files), len(existing), len(r.errors), len(r.warnings)))
    if r.errors:
        log("错误清单：")
        for e in r.errors:
            log("  - %s" % e)
        return 1
    log("全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
