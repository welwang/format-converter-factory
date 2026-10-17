# 第 0 批整理：把目前的工作區安全地提交到 git，並清掉舊的建置候選版（約 50 GB 以上）。
#
# 預設只「預覽」，不改任何東西：
#   powershell -NoProfile -ExecutionPolicy Bypass -File _build\整理與提交_第0批.ps1
# 確認預覽內容後再實際執行：
#   powershell -NoProfile -ExecutionPolicy Bypass -File _build\整理與提交_第0批.ps1 -Apply
#
# 會做的事：
#   1. 暫停 autosync（建立 autosync\state\paused），避免整理到一半被自動推送。
#   2. 用「明確的路徑清單」提交：已追蹤檔案的修改與刪除＋清單內的新檔（健康檢查、AI 智慧工具、治理文件、
#      合規閘門與保留的測試 _build\compliance\keep）。清單外的未追蹤檔案不會被加入，只列出來給你看。
#      提交前檢查不含憑證、私鑰、設定檔。
#   3. 刪除 _build\release-stage-*（保留最新的一個）與 _build 底下的空資料夾 libdeflate。
#      刪除前會列出大小，並要求輸入「刪除」確認。
# 不會做的事：不 push、不打標籤（除非加 -Tag），不動 tools、輸出、使用者設定。
param(
    [switch]$Apply,
    [string]$Tag = '',          # 例如 -Tag v2.4.0-dev；目前工作區已含 2.3.4 之後的變更，不建議標成 v2.3.4
    [switch]$SkipCleanup,
    [switch]$SkipCommit
)
$ErrorActionPreference = 'Stop'
# git 的中文路徑與訊息以 UTF-8 讀寫（Windows PowerShell 5.1 預設是系統字碼頁）
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding $false
$OutputEncoding = [Console]::OutputEncoding
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
Set-Location -LiteralPath $root
$mode = if ($Apply) { '執行' } else { '預覽（加 -Apply 才會真的執行）' }
Write-Host "四維八德 第 0 批整理 —— $mode" -ForegroundColor Cyan
Write-Host "專案：$root`n"

function RunGit([string[]]$GitArgs) {
    $previous = $ErrorActionPreference; $ErrorActionPreference = 'Continue'
    try { $out = & git.exe -c core.quotepath=false @GitArgs 2>&1 } finally { $ErrorActionPreference = $previous }
    if ($LASTEXITCODE -ne 0) { throw "git $($GitArgs -join ' ') 失敗：$($out | Out-String)" }
    return $out
}
function SizeText([double]$bytes) {
    if ($bytes -ge 1GB) { return ('{0:N2} GB' -f ($bytes / 1GB)) }
    if ($bytes -ge 1MB) { return ('{0:N1} MB' -f ($bytes / 1MB)) }
    return ('{0:N0} KB' -f ($bytes / 1KB))
}

if (-not (Get-Command git -ErrorAction SilentlyContinue)) { throw '找不到 git。請先安裝 Git for Windows。' }
if (-not (Test-Path -LiteralPath (Join-Path $root '.git'))) { throw '這個資料夾不是 git 儲存庫。' }
if (@(Get-Process -Name '四維八德', 'swbd-core' -ErrorAction SilentlyContinue).Count) { throw '請先關閉四維八德。' }

# ---------------------------------------------------------------- 1 暫停自動同步
$pause = Join-Path $root 'autosync\state\paused'
Write-Host '1. 暫停 autosync' -ForegroundColor Cyan
if (Test-Path -LiteralPath $pause) { Write-Host '   已經是暫停狀態。' }
elseif ($Apply) {
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $pause) | Out-Null
    Set-Content -LiteralPath $pause -Value "第 0 批整理時暫停（$(Get-Date -Format 'yyyy-MM-dd HH:mm')）。確認提交內容並手動 push 後，刪除這個檔案即可恢復。" -Encoding UTF8
    Write-Host '   已暫停（刪除 autosync\state\paused 可恢復）。'
} else { Write-Host '   將建立 autosync\state\paused。' }

# ---------------------------------------------------------------- 2 提交
if (-not $SkipCommit) {
    Write-Host "`n2. 提交（明確路徑清單）" -ForegroundColor Cyan
    $branch = (RunGit @('rev-parse', '--abbrev-ref', 'HEAD') | Select-Object -First 1)
    Write-Host "   分支：$branch"
    $required = @('_build\src\health_check.py', '_build\src\smart_tools.py')
    foreach ($r in $required) { if (-not (Test-Path -LiteralPath (Join-Path $root $r))) { throw "缺少 $r，停止。" } }

    # 新檔白名單：只有清單內、存在、且沒被 .gitignore 排除的路徑才會加入
    $newPaths = @(
        'README.md', 'CHANGELOG.md', 'CONTRIBUTING.md', 'SECURITY.md', 'CODE_OF_CONDUCT.md',
        '.gitignore', '.gitattributes', '.github',
        '重新建置安裝包到桌面.cmd', 'assets', 'source\來源清單.json',
        '_build\src\health_check.py', '_build\src\smart_tools.py', '_build\src\ui',
        '_build\shell', '_build\cpp', '_build\logo',
        '_build\compliance\compliance_audit.py', '_build\compliance\gate_release.ps1', '_build\compliance\keep',
        '_build\build.ps1', '_build\setup.iss', '_build\ZDGC.spec',
        '_build\整理舊檔.ps1', '_build\部署最新候選版.ps1', '_build\重新建置安裝包到桌面.ps1', '_build\整理與提交_第0批.ps1'
    ) | Where-Object { Test-Path -LiteralPath (Join-Path $root $_) }

    $tracked = @(RunGit @('status', '--porcelain', '--untracked-files=no'))
    $untrackedBefore = @(RunGit @('ls-files', '--others', '--exclude-standard'))
    Write-Host "   已追蹤檔案的修改／刪除：$($tracked.Count) 筆"
    $deleted = @($tracked | Where-Object { $_ -match '^ ?D' })
    if ($deleted.Count) {
        Write-Host "   其中刪除 $($deleted.Count) 個檔案（例如）：" -ForegroundColor Yellow
        $deleted | Select-Object -First 15 | ForEach-Object { Write-Host "     $_" }
        if ($deleted.Count -gt 15) { Write-Host "     …另外 $($deleted.Count - 15) 個" }
    }
    $willAdd = @($untrackedBefore | Where-Object { $p = $_ -replace '/', '\'; @($newPaths | Where-Object { $p -eq $_ -or $p.StartsWith($_ + '\') }).Count -gt 0 })
    $leftOut = @($untrackedBefore | Where-Object { $willAdd -notcontains $_ })
    Write-Host "   新加入：$($willAdd.Count) 個檔案"
    $willAdd | Select-Object -First 40 | ForEach-Object { Write-Host "     + $_" }
    if ($willAdd.Count -gt 40) { Write-Host "     …另外 $($willAdd.Count - 40) 個" }
    if ($leftOut.Count) {
        Write-Host "   清單外、不會加入的未追蹤檔案：$($leftOut.Count) 個（需要的話請手動 git add）" -ForegroundColor Yellow
        $leftOut | Select-Object -First 20 | ForEach-Object { Write-Host "     ? $_" }
    }
    $danger = @($willAdd + ($tracked | ForEach-Object { $_.Substring(3) })) | Where-Object { $_ -match '\.(pfx|p12|pem|key|env)$|(^|/)settings\.json$|(^|/)window\.ini$|id_rsa' }
    if ($danger.Count) { throw "提交內容含疑似憑證或個人設定，停止：$($danger -join '、')" }

    if ($Apply) {
        if (-not $tracked.Count -and -not $willAdd.Count) { Write-Host '   沒有需要提交的變更。' }
        else {
            RunGit @('add', '-u') | Out-Null
            foreach ($p in $newPaths) {
                & git.exe check-ignore -q -- $p 2>$null
                if ($LASTEXITCODE -eq 0) { Write-Host "   略過（被 .gitignore 排除）：$p" -ForegroundColor Yellow; continue }
                RunGit @('add', '--', $p) | Out-Null
            }
            $msg = "整理：2.3.4 文件與治理檔、電腦健康檢查、AI 智慧工具、功能缺陷修正、合規閘門 fail-closed`n`n保留的發布測試在 _build/compliance/keep（rt_ 前綴）。"
            RunGit @('commit', '-q', '-m', $msg) | Out-Null
            Write-Host "   已提交：$(RunGit @('log', '-1', '--format=%h %s') | Select-Object -First 1)" -ForegroundColor Green
        }
        if ($Tag) { RunGit @('tag', '-a', $Tag, '-m', "四維八德 $Tag") | Out-Null; Write-Host "   已建立標籤 $Tag" }
    } else {
        Write-Host '   （預覽：沒有執行 git add／commit）'
        if ($Tag) { Write-Host "   將建立標籤 $Tag" }
    }
}

# ---------------------------------------------------------------- 3 清理舊候選版
if (-not $SkipCleanup) {
    Write-Host "`n3. 清理舊的建置候選版" -ForegroundColor Cyan
    $stages = @(Get-ChildItem -LiteralPath (Join-Path $root '_build') -Directory -Filter 'release-stage-*' | Sort-Object Name -Descending)
    $keep = $stages | Select-Object -First 1
    $remove = @($stages | Select-Object -Skip 1)
    $empty = @(Get-ChildItem -LiteralPath (Join-Path $root '_build') -Directory -Recurse -Filter 'libdeflate' -ErrorAction SilentlyContinue |
               Where-Object { $_.FullName -notmatch 'release-stage-' -and -not (Get-ChildItem -LiteralPath $_.FullName -Force) })
    if ($keep) { Write-Host "   保留最新：$($keep.Name)" }
    $total = 0.0
    foreach ($d in $remove) {
        $size = (Get-ChildItem -LiteralPath $d.FullName -Recurse -File -Force -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum
        $total += $size
        Write-Host ("   刪除 {0}  {1}" -f $d.Name, (SizeText $size))
    }
    foreach ($d in $empty) { Write-Host "   刪除空資料夾 $($d.FullName.Substring($root.Length + 1))" }
    Write-Host ("   合計可回收：{0}" -f (SizeText $total)) -ForegroundColor Yellow
    if (-not $remove.Count -and -not $empty.Count) { Write-Host '   沒有要清理的項目。' }
    elseif ($Apply) {
        $answer = Read-Host '   刪除後無法復原。確定要刪除上面這些資料夾嗎？請輸入「刪除」確認'
        if ($answer -ne '刪除') { Write-Host '   已略過清理。' }
        else {
            foreach ($d in $remove + $empty) {
                Remove-Item -LiteralPath $d.FullName -Recurse -Force
                Write-Host "   已刪除 $($d.Name)"
            }
        }
    } else { Write-Host '   （預覽：沒有刪除任何東西）' }
}

Write-Host "`n下一步：" -ForegroundColor Cyan
Write-Host '  1. git log -1 --stat 檢查提交內容。'
Write-Host '  2. 確認後手動推送：git push origin HEAD（有標籤再加 git push origin --tags）。'
Write-Host '  3. 要恢復自動同步，刪除 autosync\state\paused。'
if (-not $Apply) { Write-Host "`n這次只是預覽。確認沒問題後，加上 -Apply 再執行一次。" -ForegroundColor Yellow }
