# testlib

`testlib.h` 是本工程数据生成器（`gen.cpp`）、校验器（`valid.cpp`）、
交互器（`interactor.cpp`）以及 testlib 型 `checker.cpp` 的唯一依赖。

- 文件位置：`resources/testlib/testlib.h`（版本见文件内 `#define VERSION`）
- 来源：`resources/source/testlib/testlib.h`，由 `python3 tools/setup_resources.py` 同步；
  上游 <https://github.com/MikeMirzayanov/testlib>
- 本工程固定使用 testlib，以保证所有随机数据可复现（见 `docs/workflow.md`）。

编译时统一加 `-I resources/testlib`（`tools/build.py` 已内置）。
需要手动编译时：

```bash
g++ -std=c++14 -O2 -Wall -I resources/testlib gen.cpp -o build/gen
```

## 使用约定

- `gen.cpp`：`registerGen(argc, argv, 1)`，seed 只来自生成器内部的 `CASES` 表。
- `valid.cpp`：`registerValidation(argc, argv)`，用带范围的 `readInt(l, r, "name")` 读取。
- `interactor.cpp`：`registerInteraction(argc, argv)`。
- `checker.cpp`：`registerTestlibCmd(argc, argv)`，用 `quitf(_ok/_wa/_pe/_fail/...)` 返回。

不要修改本目录下的 `testlib.h`；要升级请换 `resources/source/testlib/testlib.h` 后重跑同步脚本。
