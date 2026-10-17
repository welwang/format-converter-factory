$ErrorActionPreference = 'Continue'
# 驗證「合規閘門改用子行程呼叫」的機制：
#   1) 閘門回傳非零（目前是 BLOCKED）
#   2) 父腳本仍然存活（這就是先前的 bug：用 & 呼叫會把整個腳本結束掉）
$gate = Join-Path (Split-Path -Parent $PSScriptRoot) 'compliance\gate_release.ps1'
$previous = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $gate | Out-Null
$code = $LASTEXITCODE
$ErrorActionPreference = $previous
Write-Host "gate_path_exists=$(Test-Path -LiteralPath $gate)"
Write-Host "gate_exit=$code"
Write-Host "parent_survived=YES"
if ($code -ne 0) {
    Write-Host "verdict=BLOCKED_BUT_PARENT_CONTINUES (離開碼非零，父腳本繼續執行 —— 這正是要的行為)"
} else {
    Write-Host "verdict=PASS"
}
