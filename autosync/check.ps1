# 上傳前安全檢查：擋下 >50MB 的檔案與疑似密鑰／個人路徑（pre-commit 與 pre-push 共用）
param([string]$Mode = 'commit')
$Repo = Split-Path -Parent $PSScriptRoot
Set-Location $Repo
$files = if ($Mode -eq 'commit') { git diff --cached --name-only --diff-filter=ACMR } else { git ls-files }
$patterns = @(
  'gh[pousr]_[A-Za-z0-9]{30,}', 'github_pat_[A-Za-z0-9_]{40,}', 'AKIA[0-9A-Z]{16}', 'xox[abpr]-[A-Za-z0-9-]{10,}',
  'sk-[A-Za-z0-9]{32,}', '-----BEGIN [A-Z ]*PRIVATE KEY-----', 'AIza[0-9A-Za-z_\-]{35}',
  '(?i)C:\\Users\\(?!Public)[A-Za-z0-9._-]+\\', 'discord(app)?\.com/api/webhooks/'
)
$bad = @()
foreach ($f in $files) {
  if (-not $f -or -not (Test-Path -LiteralPath $f)) { continue }
  $item = Get-Item -LiteralPath $f
  if ($item.Length -gt 50MB) { $bad += "$f（超過 50 MB）"; continue }
  if ($item.Extension -in '.png', '.ico', '.jpg', '.exe', '.dll', '.zip') { continue }
  $text = [IO.File]::ReadAllText($item.FullName)
  foreach ($p in $patterns) { if ($text -match $p) { $bad += "$f（符合安全規則：$p）"; break } }
}
if ($bad) { Write-Host "已擋下上傳：`n$($bad -join "`n")"; exit 1 }
exit 0
