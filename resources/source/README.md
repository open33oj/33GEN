# 原始素材

这里只放两样东西：

| 文件 | 用途 | 谁用 |
| --- | --- | --- |
| `style/*.cc` | 8 份 C++ 风格样本，`docs/style.md` 的归纳依据 | 只被人读 |
| `testlib/testlib.h` | testlib 上游快照 | `setup_resources.py` 同步到 `resources/testlib/` |

**CNOI 生成器的发行包不再随仓库分发**（34 MB，AGPL-3.0，且内含商业字体）。
`resources/cnoi/` 已经落地，日常出题不需要它。

只有要重建 `resources/cnoi/` 时才需要：

1. 到 <https://github.com/Mr-Python-in-China/cnoi-statement-generator> 下载对应版本
   （版本见 `resources/cnoi/VERSION`）；
2. 把发布包放到本目录，命名 `cnoi-statement-generator-<版本>.zip`；
3. 运行 `python tools/setup_resources.py --only cnoi`，再跑 `python tools/selftest.py`。

字体说明见 `resources/cnoi/README.md`：仓库只带自由字体，中文字体用系统字体。
