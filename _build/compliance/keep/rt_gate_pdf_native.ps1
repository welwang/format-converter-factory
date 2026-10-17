# 原生 PDF→PNG 工作的等價閘門：建置 engine-test，驅動 C 引擎跑一次 PDF→PNG 工作，
# 再與 Python（pypdfium2 + Pillow）逐頁逐像素比對。
# 用法：gate_pdf_native.ps1
$ErrorActionPreference = 'Stop'
$repo = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..'))
$buildRoot = Join-Path $repo '_build'
$python = Join-Path $buildRoot 'venv\Scripts\python.exe'
$env:PYTHONPATH = Join-Path $buildRoot 'vendor'

Write-Host '=== 建置 engine-test（C 引擎測試驅動）==='
& (Join-Path $PSScriptRoot 'build_test_cli.ps1')
$exe = Join-Path $buildRoot 'shell\out\engine-test.exe'
if (-not (Test-Path -LiteralPath $exe)) { throw '找不到 engine-test.exe' }

$work = Join-Path $buildRoot 'cpp-migration\pdf-native-job'
Write-Host '=== 執行原生工作並與 Python 比對 ==='
& $python (Join-Path $PSScriptRoot 'check_pdf_native_job.py') $exe $repo $work
exit $LASTEXITCODE
