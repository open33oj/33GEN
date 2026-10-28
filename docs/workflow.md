# 出题流程与工具链

本文件讲「按什么顺序做什么」，以及每个 `tools/*.py` 的职责。
**哪些规则在什么场景生效**见 `docs/rules.md`；这里只讲机制。

## 0. 环境

| 依赖 | 本机实测 | 说明 |
| --- | --- | --- |
| g++ | MinGW-w64 9.3.0 | 必须支持 `-std=c++14` |
| python | 3.15.2 | `python` / `python3` 都可用；需要 PyYAML |
| typst | **0.14.2** | 题面 PDF。**必须 0.14.x**：0.15 与 `@preview/mitex:0.2.5` 不兼容（实测报 `unknown variable: kai`） |
| testlib | 0.9.37 | `resources/source/testlib/testlib.h` |

```bash
python tools/setup_resources.py           # 同步 testlib / CNOI 模板与字体 / Typst 包
python tools/setup_resources.py --check   # 检查是否就绪
```

依赖从哪儿找、国内网络怎么绕过，见 `docs/environment.md`。

**本机三个坑（工具已自动绕过，但要知道）**：

1. **`libgcc_s` 缺失** → `_common.py` 在 Windows 上自动追加 `-static-libgcc`。
2. **Typst 无法自建下载包**（TLS 无凭证）→ `setup_resources.py` 预先把
   `@preview/oxifmt`、`@preview/mitex` 下载到 `resources/typst-packages/`，编译时加 `--package-path`。
3. **testlib 的换行判断**：Windows 上 `eoln()` 默认要求 CRLF → 编译时加 `-DFOR_LINUX`，
   让校验器按评测机（Linux/LF）语义工作。

中文日志乱码时先 `set PYTHONIOENCODING=utf-8`（PowerShell 用
`$env:PYTHONIOENCODING="utf-8"`）。

## 1. 目录约定

**一次任务 = 一个日期目录**（K7）。开工先建目录，之后所有东西都在里面：

```bash
python tools/new_run.py            # 建 runs/<今天>/，已存在则复用
```

```
runs/2026-10-28/
├── batch.md                      # 本批 P1–P7 的取值（首次生成模板）
├── problems/<pid>/               # 每道题
├── contests/<cid>.yaml           # 比赛配置
├── notes/                        # 对拍、草稿
└── build/                        # 本轮全部产物，可随时删
```

题目目录：

```
problems/<pid>/
├── meta.yaml                     # 标题/短名/时限/内存/标签/样例表（打包与题面都用它）
├── statement/
│   ├── zh_CN.md                  # 题面唯一事实来源
│   ├── contest.yaml              # 比赛级信息，可选
│   └── precaution.md             # 注意事项，可选
├── src/
│   ├── std.cpp                   # 标程
│   ├── 30.cpp / 60.cpp           # 可选：按目标分数命名的子任务程序
│   ├── gen.cpp                   # 数据生成器（testlib）
│   ├── valid.cpp                 # 数据校验器（testlib）
│   ├── checker.cpp               # 可选：SPJ（testlib）
│   └── interactor.cpp            # 可选：交互器（testlib）
├── data/                         # 由 build.py gen 生成，不手改、不入 git
├── hydro/
│   ├── testdata/config.yaml      # 测试点/分值/时空限制（唯一事实来源）
│   └── additional_file/          # 题面图片
└── sol.md                        # 题解
```

仓库根：

```
resources/      公共资源（setup_resources.py 从 source/ 落地，只读）
tools/          全部构建入口（python3）
docs/           规则与细节文档
runs/           每次任务一个日期目录
```

工具怎么找到当前任务目录（`_common.WORK`）：
`GEN_WORK` 环境变量 > 当前目录（含 `problems/` 或 `contests/`）> 仓库根。
所以**在日期目录里直接跑** `python ..\..\tools\build.py ...` 就会自动认到。

## 2. 一道题的标准流程

```bash
python tools/new_run.py                                # 建 runs/<日期>/（记下路径）
set GEN_WORK=runs\2026-10-28                           # 之后都在仓库根跑工具

python tools/setup_resources.py                        # 首次
xcopy /E /I problems\_template %GEN_WORK%\problems\mypid   # ① 复制模板
# ② 改 %GEN_WORK%\problems\mypid 下的 meta.yaml、statement/zh_CN.md、src/*.cpp、config.yaml
python tools/cnoi.py check --problem mypid -o build/tmp --strict   # ③ 题面方言自检
python tools/build.py all --problem mypid              # ④ 编译 + 造数 + 校验 + 查答案
python tools/cnoi.py build --problem mypid -o build/statement/mypid --preview   # ⑤ PDF
```

不想设环境变量也可以 `cd %GEN_WORK%`，然后用 `..\..\tools\build.py` 这样的相对路径调用
——`_common.py` 会按当前目录认出任务根。

`build.py all` 的四步：

| 步骤 | 做什么 | 失败条件 |
| --- | --- | --- |
| `build` | 用固定选项编译 `src/` 下所有 C++ | 编译错误或**任何警告** |
| `gen` | 对 `config.yaml` 每个测试点调用 `gen --case <点>`，再跑 `std` 得答案 | 点未声明 / 生成器没写文件 / 标程崩溃 |
| `validate` | 把每个 `.in` 从 stdin 喂给 `valid` | 任一点不合法 |
| `check` | 检查 `.ans` 存在、非空、LF、末尾换行 | 任一项不满足 |

单步：

```bash
python tools/build.py build    --problem mypid
python tools/build.py gen      --problem mypid --case a1
python tools/build.py validate --problem mypid
python tools/build.py list     --problem mypid      # 列出测试点并核对 gen 声明
python tools/build.py clean    --problem mypid
```

`list` 会逐个标出「是否已在 gen.cpp 声明」；`config.yaml` 的测试点名与 `gen --list`
的输出必须完全一致，否则 `gen` 直接报错。

## 3. `gen.cpp` 契约

- 入口 `registerGen(argc, argv, 1);`，第三参固定 `1`。
- `build.py` 对每个点调用一次：`gen --case <测试点名>`，**工作目录是 `data/`**，
  生成器自己把输入写成 `<测试点名>.in`。
- 测试点名 = `config.yaml` 里该点 `input` 去掉 `.in`。
- 建议实现 `--list`（每行一个点名），`build.py list` 与 `contest_check.py` 用它核对。
- `--stdout` 把数据打到终端（不写文件，调试用）。
- `--seed <n>` 覆盖 seed，**只给大样例用**（见 `docs/rules.md` M3）。

`CASES` 表写在 `gen.cpp` 里（不写进 `config.yaml`）：

```cpp
struct GenCase
{
    const char *name;   // 必须与 config.yaml 里 input 去掉 .in 后一致
    long long seed;     // 一经确定不要再改；各测试点用不同值
    long long maxv;     // 本测试点的规模，对应题面的子任务
    const char *kind;   // random / max / equal ...
};

static const GenCase CASES[] = {
    {"a1", 0x5EED0001LL, 10LL, "random"},
    {"a2", 0x5EED0002LL, 10LL, "max"},
};
```

要点：

- **seed 是唯一随机性来源**：`rnd.setSeed(c->seed)`；禁 `time(0)` / `random_device` / `std::chrono`。
- 改 seed 就等于换数据，定稿后别再动；`selftest.py` 用「删数据重生成、逐字节比对」验证。
- 规模与特殊性质都在同一张表里，一份表读完就知道每个点在测什么。
- 每个测试点必须在表里有一行（否则 `--list` 对不上）。
- 写文件用 `fopen(..., "wb")`：Windows 上 `"w"` 会把 `\n` 写成 `\r\n`，
  `build.py` 虽会自动归一化并告警，但生成器自己写对更稳。

## 4. 校验与答案

### 4.1 `valid.cpp`（testlib）

- 入口 `registerValidation(argc, argv);`
- **从 stdin 读**：`valid < a1.in`。testlib 校验器不接受文件名参数，传了也仍读 stdin。
- 读取函数必须带范围，错误信息交给 testlib：

| 用途 | 函数 |
| --- | --- |
| 一个整数并校验范围 | `inf.readInt(minn, maxn, "n")` |
| 一行 n 个整数（跨过任意空白） | `inf.readInts(n, minn, maxn, "a")` |
| 64 位整数 | `inf.readLong(...)` |
| 实数 | `inf.readDouble(...)` |
| token / 整行 | `inf.readToken("[a-z]{1,10}", "s")` / `inf.readLine(...)` |
| 空格 / 行尾 / 文件尾 | `inf.readSpace()` / `inf.readEoln()` / `inf.readEof()` |

- **最后必须 `inf.readEof()`**，卡住多余内容（最常漏的一条）。
- 分隔空白用 `readInts`，**不要** `readSpace()`（要求恰好一个空格）。
- 读到的值必须用掉，否则 `-Wall` 报 unused；可用 `ensuref` 引用并补充断言：
  `ensuref(x <= y, "x > y at i = %d: x = %d, y = %d", i, x, y);`
- 校验器按**题面**写，不抄生成器的判断；不得因数据「难看/太大」报错；
  不得按测试点名放宽（数据必须整体合法）。
- 全量校验：`python tools/build.py validate --problem <pid>`。

### 4.2 答案从哪来

- **传统题**：`build.py` 用 `src/std.cpp` 跑每个 `.in` 得到 `.ans`。
  写了 `filename: foo` 时，会在临时目录里以 `foo.in` / `foo.out` 的文件 IO 方式运行，
  产物按 LF 归一化后收进 `data/`。
- **`.ans` 规范**：非空、LF、末尾有换行；CRLF 会被 `build.py` 归一化并告警。
- **SPJ**：仍然用 `std.cpp` 生成 `.ans` 作参照答案（checker 判的是选手答案相对输入是否合法），
  这样「标程能跑通全部数据」仍是硬检查。
- `build.py check` 会用 `checker <in> <ans> <ans>` **自校** checker，必须判 `ok`。
- **交互题**没有 `.ans`，由 `interactor.cpp` 负责。

## 5. 打包

```bash
python tools/samples.py      --problem mypid     # 下发样例 -> problems/<pid>/data/samples/
python tools/cnoi.py build   --problem mypid -o build/statement/mypid --preview
python tools/cnoi.py build   --contest <cid> -o build/contests/<cid>          # 整场合并试题
python tools/pack_hydro.py   --problem mypid     # build/hydro/<hydro_pid>.zip
python tools/pack_hydro.py   --day d1            # 场次包：解压后直接是各题文件夹
python tools/pack_hydro.py   --batch 名称 --problem a --problem b             # 批量包
python tools/pack_lemon.py   --contest <cid>     # build/lemon/<cid>/
```

- `pack_hydro.py` 的题号取自 `meta.yaml` 的 `hydro_pid`；场次/批量的题目清单来自
  `contests/*.yaml` 与 `--problem`，工具里没有第二份名单。
- 打包时会自动：样例改 ` ```inputk ` / ` ```outputk `、大样例改 `file://` 链接并放进
  `additional_file/`、末尾补「## 子任务」小节。
- `pack_lemon.py` 输出 `.cdf` + `data/<短名>/` + `down/`（整场 PDF + 每题样例），
  缺数据或缺样例时直接报错并提示该跑哪条命令。

## 6. 验收清单

```bash
python tools/build.py list --problem <pid>     # 每个点都 [gen.cpp 已声明]
python tools/build.py all  --problem <pid>     # 全绿：零警告、校验全过、答案规范
python tools/build.py gen  --problem <pid>     # 再跑一次，data/ 逐字节不变
python tools/cnoi.py check --problem <pid> -o build/tmp --strict
python tools/cnoi.py build --problem <pid> -o build/statement/<pid> --preview
python tools/samples.py --problem <pid>        # 顺带验题面小样例的输出
python tools/data_strength.py <pid>            # 规模与答案分布，0 处需人工确认
python tools/score_solution.py --problem <pid> --source <错解>.cpp
python tools/contest_check.py                  # 整场验收（仅当时有成场比赛）
```

外加人工抽查：

- [ ] PDF 里的样例与 `data/` 一致，数据范围表与 `valid.cpp` 一致，时限/内存与 `config.yaml` 一致。
- [ ] 两个包都能产出，且人工看过内容。
- [ ] `build/` 没被打进任何对外交付物。
- [ ] `runs/` 已被 `.gitignore` 忽略（任务目录不进库）。

## 7. 对拍（强烈建议）

1. 另写 `brute.cpp`（**不进最终交付**，可放 `problems/<pid>/notes/`）；
2. 在 `CASES` 表里临时加小规模点，或让 `gen.cpp` 支持 `--case small1`；
3. 比较 `std` 与 `brute` 的输出，不一致就停下来查。

暴力程序同样要遵守 `docs/style.md` 的编译选项与风格。

## 8. 工具一览

| 工具 | 作用 |
| --- | --- |
| `new_run.py` | 建立 `runs/<日期>/` 任务目录（`problems/`、`contests/`、`notes/`、`build/` + `batch.md` 模板） |
| `setup_resources.py` | 把 `resources/source/` 落地成 testlib / CNOI 模板与字体，并下载 Typst 包 |
| `build.py` | 编译、造数、校验、检查答案（编译零警告才算过） |
| `samples.py` | 下发样例：题面小样例 + 满规模大样例 |
| `cnoi.py` | 题面工具：`build` / `convert` / `check` / `info` |
| `pack_hydro.py` | 导出 Hydro 题包（单题 / `--day` / `--batch`） |
| `pack_lemon.py` | 导出 LemonLime 包（`data/` + `down/`） |
| `selftest.py` | 工具链自检（依赖 `problems/_template`） |
| `contest_check.py` | 比赛级验收（依赖 `contests/*.yaml`） |
| `data_strength.py` | 逐测试点摊开规模与答案分布 |
| `score_solution.py` | 给一份代码按点打分 |
| `_common.py` | 公共库：路径、编译选项、题目解析（不直接调用） |

## 9. 字体

- 仓库只带模板需要的**自由字体**（Latin Modern、New Computer Modern Math、Fira Mono，
  共 12 个文件，约 4 MB），在 `resources/cnoi/fonts/`。
- **SimSun / SimHei / KaiTi 是商业字体，不随仓库分发**：出 PDF 时由 Typst 从系统字体读取。
  Windows 一般自带这三个；Linux 需要自己装，否则 PDF 缺字。
- 检测：`python tools/setup_resources.py --check` 会用 `typst fonts` 查这三个家族，
  缺失时打 `[warn]`（仓库本来就不带，所以不影响退出码）。
- 想自带或换开源字体：放进 `resources/cnoi/fonts/`，或走 `STAGE_PATCHES` 改家族名；
  具体见 `docs/environment.md` 的「字体」一节。