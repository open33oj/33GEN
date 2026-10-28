# 交付格式：Hydro / LemonLime / SPJ

本文件是**格式与平台事实**的查表手册；规则层见 `docs/rules.md`（D1/D2/M4/M5）。

## 1. Hydro 题包

### 1.1 压缩包结构

顶层必须只有一个文件夹（名字用 `hydro_pid`）：

```
<hydro_pid>/
├── problem.yaml
├── problem_zh.md
├── testdata/
│   ├── config.yaml
│   ├── a1.in  a1.ans
│   ├── std.cc  gen.cc  valid.cc  [checker.cc]  [interactor.cc]
│   └── sol.md
└── additional_file/          # 图片、大样例
```

`problem.yaml`：

```yaml
title: 题目名      # 必填
tag:               # 可选
  - 标签
pid: C0141         # 字母 + 数字，不能全为数字
```

### 1.2 `testdata/config.yaml`

```yaml
type: default          # default / objective / interactive
time: 1s
memory: 128m
filename: foo          # 文件 IO 时写；标准 IO 删掉本项
checker_type: default  # 见 §1.3
checker: checker.cc    # checker_type 不是 default/strict 时必填
interactor: interactor.cc   # 交互题

subtasks:
  - score: 30
    type: sum          # sum = 按测试点给分；min = 整档全对才给分
    time: 1s
    memory: 64m
    cases:
      - input: t01.in
        output: t01.ans
```

- 优先级：测试点 > 子任务 > 题目 `config.yaml`。
- `CASES` 已废弃，只用 `SUBTASKS`。
- `input` 去掉 `.in` 必须等于 `gen.cpp` 里声明的测试点名。
- **不在 `config.yaml` 里写 seed 与规模**（那是 `gen.cpp` 的 `CASES` 表，见 `docs/workflow.md` §3）。
- 测试点命名要含数字（`t01.in` 可以，`sample.in` 不会被自动识别）。

### 1.3 `checker_type`（已核对 Hydro 源码）

| 取值 | 需要 checker 文件 | 语义 |
| --- | --- | --- |
| `default` | 否 | 逐行比对，忽略行末空格与末尾空行 |
| `strict` | 否 | 不忽略行末空格与空行 |
| `testlib` | **是** | 运行自写 testlib checker（推荐） |
| `hustoj` / `lemon` / `qduoj` / `syzoj` / `kattis` | 是 | 兼容对应评测系统接口 |

- 官方文档里的 `ccr` / `cena` 在源码中**不存在**，写了会报 `Unknown checker type`。
- `rcmp6` / `rcmp9` **不是** `checker_type`；它们是 testlib 的示例 checker，
  要用只能整份上传成 `checker.cpp` 再配 `testlib`。
- 非 `default` / `strict` 必须提供 checker 文件，否则报 `You did not specify a checker.`。
- Hydro 自动注入 `testlib.h`，**不需要**打包 testlib。

### 1.4 打包时自动做的事

`tools/pack_hydro.py` 会：

1. 把题面里的 `## 样例 k 输入/输出` 转成 ` ```inputk ` / ` ```outputk `；
2. 把「见选手目录下的 …」改写成 `additional_file/` 的 `file://` 下载链接，并复制文件；
3. 在题面末尾按 `config.yaml` 的 `subtasks` 补「## 子任务」小节（题面已有「子任务」字样时跳过）；
4. 把 `std/gen/valid/checker/interactor.cpp` 改名为 `.cc` 放进 `testdata/`，并同步 `config.yaml`。

### 1.5 导出命令

```bash
python tools/pack_hydro.py --problem <pid>                 # 单题 -> build/hydro/<hydro_pid>.zip
python tools/pack_hydro.py --day d1                        # 场次包 -> build/hydro/d1.zip
python tools/pack_hydro.py --batch 名称 --problem a --problem b   # 批量包
```

- 单题包的顶层文件夹 = `meta.yaml` 的 `hydro_pid`。
- 场次包/批量包**解压后直接是各题文件夹**，不再套日期目录。
- 题目清单来自 `contests/*.yaml` 与 `--problem`，工具里没有第二份名单。

### 1.6 导出前自查

- [ ] 顶层只有一个文件夹，含 `problem.yaml`、`problem_zh.md`、`testdata/`。
- [ ] `pid` 不含全数字，且等于 `meta.yaml` 的 `hydro_pid`。
- [ ] 每个 `input` / `output` 都真实存在，后缀一致。
- [ ] 每个点过 `valid`，`std` 输出与 `.ans` 一致。
- [ ] SPJ / 交互的 `checker` / `interactor` 路径正确。
- [ ] 没有 `build/`、`*.exe`、`notes/`。

## 2. LemonLime 包

### 2.1 目录

```
build/lemon/<contest>/
├── <contest>.cdf
├── data/<短名>/<短名><n>.in|ans     # n = 1..测试点数
└── down/                            # 下发给选手（不是 Lemon 概念）
    ├── <比赛名>-<组别>-<场次>.pdf
    └── <短名>/<短名><k>.in|ans
```

### 2.2 `.cdf`

LemonLime 的配置是**压缩成一行的 JSON**，名为 `<名称>.cdf`；`version` 必须是 `"1.0"`。

```json
{
  "contestTitle": "demo",
  "version": "1.0",
  "tasks": [{
    "problemTitle": "aplusb",
    "sourceFileName": "aplusb",
    "inputFileName": "aplusb.in",
    "outputFileName": "aplusb.out",
    "standardInputCheck": false,
    "standardOutputCheck": false,
    "taskType": 0,
    "comparisonMode": 1,
    "specialJudge": "",
    "testCases": [{
      "fullScore": 5,
      "timeLimit": 1000,
      "memoryLimit": 256,
      "inputFiles": ["aplusb/aplusb1.in"],
      "outputFiles": ["aplusb/aplusb1.ans"]
    }]
  }]
}
```

- **没有 task 级总分**：满分 = 各测试点 `fullScore` 之和。
- `timeLimit` 毫秒、`memoryLimit` MB，都是每点设置。
- `taskType`：`0` 传统 / `1` 只测答案 / `2` 交互 / `3`~`4` 通信。
- `comparisonMode`：`0` 逐行 / `1` 忽略空格 / `2` 外部 diff / `3` 实数 / `4` Lemon SJ / `5` testlib SJ。

### 2.3 SPJ

- `comparisonMode: 5` + `specialJudge: "<短名>/checker"`（相对 `data/`）。
- 调用 `checker <input> <user_out> <answer>`，解析 **stdout**：
  `ok` 满分 / `FAIL` 评测机错误 / `partially correct (N)` N% / `points <x>`。
- 与 Hydro 共用同一份 `checker.cpp`。

### 2.4 子任务

LemonLime **没有子任务数组**：依赖靠往 `inputFiles` 塞哨兵字符串实现
（`"<n>_lemon_SUbtaskDEPENDENCE_fLAg"`）。`pack_lemon.py` 会把 `subtasks[].if` 翻译过去。

- `min` / `max` / `sum` 的语义只有 Hydro 支持；导出到 Lemon 一律按「每点独立给分」，
  打包报告里会提示，**分值需人工确认**。

### 2.5 `down/`

- 放**整场合并**的完整试题 PDF（不是每题分开）+ 每题一个文件夹的样例。
- 不得出现标程、生成器、完整测试数据、答案表。
- 样例来自 `problems/<pid>/data/samples/`，由 `tools/samples.py` 生成。

## 3. SPJ / `checker.cpp`

### 3.1 骨架

```cpp
#include "testlib.h"
using namespace std;

const double EPS = 1e-6;

int main(int argc, char *argv[])
{
    registerTestlibCmd(argc, argv);
    int n = inf.readInt();

    long long userAns = ouf.readLong();
    long long juryAns = ans.readLong();
    if (userAns != juryAns)
        quitf(_wa, "expected %lld, found %lld", juryAns, userAns);

    if (!ouf.seekEof())
        quitf(_wa, "extra output after the answer");

    quitf(_ok, "answer is correct");
}
```

### 3.2 要点

- 三个流：`inf`（输入）、`ouf`（选手输出）、`ans`（标准答案）；**不要**用 `ans` 读输入。
- 用 `ouf.readInt(...)` 等带范围读取，格式错误由 testlib 变成 `_pe`/`_wa`。
- 结尾 `ouf.seekEof()` 卡多余输出。
- 只用 `quitf(_ok/_wa/_pe/_fail)` 与 `quitp(ratio, ...)`，**禁止** `return 0/1/2`。
- 浮点比较用 `doubleCompare(jury, user, EPS)`，不要手写 `abs(a-b)<eps`。
- 判定逻辑必须与题面写明的标准逐条对应。
- 构建期会自校：`checker <in> <ans> <ans>` 必须判 `ok`。

### 3.3 两平台接口

| 平台 | 配置 | 调用 | 判定来源 |
| --- | --- | --- | --- |
| Hydro | `checker_type: testlib`、`checker: checker.cc` | `checker <in> <user_out> <ans>` | **stderr** |
| LemonLime | `comparisonMode: 5`、`specialJudge: "<dir>/checker"` | 同上 | **stdout** |

Hydro 的 stderr 前缀：`ok ` / `wrong answer ` / `wrong output format ` /
`partially correct (p)`（得 `floor(full*p)`）/ `points p`。

### 3.4 实数

`rcmpN` 的 `N` 是误差指数（`EPS = 1E-N`），判定为绝对误差或相对误差 ≤ EPS。
它按 token 逐个比较，**选手多输出不会被发现**——要求「恰好 k 个数」时自写 checker 卡 `seekEof()`。

## 4. 平台事实速查

| 事实 | 值 |
| --- | --- |
| Hydro `checker_type` | `default` / `strict` / `testlib` / `hustoj` / `lemon` / `qduoj` / `syzoj` / `kattis` |
| Hydro `subtasks[].type` | `min` 整档全对才给分；`max` 取最好；`sum` 按点累加 |
| Hydro 时空写法 | `1s` / `0.5s` / `256m` / `1.5s` |
| LemonLime 配置 | `<名称>.cdf`（JSON），不是 `lemon.conf` |
| LemonLime 时间/内存 | 毫秒 / MB，按测试点设置 |
| LemonLime 依赖哨兵 | `"<n>_lemon_SUbtaskDEPENDENCE_fLAg"` 放进 `inputFiles` |
| 官方文档提到但源码没有的 | `ccr`、`cena`（写 `checker_type` 会报错） |
| testlib 示例 checker | `rcmp4/6/9.cpp`，是文件不是类型 |
