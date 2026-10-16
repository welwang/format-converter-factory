# 刪除已移除功能、舊版 Logo、測試檔案與舊說明文件的殘留。
# 只刪除下列固定清單；不動 tools、設定、輸出成品與健康檢查報告。
# 建置需要的兩個素材（_build\samples\smoke.pdf、i.heic）會保留。
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$obsolete = @(
  # 已移除的功能與舊 Logo
  '_build\src\disk_tools.py', '_build\cpp\src\modules\disk_tools.cpp',
  '_build\src\ui\logo-sm.png', '_internal\ui\logo-sm.png', 'assets\logo-sm.png',
  '_build\logo\logo-small.svg', '_build\logo\logo-tiny.svg', '_build\logo\logo-mark.svg',
  '_build\logo\logo-mark_1024.png', '_build\logo\新舊對照.png',
  # 測試程式、測試資料與測試報告
  '_build\tests', '_build\cpp\tests', '_build\shell\test', '_build\shell\engine_test_cli.cpp',
  '_build\cpp-migration', '_build\shots', '_build\shot.ps1',
  '_build\compliance\health_probe.py', '_build\compliance\test_gate_invocation.ps1',
  'smoke-fixtures', 'smoke-output', 'webview-test-profile',
  'TEST_RESULTS.md', 'TEST_RESULTS_2.3.3.md', '測試報告.html', '測試報告_2.3.3.html', 'PACKAGE_VALIDATION.md',
  # 舊說明文件（內容已整合進 README.md 與 CHANGELOG.md）
  '使用說明.md', 'PDF功能清單.md', '版本更新.md', '工程技術說明書.md',
  '_build\docs', '_build\compliance\README.md',
  # 上一個整理腳本
  '_build\整理2.3.4.ps1'
)
foreach ($rel in $obsolete) {
  $p = Join-Path $root $rel
  if (Test-Path -LiteralPath $p) { Remove-Item -LiteralPath $p -Recurse -Force; Write-Host "已刪除 $rel" }
}
$samples = Join-Path $root '_build\samples'
if (Test-Path -LiteralPath $samples) {
  Get-ChildItem -LiteralPath $samples -Force | Where-Object { $_.Name -notin 'smoke.pdf', 'i.heic' } | ForEach-Object {
    Remove-Item -LiteralPath $_.FullName -Recurse -Force; Write-Host "已刪除 _build\samples\$($_.Name)"
  }
}
Get-ChildItem -LiteralPath (Join-Path $root '_build\src\__pycache__') -Filter 'disk_tools*.pyc' -ErrorAction SilentlyContinue | Remove-Item -Force
Write-Host '整理完成。'
