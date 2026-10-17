# 建置 C++ 主程式（四維八德.exe）：Win32 視窗 + Microsoft Edge WebView2。
# 需要 Visual Studio 2022／2026（「使用 C++ 的桌面開發」）與 CMake；WebView2 SDK 第一次建置時自動下載到 shell\sdk。
# 實際編譯規則在 shell\CMakeLists.txt（C++20）；本腳本負責取得 SDK、驅動 CMake、複製輸出。
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

    # 2. CMake (the Visual Studio generator is the default on a machine with VS installed)
    $cmake = (Get-Command cmake.exe -ErrorAction SilentlyContinue).Source
    if (-not $cmake) { $cmake = Join-Path ${env:ProgramFiles} 'CMake\bin\cmake.exe' }
    if (-not (Test-Path -LiteralPath $cmake)) { throw '找不到 CMake。請安裝 CMake（或 Visual Studio 的 C++ CMake 工具）後再建置。' }

    # 3. configure + build
    $build = Join-Path $here 'out\cmake'
    Log '設定 CMake…'
    & $cmake -S $here -B $build "-DSWBD_WEBVIEW2_SDK=$sdk" 2>&1 | Add-Content -LiteralPath $log -Encoding UTF8
    if ($LASTEXITCODE -ne 0) { throw "CMake 設定失敗，詳細訊息在 $log" }
    Log '編譯中…'
    & $cmake --build $build --config Release 2>&1 | Add-Content -LiteralPath $log -Encoding UTF8
    if ($LASTEXITCODE -ne 0) { throw "編譯失敗，詳細訊息在 $log" }

    $built = Get-ChildItem -LiteralPath $build -Recurse -Filter 'swbd-shell.exe' -File |
             Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if (-not $built) { throw "建置完成但找不到 swbd-shell.exe，詳細訊息在 $log" }

    $outDir = Join-Path $here 'out'
    New-Item -ItemType Directory -Force -Path $outDir | Out-Null
    $exe = Join-Path $outDir 'swbd-shell.exe'
    Copy-Item -LiteralPath $built.FullName -Destination $exe -Force
    if ($OutFile) { Copy-Item -LiteralPath $exe -Destination $OutFile -Force }
    Log "完成：$exe"
} catch {
    Log ('失敗：' + $_.Exception.Message)
    exit 1
}
