#include "testlib.h"
#include <bits/stdc++.h>
using namespace std;

// 每个测试点的 seed 与规模只写在这里（不写进 config.yaml，见 docs/rules.md K4）。
struct GenCase
{
    const char *name;
    long long seed;
    long long maxv;
    const char *kind;   // random / min / max / equal / zero
};

static const GenCase CASES[] = {
    {"t01", 0x5EED0001LL, 10LL, "min"},
    {"t02", 0x5EED0002LL, 10LL, "max"},
    {"t03", 0x5EED0003LL, 10LL, "equal"},
    {"t04", 0x5EED0004LL, 10LL, "zero"},
    {"t05", 0x5EED0005LL, 10LL, "random"},
    {"t06", 0x5EED0006LL, 10LL, "random"},
    {"t07", 0x5EED0007LL, 100000LL, "min"},
    {"t08", 0x5EED0008LL, 100000LL, "max"},
    {"t09", 0x5EED0009LL, 100000LL, "equal"},
    {"t10", 0x5EED000ALL, 100000LL, "zero"},
    {"t11", 0x5EED000BLL, 100000LL, "random"},
    {"t12", 0x5EED000CLL, 100000LL, "random"},
    {"t13", 0x5EED000DLL, 1000000000LL, "min"},
    {"t14", 0x5EED000ELL, 1000000000LL, "max"},
    {"t15", 0x5EED000FLL, 1000000000LL, "equal"},
    {"t16", 0x5EED0010LL, 1000000000LL, "zero"},
    {"t17", 0x5EED0011LL, 1000000000LL, "random"},
    {"t18", 0x5EED0012LL, 1000000000LL, "random"},
    {"t19", 0x5EED0013LL, 1000000000LL, "random"},
    {"t20", 0x5EED0014LL, 1000000000LL, "random"},
};

static void genCase(const GenCase &c, long long seed, bool toStdout)
{
    rnd.setSeed(seed);
    long long a = 0, b = 0;
    string kind = c.kind;
    if (kind == "min")
    {
        a = 0;
        b = 0;
    }
    else if (kind == "max")
    {
        a = c.maxv;
        b = c.maxv;
    }
    else if (kind == "equal")
    {
        a = rnd.next(0LL, c.maxv);
        b = a;
    }
    else if (kind == "zero")
    {
        a = 0;
        b = rnd.next(0LL, c.maxv);
    }
    else
    {
        a = rnd.next(0LL, c.maxv);
        b = rnd.next(0LL, c.maxv);
    }

    if (toStdout)
    {
        printf("%lld %lld\n", a, b);
        return;
    }
    string outName = string(c.name) + ".in";
    FILE *f = fopen(outName.c_str(), "wb");
    if (f == NULL)
        quitf(_fail, "cannot open %s", outName.c_str());
    fprintf(f, "%lld %lld\n", a, b);
    fclose(f);
}

int main(int argc, char *argv[])
{
    registerGen(argc, argv, 1);

    string caseName;
    long long seedOverride = -1;
    bool toStdout = false;
    for (int i = 1; i < argc; i++)
    {
        string arg = argv[i];
        if (arg == "--list")
        {
            for (const GenCase &c : CASES)
                printf("%s\n", c.name);
            return 0;
        }
        if (arg == "--stdout")
        {
            toStdout = true;
            continue;
        }
        if (arg == "--case" && i + 1 < argc)
            caseName = argv[++i];
        else if (arg == "--seed" && i + 1 < argc)
            seedOverride = atoll(argv[++i]);
    }

    for (const GenCase &c : CASES)
    {
        if (caseName == c.name)
        {
            genCase(c, seedOverride >= 0 ? seedOverride : c.seed, toStdout);
            return 0;
        }
    }
    quitf(_fail, "unknown case: %s", caseName.c_str());
    return 0;
}
