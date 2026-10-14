param([switch]$Resume)
$ErrorActionPreference='Stop'
$work=[IO.Path]::GetFullPath($PSScriptRoot)
$install=Join-Path $work 'installer-validation\四維八德 測試安裝'
if(-not $install.StartsWith($work+'\',[StringComparison]::OrdinalIgnoreCase)){throw '測試安裝目錄超出工作區'}
$appKey='Software\Microsoft\Windows\CurrentVersion\Uninstall\{7B1E6C2A-9D41-4E7B-A3F0-ZDGC20261013}_is1'
foreach($key in ('HKCU:\'+$appKey),('HKLM:\'+$appKey),('HKLM:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\{7B1E6C2A-9D41-4E7B-A3F0-ZDGC20261013}_is1')){
 if(Test-Path -LiteralPath $key){
  $existing=Get-ItemProperty -LiteralPath $key
  if(-not $Resume -or [IO.Path]::GetFullPath($existing.InstallLocation).TrimEnd('\') -ne $install -or $existing.DisplayVersion -ne '2.3.2'){throw '已存在相同產品的其他安裝記錄，未執行測試安裝以免覆寫。'}
 }
}
$setup=Join-Path $work 'release\輸出\四維八德_2.3.2_離線安裝程式.exe'
$testGroup='四維八德 測試 2.3.2'
$args=@('/VERYSILENT','/SUPPRESSMSGBOXES','/SP-','/NORESTART',('/GROUP="'+$testGroup+'"'),'/TASKS=""',('/DIR="'+$install+'"'),('/LOG="'+(Join-Path $work 'installer-validation.log')+'"'))
if(-not $Resume){
 $p=Start-Process -FilePath $setup -ArgumentList $args -WindowStyle Hidden -PassThru
 if(-not $p.WaitForExit(300000)){throw '測試安裝超時'}
 if($p.ExitCode -ne 0){throw ('測試安裝失敗：'+$p.ExitCode)}
}
foreach($name in '四維八德.exe','swbd-core.exe','TEST_RESULTS.md','測試報告.html','assets\logo.png','assets\logo-sm.png','_internal\ui\logo.png','_internal\ui\logo-sm.png','tools\models\ggml-base.bin','tools\models\ggml-silero-v5.1.2.bin','tools\models\Whisper-LICENSE.txt','tools\models\Silero-LICENSE.txt'){
 if((Get-FileHash -LiteralPath (Join-Path $install $name)).Hash -ne (Get-FileHash -LiteralPath (Join-Path $work ('release\'+$name))).Hash){throw ('安裝檔案校驗不符：'+$name)}
}
$registration=Get-ItemProperty -LiteralPath ('HKCU:\'+$appKey)
$actualGroup=$registration.'Inno Setup: Icon Group'
if($actualGroup -notin @($testGroup,'四維八德')){throw '測試安裝的捷徑群組不符'}
$shortcutPath=Join-Path ([Environment]::GetFolderPath('Programs')) ($actualGroup+'\四維八德.lnk')
if(-not (Test-Path -LiteralPath $shortcutPath)){throw '測試捷徑未建立'}
$wsh=New-Object -ComObject WScript.Shell
$shortcut=$wsh.CreateShortcut($shortcutPath)
if([IO.Path]::GetFullPath($shortcut.TargetPath) -ne (Join-Path $install '四維八德.exe')){throw '捷徑目標不符'}
if($shortcut.IconLocation -and $shortcut.IconLocation -ne ',0' -and -not $shortcut.IconLocation.StartsWith((Join-Path $install '四維八德.exe'),[StringComparison]::OrdinalIgnoreCase)){throw '捷徑圖示未引用主程式'}
$env:PYTHONIOENCODING='utf-8'
foreach($binary in $setup,(Join-Path $install '四維八德.exe'),(Join-Path $install 'swbd-core.exe')){
 & 'E:\四維八德\_build\venv\Scripts\python.exe' (Join-Path $work 'test_logo_resources.py') $binary
 if($LASTEXITCODE -ne 0){throw '安裝後內嵌圖示不符'}
}
Copy-Item -LiteralPath (Join-Path $work 'release\smoke-fixtures') -Destination $install -Recurse -Force
$exe=Join-Path $install '四維八德.exe'
$smoke=Join-Path $work 'installed-window-smoke.json'
$p=Start-Process -FilePath $exe -ArgumentList @('--shell-smoke-test',('"'+$smoke+'"')) -WindowStyle Hidden -PassThru
if(-not $p.WaitForExit(60000)){throw '安裝後視窗測試逾時'}
$result=Get-Content -LiteralPath $smoke -Raw -Encoding UTF8 | ConvertFrom-Json
if($p.ExitCode -ne 0 -or -not $result.ok){throw '安裝後視窗測試失敗'}
$pdf=Join-Path $work 'installed-pdf'
$p=Start-Process -FilePath $exe -ArgumentList @('--pdf-selftest',('"'+$pdf+'"')) -WindowStyle Hidden -PassThru
if(-not $p.WaitForExit(60000)){throw '安裝後 PDF 測試逾時'}
$results=Get-Content -LiteralPath (Join-Path $pdf 'results.json') -Raw -Encoding UTF8 | ConvertFrom-Json
if($p.ExitCode -ne 0 -or $results.Count -ne 12 -or @($results | Where-Object {-not $_.ok}).Count){throw '安裝後 PDF 測試失敗'}
$registered=Get-ItemProperty -LiteralPath ('HKCU:\'+$appKey)
if([IO.Path]::GetFullPath($registered.InstallLocation).TrimEnd('\') -ne $install){throw '安裝記錄路徑不符，停止解除安裝'}
$p=Start-Process -FilePath (Join-Path $install 'unins000.exe') -ArgumentList @('/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART') -WindowStyle Hidden -PassThru
if(-not $p.WaitForExit(120000) -or $p.ExitCode -ne 0){throw '解除安裝驗證失敗'}
if(Test-Path -LiteralPath ('HKCU:\'+$appKey)){throw '解除安裝仍留有安裝記錄'}
if(Test-Path -LiteralPath $shortcutPath){throw '解除安裝仍留有測試捷徑'}
foreach($name in '四維八德.exe','swbd-core.exe','_internal','tools'){
 if(Test-Path -LiteralPath (Join-Path $install $name)){throw ('解除安裝仍留有產品檔案：'+$name)}
}
$report=[ordered]@{version='2.3.2';installed=$true;hashes_match=$true;unicode_path=$true;native_window=$result;pdf_passed=$results.Count;uninstall=$true;new_icon_resources=$true;shortcut_icon_target=$true;private_data_included=$false;setup_sha256=(Get-FileHash -LiteralPath $setup).Hash;setup_bytes=(Get-Item -LiteralPath $setup).Length}
$report | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $work 'package-validation.json') -Encoding UTF8
Write-Host '安裝、中文含空白路徑、C 視窗、12 項 PDF、雜湊與解除安裝全部通過。'
