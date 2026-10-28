#include <bits/stdc++.h>
using namespace std;
const int MAXN = 500;
const int MAXM = 1000;
const int INF = 100000 + 10000 + 1;
int n, m, q;
struct Edge
{
    int v, l, t; // 终点、开放时间、需要用的时间
};
vector<Edge> e[MAXN + 5];
int minTim[MAXN + 5][MAXN + 5]; // minTim[x][y] 从 x 到 y 的最晚出发时间
int visNow = 0, vis[MAXN + 5];  // 如果 vis[i] == visNow 表示真，否则表示假
// 处理从每个点走到 ed 的最晚出发时间
// <出发时间,点的编号>
priority_queue<pair<int, int>> pq;
void work(int ed)
{
    while (!pq.empty())
        pq.pop();
    visNow++;
    for (int st = 1; st <= n; st++)
        minTim[st][ed] = -1;
    minTim[ed][ed] = INF;
    pq.push({minTim[ed][ed], ed});
    while (!pq.empty())
    {
        // 取出最近点
        int now = pq.top().second;
        pq.pop();
        // 已经确定了就不做了
        if (vis[now] == visNow)
            continue;
        // 确定这个点，更新其他点的时间
        vis[now] = visNow;
        for (int i = 0; i < e[now].size(); i++)
        {
            int nxt = e[now][i].v;
            int l = e[now][i].l;                      // 当前边最晚发车时间
            int t = e[now][i].t;                      // 需要的时间
            int nowTim = min(l, minTim[now][ed] - t); // 当前情况的最晚出发时间
            if (nowTim > minTim[nxt][ed])
            {
                minTim[nxt][ed] = nowTim;
                pq.push({minTim[nxt][ed], nxt});
            }
        }
    }
}
int main()
{
    ios::sync_with_stdio(false);
    cin.tie(0);
    cin >> n >> m >> q;
    for (int i = 1; i <= m; i++)
    {
        int u, v, l, t;
        cin >> u >> v >> l >> t;
        e[v].push_back({u, l, t});
    }
    // 预处理 minTim
    for (int i = 1; i <= n; i++)
        work(i);
    // 处理每个询问
    while (q--)
    {
        int x, y, s;
        cin >> x >> y >> s;
        if (s <= minTim[x][y])
            cout << "Yes\n";
        else
            cout << "No\n";
    }
    return 0;
}
