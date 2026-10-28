#include <bits/stdc++.h>
using namespace std;
int m;
long long cnt[200000 + 100 + 5];
int main()
{
    ios::sync_with_stdio(false);
    cin.tie(0);
    cin >> m;
    for (int i = 0; i <= m; i++)
        cin >> cnt[i];
    for (int i = 0;; i++)
    {
        if (cnt[i] == 0)
        {
            cout << i - 1 << "\n";
            return 0;
        }
        cnt[i + 1] += (cnt[i] - 1) / 2;
        // cnt[i] = 1 + (cnt[i] - 1) % 2;
    }
    return 0;
}
