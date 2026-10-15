# 2.3.4 整理：刪除已移除功能與舊 Logo 版本的殘留檔案。
# 只刪除下列固定清單中的檔案；不動 tools、設定與輸出。
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$obsolete = @(
  '_build\src\disk_tools.py',
  '_build\cpp\src\modules\disk_tools.cpp',
  '_build\tests\release-tests\check_disk_tools.py',
  '_build\tests\release-tests\gate_disk_tools.ps1',
  '_build\src\ui\logo-sm.png',
  '_internal\ui\logo-sm.png',
  'assets\logo-sm.png',
  '_build\logo\logo-small.svg',
  '_build\logo\logo-tiny.svg',
  '_build\logo\logo-mark.svg',
  '_build\logo\logo-mark_1024.png',
  '_build\logo\新舊對照.png'
)
foreach ($rel in $obsolete) {
  $p = Join-Path $root $rel
  if (Test-Path -LiteralPath $p) { Remove-Item -LiteralPath $p -Force; Write-Host "已刪除 $rel" }
}
Get-ChildItem -LiteralPath (Join-Path $root '_build\src\__pycache__') -Filter 'disk_tools*.pyc' -ErrorAction SilentlyContinue | Remove-Item -Force
Write-Host '完成。'
