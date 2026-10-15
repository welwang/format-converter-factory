# 原生外殼等價閘門：把受測 exe 放進應用程式目錄跑 --shell-smoke-test，輸出可逐欄比對的報告。
# 用法：gate_shell.ps1 -Exe <swbd-shell.exe> -OutJson <報告 json>
param(
  [Parameter(Mandatory=$true)][string]$Exe,
  [Parameter(Mandatory=$true)][string]$OutJson,
  [string]$AppRoot = ''
)
$ErrorActionPreference = 'Stop'
$repo = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..'))
$python = Join-Path $repo '_build\venv\Scripts\python.exe'
if (-not $AppRoot) {
    $candidate = Get-ChildItem -LiteralPath (Join-Path $repo '_build') -Directory -Filter 'release-stage-*' |
                 Sort-Object Name -Descending | Select-Object -First 1
    if ($candidate) { $AppRoot = Join-Path $candidate.FullName 'dist\swbd-core' }
    if (-not $AppRoot) { throw '請用 -AppRoot 指定隔離的候選版本目錄；煙霧測試會寫入受測目錄的設定及輸出。' }
}
$AppRoot = [IO.Path]::GetFullPath($AppRoot)
if (-not (Test-Path -LiteralPath (Join-Path $AppRoot 'swbd-core.exe'))) { throw '受測目錄缺少 swbd-core.exe' }

# 1) 測試素材：與 _build\build.ps1 的 smoke 佈置相同
$fx = Join-Path $AppRoot 'smoke-fixtures'
New-Item -ItemType Directory -Force -Path $fx | Out-Null
if (-not (Test-Path -LiteralPath (Join-Path $fx 'video.mp4'))) {
    & (Join-Path $repo 'tools\ffmpeg.exe') -hide_banner -y -v error `
      -f lavfi -i 'testsrc2=size=640x360:rate=24:duration=3' -f lavfi -i 'sine=duration=3' `
      -c:v libx264 -preset ultrafast -c:a aac (Join-Path $fx 'video.mp4') 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) { throw '建立 smoke 影片素材失敗' }
}
if (-not (Test-Path -LiteralPath (Join-Path $fx 'image.png'))) {
    & $python -c "from PIL import Image;import sys;Image.new('RGB',(64,48),'blue').save(sys.argv[1])" (Join-Path $fx 'image.png') 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) { throw '建立 smoke 圖片素材失敗' }
}
# 原生 PDF→PDF 的煙霧素材：煙霧測試會實際送出一個 PDF→PDF 工作，並要求由 C 引擎（qpdf）完成。
if (-not (Test-Path -LiteralPath (Join-Path $fx 'smoke.pdf'))) {
    $sample = Join-Path $repo '_build\samples\smoke.pdf'
    if (-not (Test-Path -LiteralPath $sample)) { throw '缺少 samples\smoke.pdf 素材' }
    Copy-Item -LiteralPath $sample -Destination (Join-Path $fx 'smoke.pdf') -Force
}

# 2) 受測 exe 必須與 swbd-core.exe 同目錄（外殼以自身路徑解析背景元件）
$stage = Join-Path $AppRoot ('swbd-shell-gate-' + [guid]::NewGuid().ToString('N').Substring(0, 8) + '.exe')
Copy-Item -LiteralPath $Exe -Destination $stage -Force
$report = Join-Path $env:TEMP ('smoke-' + [guid]::NewGuid().ToString('N') + '.json')
try {
    $p = Start-Process -FilePath $stage -ArgumentList @('--shell-smoke-test', ('"' + $report + '"')) -WindowStyle Hidden -PassThru
    if (-not $p.WaitForExit(180000)) { try { $p.Kill() } catch { }; throw '煙霧測試逾時（180 秒）' }
    if (-not (Test-Path -LiteralPath $report)) { throw "煙霧測試沒有產生報告（離開碼 $($p.ExitCode)）" }
    $obj = Get-Content -LiteralPath $report -Raw -Encoding UTF8 | ConvertFrom-Json
    [pscustomobject]@{ exe = (Split-Path $Exe -Leaf); exit_code = $p.ExitCode; report = $obj } |
        ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $OutJson -Encoding UTF8
    if ($p.ExitCode -ne 0 -or $obj._swbd_smoke -ne $true -or $obj.ok -ne $true) { throw "外殼煙霧測試失敗：$($obj.error)（離開碼 $($p.ExitCode)）" }
    if ($obj.preview -ne $true -or $obj.error_rejection -ne $true -or $obj.mixed_jobs -ne 2 -or $obj.formats -lt 1 -or $obj.completion_notifications -lt 1) { throw '外殼煙霧報告缺少必要的通過斷言' }
    "exit={0} ok={1} version={2} platform={3} formats={4} mixed_jobs={5} preview={6} error_rejection={7} completion_notifications={8} error={9}" -f `
        $p.ExitCode, $obj.ok, $obj.version, $obj.platform, $obj.formats, $obj.mixed_jobs, $obj.preview, $obj.error_rejection, $obj.completion_notifications, $obj.error
} finally {
    Remove-Item -LiteralPath $stage -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $report -Force -ErrorAction SilentlyContinue
}
