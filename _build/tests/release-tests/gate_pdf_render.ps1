# 原生 PDF 渲染等價閘門：同一頁分別由 C++（PDFium + stb_image_write）與 Python（pypdfium2 + Pillow）
# 以相同 dpi 渲染，再逐像素比對。
# 用法：gate_pdf_render.ps1 [-Artifacts <目錄>]
param([string]$Artifacts = '')
$ErrorActionPreference = 'Stop'
$repo = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..'))
$buildRoot = Join-Path $repo '_build'
$cpp = Join-Path $buildRoot 'cpp'
$python = Join-Path $buildRoot 'venv\Scripts\python.exe'
$env:PYTHONPATH = Join-Path $buildRoot 'vendor'
if (-not $Artifacts) { $Artifacts = Join-Path $buildRoot 'cpp-migration\pdf-render' }
New-Item -ItemType Directory -Force -Path $Artifacts | Out-Null

# 1) 建置（單一專案模式優先，找不到就獨立建置）
& cmake -S $cpp -B (Join-Path $cpp 'build') -A x64 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'CMake 設定失敗' }
& cmake --build (Join-Path $cpp 'build') --config Release --target swbd-cpp-pdf-render 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'C++ 渲染探針建置失敗' }
$probe = Get-ChildItem -LiteralPath (Join-Path $cpp 'build') -Recurse -Filter 'swbd-cpp-pdf-render.exe' -File |
         Sort-Object LastWriteTime -Descending | Select-Object -First 1
if (-not $probe) { throw '找不到 swbd-cpp-pdf-render.exe' }
"探針：$($probe.FullName)"

# 2) 素材（中文檔名，同時驗證 UTF-8 路徑）
$fixture = Join-Path $Artifacts '渲染測試 中文.pdf'
& $python (Join-Path $PSScriptRoot 'pdf_ref.py') --make $fixture
if ($LASTEXITCODE -ne 0) { throw '建立 PDF 素材失敗' }

$failures = 0
foreach ($case in @(@{ page = 1; dpi = 150 }, @{ page = 2; dpi = 200 })) {
    $tag = "p$($case.page)-$($case.dpi)dpi"
    $pyPng = Join-Path $Artifacts "py-$tag.png"
    $cppPng = Join-Path $Artifacts "cpp-$tag.png"
    $out = Join-Path $Artifacts "cpp-$tag.json"

    Write-Host "--- 第 $($case.page) 頁 @ $($case.dpi) dpi ---"
    & $python (Join-Path $PSScriptRoot 'pdf_render_ref.py') $fixture $case.page $case.dpi $pyPng
    if ($LASTEXITCODE -ne 0) { throw 'Python 渲染失敗' }

    $batch = Join-Path $Artifacts "run_render_$tag.cmd"
    $lines = @('@echo off', 'chcp 65001 >nul',
               "`"$($probe.FullName)`" `"$repo`" `"$fixture`" $($case.page) $($case.dpi) `"$cppPng`" > `"$out`"",
               'exit /b %errorlevel%')
    [IO.File]::WriteAllText($batch, ($lines -join "`r`n") + "`r`n", [Text.UTF8Encoding]::new($false))
    & cmd.exe /d /c $batch
    $probeCode = $LASTEXITCODE
    Get-Content -LiteralPath $out -Encoding UTF8 | ForEach-Object { "  C++ 探針：$_" }
    if ($probeCode -ne 0) { $failures++; continue }

    & $python (Join-Path $PSScriptRoot 'pdf_render_ref.py') --compare $cppPng $pyPng
    if ($LASTEXITCODE -ne 0) { $failures++ }
}

Write-Host ''
if ($failures -eq 0) {
    Write-Host 'PASS：原生 PDF 渲染與 Python（pypdfium2）逐像素相同。' -ForegroundColor Green
    exit 0
}
Write-Host "FAIL：$failures 個案例不同" -ForegroundColor Red
exit 1
