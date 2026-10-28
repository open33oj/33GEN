# 环境与依赖：去哪儿找

> 主要使用环境在**中国大陆**（内核 K11），所以安装任何东西都要先想网络。
> 下表里标「未验证」的只是候选渠道，**不是实测结论**（K9）；标「已验证」的是本机实际跑通的。

## 0. 速查

| 依赖 | 版本 | 官方来源 | 国内获取方式 | 本机位置 |
| --- | --- | --- | --- | --- |
| g++（MinGW-w64） | 9.3.0+，支持 C++14 | winlibs.com / msys2.org | MSYS2 清华镜像（未验证）/ winlibs 直链 | `<MinGW 目录>\bin`（本机在 `Documents\mingw64\bin`） |
| Python | 3.8+ | python.org | 华为云镜像（未验证）/ Microsoft Store | 3.15.2，`WindowsApps\python.exe` |
| PyYAML | 6.x | pypi.org | pip 清华镜像（未验证）/ 手动装纯 Python 包（已验证） | 用户 site-packages |
| Typst | **0.14.2**（不能 0.15） | GitHub Releases | 本机代理 / ghproxy（未验证） | `%LOCALAPPDATA%\Programs\typst` |
| MSVC 运行库 | 14.x | microsoft.com | PyPI `msvc-runtime` 包（**已验证**） | 与 `typst.exe` 同目录 |
| Git | 2.5x | git-scm.com | 清华 github-release 镜像（未验证）/ winget | `C:\Program Files\Git` |
| testlib | 0.9.37 | GitHub `MikeMirzayanov/testlib` | **不需要下载**，仓库已快照 | `resources/source/testlib/testlib.h` |
| CNOI 模板 | 2.0.6 | GitHub `Mr-Python-in-China/cnoi-statement-generator` | **不需要下载**，模板已落地 | `resources/cnoi/typst/` |
| 字体 | — | 自由字体随仓库；中文用系统字体 | Windows 自带 / Linux 自行安装 | `resources/cnoi/fonts/`（仅自由字体） |
| Typst 包 oxifmt / mitex | 1.0.0 / 0.2.5 | typst universe | 清华 Typst 镜像（未验证）/ `setup_resources.py` 下载 | `resources/typst-packages/` |

## 1. 网络（中国大陆）

- **实测**：GitHub 直连会被 `Connection reset`；本机代理 `http://127.0.0.1:7890` 可用
  （本次下载 typst 0.14.2 就是走它）。
- **PyPI**：pip 有时能直连，但在沙箱里更容易栽在临时目录权限上；优先配镜像：
  `python -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple pyyaml`
- **原则**：先试镜像 → 再试代理 → 最后才考虑离线包；**不要**把「能直连 GitHub / PyPI」当前提。

## 2. 各依赖的安装要点

### g++（MinGW-w64）

- 必须支持 `-std=c++14`；本机是 MinGW-w64 9.3.0。
- 安装后把 `bin` 目录加进**用户 PATH**，然后**新开终端**才生效。
- 校验：`g++ --version`。

### Python + PyYAML

- Python 版本太新时（如 3.15）PyYAML 没有预编译轮子，pip 会尝试用 MSVC 编译并失败。
- **已验证的绕过办法**：下载 cp312 的 wheel，只取其中的纯 Python 模块：
  ```bash
  python -m pip download --only-binary :all: --python-version 3.12 \
      --platform win_amd64 --implementation cp --abi cp312 pyyaml -d .tmp
  # 解压 wheel，把 yaml/ 目录复制到用户 site-packages，并删掉里面的 *.pyd
  ```
- 校验：`python -c "import yaml; print(yaml.__version__)"`。

### Typst

- **必须 0.14.x**：0.15 与 `@preview/mitex:0.2.5` 不兼容，PDF 编译报 `unknown variable: kai`。
- Windows 版是 MSVC 构建，缺 `vcruntime140.dll` / `vcruntime140_1.dll` / `msvcp140.dll` 时
  启动直接报 `0xC0000135`（STATUS_DLL_NOT_FOUND）。
- **已验证的绕过办法**：
  ```bash
  python -m pip download --only-binary :all: msvc-runtime -d .tmp
  # 解压 wheel，把 *.dll 复制到 typst.exe 同目录（app-local，不必装系统运行库）
  ```
- 校验：`typst --version` 应输出 `0.14.2`。

### Git

- 安装后同样要**新开终端**才进 PATH（本次 DSH 进程用的是旧环境快照，只能写全路径调用）。
- 校验：`git --version`。

### 仓库内自带、不用下载

- testlib、CNOI 模板与自由字体、Typst 包都在 `resources/`。
- 校验：`python tools/setup_resources.py --check`。

## 3. 一键自检

```bash
g++ --version
python -c "import yaml; print(yaml.__version__)"
typst --version
git --version
python tools/setup_resources.py --check
```

全部通过再开始出题；任何一项失败，先按 §2 修环境，不要带着坏环境往下跑。

# 字体

仓库只带**自由字体**（Latin Modern Roman、New Computer Modern Math、Fira Mono），
在 `resources/cnoi/fonts/`。

**SimSun / SimHei / KaiTi 已从仓库移除**（商业字体，公开再分发有授权风险）。
出 PDF 时 Typst 会去系统字体里找：

- Windows：一般自带这三个，直接可用；
- Linux：需要自己装（或放同名 `.ttf` 进 `resources/cnoi/fonts/`）；
- 找不到时 PDF 会缺字。

## 检测

```bash
python tools/setup_resources.py --check
```

它用 `typst fonts` 查这三个家族，正常时输出：

```
[info ] 中文字体可用：KaiTi, SimHei, SimSun（检测方式：`typst fonts`）
```

缺了会变成 `[warn]` 并列出缺失家族。因为仓库本来就不带这三个字体，
`--check` **不会**因此返回失败，但 PDF 生成会缺字，需要先补字体。

## 想换开源字体

| 模板家族 | 开源替代（OFL） |
| --- | --- |
| SimSun | 思源宋体 / Noto Serif CJK SC |
| SimHei | 思源黑体 / Noto Sans CJK SC |
| KaiTi | 霞鹜文楷 LXGW WenKai |

替换要改模板 `main.typ` 的家族名，走 `tools/cnoi/cli.py` 的 `STAGE_PATCHES`
（`resources/cnoi` 只读）。代价：CJK 单字重 15~20 MB、标点字重行高会变、要逐页看预览。

> 目前未实现字体替换；系统里已有这三个字体时不需要做任何事。