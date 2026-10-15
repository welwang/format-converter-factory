param([Parameter(Mandatory=$true)][string]$CandidateRoot)
$ErrorActionPreference='Stop'
$python=Join-Path $PSScriptRoot 'venv\Scripts\python.exe'
& $python (Join-Path $PSScriptRoot 'prune_payload.py') $CandidateRoot
if($LASTEXITCODE -ne 0){throw '候選安裝資料精簡失敗；不直接修改正在使用的程式。'}
