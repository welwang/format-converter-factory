# 既有回歸套件的可重複執行版本。
#
# 為什麼要另開工作區：這些腳本需要 ASCII 路徑的測試工作區，而且需要幾個相對配置：
#   <工作區>\shell          → _build\shell        （engine-test.exe）
#   <工作區>\release        → 候選版本目錄        （tools\ 內的 ghostscript／pdf-ocr／pdf-ai…）
#   <工作區>\src            → _build\src          （index.html 等前端檔案）
#   <工作區>\..\..\shell    → _build\shell        （test_uri_paths.ps1 用 PSScriptRoot\..\.. 找 main.cpp）
# 另外 PDF 套件會把 tempfile.tempdir 設在 <工作區>\scratch；pdf_tools 的 OCR 模型快取在來源路徑
# 非 ASCII 時會用到它，若工作區本身是非 ASCII，快取會退回到（本機不可寫的）Public\Documents 而失敗。
# 所以工作區預設放在 E:\swbd-tests\_build\tests\release-tests。
#
# 用法：
#   run_legacy_regression.ps1                       # 用最新的發布候選版本
#   run_legacy_regression.ps1 -Release <目錄>       # 指定受測目錄（或 E:\四維八德）
#   run_legacy_regression.ps1 -Only test_pdf        # 只跑檔名含此字串的套件
param(
    [string]$Workspace = 'E:\swbd-tests\_build\tests\release-tests',
    [string]$Release = '',
    [string]$Only = ''
)
$ErrorActionPreference = 'Stop'
$repo = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..'))
$buildRoot = Join-Path $repo '_build'
$python = Join-Path $buildRoot 'venv\Scripts\python.exe'
$tests = Join-Path $buildRoot 'tests\release-tests'

# 1) 決定受測的應用程式目錄：預設用最新的發布候選版本
if (-not $Release) {
    $stage = Get-ChildItem -LiteralPath $buildRoot -Directory -Filter 'release-stage-*' -ErrorAction SilentlyContinue |
             Sort-Object Name -Descending | Select-Object -First 1
    if ($stage -and (Test-Path -LiteralPath (Join-Path $stage.FullName 'dist\swbd-core\四維八德.exe'))) {
        $Release = Join-Path $stage.FullName 'dist\swbd-core'
    } else {
        $Release = $repo
    }
}
if (-not (Test-Path -LiteralPath (Join-Path $Release '四維八德.exe'))) { throw "找不到受測版本：$Release" }

# 2) 重建 ASCII 工作區（每次都重新複製測試腳本，避免改過的測試沒被帶進去）
Write-Host "=== 準備測試工作區：$Workspace ==="
if (Test-Path -LiteralPath $Workspace) { Remove-Item -LiteralPath $Workspace -Recurse -Force }
New-Item -ItemType Directory -Path $Workspace -Force | Out-Null
Get-ChildItem -LiteralPath $tests -File | Where-Object { $_.Extension -in '.py', '.cjs', '.ps1' } |
    ForEach-Object { Copy-Item -LiteralPath $_.FullName -Destination $Workspace -Force }
New-Item -ItemType Directory -Path (Join-Path $Workspace 'scratch') -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $Workspace '..\..') -Force | Out-Null
$links = @(
    @((Join-Path $Workspace 'shell'), (Join-Path $buildRoot 'shell')),
    @((Join-Path $Workspace '..\..\shell'), (Join-Path $buildRoot 'shell')),
    @((Join-Path $Workspace 'src'), (Join-Path $buildRoot 'src')),
    @((Join-Path $Workspace 'release'), $Release)
)
foreach ($pair in $links) {
    $target = [IO.Path]::GetFullPath($pair[0])
    if (Test-Path -LiteralPath $target) { cmd /c rmdir "$target" | Out-Null }
    cmd /c mklink /J "$target" ([IO.Path]::GetFullPath($pair[1])) | Out-Null
}
"  受測版本：$Release"
"  測試腳本：$((Get-ChildItem -LiteralPath $Workspace -File).Count) 個"

# 3) 前端套件需要工具表單結構
$env:PYTHONPATH = "$buildRoot\src;$buildRoot\vendor"
$env:PYTHONIOENCODING = 'utf-8'
$previous = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
& $python -c "import json,sys;sys.path.insert(0,sys.argv[1]);import tools as T;json.dump(T.schema(),open(sys.argv[2],'w',encoding='utf-8'),ensure_ascii=False)" `
    (Join-Path $buildRoot 'src') (Join-Path $Workspace 'scratch\tool-schema.json')
$ErrorActionPreference = $previous
if (-not (Test-Path -LiteralPath (Join-Path $Workspace 'scratch\tool-schema.json'))) { throw '無法產生 scratch\tool-schema.json' }
Set-Location $Workspace

# 4) 套件清單（順序有意義：test_engine_windows 會建立 test_feature_edges 需要的 fixtures）
$suites = @(
    @{ name = 'engine（C 轉檔與工作控制）';       kind = 'py';     file = 'test_engine_windows.py' },
    @{ name = 'equivalence（C／Python 內容比對）'; kind = 'py';     file = 'test_equivalence.py' },
    @{ name = 'native options（C 編碼與加速）';   kind = 'py';     file = 'test_native_options.py' },
    @{ name = 'protocol（視窗管線與對話框）';     kind = 'py';     file = 'test_protocol.py' },
    @{ name = 'pdf suite（PDF 功能與內容）';      kind = 'py';     file = 'test_pdf_suite.py' },
    @{ name = 'additional（工作流程與工具）';     kind = 'py';     file = 'test_additional.py' },
    @{ name = 'feature edges（特殊格式與邊界）';  kind = 'py';     file = 'test_feature_edges.py' },
    @{ name = 'integration（交付與電腦工具）';  kind = 'py';     file = 'test_integration.py' },
    @{ name = 'uri paths（Unicode 與網址限制）';  kind = 'ps1';    file = 'test_uri_paths.ps1' },
    @{ name = 'logo（新版圖示資源）';             kind = 'logopy'; file = 'test_logo_resources.py' },
    @{ name = 'ui（介面與表單）';                 kind = 'cjs';    file = 'test_ui.cjs' }
)

$results = @()
foreach ($suite in $suites) {
    if ($Only -and $suite.file -notmatch [regex]::Escape($Only)) { continue }
    Write-Host ''
    Write-Host "=== $($suite.name)（$($suite.file)）==="
    $log = Join-Path $Workspace ("suite-" + [IO.Path]::GetFileNameWithoutExtension($suite.file) + ".log")
    # 一律把輸出寫進檔案再讀回來：PowerShell 5.1 對原生程式 stderr 的處理會讓管線擷取失效。
    $previous = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        switch ($suite.kind) {
            'py'     { & $python -u (Join-Path $Workspace $suite.file) *> $log; $code = $LASTEXITCODE }
            'ps1'    { & (Join-Path $Workspace $suite.file) *> $log; $code = $LASTEXITCODE }
            'logopy' { & $python (Join-Path $Workspace $suite.file) (Join-Path $Release '四維八德.exe') (Join-Path $buildRoot 'logo.ico') *> $log; $code = $LASTEXITCODE }
            'cjs'    { & node (Join-Path $Workspace $suite.file) *> $log; $code = $LASTEXITCODE }
        }
    } finally {
        $ErrorActionPreference = $previous
    }
    $output = @()
    if (Test-Path -LiteralPath $log) { $output = Get-Content -LiteralPath $log -Encoding UTF8 }
    $output | Select-Object -Last 5 | ForEach-Object { "  $_" }
    $line = ($output | Select-String -Pattern 'PASSED \d+ ?/ ?\d+|^OK$|Ran \d+ tests|"ok": true' | Select-Object -Last 1)
    $results += [pscustomobject]@{
        suite  = $suite.name
        exit   = $code
        detail = if ($line) { $line.Line.Trim() } else { '(沒有可辨識的結果行)' }
        ok     = ($code -eq 0)
    }
}

# 5) 總結
Write-Host ''
Write-Host '=== 既有回歸套件總結 ==='
foreach ($r in $results) {
    "{0} {1,-34} exit={2}  {3}" -f $(if ($r.ok) { '[PASS]' } else { '[FAIL]' }), $r.suite, $r.exit, $r.detail
}
$failed = @($results | Where-Object { -not $_.ok }).Count
"  套件：$($results.Count) 個，失敗 $failed 個"
if ($failed) { Write-Host '既有回歸套件有失敗項目。'; exit 1 }
Write-Host '既有回歸套件全部通過。'
exit 0
