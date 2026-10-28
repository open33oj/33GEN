#include <bits/stdc++.h>
using namespace std;
int n, m;
// 1~x 有几个数 % 5 为 i
int f(int x, int i)
{
    int base = x / 5;
    if (x % 5 >= i && i != 0)
        base++;
    return base;
}
int main()
{
    cin >> n >> m;
    long long ans = 0;
    for (int i = 0; i <= 4; i++)
    {
        int L = f(n, i);
        int j = 5 - i;
        int R = f(m, j);
        ans += 1LL * L * R;
    }
    cout << ans;
}
