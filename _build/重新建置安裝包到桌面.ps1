# 一鍵：重新建置最新版 → 安裝包與免安裝版放到桌面 → 換上新版程式 → 刪除舊版本。
# 建置或測試任何一步失敗就停止，這時不會刪除任何東西。
$ErrorActionPreference = 'Stop'
$build = $PSScriptRoot
$root = Split-Path -Parent $build
try {
    if (@(Get-Process -Name '四維八德', 'swbd-core' -ErrorAction SilentlyContinue).Count) { throw '請先關閉四維八德，再執行這個腳本。' }
    $cleanup = Join-Path $build '整理舊檔.ps1'
    if (Test-Path -LiteralPath $cleanup) { & $cleanup }

    $before = @(Get-ChildItem -LiteralPath $build -Directory -Filter 'release-stage-*' | ForEach-Object { $_.Name })
    Write-Host '1/5 建置與測試新版（需要一段時間，請不要關閉這個視窗）…' -ForegroundColor Cyan
    & (Join-Path $build 'build.ps1')
    $new = Get-ChildItem -LiteralPath $build -Directory -Filter 'release-stage-*' | Where-Object { $before -notcontains $_.Name } | Sort-Object Name -Descending | Select-Object -First 1
    if (-not $new) { throw '建置沒有產生新的資料夾。' }
    $setup = Get-ChildItem -LiteralPath (Join-Path $new.FullName 'dist\swbd-core\輸出') -Filter '四維八德_*_離線安裝程式.exe' -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if (-not $setup) { throw '建置完成，但沒有產生安裝程式。' }

    Write-Host '2/5 把安裝程式放到桌面…' -ForegroundColor Cyan
    $desktop = [Environment]::GetFolderPath('Desktop')
    Get-ChildItem -LiteralPath $desktop -Filter '四維八德_*_離線安裝程式.exe' -ErrorAction SilentlyContinue | Where-Object { $_.Name -ne $setup.Name } | Remove-Item -Force
    Copy-Item -LiteralPath $setup.FullName -Destination $desktop -Force
    $onDesktop = Join-Path $desktop $setup.Name
    if ((Get-FileHash -LiteralPath $onDesktop).Hash -ne (Get-FileHash -LiteralPath $setup.FullName).Hash) { throw '桌面上的安裝程式校驗不符。' }

    Write-Host '3/5 整理免安裝版（解壓縮後直接執行 四維八德.exe）…' -ForegroundColor Cyan
    $version = ($setup.BaseName -replace '^四維八德_', '' -replace '_離線安裝程式$', '')
    $work = Join-Path $new.FullName 'portable'
    $folder = Join-Path $work '四維八德'
    if (Test-Path -LiteralPath $work) { Remove-Item -LiteralPath $work -Recurse -Force }
    # 只放執行需要的檔案：建置時的測試素材、測試設定與安裝程式本身都不放進去
    $dist = Join-Path $new.FullName 'dist\swbd-core'
    $skipDirs = @('輸出', 'smoke-fixtures', 'smoke-output', 'webview-test-profile', 'logs', '_build') | ForEach-Object { Join-Path $dist $_ }
    $skipFiles = @('settings.json', 'window.ini', 'watch_state.json', 'hw_cache.json', 'hw_cache_c.json', 'ffmpeg_caps.json') | ForEach-Object { Join-Path $dist $_ }
    & robocopy $dist $folder /E /NFL /NDL /NJH /NJS /NP /XD @skipDirs /XF @skipFiles | Out-Null
    if ($LASTEXITCODE -ge 8) { throw "整理免安裝版失敗（robocopy $LASTEXITCODE）" }
    foreach ($n in '四維八德.exe', 'swbd-core.exe', '_internal', 'tools') {
        if (-not (Test-Path -LiteralPath (Join-Path $folder $n))) { throw "免安裝版缺少 $n" }
    }
    $zipName = "四維八德_$($version)_免安裝版.zip"
    $zip = Join-Path $work $zipName
    & (Join-Path $folder 'tools\7z.exe') a -tzip -mx=5 -mmt=on $zip $folder | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "壓縮免安裝版失敗（7-Zip $LASTEXITCODE）" }
    & (Join-Path $folder 'tools\7z.exe') t $zip | Out-Null
    if ($LASTEXITCODE -ne 0) { throw '免安裝版壓縮檔驗證失敗。' }
    Get-ChildItem -LiteralPath $desktop -Filter '四維八德_*_免安裝版.zip' -ErrorAction SilentlyContinue | Where-Object { $_.Name -ne $zipName } | Remove-Item -Force
    Copy-Item -LiteralPath $zip -Destination $desktop -Force
    if ((Get-FileHash -LiteralPath (Join-Path $desktop $zipName)).Hash -ne (Get-FileHash -LiteralPath $zip).Hash) { throw '桌面上的免安裝版校驗不符。' }
    Remove-Item -LiteralPath $work -Recurse -Force

    Write-Host '4/5 換上新版程式…' -ForegroundColor Cyan
    & (Join-Path $build '部署最新候選版.ps1') -Stage $new.Name

    Write-Host '5/5 刪除舊版本…' -ForegroundColor Cyan
    $old = @()
    $old += Get-ChildItem -LiteralPath $build -Directory -Filter 'release-stage-*' | Where-Object { $_.Name -ne $new.Name }
    $old += Get-ChildItem -LiteralPath $build -Directory -Filter 'deploy-backup-*'
    $old += Get-ChildItem -LiteralPath (Join-Path $root '輸出') -Force -ErrorAction SilentlyContinue
    $old += Get-ChildItem -LiteralPath $build -File | Where-Object { $_.Name -like 'publish-233-*' -or $_.Name -like '*-233.json' }
    foreach ($rel in '_build\logo\舊版', '_build\logo-original.png', 'TEST_RESULTS_2.3.3.md', '測試報告_2.3.3.html') {
        $p = Join-Path $root $rel
        if (Test-Path -LiteralPath $p) { $old += Get-Item -LiteralPath $p }
    }
    foreach ($item in $old) {
        Remove-Item -LiteralPath $item.FullName -Recurse -Force
        Write-Host "  已刪除 $($item.FullName.Substring($root.Length + 1))"
    }
    Write-Host ''
    Write-Host "完成：桌面上有 $($setup.Name)（安裝包）和 $zipName（免安裝版，解壓縮後執行 四維八德.exe）；資料夾裡的程式也已換成新版。" -ForegroundColor Green
} catch {
    Write-Host ''
    Write-Host ('沒有完成：' + $_.Exception.Message) -ForegroundColor Red
    Write-Host '舊版本都還保留著，沒有刪除。'
}
Read-Host '按 Enter 關閉'
