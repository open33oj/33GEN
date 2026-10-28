# 出题规则分层

本文件只回答一个问题：**哪条要求在什么情况下才适用**。
原来 14 份文档里平铺的 ~100 条要求，按下面四层重新归类：

| 层 | 含义 | 谁决定 |
| --- | --- | --- |
| **K 内核** | 任何题、任何场景都生效 | 工程本身（固定） |
| **M 题型模块** | 由这道题的形态决定（有子任务？多解？交互？） | 题目形态 |
| **D 交付模块** | 由这次要交什么决定（Hydro？Lemon？PDF？） | 交付目标 |
| **P 批次参数** | 每一批都不一样：人物、比赛结构、测试点规格、题号… | **每次开工必须问用户** |

> **P 层没有默认值。** 上一批（三三信奥国庆模拟赛）的取值只记在 §4 的「上次取值」里，
> 仅供理解背景，**不得**当成新批次的默认规则。
>
> **一次任务 = 一个日期目录**：开工先 `python tools/new_run.py` 建 `runs/<开始日期>/`，
> 之后所有题目、比赛配置、草稿与产物都只在那个目录里（K7）。

---

## 1. 内核 K（11 条，永远生效）

| ID | 规则 | 谁在强制 |
| --- | --- | --- |
| K1 | 编译、造数、校验、打包**只用 `python3`**（`tools/*.py`），不写 shell/ps1 脚本 | 约定 |
| K2 | 编译固定 `g++ -std=c++14 -O2 -Wall`，**零警告**；本机 `-DFOR_LINUX -static-libgcc` 由工具追加 | `_common.compile_source` |
| K3 | 目录与文件名固定：`problems/<pid>/{meta.yaml, statement/zh_CN.md, src/{std,gen,valid[,checker][,interactor]}.cpp, sol.md}` | `build.py` 按名找文件 |
| K4 | `gen.cpp`/`valid.cpp` 必须 testlib；随机性只来自 seed；seed 与规模写在 `gen.cpp` 的 `CASES` 表；数据可逐字节重建 | `--list` 核对 + 重建比对 |
| K5 | `valid.cpp` 按**题面**独立校验（每条约束 + 跨变量一致性 + `readEof`），不按测试点名放宽 | `build.py validate` |
| K6 | 数据要有区分度：边界覆盖、满规模卡满、能卡掉常见错解 | `data_strength` / `score_solution` |
| K7 | 每次任务都在**新建的日期目录** `runs/<开始日期>/` 内完成（`problems/`、`contests/`、`notes/`、`build/`），仓库其余目录本轮只读；产物只写 `build/`。**整个 `runs/` 不进 git** | `new_run.py` / `.gitignore` |
| K8 | `resources/source`、`resources/testlib`、`resources/cnoi` 是第三方快照，**不改** | `setup_resources --check` |
| K9 | 不留调试代码；不确定的结论实测或标「未验证」；不编造测试点、分值、checker 行为 | 人工 / style §7 |
| K10 | 改了字段、目录结构或工具参数，同步更新文档与模板 | 人工 |
| K11 | 主要使用环境在**中国大陆**：装环境/升级依赖先考虑网络（国内镜像或本机代理），不假定能直连 GitHub / PyPI；来源见 `docs/environment.md` | 人工 |

内核里**没有**：人物名、测试点数量、子任务划分、文件 IO、大样例、比赛结构、题号。
这些要么属于 M/D（由题目形态与交付目标决定），要么属于 P（每次问你）。

---

## 2. 题型模块 M（题目形态决定，启用即适用）

### M1 文件 IO
**启用**：程序按文件读写。
**要求**：`config.yaml` 写 `filename: <短名>`；`std.cpp` 用 `freopen` 读 `<短名>.in`、写 `<短名>.out`（`"wb"`）；
题面「输入格式/输出格式」第一句写明这两个文件名。三处必须一致。

### M2 子任务与计分
**启用**：有子任务 / 部分分。
**要求**：只在 `hydro/testdata/config.yaml` 声明（`score`/`type`/`cases`/`name`）；
`type: sum` 按点给分、`min` 整档全对才给分，别写反；
题面子任务表**不手写**，由 `subtask_table()` 从 config 生成。

### M3 大样例下发
**启用**：要给选手满规模样例。
**要求**：`meta.yaml` 的 `samples` 表（借用某满规模测试点 + 换 `seed`）；`gen.cpp` 支持 `--seed`；
文件名 `<短名><k>.in|ans`，编号接在小样例之后连续；题面写明「见选手目录下的 …」；
由 `samples.py` 生成，不手抄。

### M4 SPJ（答案不唯一）
**启用**：多解 / 构造 / 输出方案。
**要求**：testlib `checker.cpp` + `checker_type: testlib`；只用 `_ok/_wa/_pe/_fail/_points`；
`seekEof()` 卡多余输出；标准答案仍由 `std.cpp` 生成；`checker <in> <ans> <ans>` 自判 ok；
题面写「答案不唯一」+ 判定标准。

### M5 实数比较
**启用**：输出浮点数。
**要求**：checker 用 `doubleCompare`（或题面给定误差），不用 `abs(a-b)<eps`；题面写清误差口径。

### M6 交互
**启用**：交互题。
**要求**：testlib `interactor.cpp` + `type: interactive`；没有 `.ans`；题面写交互方式与 flush，与 interactor 逐条对应。

### M7 多组数据
**启用**：输入含 `T` 组。
**要求**：题面写 `T` 范围**和**「所有用例的 Σn / Σnm」；`valid.cpp` 校验 Σ；`data_spec` 写对。

### M8 C++ 风格
**启用**：写任何 C++。
**要求**：`docs/style.md` 全文。最容易忘的四条：4 空格无 Tab、Allman 花括号、
`bits/stdc++.h` + `using namespace std;` + `main` 显式 `return 0;`、变量声明处写中文行尾注释。

### M9 题面基线
**启用**：写任何题面。
**要求**：章节顺序固定；样例与 `data/` 一致并能过 `valid`；范围闭合；
不出现测试点编号/卡常/骗分/std 做法；**不剧透**（提示只写读入/格式/判分，样例解释只解释输出为什么对）；
公式 `$...$`，乘号 `\times`。

---

## 3. 交付模块 D

### D1 Hydro 题包
顶层一个文件夹 = `hydro_pid`；含 `problem.yaml` / `problem_zh.md` / `testdata/` / `additional_file/`；
题解、标程、生成器、校验器、checker、interactor 全放 `testdata/`（打包改 `.cc`）；
`checker_type` 只用 `default/strict/testlib/hustoj/lemon/qduoj/syzoj/kattis`
（没有 `ccr`/`cena`，`rcmpN` 不是类型）；非 `default/strict` 必须给 checker；
不夹带 `build/`、`*.exe`、`notes/`。

### D2 LemonLime 包
`<名称>.cdf`（紧凑 JSON，`version: "1.0"`）；无 task 总分，满分 = 各点 `fullScore` 之和；
`data/<短名>/<短名><n>.in|ans`；`down/` 放整场合并 PDF + 每题样例；
SPJ 走 `comparisonMode: 5` + `specialJudge: "<短名>/checker"`；
子任务依赖用哨兵字符串（`min/max/sum` 只有 Hydro 支持）。

### D3 CNOI 题面 PDF
`cnoi.py check --strict` 先过再 `build`；只用 `##`；禁 HTML/front matter/参考式链接/深层嵌套/>63 列；
图片只支持相对单位；`resources/cnoi` 不改，版式改动走 `STAGE_PATCHES`。

---

## 4. 批次参数 P（每次开工必须问，**无默认值**）

| ID | 要问什么 | 影响 | 上次取值（仅参考，不是默认） |
| --- | --- | --- | --- |
| P1 | 人物与世界观：主角/配角叫什么？要不要固定人物？能不能写背景铺垫？题目名有什么限制？ | M9 | 主角 33DAI、配角 Tom、代词「他」、无「题目背景」、题目名不带主角前缀且 ≤12 列、英文短名 `^[a-z]{1,6}$` |
| P2 | 比赛结构：成不成场？一场几题、几天、几场？题目复用吗？封面要几行？ | M2/D3 | 一天两场（CSP-J / CSP-S），每场 4 题；一天 6 道不同题，S 场复用 J 组后两题；封面三行、不印时间 |
| P3 | 测试点规格：每题几个点？子任务怎么分、各多少分？按点给分还是整档？ | M2/K6 | 20 点、6+6+8、30+30+40、每点 5 分、`type: sum` |
| P4 | 题号与命名：Hydro 题号区间/规则？数据目录用什么名？ | D1/D2 | `hydro_pid` 从 `C0141` 顺排；Lemon 目录用英文短名 |
| P5 | 样例策略：小样例几个？大样例几个、要多大规模？要不要下发 `down/`？ | M3/D2 | 小样例 1~2 个 + 满规模大样例 1~2 个；`down/` 放整场合并 PDF |
| P6 | 交付物：只出 Hydro？还是 Hydro + Lemon + PDF？单题还是整场？ | D1/D2/D3 | 三样都出 |
| P7 | 题面形式：中文/英文？文件 IO 还是标准 IO？要不要封面表格？ | M1/M9/D3 | 中文；文件 IO（`<短名>.in/.out`）；封面有输入输出文件名两行 |

> 问清之后，把这一批的取值写进**本表右列**或新开一份 `docs/batch-<id>.md`，
> 后续所有题都按它执行；下一批重新问。

---

## 5. 场景 → 模块速查

| 场景 | 加载 |
| --- | --- |
| 单道传统题，标准 IO，无子任务 | K + M8 + M9 + D1 |
| 单道传统题，文件 IO | K + M1 + M8 + M9 + D1 |
| 有子任务 / 部分分 | + M2 |
| 要下发大样例 | + M3 |
| 答案不唯一 / 构造 / 浮点 | + M4（+ M5） |
| 交互题 | + M6 |
| 多组数据 | + M7 |
| 出整场比赛 | + D3（+ D2）+ P2/P3/P4 的取值 |
| 只要 Hydro | 不加载 D2 |

---

## 6. 附录 A：平台事实（不是规则）

- Hydro `checker_type` 8 个取值与语义；checker 判定从 **stderr** 读。
- LemonLime `.cdf` 字段、`comparisonMode` 1–5、子任务哨兵、`timeLimit` 毫秒 / `memoryLimit` MB。
- `rcmpN` 是 testlib 示例 checker，`N` 是误差指数。
- `type: min` vs `sum` 的实际行为。
- CNOI 模板的自由字体随仓库，中文字体用系统字体；`--package-path` 必须。
- 本机三坑：`libgcc_s`、Typst 下不了包、testlib 的 CRLF。
- 本机用 `python` 而不是 `python3`。

---

## 7. 附录 B：原始 12 条需求（建仓依据）

1. 这是信息学竞赛出题工程，给出导出格式与出题流程规范。
2. 环境：g++、testlib.h、python3、typst。
3. 编译选项 `-std=c++14 -O2 -Wall`。
4. C++ 风格：从风格样本归纳成文档。
5. 文件命名：`std.cpp`、`30.cpp`/`60.cpp`、`gen.cpp`、`valid.cpp`、`interactor.cpp`、`checker.cpp`、`sol.md`。
6. 产出：Hydro 压缩包；LemonLime 包（含下发给选手的 `down/`）。
7. 总结 Hydro 三份官方文档；hydro 内置 spj 包括 rcmp6/rcmp9（**已按源码修正**：rcmpN 不是 checker_type）。
8. Hydro 包里题解、标程、生成器统一放 `testdata/`。
9. 不用 shell 脚本，用 python3 控制编译与造数。
10. 只有极小数据允许硬编码，其余由 `gen.cpp` 按逻辑生成。
11. `gen.cpp`、校验器、交互器都用 testlib 保证可复现。
12. 题面用 CNOI 生成器出 PDF。
