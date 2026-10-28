# 加法练习 · 题解

## 思路

直接读入两个整数并输出它们的和。

## 算法 / 复杂度

一次加法，时间复杂度 $O(1)$，空间复杂度 $O(1)$。

## 实现要点

- $a + b$ 最大为 $2 \times 10^9$，超过 `int` 的安全范围时可以开 `long long`。
- 标准 IO，直接 `scanf` / `printf`。

## 参考实现

```cpp
#include <bits/stdc++.h>
using namespace std;

int main()
{
    long long a, b;
    scanf("%lld%lld", &a, &b);
    printf("%lld\n", a + b);
    return 0;
}
```

## 子任务说明

- 子任务 1（30 分）：$a, b \le 10$；
- 子任务 2（30 分）：$a, b \le 10^5$；
- 子任务 3（40 分）：$a, b \le 10^9$。

## 数据设计说明

每个子任务都包含最小值（$0$）、最大值、两数相等与随机数据。
