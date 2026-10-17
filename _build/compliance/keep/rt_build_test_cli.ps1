$ErrorActionPreference='Stop'
# Builds the Windows engine test driver (engine-test.exe).
# The compile rules live in exactly one place now: shell\CMakeLists.txt (C++20).
$shell=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\shell'))
$cmake=(Get-Command cmake.exe -ErrorAction SilentlyContinue).Source
if(-not $cmake){$cmake=Join-Path ${env:ProgramFiles} 'CMake\bin\cmake.exe'}
if(-not (Test-Path -LiteralPath $cmake)){throw 'CMake not found'}
$build=Join-Path $shell 'out\cmake'
& $cmake -S $shell -B $build 2>&1 | Out-Null
if($LASTEXITCODE -ne 0){throw 'CMake configure failed'}
& $cmake --build $build --config Release --target engine-test 2>&1 | Out-Null
if($LASTEXITCODE -ne 0){throw 'C test driver compilation failed'}
$exe=Get-ChildItem -LiteralPath $build -Recurse -Filter 'engine-test.exe' -File | Sort-Object LastWriteTime -Descending | Select-Object -First 1
if(-not $exe){throw 'engine-test.exe not found'}
$out=Join-Path $shell 'out'
New-Item -ItemType Directory -Force -Path $out | Out-Null
Copy-Item -LiteralPath $exe.FullName -Destination (Join-Path $out 'engine-test.exe') -Force
Write-Host "engine-test.exe built: $out\engine-test.exe"
