# 把最新一次「全部測試通過」的候選版本（_build\release-stage-*）換到這個資料夾。
# build.ps1 只建置與測試候選版，不會替換正在使用的程式；這個腳本負責最後一步。
# 只替換 四維八德.exe、swbd-core.exe 與 _internal；tools、設定與輸出都不動。
# 舊檔先搬到 _build\deploy-backup-<時間>，任何一步失敗都會自動還原。
param([string]$Stage = '')
$ErrorActionPreference = 'Stop'
$build = $PSScriptRoot
$root = Split-Path -Parent $build

function Test-Candidate($stage) {
    $c = Join-Path $stage.FullName 'dist\swbd-core'
    foreach ($n in '四維八德.exe', 'swbd-core.exe', '_internal') { if (-not (Test-Path -LiteralPath (Join-Path $c $n))) { return $null } }
    $log = Join-Path $stage.FullName 'selftest\selftest.log'
    if (-not (Test-Path -LiteralPath $log)) { return $null }
    $text = Get-Content -LiteralPath $log -Raw -Encoding UTF8
    $m = [regex]::Match($text, '結果：(\d+) / (\d+) 通過')
    if ($text -match '(?m)^(FAIL|SKIP)' -or -not $m.Success -or $m.Groups[1].Value -ne $m.Groups[2].Value) { return $null }
    $pdf = Join-Path $stage.FullName 'pdf-test\results.json'
    if (-not (Test-Path -LiteralPath $pdf)) { return $null }
    $results = @(Get-Content -LiteralPath $pdf -Raw -Encoding UTF8 | ConvertFrom-Json)
    if ($results.Count -eq 0 -or @($results | Where-Object { -not $_.ok }).Count) { return $null }
    $smoke = Join-Path $stage.FullName 'native-window-smoke.json'
    if (-not (Test-Path -LiteralPath $smoke)) { return $null }
    $s = Get-Content -LiteralPath $smoke -Raw -Encoding UTF8 | ConvertFrom-Json
    if (-not $s.ok) { return $null }
    return [pscustomobject]@{ Folder = $c; Stage = $stage.Name; Version = $s.version; Tests = $m.Groups[1].Value }
}

$pick = $null
foreach ($stage in Get-ChildItem -LiteralPath $build -Directory -Filter 'release-stage-*' | Where-Object { -not $Stage -or $_.Name -eq $Stage } | Sort-Object Name -Descending) {
    $pick = Test-Candidate $stage
    if ($pick) { break }
}
if (-not $pick) { throw '找不到全部測試通過的候選版本。請先執行 _build\建置安裝包.ps1。' }
Write-Host "候選版本：$($pick.Stage)（版本 $($pick.Version)，自我測試 $($pick.Tests) 項全部通過）"

$running = @(Get-Process -Name '四維八德', 'swbd-core' -ErrorAction SilentlyContinue)
if ($running.Count) { throw '四維八德正在執行。請先關閉程式，再執行這個腳本。' }

$backup = Join-Path $build ('deploy-backup-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
New-Item -ItemType Directory -Path $backup | Out-Null
$items = '四維八德.exe', 'swbd-core.exe', '_internal'
$moved = @()
try {
    foreach ($n in $items) {
        $p = Join-Path $root $n
        if (Test-Path -LiteralPath $p) { Move-Item -LiteralPath $p -Destination $backup; $moved += $n }
    }
    Copy-Item -LiteralPath (Join-Path $pick.Folder '四維八德.exe') -Destination $root
    Copy-Item -LiteralPath (Join-Path $pick.Folder 'swbd-core.exe') -Destination $root
    & robocopy (Join-Path $pick.Folder '_internal') (Join-Path $root '_internal') /E /NFL /NDL /NJH /NJS /NP | Out-Null
    if ($LASTEXITCODE -ge 8) { throw "複製 _internal 失敗（robocopy $LASTEXITCODE）" }
    foreach ($n in '四維八德.exe', 'swbd-core.exe') {
        if ((Get-FileHash -LiteralPath (Join-Path $root $n)).Hash -ne (Get-FileHash -LiteralPath (Join-Path $pick.Folder $n)).Hash) { throw "$n 校驗不符" }
    }
} catch {
    Write-Host "部署失敗，正在還原：$($_.Exception.Message)"
    foreach ($n in $items) {
        $p = Join-Path $root $n
        if ((Test-Path -LiteralPath $p) -and ($moved -contains $n)) { Remove-Item -LiteralPath $p -Recurse -Force }
    }
    foreach ($n in $moved) { Move-Item -LiteralPath (Join-Path $backup $n) -Destination $root }
    throw
}
Write-Host "完成：已換上 $($pick.Version)。舊版備份在 $backup，確認新版正常後可以刪除。"
