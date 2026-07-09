# darkMark 打包脚本
# 用法: .\build.ps1

$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot

Write-Host "==> 安装打包依赖..."
pip install -r "$Root\requirements-build.txt"

Write-Host "==> 清理旧构建..."
if (Test-Path "$Root\build") { Remove-Item -Recurse -Force "$Root\build" }
if (Test-Path "$Root\dist\darkMark") { Remove-Item -Recurse -Force "$Root\dist\darkMark" }

Write-Host "==> PyInstaller 打包..."
python -m PyInstaller "$Root\darkmark.spec" --noconfirm

$Dist = "$Root\dist\darkMark"
if (-not (Test-Path "$Dist\darkMark.exe")) {
    throw "打包失败：未找到 darkMark.exe"
}

Write-Host ""
Write-Host "打包完成！输出目录: $Dist"
Write-Host ""
Write-Host "可执行文件:"
Write-Host "  darkMark.exe          市场监控（--dry-run / --live）"
Write-Host "  darkMark-config.exe   可视化配置页面"
Write-Host "  darkMark-picker.exe   屏幕区域选取工具"
Write-Host ""
Write-Host "注意:"
Write-Host "  1. 仍需安装 Tesseract OCR 并加入 PATH（或放到 exe 同目录\tesseract\）"
Write-Host "  2. 首次运行会在 exe 旁自动创建 config/、logs/、assets/ 目录"
Write-Host "  3. 将整个 dist\darkMark 文件夹复制到其他电脑即可使用"
