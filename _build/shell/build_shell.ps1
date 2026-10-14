# 建置 C 主程式（四維八德.exe）：Win32 視窗 + Microsoft Edge WebView2。
# 需要 Visual Studio 2022 或 Build Tools（「使用 C++ 的桌面開發」）；WebView2 SDK 第一次建置時自動下載到 shell\sdk。
# 輸出：shell\out\swbd-shell.exe；完整記錄：shell\build_shell.log
param([string]$OutFile = '')
$ErrorActionPreference = 'Stop'
$here = $PSScriptRoot
$log = Join-Path $here 'build_shell.log'
"建置開始 $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" | Set-Content -LiteralPath $log -Encoding UTF8
function Log($m) { $m | Add-Content -LiteralPath $log -Encoding UTF8; Write-Host $m }
try {
    # 1. WebView2 SDK (header + static loader, so the program needs no WebView2Loader.dll)
    $sdk = Join-Path $here 'sdk'
    $header = Join-Path $sdk 'build\native\include\WebView2.h'
    if (-not (Test-Path -LiteralPath $header)) {
        Log '下載 WebView2 SDK…'
        $pkg = Join-Path $here 'webview2-sdk.zip'
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        Invoke-WebRequest -UseBasicParsing -Uri 'https://api.nuget.org/v3-flatcontainer/microsoft.web.webview2/1.0.4258.31/microsoft.web.webview2.1.0.4258.31.nupkg' -OutFile $pkg
        $sdkAbsolute = [IO.Path]::GetFullPath($sdk)
        if (-not $sdkAbsolute.StartsWith([IO.Path]::GetFullPath($here) + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'SDK 路徑超出本次建置目錄' }
        if (Test-Path -LiteralPath $sdkAbsolute) {
            if ((Get-Item -LiteralPath $sdkAbsolute).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'SDK 目錄不可為連結' }
            Remove-Item -LiteralPath $sdkAbsolute -Recurse -Force
        }
        Expand-Archive -LiteralPath $pkg -DestinationPath $sdk
        Remove-Item -LiteralPath $pkg
        if (-not (Test-Path -LiteralPath $header)) { throw 'WebView2 SDK 內容不完整' }
    }
    $lib = Join-Path $sdk 'build\native\x64'

    # 2. MSVC
    $vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio\Installer\vswhere.exe'
    if (-not (Test-Path -LiteralPath $vswhere)) { throw '找不到 Visual Studio。請安裝 Visual Studio 2022 Build Tools，勾選「使用 C++ 的桌面開發」。' }
    $vs = & $vswhere -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
    if (-not $vs) { throw 'Visual Studio 缺少 C++ 編譯器。請在 Visual Studio Installer 勾選「使用 C++ 的桌面開發」。' }
    $vcvars = Join-Path $vs 'VC\Auxiliary\Build\vcvars64.bat'

    # 3. compile (static C runtime: the shell itself needs no Visual C++ Redistributable)
    $out = Join-Path $here 'out'
    New-Item -ItemType Directory -Force -Path $out | Out-Null
    $exe = Join-Path $out 'swbd-shell.exe'
    $batch = Join-Path $out 'compile.cmd'
    $lines = @('@echo off', 'chcp 65001 >nul', "call `"$vcvars`" >nul", 'if errorlevel 1 exit /b 1',
        "cd /d `"$here`"", "rc /nologo /fo `"$out\shell.res`" shell.rc", 'if errorlevel 1 exit /b 1',
        "cl /nologo /O2 /W3 /utf-8 /MT /std:c11 /GS /guard:cf /DUNICODE /D_UNICODE /I `"$sdk\build\native\include`" main.c api.c engine.c plat.c json.c `"$out\shell.res`" /Fo`"$out\\`" /Fe`"$exe`" /link /SUBSYSTEM:WINDOWS /GUARD:CF /LIBPATH:`"$lib`"", 'exit /b %errorlevel%')
    [IO.File]::WriteAllText($batch, ($lines -join "`r`n")+"`r`n", [Text.UTF8Encoding]::new($false))
    Log '編譯中…'
    $output = & cmd.exe /d /c $batch 2>&1
    $output | Add-Content -LiteralPath $log -Encoding UTF8
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $exe)) { throw "編譯失敗，詳細訊息在 $log" }
    if ($OutFile) { Copy-Item -LiteralPath $exe -Destination $OutFile -Force }
    Log "完成：$exe"
} catch {
    Log ('失敗：' + $_.Exception.Message)
    exit 1
}
