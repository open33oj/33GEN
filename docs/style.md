# C++ 代码风格规范

本规范由 **8 份风格样本**归纳而来，样本存放在
`resources/source/style/`（原始文件名 `foo (1).cc` ~ `foo (8).cc`，
文件名的对照见该目录的 `README.md`）。所有 C++ 代码——标程 `std.cpp`、
子任务程序（`30.cpp`、`60.cpp`）、数据生成器 `gen.cpp`、校验器 `valid.cpp`、
交互器 `interactor.cpp`、checker `checker.cpp`——都必须遵守。

> 样本里存在少量互相矛盾的写法（尤其见 §8）。
> 本文档是**唯一标准**：以本文档为准，不要模仿样本中的反例。

## 1. 编译

固定使用以下选项，不允许添加其他优化/警告开关：

```bash
g++ -std=c++14 -O2 -Wall
```

- 语言标准必须是 C++14。不要使用 C++17 及以上的语法
  （结构化绑定 `auto [a, b]`、`std::optional`、`std::string_view`、
  模板参数推导 `std::pair p{1, 2}`、`if constexpr` 等一律禁止）。
- `-O2` 必须带上，标程的常数复杂度结论依赖它。
- `-Wall` 产生的警告必须清零；有意的未使用变量用 `(void)x;` 而不是 `-Wno-*`。
- 编译 testlib 程序时额外加 `-I resources/testlib`（见 `docs/workflow.md`）。

## 2. 文件骨架

```cpp
#include <bits/stdc++.h>
using namespace std;
const int MAXN = 100000;
const int MOD = 998244353;
int n;
int a[MAXN + 5];
int main()
{
    // ...
    return 0;
}
```

- 只写一个 `#include <bits/stdc++.h>`（8 份样本全部如此），
  不要逐个 include 标准库头文件。
- 紧随其后写 `using namespace std;`。代码中不要再写 `std::` 前缀。
- 文件开头**不写**作者、日期、题意等头注释；仅在算法不直观处写注释（§7）。
- `main` 必须显式 `return 0;`（`03-combination-factorize.cc` / `05-mod-pair-count.cc` 漏写，属于反例）。

## 3. 缩进与空白

- 缩进 **4 个空格**。禁止 Tab。
- 行尾不留空格；文件末尾保留且只保留一个换行；不留连续空行（最多一个空行）。
- 运算符两侧各一个空格：`a + b`、`x <= n`、`ans = max(ans, x)`。
- 逗号后一个空格，分号前不留空格：`f(i, j)`；`for (int i = 1; i <= n; i++)`。
- 函数调用的括号前不留空格：`work(i)`；
  关键字与括号之间留一个空格：`if (...)`、`for (...)`、`while (...)`、`switch (...)`。
- 二元运算符与 `1LL` 的乘法写成 `1LL * ans * i % MOD`。
- `abs`、`max`、`min`、`sort` 直接用（有 `using namespace std;`），不写 `std::`。

## 4. 花括号

Allman 风格：**左花括号独占一行**，且所有控制语句与函数都带花括号。

```cpp
struct Edge
{
    int v, l, t;
};
void work(int ed)
{
    while (!pq.empty())
        pq.pop();
    if (vis[now] == visNow)
        continue;
}
int main()
{
    return 0;
}
```

- 单语句的 `if` / `for` / `while` 可以省略花括号（8 份样本中普遍如此），
  但**只要分支体不是紧邻的下一行唯一语句，就必须补花括号**：
  - 允许：`if (x) continue;` 写成
    ```cpp
    if (vis[now] == visNow)
        continue;
    ```
  - 必须加花括号：`else` 分支、嵌套分支、多行语句体。
- `struct` / `class` / `enum` 的左花括号同样独占一行。
- 不要写 `};` 之外的紧凑形式（`int main() { ... }` 禁止）。

## 5. 命名

| 种类 | 规则 | 示例 |
| --- | --- | --- |
| 常量 | 全大写下划线 | `MAXN`、`MAXM`、`MOD`、`INF` |
| 变量 | 小驼峰 / 全小写 | `minTim`、`ansTim`、`posA`、`visNow`、`n`、`m`、`q` |
| 函数 | 小驼峰 / 全小写 | `work`、`dfs`、`cmp` |
| 结构体 | 大驼峰 | `Edge`、`Node` |
| 容器 | 按内容命名，避免 `vec`、`tmp` 之类无意义名 | `best`、`temp`、`e` |

- 下标/计数变量沿用竞赛惯例：`n`、`m`、`q`、`i`、`j`、`tot`、`cnt`。
- 一个字母的变量只允许用于循环下标与题面同名变量；
  其余变量含义必须能从名字读出（`minTim[x][y]` 表示从 `x` 到 `y` 的最晚出发时间）。
- 不要用 `#define int long long`；需要 64 位时显式使用 `long long`。

## 6. 数组与常量

- 数组大小写成 `MAXN + 5` 形式，并定义 `const int MAXN = ...;`，
  不要出现裸魔法数字：`int a[MAXN + 5];`、`int cnt[3 * MAXN + 2 + 5];`。
- 下标统一从 1 开始使用，第 0 位留作哨兵/边界。
- 极值常量写成 `const int INF = 100000 + 10000 + 1;` 这类**算式形式**，
  便于看出与数据范围的关系；不要写 `0x3f3f3f3f`。
- C++14 支持数字分隔符 `'`，大数可写成 `3'000'000'000'000`（`08-knapsack-dp.cc` 用法），
  但保持全文件一致。
- 内存估算必须留出余量：数组规模按最大数据范围 × 常数 计算，
  不确定时用 `vector` 并在运行时 `resize`。

## 7. 注释

- 注释使用 `//`，中文，写在被注释对象的上方或行尾，与代码之间至少一个空格。
- 变量声明处必须解释其含义：
  ```cpp
  int minTim[MAXN + 5][MAXN + 5]; // minTim[x][y] 从 x 到 y 的最晚出发时间
  int visNow = 0, vis[MAXN + 5];  // 如果 vis[i] == visNow 表示真，否则表示假
  ```
- 关键步骤前写一句话说明这一步在做什么，例如 `// 离散化`、`// 预处理 minTim`。
- **不要提交调试代码**：`cout << "ok:" << xTim << "\n";` 这类语句必须删除，
  不要用注释保留（`02-matching-greedy.cc` 中被注释掉的调试输出属于反例）。

## 8. 需要统一的分歧点

8 份样本中写法不一致之处，按本表统一：

| 项目 | 统一标准 | 反例（样本文件） |
| --- | --- | --- |
| `#include` 后空格 | `#include <bits/stdc++.h>` 留一个空格 | `04-circular-shift.cc`：`#include<bits/stdc++.h>` |
| 文件末尾换行 | 必须有，且只有一个 | `03-combination-factorize.cc`：`cout << ans;` 后无换行 |
| `main` 返回值 | 必须 `return 0;` | `03-combination-factorize.cc`、`05-mod-pair-count.cc` |
| `ios::sync_with_stdio` | 输入规模可达 $10^5$ 及以上、或使用 `cin`/`cout` 的一律加上 `ios::sync_with_stdio(false); cin.tie(0);`（缩进 4 空格） | `02-matching-greedy.cc`、`05-mod-pair-count.cc` 未加 |
| 缩进 | 只用 4 空格 | `04-circular-shift.cc` 混用 Tab |
| 运算符空格 | 二元运算符两侧一个空格 | `04-circular-shift.cc`：`cin>>n`、`posA-1` |
| Tab 后残留空格 | 禁止 | `04-circular-shift.cc` 第 11、14、22 行 |
| 调试输出 | 必须删除 | `02-matching-greedy.cc` 注释掉的 `cout` |

样本的完整对照（含每份样本体现的正/反例）见 `resources/source/style/README.md`。

## 9. 生成器 / 校验器 / 交互器 / checker 的额外要求

这几类程序必须使用 testlib（见 `docs/workflow.md`），并遵守：

- `gen.cpp`
  - 入口固定为 `int main(int argc, char *argv[])`，第一行调用 `registerGen(argc, argv, 1);`
    （第三个参数固定为 `1`，锁定随机行为版本，保证可复现）。
  - 所有随机性来自 `rnd`；**任何**种子与规模参数都通过命令行参数传入，
    禁止使用 `time(0)`、`random_device`、`std::chrono` 等不可复现来源。
  - 生成函数拆分为 `void genCase(int n, int m, ...)` 之类的子函数，`main` 只做参数解析与分发。
  - 输出量大的（$>10^6$ 字节）用 `printf` 或 `std::string` 拼接后一次性输出。
- `valid.cpp`
  - `registerValidation(argc, argv);`；用 `readInt(l, r, "n")` 等带范围参数的形式读取，
    让 testlib 负责报错，不要自己写 `if` + `cerr`。
  - 必须校验题面声明的每一条约束，以及跨变量的一致性约束。
- `interactor.cpp`
  - `registerInteraction(argc, argv);`；选手输出、标准答案、输入分别用
    `ouf`、`ans`、`inf` 读取，判定用 `quitf(...)`。
- `checker.cpp`
  - `registerTestlibCmd(argc, argv);`；
    只使用 `_ok` / `_wa` / `_pe` / `_fail` / `_points`（后者需在题面写明部分分规则），
    不要 `return 0/1/2` 这种魔法退出码。

## 10. 提交前自查清单

- [ ] `g++ -std=c++14 -O2 -Wall` 编译零警告（含 testlib 程序）。
- [ ] 无 Tab、无行尾空格、文件以单个换行结尾。
- [ ] 无调试输出、无注释掉的废代码。
- [ ] 数组大小按最大范围计算且带 `+5` 余量，没有越界风险。
- [ ] `int` 溢出检查：出现 `n * m`、`a * b`、求和、计数时确认是否要 `long long` / `1LL`。
- [ ] 变量名与注释能让人不看题面读懂 `minTim`、`cntP` 这类核心数组的含义。
