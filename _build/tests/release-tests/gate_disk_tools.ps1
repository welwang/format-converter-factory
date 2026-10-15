# 磁碟工具模組的等價閘門：C++ 接手的 disk_info／disk_preview／disk_launch 要與 Python 版相同，
# 並以 WMI（Win32_LogicalDisk）當獨立來源交叉驗證磁碟清單。
# 用法：gate_disk_tools.ps1
$ErrorActionPreference = 'Stop'
$repo = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..'))
$buildRoot = Join-Path $repo '_build'
$cpp = Join-Path $buildRoot 'cpp'
$python = Join-Path $buildRoot 'venv\Scripts\python.exe'
$env:PYTHONPATH = (Join-Path $buildRoot 'vendor') + ';' + (Join-Path $buildRoot 'src')
$work = Join-Path $buildRoot 'cpp-migration\disk-tools'
New-Item -ItemType Directory -Force -Path $work | Out-Null

function Invoke-Native([scriptblock]$Command) {
    $previous = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try { & $Command 2>&1 | ForEach-Object { Write-Host $_ } } finally { $ErrorActionPreference = $previous }
    return $LASTEXITCODE
}

Write-Host '=== 建置探針（獨立模式）==='
& cmake -S $cpp -B (Join-Path $cpp 'build') -A x64 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'CMake 設定失敗' }
& cmake --build (Join-Path $cpp 'build') --config Release --target swbd-cpp-probe 2>&1 | Select-Object -Last 2
if ($LASTEXITCODE -ne 0) { throw '探針建置失敗' }
$probe = Get-ChildItem -LiteralPath (Join-Path $cpp 'build') -Recurse -Filter 'swbd-cpp-probe.exe' -File |
         Sort-Object LastWriteTime -Descending | Select-Object -First 1
if (-not $probe) { throw '找不到 swbd-cpp-probe.exe' }
"探針：$($probe.FullName)"

# 獨立來源：Windows 自己怎麼說（固定 3 與可移除 2 的磁碟）
$wmiJson = Join-Path $work 'wmi.json'
@(Get-CimInstance Win32_LogicalDisk -ErrorAction SilentlyContinue |
  Where-Object { $_.DriveType -eq 2 -or $_.DriveType -eq 3 } |
  Select-Object DeviceID, FileSystem, FreeSpace) |
  ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $wmiJson -Encoding UTF8

Write-Host '=== 逐項比對 ==='
exit (Invoke-Native { & $python (Join-Path $PSScriptRoot 'check_disk_tools.py') $probe.FullName $repo $work $wmiJson })
