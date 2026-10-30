# 题面（CNOI 风格）

题面的最终产物是 **CNOI 风格 PDF**，同一份 Markdown 也作为 Hydro 题面。
规则层见 `docs/rules.md`（M9 题面基线、D3 PDF、P1/P7 批次参数）。

## 1. 文件与产物

| 文件 | 位置 | 说明 |
| --- | --- | --- |
| 题面源文件 | `problems/<pid>/statement/zh_CN.md` | 唯一事实来源 |
| 英文题面（可选） | `problems/<pid>/statement/en_US.md` | **不做就不要留空文件** |
| 注意事项（可选） | `problems/<pid>/statement/precaution.md` | 不给就用内置通用模板 |
| 题解 | `problems/<pid>/sol.md` | 同时用于 PDF 与 Hydro |
| Hydro 题面 | 包内 `problem_zh.md` | 打包时自动生成，**不要手改** |
| 样例 | `problems/<pid>/data/samples/` | `<短名><编号>.in/.ans`，由 `samples.py` 生成 |

## 2. 章节顺序（强制）

缺少的章节直接省略，不要留占位符；**没有「题目背景」这一节**。

1. **题目描述** —— 完整、无歧义、简洁；公式用 LaTeX，变量用行内公式 `$n$`。
2. **输入格式** —— 按输入顺序逐行描述，每段能对应到输入文件的一部分。
3. **输出格式** —— 说明输出内容、格式与换行要求。
4. **样例** —— 每个样例先输入后输出，编号从 1 开始。
5. **样例解释**（可选）—— 仅当样例不足以自明时给出。
6. **数据范围** —— 用表格给出子任务/测试点、分值、范围、特殊性质。
7. **提示**（可选）—— 只写读入/格式/判分说明。
8. **子任务** —— 由 `config.yaml` 自动生成（见 §3.9），一般不用手写。

## 3. 写作要求（M9 基线，任何题面都适用）

1. **范围闭合**：写了 `$1 \le n \le 10^5$`，所有测试点就必须满足；`valid.cpp` 按题面校验。
2. **样例与数据一致**：题面样例必须能过 `valid`，答案与 `std` 一致。
3. **不出现内部信息**：不得出现测试点编号、「卡常」「骗分」、std 的做法提示。
4. **不剧透**：
   - `## 提示` 只写读入方式、文件/输出格式、判分方式（如 SPJ「答案不唯一」）；
     禁止「策略 / 贪心 / 二分 / 单调 / 性质 / 结论 / 只取决于 / 复杂度 / 不变量 / 溢出 / 注意到」。
   - `## 样例 k 解释` 只解释**给出的输出为什么正确**：可解时列出方案，
     不可解时只写「不存在满足条件的方案」，**不要**解释为什么无解、为什么最优。
5. **下标与含义显式声明**：如「下标从 1 开始」。
6. **字符集声明**：涉及字符串时写明大小写/数字/可见字符，以及是否含空格。
7. **多组数据**（启用 M7 时）：写明 `T` 的范围与「所有测试用例的 `n` 之和」。
8. **位运算**：必须解释规则并给出 C++ 运算符，例如「按位异或：二进制逐位比较，
   相同得 0、不同得 1；C++ 中写作 `^`」。与/或/移位同理（`&`、`|`、`<<`、`>>`）。
9. **子任务表不手写**：由 `tools/_common.py` 的 `subtask_table()` 从 `config.yaml` 生成，
   PDF 与 Hydro 共用同一份；题面里已经出现「子任务」字样时，工具不再追加。
   最后一列是「特殊性质」，不是「特殊限制」：`name` 要写精确的性质或限制；
   表示“存在”时写「至少含一个空格」这类说法，不要只写「含空格」；没有特殊性质就写「无特殊性质」。
10. **公式与符号**：`$...$` / `$$...$$`；乘号写 `\times`；下取整 `\lfloor \cdot \rfloor`；
    不用 `\(...\)`。

### 3.1 按模块补充

| 模块 | 题面里必须写 |
| --- | --- |
| M1 文件 IO | 「输入格式」第一句：「从文件 `<短名>.in` 读入数据。」；「输出格式」第一句：「输出到文件 `<短名>.out`。」 |
| M3 大样例 | 小样例之后：「`## 样例 k`」+「见选手目录下的 `<短名>/<短名>k.in` 与 `<短名>/<短名>k.ans`。」（`k` 从小样例数 +1 连续） |
| M4 SPJ | 「答案不唯一」+ 判定标准；浮点要写误差口径（与 checker 一致） |
| M6 交互 | 交互方式 + flush 要求，与 `interactor.cpp` 逐条对应 |
| M7 多组数据 | `T` 的范围与 Σ 限制 |

### 3.2 样例编号

- 源文件里只用「`## 样例 k 输入`」/「`## 样例 k 输出`」+ 紧跟一个普通代码块
  （1~6 级标题都认，同级即可）。
- **不要手写** Hydro 的 ` ```inputk ` / ` ```outputk `，打包时自动转换。
- 编号从 1 开始，与 `data/samples/` 一一对应。

## 4. Markdown 方言

模板是 `remark-parse + remark-gfm + remark-math + remark-directive` 方言，
与 Hydro 的 Markdown 不完全一致。

### 4.1 支持

| 写法 | 效果 |
| --- | --- |
| `## 小节名` | CNOI 的【小节名】；**全文只用二级标题** |
| 普通段落 | 自动首行缩进 |
| `**加粗**` / `*斜体*` / `~~删除~~` | 加粗渲染为黑体 + 波浪线 |
| `` `code` `` / ` ```cpp ` | 等宽 / 带行号与边框的代码块 |
| `$a_i$` / `$$...$$` | mitex 转 Typst 数学 |
| `- ` / `1. ` | 列表，最多 3 层 |
| GFM 表格 | 见 §4.2 |
| `![说明](x.png){width=50%}` | 图片，尺寸只支持相对单位 |
| `:::figure{caption="..."}` | 图注容器 |
| `[^1]` + `[^1]: …` | 脚注 |
| `---` | 分隔线 |

### 4.2 表格合并

- `^`（整格只有 `^`）：与**正上方**单元格纵向合并。
- `<`（整格只有 `<`）：与**左边**单元格横向合并。

### 4.3 图片

属性写在图片后的花括号里，只支持相对单位（`pt`/`mm`/`cm`/`in`/`em`/`%`）。
绝对像素会被静默丢弃。图片放 `hydro/additional_file/`，题面写
`![说明](file://x.png)`，PDF 源文件用相对路径 `../hydro/additional_file/x.png`。

### 4.4 不支持 / 会报错

- HTML 标签（会被当成行内代码显示）。
- YAML front matter（被忽略，元信息写 `meta.yaml`）。
- 参考式链接/图片（`[x][id]`）。
- 嵌套引用块、超过 3 层的嵌套列表。
- 代码块里单行超过 **63 列**（上游模板硬限制，直接报错）。
- Hydro 的 ` ```inputk ` 围栏（PDF 里只是普通代码块，打包时才需要）。

## 5. 骨架

````markdown
## 题目描述

……

## 输入格式

从文件 `foo.in` 读入数据。

## 输出格式

输出到文件 `foo.out`。

## 样例 1 输入

```
1 2
```

## 样例 1 输出

```
3
```

## 样例 1 解释

……

## 样例 2

见选手目录下的 `foo/foo2.in` 与 `foo/foo2.ans`。

## 数据范围

对于所有测试数据，保证 $1 \le n \le 10^5$。

| 测试点 | $n \le$ | 特殊性质 |
| :----: | :-----: | :------: |
|  $1$   |  $10$   |    无    |

## 提示

……
````

`foo` 一律换成该题的英文短名，与 `config.yaml` 的 `filename`、封面表格的输入输出文件名一致。

## 6. 题解 `sol.md`

结构：**思路 → 算法/复杂度 → 实现要点 → 完整代码**。

- 至少一份完整可编译的参考实现，**与 `std.cpp` 逻辑一致**（文件 IO 题也要有 `freopen`）；
- 写明时间/空间复杂度，卡常时给常数优化建议；
- 有子任务时说明各档得分策略；
- 不得包含测试点答案表（答案放 `problems/<pid>/notes/answers.md`，不打包）。

## 7. PDF 编译

```bash
python tools/cnoi.py build --problem <pid> -o build/statement/<pid> --preview
python tools/cnoi.py check --problem <pid> -o build/tmp --strict   # 只校验方言
```

选项：`--out`（必填）、`--problem` 或 markdown 路径、`--title/--name/--subtitle/--day`、
`--no-compile`、`--preview`、`--ppi`、`--pages-from/--pages-to`、`--strict`、
`--resource-dir`、`-v`。

产物：

```
<out>/
├── statement.pdf
├── preview/page-*.png
└── typst/                 # 完整 Typst 工程
    ├── content.json       # 可直接导入网页版生成器
    └── problem-0.md / problem-0.typ / main.typ …
```

实际执行的核心命令：

```bash
typst compile --font-path resources/cnoi/fonts --font-path <系统字体目录> \
  --package-path resources/typst-packages --root <仓库根> \
  build/statement/<pid>/typst/main.typ build/statement/<pid>/statement.pdf
```

- `--package-path` **必须**：模板依赖 `@preview/oxifmt` 与 `@preview/mitex`。
- `--root` 要包含题面引用的资源（工具会自动选）。
- 中文字体用系统字体（仓库只带自由字体），详见 `docs/workflow.md` §9。

返回码：`0` 成功 / `1` 参数或校验问题 / `2` Markdown 解析失败 / `3` Typst 编译失败。

排错：

| 现象 | 处理 |
| --- | --- |
| 找不到 `typst` | 安装 0.14+ 并加入 PATH |
| `failed to download package` | 跑 `setup_resources.py` |
| `unknown font family` | 用本工具跑，会自动带 `--font-path` |
| `source file must be contained in project root` | 图片路径超出 `--root`，用 `--resource-dir` |
| `label <...> does not exist` | 正文有未转义的 `@`（工具已自动转义） |
| 中文乱码 | `set PYTHONIOENCODING=utf-8` |

## 8. `check` 规则

**错误（返回码 1）**：代码围栏未闭合、`$$` 数量为奇数、代码块行宽 >63 列、
`:::` 容器未闭合。

**警告（`--strict` 时升级为错误）**：没有 `## 题目描述` / 没有二级标题、
图片尺寸不是相对单位、行内 `$` 数量为奇数、出现 HTML 标签、开头有 YAML front matter、
脚注引用了未定义标签。

## 9. 上游与差异

上游 [cnoi-statement-generator](https://github.com/Mr-Python-in-China/cnoi-statement-generator)
是浏览器端应用；本工程用 Python 重实现了它的编译器（`tools/cnoi/`），
共用同一套 Typst 模板与 Markdown 方言。有意差异：

| 项目 | 上游 | 本工具 |
| --- | --- | --- |
| 运行形态 | 浏览器 SPA | 命令行，调用本机 Typst |
| 正文转义 | 不转义 `@` | **额外转义 `@`**（否则 `CPU @3.70GHz` 报错） |
| 列表嵌套 | 任意深度 | 最多 3 层 |
| 引用块 | 支持嵌套 | 只支持单层 |
| 参考式链接 | 支持 | 不支持 |

上游模板是第三方快照（`resources/cnoi/`），**不得直接改**；
版式改动走 `tools/cnoi/cli.py` 的 `STAGE_PATCHES`（每个补丁必须恰好命中一次）。
