# 轉檔工廠：把 tools 裡轉檔用不到的元件移到 _build\pruned（可隨時搬回，不會刪除）
# 用法：在 PowerShell 執行  powershell -ExecutionPolicy Bypass -File E:\轉檔工廠\_build\精簡tools.ps1
#       還原：加上 -Restore
param([switch]$Restore)
$R = 'E:\轉檔工廠'; $P = "$R\_build\pruned"
$items = @(
  'tools\calibre\app\share\espeak-ng-data',          # 文字轉語音字典（電子書轉檔用不到）
  'tools\calibre\app\resources\content-server',      # Calibre 網頁書庫伺服器
  'tools\calibre\app\resources\builtin_recipes.zip', # 新聞下載食譜
  'tools\calibre\app\plugins\texttospeech',          # 朗讀外掛
  'tools\libreoffice\program\python-core-3.13.15',   # LibreOffice 巨集用的 Python（轉檔不需要）
  'tools\libreoffice\program\Engine12.dll',          # Firebird 資料庫（Base 才用）
  'tools\libreoffice\program\intl'                   # Firebird 語系
)
$total = 0
foreach ($it in $items) {
  $src = Join-Path $R $it; $dst = Join-Path $P $it
  if ($Restore) { $src, $dst = $dst, $src }
  if (Test-Path $src) {
    $sz = (Get-ChildItem $src -Recurse -File -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum
    if (-not $sz) { $sz = (Get-Item $src).Length }
    $total += $sz
    New-Item -ItemType Directory -Force -Path (Split-Path $dst) | Out-Null
    Move-Item -Force $src $dst
    Write-Host ('{0,8:N1} MB  {1}' -f ($sz/1MB), $it)
  }
}
Write-Host ('合計 {0:N1} MB {1}' -f ($total/1MB), $(if ($Restore) {'已搬回'} else {'已移出'}))
if (-not $Restore) { Write-Host '請執行自我測試確認：  & "E:\轉檔工廠\轉檔工廠.exe" --selftest E:\轉檔工廠\_build\samples   然後看 samples\selftest.log' }
