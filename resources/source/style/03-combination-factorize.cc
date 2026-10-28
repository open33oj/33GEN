#include <bits/stdc++.h>
using namespace std;
const int MOD = 998244353;
const int MAXN = 100000;
const int MAXL = 1000000;
int L, N;
string s;
int l[MAXN + 5];
int cntP[MAXL + 5];
int main()
{
    cin >> L >> N;
    cin >> s;
    for (int i = 1; i <= N; i++)
        cin >> l[i];

    for (int i = 1; i <= N - 1; i++)
        if (s[i - 1] == '1')
            l[i]++;
    long long suml = 0;
    for (int i = 1; i <= N; i++)
        suml += l[i];
    if (suml > L)
    {
        cout << 0 << "\n";
        return 0;
    }

    L = L - suml + N;
    N = N;
    // C(L,N)=  L!/N!/(L-N)!
    // 这里就不用逆元欺负人了，来个华丽的质因数分解
    // 质因数分解
    for (int i = N + 1; i <= L; i++)
    {
        int x = i;
        // 把 x 的所有质因子个数累计到 cntP
        for (int j = 2; j * j <= x; j++)
        {
            while (x % j == 0)
            {
                cntP[j]++;
                x /= j;
            }
        }
        if (x > 1)
            cntP[x]++;
    }
    // 质因数分解的方式 /(L-N)!
    for (int i = 1; i <= L - N; i++)
    {
        int x = i;
        for (int j = 2; j * j <= x; j++)
        {
            while (x % j == 0)
            {
                cntP[j]--;
                x /= j;
            }
        }
        if (x > 1)
            cntP[x]--;
    }
    int ans = 1;
    for (int i = 1; i <= L; i++)
        for (int j = 1; j <= cntP[i]; j++)
            ans = 1LL * ans * i % MOD;
    cout << ans;
}
