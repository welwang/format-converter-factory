# Validate the candidate before packaging or replacing a working installation.
param([switch]$SkipPackages)
$ErrorActionPreference = 'Stop'
$buildRoot = $PSScriptRoot
$projectRoot = [IO.Path]::GetFullPath((Join-Path $buildRoot '..'))
$python = Join-Path $buildRoot 'venv\Scripts\python.exe'
$stage = Join-Path $buildRoot ('release-stage-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
$candidate = Join-Path $stage 'dist\swbd-core'
Push-Location $buildRoot
try {
    $env:PYTHONPATH = Join-Path $buildRoot 'vendor'
    & $python -m PyInstaller --clean --noconfirm ZDGC.spec --distpath (Join-Path $stage 'dist') --workpath (Join-Path $stage 'work')
    if ($LASTEXITCODE -ne 0) { throw '背景元件建置失敗，現有程式未修改。' }
    & (Join-Path $buildRoot 'shell\build_shell.ps1') -OutFile (Join-Path $candidate '四維八德.exe')
    if ($LASTEXITCODE -ne 0) { throw 'C 主程式建置失敗，現有程式未修改。' }
    foreach ($name in 'tools','source','assets') {
        Copy-Item -LiteralPath (Join-Path $projectRoot $name) -Destination $candidate -Recurse
    }
    foreach ($name in '使用說明.md','授權說明.md','使用授權條款.md','LICENSE','COPYING.AGPL-3.0','開源與散布說明.md','PDF功能清單.md','版本更新.md','TEST_RESULTS.md','測試報告.html') {
        Copy-Item -LiteralPath (Join-Path $projectRoot $name) -Destination $candidate
    }
    & $python -c "import sys;sys.path.insert(0,sys.argv[1]);import engine as E;E.base_dir=lambda:sys.argv[2];m=E.missing_components();print(m);sys.exit(bool(m))" (Join-Path $buildRoot 'src') $candidate
    if ($LASTEXITCODE -ne 0) { throw '缺少完整離線元件，停止打包。' }
    $heic = Join-Path $buildRoot 'samples\i.heic'
    if (Test-Path -LiteralPath $heic) {
        $sampleDir = Join-Path $candidate '_build\samples'
        New-Item -ItemType Directory -Path $sampleDir -Force | Out-Null
        Copy-Item -LiteralPath $heic -Destination $sampleDir
    }
    $smokeDir = Join-Path $candidate 'smoke-fixtures'
    New-Item -ItemType Directory -Path $smokeDir -Force | Out-Null
    & (Join-Path $candidate 'tools\ffmpeg.exe') -hide_banner -y -v error -f lavfi -i 'testsrc2=size=640x360:rate=24:duration=3' -f lavfi -i 'sine=duration=3' -c:v libx264 -preset ultrafast -c:a aac (Join-Path $smokeDir 'video.mp4')
    if ($LASTEXITCODE -ne 0) { throw 'C 視窗測試素材建立失敗。' }
    & $python -c "from PIL import Image;import sys;Image.new('RGB',(64,48),'blue').save(sys.argv[1])" (Join-Path $smokeDir 'image.png')
    $smokeReport = Join-Path $stage 'native-window-smoke.json'
    $windowTest = Start-Process -FilePath (Join-Path $candidate '四維八德.exe') -ArgumentList @('--shell-smoke-test',('"'+$smokeReport+'"')) -WindowStyle Hidden -PassThru
    if (-not $windowTest.WaitForExit(60000)) { throw 'C 視窗診斷逾時。' }
    $smokeResult = Get-Content -LiteralPath $smokeReport -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($windowTest.ExitCode -ne 0 -or -not $smokeResult.ok) { throw 'C 視窗／混合工作診斷失敗。' }
    & $python (Join-Path $buildRoot 'prune_payload.py') $candidate
    if ($LASTEXITCODE -ne 0) { throw '安裝資料精簡失敗。' }
    # Run the actual frozen core; do not record the user's desktop or change disks.
    $test = Join-Path $stage 'selftest'
    & (Join-Path $candidate 'swbd-core.exe') --selftest $test --ai --no-open
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath (Join-Path $test 'selftest.log'))) { throw '自我測試失敗。' }
    $testLog = Get-Content -LiteralPath (Join-Path $test 'selftest.log') -Raw -Encoding UTF8
    if ($testLog -match '(?m)^FAIL|(?m)^SKIP' -or $testLog -notmatch '結果：\d+ / \d+ 通過') { throw '有失敗或略過的案例，停止打包。請補齊測試素材。' }
    $pdf = Join-Path $stage 'pdf-test'
    & (Join-Path $candidate 'swbd-core.exe') --pdf-selftest $pdf
    if ($LASTEXITCODE -ne 0) { throw 'PDF 打包測試失敗。' }
    $pdfResults = Get-Content -LiteralPath (Join-Path $pdf 'results.json') -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($pdfResults.Count -ne 12 -or @($pdfResults | Where-Object { -not $_.ok }).Count) { throw 'PDF 打包結果不完整。' }
    if (-not $SkipPackages) {
        & (Join-Path $buildRoot 'inno\ISCC.exe') ("/DReleaseRoot="+$candidate) (Join-Path $buildRoot 'setup.iss')
        if ($LASTEXITCODE -ne 0) { throw '安裝程式建置失敗。' }
    }
    Write-Host "候選版本與測試保存在：$stage。現有程式未替換；通過測試後可另行部署，公開散布另需完成第三方來源審核。"
} finally { Pop-Location }
