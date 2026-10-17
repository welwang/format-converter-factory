# 工具箱（run_tool）等價閘門：C++ 接手的原生工具要與 Python 版相同。
# 走 wiring 探針的 --run-tool：api_request → C++ run_tool → eng_submit_tool → 引擎原生工具工作。
# 用法：gate_pdf_tools.ps1
$ErrorActionPreference = 'Stop'
$repo = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..'))
$buildRoot = Join-Path $repo '_build'
$shell = Join-Path $buildRoot 'shell'
$python = Join-Path $buildRoot 'venv\Scripts\python.exe'
$env:PYTHONPATH = (Join-Path $buildRoot 'vendor') + ';' + (Join-Path $buildRoot 'src')
$work = Join-Path $buildRoot 'cpp-migration\pdf-tools'
New-Item -ItemType Directory -Force -Path $work | Out-Null

function Invoke-Native([scriptblock]$Command) {
    $previous = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try { & $Command 2>&1 | ForEach-Object { Write-Host $_ } } finally { $ErrorActionPreference = $previous }
    return $LASTEXITCODE
}

Write-Host '=== 建置外殼與 wiring 探針（產品建置路徑）==='
& (Join-Path $shell 'build_shell.ps1') | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'build_shell.ps1 失敗' }
& cmake --build (Join-Path $shell 'out\cmake') --config Release --target swbd-cpp-wiring 2>&1 | Select-Object -Last 2
if ($LASTEXITCODE -ne 0) { throw 'wiring 探針建置失敗' }
$wire = Get-ChildItem -LiteralPath (Join-Path $shell 'out\cmake') -Recurse -Filter 'swbd-cpp-wiring.exe' -File |
        Sort-Object LastWriteTime -Descending | Select-Object -First 1
if (-not $wire) { throw '找不到 swbd-cpp-wiring.exe' }
"探針：$($wire.FullName)"

Write-Host '=== 逐項比對 ==='
exit (Invoke-Native { & $python (Join-Path $PSScriptRoot 'check_pdf_tools.py') $wire.FullName $repo $work })
