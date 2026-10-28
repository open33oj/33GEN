# CNOI 题面生成器（编译期资源）

这里存放 [cnoi-statement-generator](https://github.com/Mr-Python-in-China/cnoi-statement-generator)
中**编译 PDF 真正需要的文件**。上游项目本体是浏览器端 React 单页应用
（Markdown -> Typst -> PDF），本工程不引入其前端依赖，而是用 Typst CLI 编译同一套模板。

```
resources/cnoi/
├── typst/       # main.typ / header.typ / 代码高亮主题
├── fonts/       # 模板需要的自由字体（Latin Modern、New CM Math、Fira Mono）
└── VERSION      # 版本标记
```

**中文字体不在仓库里**：SimSun / SimHei / KaiTi 是商业字体，公开再分发有授权风险。
出 PDF 时 Typst 会去系统字体里找；Windows 一般自带这三个，Linux 需要自己安装。
检测方式：

```bash
python tools/setup_resources.py --check
```

它会用 `typst fonts` 检查这三个家族，缺失时给出提示。也可以把同名 `.ttf`
放进 `resources/cnoi/fonts/` 覆盖。

`tools/cnoi.py build` 的工作方式：把 `typst/` 复制到构建目录，生成 `content.json`、
`extra-precaution.typ`、`problem-<i>.typ`，然后运行

```bash
typst compile --font-path resources/cnoi/fonts --font-path <系统字体目录> \
              --package-path resources/typst-packages \
              --root <仓库根目录> main.typ out/statement.pdf
```

不要手工修改本目录下的文件；要跟随上游升级请把新的发布包放到 `resources/source/`
后重跑同步脚本，再跑 `python3 tools/selftest.py`。
