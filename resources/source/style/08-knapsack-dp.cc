#include <bits/stdc++.h>
using namespace std;
const long long INF = 3'000'000'000'000;
const int MAXN = 300;
const int MAXT = 200000;
// 战利品数量, 长度，截止时间
int n, D, T;
// 位置，重量，价值
int x[MAXN + 5], w[MAXN + 5], v[MAXN + 5];
// 重量和位置转换成的花费
long long c[MAXN + 5];
// 当前面临第 now 件物品，还有 T 的时间，最大总价值
long long f[MAXN + 5][MAXT + 5];
long long dfs(int now, long long T)
{
    if (T < 0)
        return -INF;
    if (now > n)
        return 0;
    if (f[now][T] != -1)
        return f[now][T];
    return f[now][T] = max(dfs(now + 1, T),
                    dfs(now + 1, T - c[now]) + v[now]);
}
int main()
{
    ios::sync_with_stdio(false);
    cin.tie(0);
    cin >> n >> D >> T;
    for (int i = 1; i <= n; i++)
        cin >> x[i] >> w[i] >> v[i];
    // 转化
    T = T - D; // 除了走到终点，还有 T 的时间
    for (int i = 1; i <= n; i++)
        c[i] = 1LL * w[i] * (D - x[i]);
    for (int i = 0; i <= n; i++)
        for (int j = 0; j <= T; j++)
            f[i][j] = -1;
    // 有 T 的时间
    // 第 i 件物品花费 c[i] 时间
    // 能得到 v[i] 的价值
    // 求最大总价值
    cout << dfs(1, T);
    return 0;
}
