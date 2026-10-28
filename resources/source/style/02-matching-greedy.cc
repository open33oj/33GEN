#include <bits/stdc++.h>
using namespace std;
const int MAXN = 1000;
int n;
int a[MAXN + 5][MAXN + 5];
struct Node
{
    int aij, i, j;
};
vector<Node> best;
bool cmp(Node a, Node b)
{
    return a.aij > b.aij;
}
bool vis[MAXN + 5]; // 组队了没有
int tim[MAXN + 5];  // 最早组队时间
vector<int> ans[MAXN * MAXN + 5];
int main()
{
    cin >> n;
    for (int i = 1; i <= n - 1; i++)
        for (int j = i + 1; j <= n; j++)
            cin >> a[i][j];

    for (int i = 1; i <= n - 1; i++)
        for (int j = i + 1; j <= n; j++)
            best.push_back({a[i][j], i, j});
    sort(best.begin(), best.end(), cmp);
    int ansTim = 0;
    for (Node x : best)
    {
        // 都走了不用管
        if (vis[x.i] && vis[x.j])
            continue;
        // cout<<x.i<<" "<<x.j<<"\n";
        //  都在就组队成功
        if (!vis[x.i] && !vis[x.j])
        {
            int xTim = max(tim[x.i], tim[x.j]);
            ans[xTim].push_back(x.i);
            ans[xTim].push_back(x.j);
            vis[x.i] = vis[x.j] = true;
            tim[x.i] = tim[x.j] = xTim;
            // cout<<"ok:"<<xTim<<"\n";
            continue;
        }
        // 一个人x.i耽误了另一个人x.j
        if (!vis[x.i])
            swap(x.i, x.j);
        tim[x.j] = max(tim[x.j], tim[x.i] + 1);
        ansTim = max(ansTim, tim[x.j]);
        // cout<<x.i<<"->"<<x.j<<":"<<tim[x.j]<<"\n";
    }
    cout << ansTim + 1 << "\n";
    for (int i = 0;; i++)
    {
        if (ans[i].empty())
            break;
        sort(ans[i].begin(), ans[i].end());
        for (int x : ans[i])
            cout << x << " ";
        cout << "\n";
    }
}
