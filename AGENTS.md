# AGENTS.md

信息学竞赛出题工程。本文件是**给 AI 编码代理的入口**：
先读 §1 的 11 条内核，再按 `docs/rules.md` 只加载本次需要的模块。

> **当前状态**：题目与比赛配置已清空，仓库只保留规则、文档、工具与资源。
> 开工第一步永远是**问清批次参数**（§3），不要沿用上一批的设定。

## 1. 内核 K（11 条，任何题、任何场景都生效）

| ID | 规则 |
| --- | --- |
| K1 | 编译、造数、校验、打包**只用 `python3`**（`tools/*.py`），不写 shell/ps1 脚本 |
| K2 | 编译固定 `g++ -std=c++14 -O2 -Wall`，**零警告**；本机 `-DFOR_LINUX -static-libgcc` 由 `_common.py` 追加 |
| K3 | 目录与文件名固定：`problems/<pid>/{meta.yaml, statement/zh_CN.md, src/{std,gen,valid[,checker][,interactor]}.cpp, sol.md}` |
| K4 | `gen.cpp`/`valid.cpp` 必须 testlib；随机性只来自 seed；seed 与规模写在 `gen.cpp` 的 `CASES` 表；数据可逐字节重建 |
| K5 | `valid.cpp` 按**题面**独立校验（每条约束 + 跨变量一致性 + `readEof`），不按测试点名放宽 |
| K6 | 数据要有区分度：边界覆盖、满规模卡满、能卡掉常见错解 |
| K7 | 每次任务都在**新建的日期目录** `runs/<开始日期>/` 内完成（`problems/`、`contests/`、`notes/`、`build/`），仓库其余目录本轮只读；产物只写 `build/`。**整个 `runs/` 都不进 git** |
| K8 | `resources/source`、`resources/testlib`、`resources/cnoi` 是第三方快照，**不改**；升级走 `setup_resources.py` |
| K9 | 不留调试代码；不确定的结论实测或标「未验证」；不编造测试点、分值、checker 行为 |
| K10 | 改了字段、目录结构或工具参数，同步更新文档与模板 |
| K11 | 主要使用环境在**中国大陆**：装环境/升级依赖必须先考虑网络（国内镜像或本机代理），不能假定能直连 GitHub / PyPI；依赖从哪找见 `docs/environment.md` |

内核**不包含**：人物名、测试点数量、子任务划分、文件 IO、大样例、比赛结构、题号。
它们属于 M/D（题目形态与交付目标）或 P（每次问你）。

## 2. 模块索引

**M 题型**（由题目形态决定）：M1 文件 IO / M2 子任务与计分 / M3 大样例下发 / M4 SPJ /
M5 实数 / M6 交互 / M7 多组数据 / M8 C++ 风格 / M9 题面基线。

**D 交付**（由要交什么决定）：D1 Hydro 包 / D2 Lemon 包 / D3 CNOI PDF。

**P 批次**（每次开工必须问）：P1 人物与世界观 / P2 比赛结构 / P3 测试点规格 /
P4 题号与命名 / P5 样例策略 / P6 交付物 / P7 题面与 IO 形式。

逐条细节见 `docs/rules.md` §2–§4；怎么写见：

| 要做什么 | 读这个 |
| --- | --- |
| 流程、命令、gen / valid 契约 | `docs/workflow.md` |
| 装环境、依赖从哪儿找 | `docs/environment.md` |
| 题面写法、CNOI 方言、PDF | `docs/statement.md` |
| Hydro / Lemon / SPJ 格式 | `docs/formats.md` |
| 写 C++ | `docs/style.md` |

## 3. 开工前必须问清（P，无默认值）

1. **P1 人物与世界观**：主角/配角叫什么？要不要固定人物？能不能写背景铺垫？题目名有什么限制？
2. **P2 比赛结构**：成不成场？一场几题、几天几场？题目复用吗？封面几行？
3. **P3 测试点规格**：每题几个点？子任务怎么分、各多少分？按点给分还是整档？
4. **P4 题号与命名**：Hydro 题号区间/规则？数据目录用什么名？
5. **P5 样例策略**：小样例几个？大样例几个、多大规模？要不要下发 `down/`？
6. **P6 交付物**：只 Hydro？还是 Hydro + Lemon + PDF？单题还是整场？
7. **P7 题面形式**：中文/英文？文件 IO 还是标准 IO？要不要封面表格？

问清后把这一批的取值记下来，**下一批重新问**，不要沿用。
上一批（三三信奥国庆模拟赛）的取值只记在 `docs/rules.md` §4 的右列，仅作背景参考。

## 4. 开工顺序

1. `python tools/new_run.py` 建 `runs/<开始日期>/`，记下路径；之后在仓库根用
   `set GEN_WORK=<该路径>`（或 cd 进去用 `..\..\tools\...`）跑工具。
2. 问清 P1–P7，写进该目录的 `batch.md`，列出启用的 M/D 模块。
3. 从 `problems/_template/` 复制出新题（A+B 标准 IO 模板，照它的目录结构改）。
4. 写 `meta.yaml`、`statement/zh_CN.md`、`src/*.cpp`、`hydro/testdata/config.yaml`。
5. `build.py all` → `cnoi.py check --strict` → `cnoi.py build --preview` → `samples.py` → `pack_*`。
6. 按 `docs/workflow.md` §6 验收。

## 5. 命令速查

```bash
python tools/new_run.py                    # 每次任务第一步：建 runs/<日期>/
python tools/setup_resources.py            # 首次：落地 testlib / 字体 / Typst 包
python tools/setup_resources.py --check

python tools/build.py all      --problem <pid>   # 编译 + 造数 + 校验 + 查答案
python tools/build.py list     --problem <pid>
python tools/build.py gen      --problem <pid> --case a1

python tools/cnoi.py check --problem <pid> -o build/tmp --strict
python tools/cnoi.py build --problem <pid> -o build/statement/<pid> --preview
python tools/cnoi.py build --contest <cid> -o build/contests/<cid> --preview

python tools/samples.py    --problem <pid>
python tools/pack_hydro.py --problem <pid>     # --day d1 场次包 / --batch 名称 批量包
python tools/pack_lemon.py --contest <cid>

python tools/selftest.py          # 工具链自检（依赖 problems/_template）
python tools/contest_check.py     # 比赛级验收（依赖 contests/*.yaml）
```

本机注意：`python` / `python3` 都是 3.15.2，可直接用；中文乱码先 `set PYTHONIOENCODING=utf-8`。
依赖装在哪、装不上的时候去哪儿找，见 `docs/environment.md`。

## 6. 目录速查

```
AGENTS.md     内核 + 模块索引 + P 清单 + 命令
docs/
├── rules.md      分层规则（K/M/D/P）+ 场景表 + 平台事实 + 原始需求
├── workflow.md   环境、流程、gen/valid 契约、验收
├── environment.md 依赖来源、国内镜像与代理、本机安装位置
├── statement.md  题面写法、CNOI 方言、PDF
├── formats.md    Hydro / LemonLime / SPJ
└── style.md      C++ 代码风格
resources/        公共资源（setup_resources.py 落地，只读）
tools/            全部构建入口（python3）
runs/<日期>/      每次任务一个目录，开工时由 tools/new_run.py 创建
├── batch.md      本批 P1–P7 的取值
├── problems/     每道题
├── contests/     比赛配置
├── notes/        对拍与草稿
└── build/        本轮产物（可随时删除）
```

## 7. 冲突与例外

- `docs/rules.md` 决定「哪条规则什么时候生效」，其余 docs 只讲怎么做；冲突时以 `rules.md` 为准。
- 本文件的铁律**只有 §1 那 11 条**；其余要求都挂在某个 M/D/P 上，没启用就不适用。
- 遇到与现成实现冲突的地方**停下来说明**，不要偷偷绕过。
- **流程变更纪律**：出题流程只在**发现了以前的漏洞**时才改（本次新增 K11 就是因为国内网络踩过坑）；
  没有具体缺陷就不重构流程、不加规则。
