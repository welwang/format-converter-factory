# C++ 遷移總驗收：C 基準線（固定基準修訂的 .c）與 C++ 現況逐項比對，並驗證方法接手與等價性。
#
#   1. 從固定基準修訂取出 C 版外殼原始碼，建 C 基準線 exe（.c／c11）
#   2. 建 engine-test（C 版 c11、C++ 版 c++20），跑同一組 JSON 測項
#   3. 建 C++ 外殼（CMake 單一專案），跑兩版的 --shell-smoke-test
#   4. 跑整合閘門：C++ 接手的方法由 C++ 回答、Python 不會收到請求
#   5. 跑 cleanup 的 Python 等價測試
#   6. 逐項比對全部輸出
#
# 用法：test_cpp_migration.ps1 [-SkipShell] [-SkipEquivalence] [-SkipWiring]
param(
    [switch]$SkipShell,
    [switch]$SkipEquivalence,
    [switch]$SkipWiring,
    [string]$BaselineRef = '416ab3d',
    [string]$AppRoot = ''
)
$ErrorActionPreference = 'Stop'
$repo = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..'))
$buildRoot = Join-Path $repo '_build'
$shell = Join-Path $buildRoot 'shell'
$cpp = Join-Path $buildRoot 'cpp'
$art = Join-Path $buildRoot 'cpp-migration'
$out = Join-Path $art 'out'
$gold = Join-Path $art 'golden'
$cbase = Join-Path $art 'c-baseline'
$python = Join-Path $buildRoot 'venv\Scripts\python.exe'
$sdk = Join-Path $shell 'sdk'
$inc = Join-Path $sdk 'build\native\include'
$lib = Join-Path $sdk 'build\native\x64'

# Windows PowerShell 5.1 turns a native program's stderr into a terminating error while
# $ErrorActionPreference is 'Stop'; every native step goes through this helper.
function Invoke-Native([scriptblock]$Command) {
    $previous = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try { & $Command 2>&1 | ForEach-Object { Write-Host $_ } } finally { $ErrorActionPreference = $previous }
    return $LASTEXITCODE
}

$vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio\Installer\vswhere.exe'
$vs = & $vswhere -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
if (-not $vs) { throw '找不到 Visual Studio C++ 工具。' }
$vcvars = Join-Path $vs 'VC\Auxiliary\Build\vcvars64.bat'
New-Item -ItemType Directory -Force -Path $out, $gold | Out-Null

function Build-EngineTest([string]$dir, [string[]]$sources, [string]$std, [string]$exeName,
                          [string[]]$ExtraSources = @(), [string[]]$ExtraIncludes = @()) {
    $objDir = Join-Path $out ($exeName -replace '\.exe$', '-obj')
    New-Item -ItemType Directory -Force -Path $objDir | Out-Null
    $all = @($sources | ForEach-Object { '"' + (Join-Path $dir $_) + '"' })
    foreach ($extra in $ExtraSources) { $all += '"' + $extra + '"' }
    $srcList = $all -join ' '
    $incList = ($ExtraIncludes | ForEach-Object { '/I "' + $_ + '"' }) -join ' '
    $exe = Join-Path $out $exeName
    $lines = @('@echo off', 'chcp 65001 >nul', "call `"$vcvars`" >nul", 'if errorlevel 1 exit /b 1',
        "cd /d `"$dir`"",
        "cl /nologo /utf-8 /MT /O2 /W3 /std:$std /D_CRT_SECURE_NO_WARNINGS $incList $srcList /Fo`"$objDir\\`" /Fe`"$exe`" /link user32.lib advapi32.lib shell32.lib",
        'exit /b %errorlevel%')
    $batch = Join-Path $out ("compile_$($exeName -replace '\.exe$','').cmd")
    [IO.File]::WriteAllText($batch, ($lines -join "`r`n") + "`r`n", [Text.UTF8Encoding]::new($false))
    if ((Invoke-Native { & cmd.exe /d /c $batch }) -ne 0 -or -not (Test-Path -LiteralPath $exe)) { throw "編譯失敗：$exeName" }
    "  建置 $exeName（{0:N0} bytes）" -f (Get-Item -LiteralPath $exe).Length
}

Write-Host "=== 1) C 基準線（git $BaselineRef 的 .c）==="
$cbShell = Join-Path $cbase 'shell'
$cbOut = Join-Path $cbase 'out'
New-Item -ItemType Directory -Force -Path $cbShell, $cbOut | Out-Null
$cbFiles = @('main.c','api.c','engine.c','plat.c','json.c','engine_test_cli.c','api.h','engine.h','plat.h','json.h','shell.rc','app.manifest')
foreach ($f in $cbFiles) {
    $target = Join-Path $cbShell $f
    cmd /c "cd /d `"$repo`" && git show ${BaselineRef}:_build/shell/$f > `"$target`""
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $target)) { throw "無法取出 ${BaselineRef}:_build/shell/$f" }
}
Copy-Item -LiteralPath (Join-Path $buildRoot 'logo.ico') -Destination (Join-Path $cbase 'logo.ico') -Force
$cbExe = Join-Path $cbOut 'swbd-shell-c.exe'
$cbLines = @('@echo off', 'chcp 65001 >nul', "call `"$vcvars`" >nul", 'if errorlevel 1 exit /b 1',
    "cd /d `"$cbShell`"",
    "rc /nologo /fo `"$cbOut\shell.res`" shell.rc", 'if errorlevel 1 exit /b 1',
    "cl /nologo /O2 /W3 /utf-8 /MT /std:c11 /GS /guard:cf /DUNICODE /D_UNICODE /I `"$inc`" main.c api.c engine.c plat.c json.c `"$cbOut\shell.res`" /Fo`"$cbOut\\`" /Fe`"$cbExe`" /link /SUBSYSTEM:WINDOWS /GUARD:CF /LIBPATH:`"$lib`"",
    'exit /b %errorlevel%')
$cbBatch = Join-Path $cbOut 'compile_c_baseline.cmd'
[IO.File]::WriteAllText($cbBatch, ($cbLines -join "`r`n") + "`r`n", [Text.UTF8Encoding]::new($false))
if ((Invoke-Native { & cmd.exe /d /c $cbBatch }) -ne 0) { throw 'C 版基準線編譯失敗' }
'  建置 swbd-shell-c.exe（{0:N0} bytes）' -f (Get-Item -LiteralPath $cbExe).Length

Write-Host '=== 2) 引擎測試驅動與等價閘門 ==='
Build-EngineTest $cbShell @('engine_test_cli.c','engine.c','plat.c','json.c') 'c11' 'engine-test-c.exe'
# C++ 這一側直接用 CMake 建置（產品建置路徑）：不重抄原始檔清單，旗標與 include 一律與產品一致。
Write-Host '  以 CMake 建置 engine-test（產品建置路徑）'
$cmakeBuild = Join-Path $shell 'out\cmake'
& (Join-Path $shell 'build_shell.ps1') | Out-Null      # 取得 SDK、configure 並建置外殼
if ($LASTEXITCODE -ne 0) { throw 'build_shell.ps1 失敗' }
& cmake --build $cmakeBuild --config Release --target engine-test 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'CMake 建置失敗（engine-test）' }
$builtCpp = Get-ChildItem -LiteralPath $cmakeBuild -Recurse -Filter 'engine-test.exe' -File |
            Sort-Object LastWriteTime -Descending | Select-Object -First 1
if (-not $builtCpp) { throw '找不到 CMake 建出的 engine-test.exe' }
Copy-Item -LiteralPath $builtCpp.FullName -Destination (Join-Path $out 'engine-test-cpp.exe') -Force
'  建置 engine-test-cpp.exe（{0:N0} bytes，CMake）' -f (Get-Item -LiteralPath (Join-Path $out 'engine-test-cpp.exe')).Length
foreach ($pair in @(@('engine-test-c.exe','engine-c.json'), @('engine-test-cpp.exe','engine-cpp.json'), @('engine-test-c.exe','engine-c2.json'))) {
    & $python (Join-Path $PSScriptRoot 'gate_engine.py') (Join-Path $out $pair[0]) (Join-Path $gold $pair[1]) (Join-Path $gold ('work-' + ($pair[1] -replace '\.json$',''))) $repo
    if ($LASTEXITCODE -ne 0) { throw "引擎閘門失敗：$($pair[1])" }
}
Write-Host '  三個引擎閘門都完成（C、C++、C 重跑）'

if (-not $SkipShell) {
    Write-Host '=== 3) C++ 外殼建置與煙霧閘門 ==='
    & (Join-Path $shell 'build_shell.ps1')
    if ($LASTEXITCODE -ne 0) { throw 'C++ 外殼建置失敗' }
    Write-Host '  重新錄下固定 C 基準線的煙霧報告'
    & (Join-Path $PSScriptRoot 'gate_shell.ps1') -Exe $cbExe -OutJson (Join-Path $gold 'shell-c.json') -AppRoot $AppRoot
    if ($LASTEXITCODE -ne 0) { throw 'C 基準線煙霧閘門失敗' }
    & (Join-Path $PSScriptRoot 'gate_shell.ps1') -Exe (Join-Path $shell 'out\swbd-shell.exe') -OutJson (Join-Path $gold 'shell-cpp.json') -AppRoot $AppRoot
    if ($LASTEXITCODE -ne 0) { throw 'C++ 外殼煙霧閘門失敗' }
}

if (-not $SkipWiring) {
    Write-Host '=== 4) 整合閘門（C++ 真的接手、Python 不被呼叫）==='
    $wiring = Get-ChildItem -LiteralPath (Join-Path $shell 'out\cmake') -Recurse -Filter 'swbd-cpp-wiring.exe' -File -ErrorAction SilentlyContinue |
              Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if (-not $wiring) { throw '找不到 swbd-cpp-wiring.exe（請先建置外殼）' }
    $wiringData = Join-Path $out 'wiring-data'
    New-Item -ItemType Directory -Force -Path (Join-Path $wiringData 'logs') | Out-Null
    Set-Content -LiteralPath (Join-Path $wiringData 'logs\zdgc.log') -Value 'fixture' -Encoding UTF8
    if ((Invoke-Native { & $wiring.FullName $repo $wiringData }) -ne 0) { throw '整合閘門失敗' }
    '整合閘門：PASS'
}

if (-not $SkipEquivalence) {
    Write-Host '=== 5) cleanup 等價測試（C++ vs Python）==='
    & (Join-Path $cpp 'tests\equivalence.ps1') | Select-Object -Last 3
    if ($LASTEXITCODE -ne 0) { throw '等價測試失敗' }
}

Write-Host '=== 6) 逐項比對 ==='
$compareArgs = @($gold)
if ($SkipShell) { $compareArgs += '--engine-only' }
& $python (Join-Path $PSScriptRoot 'gate_compare.py') @compareArgs
exit $LASTEXITCODE
