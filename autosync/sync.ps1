# 轉檔工廠 自動同步：有程式碼變更就 commit + push（由排程工作每 2 分鐘執行一次）
$ErrorActionPreference = 'Continue'
$Repo  = Split-Path -Parent $PSScriptRoot
$State = Join-Path $PSScriptRoot 'state'
New-Item -ItemType Directory -Force $State | Out-Null
$Log   = Join-Path $State 'sync.log'
function Log($m) { "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') $m" | Add-Content -Encoding utf8 $Log }
if (Test-Path (Join-Path $State 'paused')) { exit 0 }
$lock = Join-Path $State 'lock'
if ((Test-Path $lock) -and ((Get-Date) - (Get-Item $lock).LastWriteTime).TotalMinutes -lt 10) { exit 0 }
Set-Content $lock $PID
try {
    Set-Location $Repo
    $env:GIT_TERMINAL_PROMPT = '0'
    # 等檔案寫完：最近 30 秒內有修改就下次再同步（防抖）
    $recent = git ls-files -m -o --exclude-standard | Where-Object { $_ -and (Test-Path $_) -and ((Get-Date) - (Get-Item $_).LastWriteTime).TotalSeconds -lt 30 }
    if ($recent) { exit 0 }
    git add -A 2>&1 | Out-Null
    git diff --cached --quiet
    if ($LASTEXITCODE -ne 0) {
        $msg = "自動同步 $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
        $out = git commit -q -m $msg 2>&1
        if ($LASTEXITCODE -ne 0) { Log "commit 被擋下：$out"; git reset -q; exit 1 }
        Log "commit：$msg"
    }
    $ahead = git rev-list --count '@{u}..HEAD' 2>$null
    if ($ahead -and [int]$ahead -gt 0) {
        $out = git push -q origin HEAD 2>&1
        if ($LASTEXITCODE -eq 0) { Log "push 成功（$ahead 個 commit）" } else { Log "push 失敗：$(($out | Out-String).Trim())" }
    }
} finally { Remove-Item $lock -Force -ErrorAction SilentlyContinue }
