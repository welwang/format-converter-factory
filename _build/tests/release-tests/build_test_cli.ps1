$ErrorActionPreference='Stop'
$vsPath = & 'C:\Program Files (x86)\Microsoft Visual Studio\Installer\vswhere.exe' -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
$shellPath=Join-Path $PSScriptRoot 'shell'
$compileLines=@('@echo off',('call "'+$vsPath+'\VC\Auxiliary\Build\vcvars64.bat" >nul'),('cd /d "'+$shellPath+'"'), 'cl /nologo /utf-8 /MT /O2 /W3 /std:c11 engine_test_cli.c engine.c plat.c json.c /Fo"out\\" /Fe"out\engine-test.exe" /link user32.lib advapi32.lib shell32.lib')
$batch=Join-Path $shellPath 'out\compile_test.cmd'
[IO.File]::WriteAllText($batch,($compileLines -join "`r`n")+"`r`n",[Text.UTF8Encoding]::new($false))
& cmd.exe /d /c $batch
if($LASTEXITCODE -ne 0){throw 'C test driver compilation failed'}
