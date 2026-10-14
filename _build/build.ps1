# Reproducible local build. Never remove the previous working version on build failure.
param([switch]$SkipPackages)
$ErrorActionPreference = 'Stop'
$buildRoot = $PSScriptRoot
$projectRoot = [IO.Path]::GetFullPath((Join-Path $buildRoot '..'))
$pythonPath = Join-Path $buildRoot 'venv\Scripts\python.exe'
$releaseId = Get-Date -Format 'yyyyMMdd-HHmmss'
$stageRoot = Join-Path $buildRoot "release-stage-$releaseId"
$backupRoot = Join-Path $buildRoot "backup-$releaseId"
New-Item -ItemType Directory -Force -Path $stageRoot | Out-Null
Push-Location $buildRoot
try {
    & $pythonPath -m PyInstaller --noconfirm --windowed --onedir --name ZDGC --icon logo.ico --paths vendor --add-data 'src\ui;ui' --add-data 'src\zhdict;zhdict' --hidden-import tools --hidden-import capture --hidden-import workflows --hidden-import validation --hidden-import system_tools --hidden-import disk_tools --hidden-import zhconv --hidden-import selftest --hidden-import cryptography --collect-all cryptography --collect-all pypdfium2 --collect-all rawpy --collect-all psd_tools --collect-all resvg_py --collect-all trimesh --collect-submodules webview --exclude-module pillow_heif --exclude-module tkinter --exclude-module matplotlib --exclude-module setuptools --exclude-module pip --exclude-module test --distpath "$stageRoot\dist" --workpath "$stageRoot\work" --specpath $stageRoot src\app.py
    if ($LASTEXITCODE -ne 0) { throw 'PyInstaller 建置失敗；現有版本未修改。' }
    $candidate = Join-Path $stageRoot 'dist\ZDGC'
    foreach ($rel in 'ZDGC.exe','_internal\ui\index.html','_internal\zhdict\STCharacters.txt') {
        if (-not (Test-Path -LiteralPath (Join-Path $candidate $rel))) { throw "缺少建置產物：$rel" }
    }
    New-Item -ItemType Directory -Force -Path $backupRoot | Out-Null
    $oldInternal = Join-Path $projectRoot '_internal'
    $newInternal = Join-Path $projectRoot "_internal.new-$releaseId"
    $oldExe = Join-Path $projectRoot '四維八德.exe'
    if (Test-Path -LiteralPath $oldExe) { Copy-Item -LiteralPath $oldExe -Destination (Join-Path $backupRoot '四維八德.exe') }
    Copy-Item -LiteralPath (Join-Path $candidate '_internal') -Destination $newInternal -Recurse
    # All targets are direct children of the explicit project root.
    foreach ($target in $oldInternal,$newInternal,$backupRoot) {
        if (-not [IO.Path]::GetFullPath($target).StartsWith($projectRoot + '\',[StringComparison]::OrdinalIgnoreCase)) { throw '建置路徑超出專案範圍' }
    }
    try {
        if (Test-Path -LiteralPath $oldInternal) { Move-Item -LiteralPath $oldInternal -Destination (Join-Path $backupRoot '_internal') }
        Move-Item -LiteralPath $newInternal -Destination $oldInternal
        Copy-Item -LiteralPath (Join-Path $candidate 'ZDGC.exe') -Destination $oldExe -Force
    } catch {
        if (Test-Path -LiteralPath (Join-Path $backupRoot '_internal')) {
            if (Test-Path -LiteralPath $oldInternal) { Move-Item -LiteralPath $oldInternal -Destination (Join-Path $stageRoot 'failed-internal') }
            Move-Item -LiteralPath (Join-Path $backupRoot '_internal') -Destination $oldInternal
        }
        if (Test-Path -LiteralPath (Join-Path $backupRoot '四維八德.exe')) { Copy-Item -LiteralPath (Join-Path $backupRoot '四維八德.exe') -Destination $oldExe -Force }
        throw
    }
    & $pythonPath -m pip freeze | Set-Content -LiteralPath (Join-Path $buildRoot 'requirements-lock.txt') -Encoding utf8
    if (-not $SkipPackages) {
        $portableZip = Join-Path $projectRoot '輸出\四維八德_免安裝版.zip'
        $packageStage = Join-Path $stageRoot '四維八德_免安裝版.zip'
        Push-Location $projectRoot
        try {
            & (Join-Path $projectRoot 'tools\7z.exe') a -tzip -mx=5 -mmt=on -bso0 $packageStage '四維八德.exe' '_internal' 'tools' '使用說明.md' '授權說明.md' '使用授權條款.md' 'LICENSE' '-xr!logs' '-xr!settings.json' '-xr!hw_cache.json' '-xr!watch_state.json'
            if ($LASTEXITCODE -ne 0) { throw '免安裝版打包失敗；已建置的主程式可正常使用。' }
            Move-Item -LiteralPath $packageStage -Destination $portableZip -Force
        } finally { Pop-Location }
    }
    Write-Host "完成。上一版保存在 $backupRoot；模型與網站下載元件使用首次下載機制，不會在建置時靜默下載。"
} finally { Pop-Location }
