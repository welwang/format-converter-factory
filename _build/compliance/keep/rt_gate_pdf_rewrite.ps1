# qpdf 重寫層的等價閘門：與現行 pypdf 路徑比較頁數、逐頁文字與檔案大小。
# 只建置獨立模式的 C++ 核心（_build\cpp\build），不動外殼的建置目錄。
# 用法：gate_pdf_rewrite.ps1
$ErrorActionPreference = 'Stop'
$repo = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..'))
$buildRoot = Join-Path $repo '_build'
$cpp = Join-Path $buildRoot 'cpp'
$python = Join-Path $buildRoot 'venv\Scripts\python.exe'
$env:PYTHONPATH = Join-Path $buildRoot 'vendor'

function Invoke-Native([scriptblock]$Command) {
    $previous = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try { & $Command 2>&1 | ForEach-Object { Write-Host $_ } } finally { $ErrorActionPreference = $previous }
    return $LASTEXITCODE
}

Write-Host '=== 建置 qpdf 重寫探針（獨立模式）==='
& cmake -S $cpp -B (Join-Path $cpp 'build') -A x64 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'CMake 設定失敗' }
& cmake --build (Join-Path $cpp 'build') --config Release --target swbd-cpp-pdf-rewrite 2>&1 | Select-Object -Last 2
if ($LASTEXITCODE -ne 0) { throw '探針建置失敗' }
$probe = Get-ChildItem -LiteralPath (Join-Path $cpp 'build') -Recurse -Filter 'swbd-cpp-pdf-rewrite.exe' -File |
         Sort-Object LastWriteTime -Descending | Select-Object -First 1
if (-not $probe) { throw '找不到 swbd-cpp-pdf-rewrite.exe' }
"探針：$($probe.FullName)"

Write-Host '=== 逐項比對 ==='
& $python (Join-Path $PSScriptRoot 'check_pdf_rewrite.py') $probe.FullName $repo (Join-Path $buildRoot 'cpp-migration\pdf-rewrite') 2>&1 |
    ForEach-Object { Write-Host $_ }
exit $LASTEXITCODE
