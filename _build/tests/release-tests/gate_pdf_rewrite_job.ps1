# PDF→PDF（qpdf 重寫）原生工作的閘門：建置 engine-test，驗證分派政策矩陣、
# 工作由 qpdf 完成、內容（頁數／文字／圖片）等價、以及「原檔已最小就複製」的退路。
# 用法：gate_pdf_rewrite_job.ps1
$ErrorActionPreference = 'Stop'
$repo = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..'))
$buildRoot = Join-Path $repo '_build'
$python = Join-Path $buildRoot 'venv\Scripts\python.exe'
$env:PYTHONPATH = Join-Path $buildRoot 'vendor'

function Invoke-Native([scriptblock]$Command) {
    $previous = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try { & $Command 2>&1 | ForEach-Object { Write-Host $_ } } finally { $ErrorActionPreference = $previous }
    return $LASTEXITCODE
}

Write-Host '=== 建置 engine-test（C 引擎測試驅動）==='
& (Join-Path $PSScriptRoot 'build_test_cli.ps1')
$exe = Join-Path $buildRoot 'shell\out\engine-test.exe'
if (-not (Test-Path -LiteralPath $exe)) { throw '找不到 engine-test.exe' }

Write-Host '=== 執行原生工作並逐項比對 ==='
$code = Invoke-Native { & $python (Join-Path $PSScriptRoot 'check_pdf_rewrite_job.py') $exe $repo (Join-Path $buildRoot 'cpp-migration\pdf-rewrite-job') }
exit $code
