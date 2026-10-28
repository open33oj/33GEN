#include <bits/stdc++.h>
using namespace std;
const int MAXN = 200000;
int n;
long long M, P;
long long L[MAXN + 5], R[MAXN + 5];
vector<long long> temp;
int cnt[3 * MAXN + 2 + 5];
// 希望 cnt[i] = d[0]~d[i] 之和
int d[3 * MAXN + 2 + 5];
int main()
{
    ios::sync_with_stdio(false);
    cin.tie(0);
    cin >> n >> M >> P;
    for (int i = 1; i <= n; i++)
        cin >> L[i] >> R[i];

    // 离散化
    //  复制一份
    for (int i = 1; i <= n; i++)
    {
        temp.push_back(L[i]);
        temp.push_back(R[i]);
        temp.push_back(R[i] + 1);
    }
    temp.push_back(0);
    temp.push_back(M + 1);
    // 排序
    sort(temp.begin(), temp.end());
    // (可选)去重
    int tot = unique(temp.begin(), temp.end()) - temp.begin();
    // 把原本的东西转成对应排名 0-base
    for (int i = 1; i <= n; i++)
    {
        L[i] = lower_bound(temp.begin(), temp.begin() + tot, L[i]) - temp.begin();
        R[i] = lower_bound(temp.begin(), temp.begin() + tot, R[i]) - temp.begin();
    }

    for (int i = 1; i <= n; i++)
        d[L[i]]++, d[R[i] + 1]--;
    cnt[0] = d[0];
    for (int i = 1; i <= tot - 1; i++)
        cnt[i] = cnt[i - 1] + d[i];

    int ans = n + 1;
    long long pos;
    // 离散化后是 0~tot-1
    for (int i = 0; i <= tot - 2; i++)
    {
        // cnt[i]: 离散化后 [i,i+1) 被覆盖了几次
        // 对应了离散化前 [temp[i], temp[i+1]) 被覆盖了几次
        int now = cnt[i];
        long long nowL = temp[i], nowR = temp[i + 1] - 1;
        if (nowL <= nowR)
        {
            //  nowL   nowR  P
            if (nowR <= P && now < ans)
                ans = now, pos = nowR;
            // nowL P nowR
            if (nowL <= P && P <= nowR && now <= ans)
                ans = now, pos = P;
            //  P nowL nowR
            if (P <= nowL &&
                (now < ans || now == ans && abs(nowL - P) < abs(pos - P)))
                ans = now, pos = nowL;
        }
    }
    cout << ans << " " << pos << "\n";
    return 0;
}
