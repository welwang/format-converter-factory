$ErrorActionPreference = 'Stop'
try {
    & (Join-Path $PSScriptRoot 'build.ps1')
    if ($LASTEXITCODE -ne 0) { throw '建置未完成。' }
    Write-Host '安裝程式在這次 release-stage 的 dist\swbd-core\輸出；現有版本未覆蓋。'
} catch {
    Write-Error ('建置失敗：'+$_.Exception.Message)
    exit 1
}
