# Caya Code

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/caya-code-preview-dark.png">
  <source media="(prefers-color-scheme: light)" srcset="assets/caya-code-preview-light.png">
  <img alt="Caya Code 字体样张" src="assets/caya-code-preview-light.png">
</picture>

Caya Code 是一款等宽字体，专注于优化中文用户的编程体验。拉丁字符、编程符号及连字来自 Cascadia Code，中文、日文假名及其他缺失字符由微软雅黑（Microsoft YaHei）补充；中文字符占两个英文字符宽度。本地构建会生成两种源字体共同支持的字重，例如 Light、Regular 和 Bold，具备更多字重的版本还会生成 SemiLight 和 SemiBold。

## 授权说明

[Cascadia Code](https://github.com/microsoft/cascadia-code) 采用 [SIL Open Font License 1.1](https://github.com/microsoft/cascadia-code/blob/main/LICENSE)；[微软雅黑](https://learn.microsoft.com/en-us/typography/font-list/microsoft-yahei)属于专有字体。

本项目仅供拥有相应字体许可的用户学习和研究，请勿转载。

## 下载

从 [Releases](https://github.com/JackerGamer/Cascadia-YaHei/releases/latest) 下载最新的 TTF 文件。

## 构建

在已安装 Cascadia Code 和微软雅黑的 Windows 10/11 上安装 Python 3.14 和 FontTools：

```powershell
winget install --exact --id Python.Python.3.14
python -m pip install --upgrade fonttools
```

运行构建脚本，字体会输出到项目的 `build/`。Regular 是必需字重，其他字重会根据两种源字体共同支持的范围自动生成：

```powershell
python .\build_font.py
```

发布新版本时修改 [`font_config.py`](font_config.py) 中的 `VERSION`。

## 安装与编辑器设置

关闭正在使用字体的编辑器，安装下载或生成的 TTF 文件。VS Code 示例：

```json
{
  "editor.fontFamily": "'Caya Code'",
  "editor.fontLigatures": true
}
```

可使用 [font-test.txt](font-test.txt) 检查编程连字、中英文宽度和字符对齐。
