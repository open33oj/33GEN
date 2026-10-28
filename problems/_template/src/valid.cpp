#include "testlib.h"
#include <bits/stdc++.h>
using namespace std;

const long long MAXV = 1000000000LL;

int main(int argc, char *argv[])
{
    registerValidation(argc, argv);

    long long a = inf.readLong(0LL, MAXV, "a");
    inf.readSpace();
    long long b = inf.readLong(0LL, MAXV, "b");
    inf.readEoln();
    inf.readEof();

    ensuref(a + b >= 0, "sum overflow");
    return 0;
}
