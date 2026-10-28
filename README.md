# 33GEN — 信息学竞赛出题工程

把一道题的「题面 + 标程 + 生成器 + 校验器 + 题解」加工成可直接导入评测系统的交付物：

1. **Hydro OJ 题目压缩包**（Hydro Problem Format，zip）
2. **LemonLime 评测包**（可选，额外带下发给选手的 `down/`）
3. **CNOI 风格题面 PDF**（可选）

所有编译、造数、校验、打包都由 `python tools/*.py` 驱动，不写 shell 脚本。
**本仓库是框架仓库**：只放规则、文档、工具和一道 A+B 模板题；
具体题目放在 `runs/<日期>/`，该目录不进 git。

## 快速开始

```bash
python tools/setup_resources.py --check    # 依赖资源是否就绪
python tools/selftest.py                   # 工具链自检（在 problems/_template 上跑全流程）
```

出题时：

```bash
python tools/new_run.py                    # 建 runs/<今天>/，记下路径
# Windows：set GEN_WORK=runs\2026-10-28      bash：export GEN_WORK=runs/2026-10-28
python tools/build.py all      --problem <pid>   # 编译 + 造数 + 校验 + 查答案
python tools/cnoi.py check     --problem <pid> -o build/tmp --strict
python tools/samples.py        --problem <pid>
python tools/pack_hydro.py     --problem <pid>
```

工具怎么找任务目录：`GEN_WORK` 环境变量 > 当前目录（含 `problems/` 或 `contests/`）> 仓库根。
所以要么在仓库根设 `GEN_WORK`，要么 `cd` 进任务目录后用 `..\..\tools\build.py`。

## 目录

```
AGENTS.md          入口：11 条内核 + 模块索引 + 每批必须确认的 P1–P7
docs/              规则与细节文档（6 份）
├── rules.md       分层规则：K 内核 / M 题型 / D 交付 / P 批次
├── workflow.md    流程、命令、gen/valid 契约、验收清单
├── environment.md 依赖从哪儿找、国内镜像与代理、字体与系统依赖
├── statement.md   题面写法、CNOI 方言、PDF
├── formats.md     Hydro / LemonLime / SPJ 格式
└── style.md       C++ 代码风格
resources/         只读资源：testlib、CNOI 模板与自由字体、Typst 包
tools/             全部构建入口（python3）
problems/_template  A+B 模板题（标准 IO，20 个测试点）
runs/<日期>/       每次任务的工作目录（不进 git）
```

## 核心规则（完整版见 `AGENTS.md` / `docs/rules.md`）

- 编译固定 `g++ -std=c++14 -O2 -Wall`，零警告；
- `gen.cpp` / `valid.cpp` 必须用 testlib，随机性只来自 seed，数据可逐字节重建；
- 每次任务一个 `runs/<日期>/` 目录，仓库其余目录只读；
- 人物、比赛结构、测试点数量与分值、题号、交付物等**都是批次参数，每批开工前确认**。

## 环境

依赖版本与国内获取方式见 [`docs/environment.md`](docs/environment.md)：
g++（MinGW-w64）、Python + PyYAML、Typst **0.14.x**、Git。

一键自检：

```bash
g++ --version
python -c "import yaml; print(yaml.__version__)"
typst --version
git --version
python tools/setup_resources.py --check
```

## CI 测了什么 / 没测什么

`.github/workflows/ci.yml` 在 Ubuntu 上只跑**不依赖编译器和 Typst** 的检查：

| 检查 | 说明 |
| --- | --- |
| `py_compile` | `git ls-files '*.py'` 全部能编译（语法/缩进错误） |
| `setup_resources.py --check` | 资源是否齐、自由字体是否完整、中文字体检测 |
| `cnoi.py check --problem _template --strict` | 模板题的 Markdown 方言、公式、结构 |
| 模板完整性 | `problems/_template` 的 `meta.yaml` / 题面 / 配置存在 |

**没测**（需要在本地跑，CI 环境没有）：

- C++ 编译与 `-Wall` 零警告（需要 g++）；
- 造数 / 校验 / 答案比对（`build.py all`，需要 g++）；
- 题面 PDF 生成（需要 Typst 0.14.x + 字体）；
- 打包产物（`pack_hydro.py` / `pack_lemon.py`）。

本地对应命令：

```bash
python tools/selftest.py                    # 上述全部（除打包外）在模板题上跑一遍
python tools/build.py all --problem <pid>
python tools/cnoi.py build --problem <pid> -o build/statement/<pid> --preview
```

## 许可

- 本仓库以 **AGPL-3.0** 发布，见 [`LICENSE`](LICENSE)。
- `tools/cnoi/` 是上游 [cnoi-statement-generator](https://github.com/Mr-Python-in-China/cnoi-statement-generator)
  （AGPL-3.0）的 Python 重实现；编译用的模板与自由字体已落地在 `resources/cnoi/`，发行包本身不再随仓库分发。
- `resources/testlib/testlib.h` 来自 [testlib](https://github.com/MikeMirzayanov/testlib)（MIT）。
- `resources/cnoi/fonts/` 只含自由字体（Latin Modern、New Computer Modern Math、Fira Mono）；
  SimSun / SimHei / KaiTi 由系统提供，不再随仓库分发，检测方式见 [`docs/environment.md`](docs/environment.md) 的「字体」一节。
