# 四維八德 發布閘門（fail-closed）
#
# 這是「公開發行」的必經關卡：任何一項 blocking 檢查不成立就回傳非零，
# 且所有判斷都由 compliance_audit.py 從實際檔案、雜湊與產物重新計算 ——
# 改布林值、改測試預期、或刪掉報告都不會讓它通過。
#
# 開發與測試建置不受影響（見 build.ps1 結尾的非致命提示）；只有要發布時才呼叫這一支。
#
# 用法：
#   gate_release.ps1                 # 對最新 release-stage 的 payload 稽核
#   gate_release.ps1 -Payload <dir>  # 指定 payload
#   gate_release.ps1 -Json           # 只輸出機器可讀結果
param(
    [string]$Payload = '',
    [switch]$Json
)
$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
$python = Join-Path $root '_build\venv\Scripts\python.exe'
$script = Join-Path $PSScriptRoot 'compliance_audit.py'
if (-not (Test-Path -LiteralPath $python)) { throw "找不到 Python：$python" }

$env:PYTHONIOENCODING = 'utf-8'
$args = @($script, 'all')
if ($Payload) { $args += @('--payload', $Payload) }
if ($Json) { $args += '--json' }
$previous = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
& $python @args 2>&1 | ForEach-Object { Write-Host $_ }
$code = $LASTEXITCODE
$ErrorActionPreference = $previous

$result = Join-Path $PSScriptRoot 'out\gate-result.json'
if (Test-Path -LiteralPath $result) {
    $g = Get-Content -LiteralPath $result -Raw -Encoding UTF8 | ConvertFrom-Json
    Write-Host ''
    if ($g.result -eq 'PASS') {
        Write-Host '發布閘門：PASS —— 可以進行公開發行。' -ForegroundColor Green
    } else {
        Write-Host '發布閘門：BLOCKED —— 不得公開發行。' -ForegroundColor Red
        foreach ($id in $g.blocking_failures) { Write-Host "  未通過：$id" -ForegroundColor Red }
        Write-Host '  詳細內容：_build\compliance\out\audit-report.md' -ForegroundColor Yellow
        Write-Host '  待法律確認：_build\compliance\out\needs-legal-review.md' -ForegroundColor Yellow
    }
}
exit $code
