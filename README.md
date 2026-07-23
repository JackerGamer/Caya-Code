# Caya Code

一套供本机个人使用的中英文编程字体构建项目：

- 拉丁字母、数字、符号与编程连字来自 Cascadia Code。
- 中文与日文假名等宽字符来自 Microsoft YaHei（微软雅黑）。
- 一个中文或日文全角字符严格占两个英文字符的宽度。
- 生成 Light、SemiLight、Regular、SemiBold、Bold 五种静态 TTF。

## 构建

要求 Windows 10/11，且系统已安装 Cascadia Code 与微软雅黑。在 PowerShell 中运行：

```powershell
powershell -ExecutionPolicy Bypass -File .\build.ps1
```

成品位于 `build/fonts/`：

```text
CayaCode-Light.ttf
CayaCode-SemiLight.ttf
CayaCode-Regular.ttf
CayaCode-SemiBold.ttf
CayaCode-Bold.ttf
```

脚本从 `C:\Windows\Fonts` 读取字体，不会把原始字体复制进项目。首次构建会在 `.venv` 中安装 FontTools。

自定义字体名称：

```powershell
powershell -ExecutionPolicy Bypass -File .\build.ps1 --family "My Code Font"
```

## 安装与编辑器设置

先关闭使用字体的编辑器，选择 `build/fonts/` 下的五个文件，右键安装。VS Code 示例：

```json
{
  "editor.fontFamily": "'Caya Code'",
  "editor.fontLigatures": true
}
```

如果覆盖安装后仍显示旧版本，请先在 Windows“设置 → 个性化 → 字体”中卸载旧版，再重新安装并重启编辑器。

## 授权说明

[Cascadia Code](https://github.com/microsoft/cascadia-code) 使用 [SIL Open Font License 1.1](https://github.com/microsoft/cascadia-code/blob/main/LICENSE)，并将 “Cascadia Code” 设为保留字体名称，所以本项目默认使用不同的字体家族名 “Caya Code”。[微软雅黑](https://learn.microsoft.com/en-us/typography/font-list/microsoft-yahei)是 Windows 随附的受版权保护字体，并非开放字体。

本项目不包含任何原始或合并后的字体文件；`build/` 也已被 Git 忽略。生成的合并字体仅建议在拥有相应 Windows 字体许可的电脑上供个人本机使用。未经权利人许可，不要上传、发布或随软件分发合并后的 TTF。
