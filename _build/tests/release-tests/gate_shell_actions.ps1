# 驗證新接手的三個方法（drives／open_file／reveal）與 Python 版等價。
# 只建置獨立模式的 C++ 核心（_build\cpp\build），不動外殼的建置目錄，可與發布建置並行。
# 用法：gate_shell_actions.ps1
$ErrorActionPreference = 'Stop'
$repo = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..'))
$buildRoot = Join-Path $repo '_build'
$cpp = Join-Path $buildRoot 'cpp'
$python = Join-Path $buildRoot 'venv\Scripts\python.exe'
$env:PYTHONPATH = (Join-Path $buildRoot 'vendor') + ';' + (Join-Path $buildRoot 'src')

# 探針會把「已註冊 N 個方法」寫到 stderr；PowerShell 5.1 在 Stop 模式下會把它當成終止錯誤。
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

Write-Host '=== 逐項比對 ==='
$work = Join-Path $buildRoot 'cpp-migration\shell-actions'
& $python (Join-Path $PSScriptRoot 'check_shell_actions.py') $probe.FullName $repo $work
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

# 獨立交叉驗證 drives：用 Windows 自己的 WMI（DriveType=5 就是光碟機）當第二個來源，
# 避免「C++ 與 Python 都錯」的情況被漏掉。
Write-Host '=== 獨立交叉驗證（WMI Win32_LogicalDisk）==='
$outFile = Join-Path $work 'drives.json'
if ((Invoke-Native { & $probe.FullName $repo $work drives --out $outFile }) -ne 0) { throw 'drives 探針執行失敗' }
$native = @((Get-Content -LiteralPath $outFile -Raw -Encoding UTF8 | ConvertFrom-Json).r |
            ForEach-Object { $_.path } | Sort-Object)
$wmi = @(Get-CimInstance Win32_LogicalDisk -ErrorAction SilentlyContinue |
         Where-Object { $_.DriveType -eq 5 } | ForEach-Object { $_.DeviceID + '\' } | Sort-Object)
"  WMI（DriveType=5）：[$($wmi -join ', ')]"
"  C++ drives        ：[$($native -join ', ')]"
if (Compare-Object -ReferenceObject $wmi -DifferenceObject $native) { throw 'drives 與 WMI 的結果不一致' }
Write-Host '  一致'
exit 0
