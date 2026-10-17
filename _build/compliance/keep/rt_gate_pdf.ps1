# 原生 PDF 層等價閘門：同一份 PDF 分別用 C++（PDFium）與 Python（pymupdf）讀取，逐欄比對。
# 用法：gate_pdf.ps1 [-Artifacts <目錄>]
param([string]$Artifacts = '')
$ErrorActionPreference = 'Stop'
$repo = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..'))
$buildRoot = Join-Path $repo '_build'
$python = Join-Path $buildRoot 'venv\Scripts\python.exe'
$env:PYTHONPATH = Join-Path $buildRoot 'vendor'
if (-not $Artifacts) { $Artifacts = Join-Path $buildRoot 'cpp-migration\pdf' }
New-Item -ItemType Directory -Force -Path $Artifacts | Out-Null

# 1) 找探針；找不到就用獨立模式建置 C++ 核心
$probe = Get-ChildItem -LiteralPath (Join-Path $buildRoot 'shell\out\cmake'), (Join-Path $buildRoot 'cpp\build') -Recurse -Filter 'swbd-cpp-pdf-probe.exe' -File -ErrorAction SilentlyContinue |
         Sort-Object LastWriteTime -Descending | Select-Object -First 1
if (-not $probe) {
    $cpp = Join-Path $buildRoot 'cpp'
    & cmake -S $cpp -B (Join-Path $cpp 'build') -A x64 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'CMake 設定失敗' }
    & cmake --build (Join-Path $cpp 'build') --config Release --target swbd-cpp-pdf-probe 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'PDF 探針建置失敗' }
    $probe = Get-ChildItem -LiteralPath (Join-Path $cpp 'build') -Recurse -Filter 'swbd-cpp-pdf-probe.exe' -File |
             Sort-Object LastWriteTime -Descending | Select-Object -First 1
}
if (-not $probe) { throw '找不到 swbd-cpp-pdf-probe.exe' }
"探針：$($probe.FullName)"

# 2) 素材（刻意用中文檔名，同時驗證 UTF-8 路徑）
$fixture = Join-Path $Artifacts '測試文件 中文.pdf'
& $python (Join-Path $PSScriptRoot 'pdf_ref.py') --make $fixture
if ($LASTEXITCODE -ne 0) { throw '建立 PDF 素材失敗' }

# 3) 兩邊各寫一份 JSON（原生輸出用 cmd 重導，避免 PowerShell 以主控台編碼解讀）
$pyJson = Join-Path $Artifacts 'py.json'
$cppJson = Join-Path $Artifacts 'cpp.json'
& $python (Join-Path $PSScriptRoot 'pdf_ref.py') --out $pyJson $fixture
if ($LASTEXITCODE -ne 0) { throw 'Python 參考實作失敗' }
$batch = Join-Path $Artifacts 'run_pdf_probe.cmd'
$lines = @('@echo off', 'chcp 65001 >nul', "`"$($probe.FullName)`" `"$repo`" `"$fixture`" > `"$cppJson`"", 'exit /b %errorlevel%')
[IO.File]::WriteAllText($batch, ($lines -join "`r`n") + "`r`n", [Text.UTF8Encoding]::new($false))
& cmd.exe /d /c $batch
if ($LASTEXITCODE -ne 0) { throw '原生探針執行失敗' }

# 4) 逐欄比對
$py = @(Get-Content -LiteralPath $pyJson -Encoding UTF8 | Where-Object { $_.Trim() } | ForEach-Object { $_ | ConvertFrom-Json })
$cpp = @(Get-Content -LiteralPath $cppJson -Encoding UTF8 | Where-Object { $_.Trim() } | ForEach-Object { $_ | ConvertFrom-Json })
$diffs = New-Object System.Collections.Generic.List[string]
if ($py.Count -ne $cpp.Count) { $diffs.Add("行數不同：Python=$($py.Count) C++=$($cpp.Count)") }
for ($i = 0; $i -lt [Math]::Min($py.Count, $cpp.Count); $i++) {
    foreach ($key in 'file', 'pages', 'title', 'author', 'producer', 'creator') {
        if ("$($py[$i].$key)" -ne "$($cpp[$i].$key)") {
            $diffs.Add("$key 不同：Python=$($py[$i].$key) C++=$($cpp[$i].$key)")
        }
    }
    $ps = @($py[$i].sizes); $cs = @($cpp[$i].sizes)
    if ($ps.Count -ne $cs.Count) { $diffs.Add("頁面數不同：$($ps.Count) vs $($cs.Count)"); continue }
    for ($j = 0; $j -lt $ps.Count; $j++) {
        if ([Math]::Abs([double]$ps[$j][0] - [double]$cs[$j][0]) -gt 0.01 -or
            [Math]::Abs([double]$ps[$j][1] - [double]$cs[$j][1]) -gt 0.01) {
            $diffs.Add("第 $($j + 1) 頁尺寸不同：$($ps[$j] -join 'x') vs $($cs[$j] -join 'x')")
        }
    }
}
Write-Host "--- Python ---"; $py | ForEach-Object { $_ | ConvertTo-Json -Compress -Depth 6 }
Write-Host "--- C++ (PDFium) ---"; $cpp | ForEach-Object { $_ | ConvertTo-Json -Compress -Depth 6 }
if ($diffs.Count -eq 0) {
    Write-Host 'PASS：原生 PDF 層與 Python 逐欄相同（頁數、頁面尺寸、中繼資料）。' -ForegroundColor Green
    exit 0
}
Write-Host "FAIL：$($diffs.Count) 項不同" -ForegroundColor Red
$diffs | ForEach-Object { Write-Host "  $_" -ForegroundColor Red }
exit 1
