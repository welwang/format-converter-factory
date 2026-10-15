# 等價測試：C++ 移植版（cleanup_scan／cleanup_execute）與 Python 原版必須行為相同。
# 做法：建立兩棵內容完全相同的 fixture，各自用一邊實作執行，再逐欄比對輸出與執行後的檔案清單。
# 用法：pwsh -File equivalence.ps1 [-Equivalence <exe路徑>] [-Python <python.exe路徑>]
param(
    [string]$Equivalence = '',
    [string]$Python = 'E:\四維八德\_build\venv\Scripts\python.exe'
)
$ErrorActionPreference = 'Stop'
$cppRoot = 'E:\四維八德\_build\cpp'
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$base = Join-Path $cppRoot "out\fx-$stamp"

if (-not $Equivalence) {
    $found = Get-ChildItem -LiteralPath $cppRoot -Recurse -Filter 'swbd-cpp-equivalence.exe' -ErrorAction SilentlyContinue |
             Sort-Object { $_.FullName -notmatch 'Release' } | Select-Object -First 1
    if (-not $found) { Write-Host '找不到 swbd-cpp-equivalence.exe，請先建置 C++ 核心。' -ForegroundColor Red; exit 4 }
    $Equivalence = $found.FullName
}
if (-not (Test-Path -LiteralPath $Equivalence)) { Write-Host "找不到 $Equivalence" -ForegroundColor Red; exit 4 }
if (-not (Test-Path -LiteralPath $Python)) { Write-Host "找不到 $Python" -ForegroundColor Red; exit 4 }

# ---------------------------------------------------------------- fixture
function New-Fixture([string]$fx) {
    $temp = Join-Path $fx 'temp'
    $data = Join-Path $fx 'data'
    $outside = Join-Path $fx 'outside'
    foreach ($d in @($temp, $data, $outside,
                     (Join-Path $temp 'zdgc_run1'), (Join-Path $temp 'zdgc_run1\sub'),
                     (Join-Path $temp 'not_zdgc_dir'),
                     (Join-Path $data 'models'), (Join-Path $data 'logs'))) {
        New-Item -ItemType Directory -Path $d -Force | Out-Null
    }
    # 天數＝檔案的齡期；0 表示 1 小時前（遠離所有門檻）
    $files = [ordered]@{
        (Join-Path $temp 'zdgc_run1\old.bin')          = 8
        (Join-Path $temp 'zdgc_run1\new.bin')          = 0
        (Join-Path $temp 'zdgc_run1\sub\deep_old.bin') = 8
        (Join-Path $temp 'litter_old.tmp')             = 8
        (Join-Path $temp 'litter_new.tmp')             = 0
        (Join-Path $temp 'not_zdgc_dir\old.bin')       = 8
        (Join-Path $data 'models\old_part.part')       = 2
        (Join-Path $data 'models\new_part.part')       = 0
        (Join-Path $data 'logs\zdgc.log')              = 8
        (Join-Path $data 'logs\zdgc.log.1')            = 8
        (Join-Path $data 'logs\other.txt')             = 8
        (Join-Path $outside 'keep.bin')                = 8
    }
    foreach ($path in $files.Keys) {
        Set-Content -LiteralPath $path -Value ('x' * 64) -NoNewline -Encoding ascii
        (Get-Item -LiteralPath $path).LastWriteTime = (Get-Date).AddDays(-$files[$path]).AddHours(-1)
    }
    # 目錄 junction：兩邊都不得跟隨、更不得刪掉連結目標
    cmd /c mklink /J "$temp\zdgc_link" "$outside" | Out-Null
    if (-not (Test-Path -LiteralPath "$temp\zdgc_link\keep.bin")) { throw 'junction 建立失敗' }
    return [pscustomobject]@{ root = $fx; temp = $temp; data = $data; outside = $outside }
}

New-Item -ItemType Directory -Path $base -Force | Out-Null
$py = New-Fixture (Join-Path $base 'fx_py')
$cpp = New-Fixture (Join-Path $base 'fx_cpp')
Write-Host "fixture：$base"

# ---------------------------------------------------------------- 兩邊執行
$pyJson = Join-Path $base 'py.json'
$cppJson = Join-Path $base 'cpp.json'
Write-Host '執行 Python 原版…'
& $Python (Join-Path $cppRoot 'tests\python_ref.py') $py.root $py.data $py.temp $pyJson
if ($LASTEXITCODE -ne 0) { Write-Host "Python 參考執行失敗（離開碼 $LASTEXITCODE）" -ForegroundColor Red; exit 1 }
Write-Host '執行 C++ 移植版…'
& $Equivalence $cpp.root $cpp.data $cpp.temp $cppJson
if ($LASTEXITCODE -ne 0) { Write-Host "C++ 執行失敗（離開碼 $LASTEXITCODE）" -ForegroundColor Red; exit 1 }

# ---------------------------------------------------------------- 比對
function Get-Val($object, $key) { return $object.PSObject.Properties[$key].Value }

function Compare-Node($expected, $actual, $path, $diffs) {
    $expectedIsObject = $expected -is [System.Management.Automation.PSCustomObject]
    $actualIsObject = $actual -is [System.Management.Automation.PSCustomObject]
    if ($expectedIsObject -or $actualIsObject) {
        if (-not ($expectedIsObject -and $actualIsObject)) { $diffs.Add("$path 型別不同"); return }
        $expectedKeys = @($expected.PSObject.Properties.Name)
        $actualKeys = @($actual.PSObject.Properties.Name)
        if (($expectedKeys -join ',') -ne ($actualKeys -join ',')) {
            $diffs.Add("$path 鍵不同：[$($expectedKeys -join ',')] vs [$($actualKeys -join ',')]")
            return
        }
        foreach ($key in $expectedKeys) { Compare-Node (Get-Val $expected $key) (Get-Val $actual $key) "$path.$key" $diffs }
        return
    }
    if (($expected -is [System.Array]) -or ($actual -is [System.Array])) {
        $expectedItems = @($expected); $actualItems = @($actual)
        if ($expectedItems.Count -ne $actualItems.Count) {
            $diffs.Add("$path 長度不同：$($expectedItems.Count) vs $($actualItems.Count)")
            return
        }
        for ($i = 0; $i -lt $expectedItems.Count; $i++) {
            Compare-Node $expectedItems[$i] $actualItems[$i] "$path[$i]" $diffs
        }
        return
    }
    switch -Regex ($path) {
        '^preview\.token$' {
            if (("$expected" -notmatch '^[0-9a-f]{32}$') -or ("$actual" -notmatch '^[0-9a-f]{32}$')) {
                $diffs.Add("$path 不是 32 位十六進位：$expected / $actual")
            }
            return
        }
        '^preview\.created$' {
            $now = [double](Get-Date -UFormat %s)
            foreach ($value in @($expected, $actual)) {
                if ([math]::Abs($now - [double]$value) -gt 60) { $diffs.Add("$path 時間不合理：$value（現在 $now）") }
            }
            return
        }
        default {
            if ("$expected" -ne "$actual") { $diffs.Add("$path 不同：Python=$expected C++=$actual") }
        }
    }
}

$expected = Get-Content -LiteralPath $pyJson -Raw -Encoding UTF8 | ConvertFrom-Json
$actual = Get-Content -LiteralPath $cppJson -Raw -Encoding UTF8 | ConvertFrom-Json
$diffs = New-Object System.Collections.Generic.List[string]

# before 必須一致，否則 fixture 本身就不同，後面的比對沒有意義
Compare-Node $expected.before $actual.before 'before' $diffs
Compare-Node $expected.preview $actual.preview 'preview' $diffs
Compare-Node $expected.execute $actual.execute 'execute' $diffs
Compare-Node $expected.after $actual.after 'after' $diffs

$report = [ordered]@{
    when = (Get-Date -Format 'yyyy-MM-dd HH:mm:ss')
    fixture = $base
    python = $pyJson
    cpp = $cppJson
    diffs = @($diffs)
    pass = ($diffs.Count -eq 0)
    python_preview = $expected.preview
    cpp_preview = $actual.preview
    python_execute = $expected.execute
    cpp_execute = $actual.execute
    python_after = $expected.after
    cpp_after = $actual.after
}
$reportPath = Join-Path $cppRoot 'tests\equivalence.json'
[IO.File]::WriteAllText($reportPath, ($report | ConvertTo-Json -Depth 12), [Text.UTF8Encoding]::new($false))

Write-Host ''
Write-Host '--- Python preview ---'; $expected.preview | ConvertTo-Json -Depth 6 -Compress
Write-Host '--- C++ preview ---';    $actual.preview  | ConvertTo-Json -Depth 6 -Compress
Write-Host '--- Python execute ---'; $expected.execute | ConvertTo-Json -Compress
Write-Host '--- C++ execute ---';    $actual.execute  | ConvertTo-Json -Compress
Write-Host ''
if ($diffs.Count -eq 0) {
    Write-Host 'PASS：C++ 移植版與 Python 原版逐欄相同（preview／execute／before／after）。' -ForegroundColor Green
    Write-Host "報告：$reportPath"
    exit 0
}
Write-Host "FAIL：$($diffs.Count) 項不同" -ForegroundColor Red
$diffs | ForEach-Object { Write-Host "  $_" -ForegroundColor Red }
Write-Host "報告：$reportPath"
exit 1
