# 风格样本（原样保留）

这 8 份 `.cc` 是本工程的**风格原始样本**：`docs/style.md` 里的每一条规范都是从它们归纳出来的。
它们由出题人在建仓时提供（原文件名是 `foo (1).cc` ~ `foo (8).cc`），
内容一字未改，只改了文件名以便检索。

| 文件 | 原文件 | 内容 | 主要体现的风格点 |
| --- | --- | --- | --- |
| `01-circuit-timetable.cc` | `foo (1).cc` | 反图 Dijkstra 预处理「从 x 到 y 的最晚出发时间」，离线回答询问 | 多组常量、`struct Edge`、`visNow` 时间戳代替清空、行内单位注释、`priority_queue` 配对写法 |
| `02-matching-greedy.cc` | `foo (2).cc` | 按权值从大到小贪心组队，输出每组名单与最早组队时间 | `struct Node` + `sort` 配 `cmp`、注释掉的调试输出（反例）、`vector<int> ans[]` |
| `03-combination-factorize.cc` | `foo (3).cc` | 用质因数分解算组合数 `C(L, N) mod 998244353` | `const int MOD`、算法思路的分步注释；缺 `return 0;`、缺文件末尾换行（反例） |
| `04-circular-shift.cc` | `foo (4).cc` | 把两个序列里的 `1` 都搬到开头，比较是否相同 | Tab 混用、运算符不留空格、`#include` 后无空格（都是反例） |
| `05-mod-pair-count.cc` | `foo (5).cc` | 统计两数之和能被 5 整除的数对数量 | 简洁的计数函数 + 行内注释、`1LL` 防溢出；缺 `ios::sync_with_stdio` |
| `06-interval-cover.cc` | `foo (6).cc` | 离散化 + 差分，求包含定点 P 且覆盖次数最少的区间 | 完整离散化模板（复制→排序→去重→`lower_bound`）、`d[]`/`cnt[]` 前缀和注释 |
| `07-series-limit.cc` | `foo (7).cc` | 按进位规则递推，求数值收敛位置 | 数组带 `+ 100 + 5` 余量、`ios::sync_with_stdio(false); cin.tie(0);` |
| `08-knapsack-dp.cc` | `foo (8).cc` | 带位置换算成花费的背包记忆化搜索 | 数字分隔符 `3'000'000'000'000`、`const long long INF`、`dfs + 记忆化` 写法 |

## 使用方式

- **写新代码时**：读 `docs/style.md`，不要直接抄这里的反例。
- **改规范时**：这里的文件是"证据"。`docs/style.md` §8「需要统一的分歧点」逐条对应到上表。
- **不要修改这些文件**：它们是历史快照。若确认某个样本本身有 bug（不是风格问题），
  在 `docs/style.md` 里加一条说明，不要改样本。
