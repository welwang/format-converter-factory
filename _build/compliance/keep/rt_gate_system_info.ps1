# system_info 等價閘門：C++ 接手的系統資訊要與 Python（system_tools.hardware_info + CLEANUP）相同。
# 走的是 wiring 探針：它連結 shell 的 api.cpp，所以測到的是**正式的注入路徑**（api_cpp_system_facts），
# 而不是自己塞一份假資料。
# 用法：gate_system_info.ps1
$ErrorActionPreference = 'Stop'
$repo = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..'))
$buildRoot = Join-Path $repo '_build'
$shell = Join-Path $buildRoot 'shell'
$python = Join-Path $buildRoot 'venv\Scripts\python.exe'
$env:PYTHONPATH = (Join-Path $buildRoot 'vendor') + ';' + (Join-Path $buildRoot 'src')
$work = Join-Path $buildRoot 'cpp-migration\system-info'
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
exit (Invoke-Native { & $python (Join-Path $PSScriptRoot 'check_system_info.py') $wire.FullName $repo $work })
