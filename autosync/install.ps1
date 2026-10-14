# 安裝自動同步：git hooks + 每位使用者自己的排程工作（登入時與每 2 分鐘）
$Repo = Split-Path -Parent $PSScriptRoot
$hooks = Join-Path $Repo '.git\hooks'
foreach ($h in 'pre-commit', 'pre-push') {
  $mode = if ($h -eq 'pre-push') { 'push' } else { 'commit' }
  $body = "#!/bin/sh`npowershell.exe -NoProfile -ExecutionPolicy Bypass -File ""`$(git rev-parse --show-toplevel)/autosync/check.ps1"" $mode`n"
  [IO.File]::WriteAllText((Join-Path $hooks $h), $body.Replace("`r", ''))
}
$vbs = Join-Path $PSScriptRoot 'run-hidden.vbs'
$act = New-ScheduledTaskAction -Execute 'wscript.exe' -Argument "`"$vbs`""
$t1 = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$t2 = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 2)
$set = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 10)
$pr = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited
Register-ScheduledTask -TaskName 'ZDGC-AutoSync' -Action $act -Trigger $t1, $t2 -Settings $set -Principal $pr -Description '轉檔工廠 自動同步到 GitHub' -Force | Out-Null
Write-Host '自動同步已安裝（排程工作 ZDGC-AutoSync）'
