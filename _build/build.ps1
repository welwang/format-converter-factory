# 轉檔工廠 build script (build-time only)
$ErrorActionPreference='Continue'
$B='E:\轉檔工廠\_build'; $R='E:\轉檔工廠'; cd $B
.\venv\Scripts\pyinstaller --noconfirm --windowed --onedir --name ZDGC --icon logo.ico --add-data "src\ui;ui" --add-data "src\zhdict;zhdict" --hidden-import tools --hidden-import capture --hidden-import zhconv --hidden-import selftest `
  --collect-all pypdfium2 --collect-all rawpy --collect-all psd_tools --collect-all resvg_py --collect-all trimesh `
  --collect-submodules webview --exclude-module pillow_heif --exclude-module tkinter --exclude-module matplotlib --exclude-module setuptools --exclude-module pip --exclude-module test --distpath dist --workpath work --exclude-module _test src\app.py 2>&1 | select -last 1
if(Test-Path "$R\_internal"){Remove-Item -Recurse -Force "$R\_internal"}
Copy-Item -Recurse dist\ZDGC\_internal $R; Copy-Item dist\ZDGC\ZDGC.exe "$R\轉檔工廠.exe" -Force

# ---------------------------------------------------------------- 內建元件（讓程式不依賴電腦上的任何環境）
$T = "$R\tools"; $ProgressPreference = 'SilentlyContinue'
function Get-Once($url, $dest) {
  if (Test-Path $dest) { return }
  Write-Host "下載 $(Split-Path $dest -Leaf) ..."
  New-Item -ItemType Directory -Force -Path (Split-Path $dest) | Out-Null
  try { Invoke-WebRequest -Uri $url -OutFile "$dest.part" -UseBasicParsing; Move-Item -Force "$dest.part" $dest }
  catch { Write-Warning "無法下載 $url ：$($_.Exception.Message)"; Remove-Item "$dest.part" -ErrorAction SilentlyContinue }
}
# 1) LibreOffice 需要的 Visual C++ 執行庫：放一份在它自己的資料夾（app-local），不需要電腦另外安裝
$vc = 'msvcp140.dll','msvcp140_1.dll','msvcp140_2.dll','msvcp140_atomic_wait.dll','msvcp140_codecvt_ids.dll','vcruntime140.dll','vcruntime140_1.dll','concrt140.dll'
foreach ($d in $vc) {
  $dst = "$T\libreoffice\program\$d"
  if (-not (Test-Path $dst)) {
    foreach ($src in "$env:WINDIR\System32\$d", "$R\_internal\$d") { if (Test-Path $src) { Copy-Item $src $dst; break } }
  }
}
# 2) AI 字幕：基本辨識模型＋語音段落偵測，離線可用
Get-Once 'https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.bin' "$T\models\ggml-base.bin"
Get-Once 'https://huggingface.co/ggml-org/whisper-vad/resolve/main/ggml-silero-v5.1.2.bin' "$T\models\ggml-silero-v5.1.2.bin"
# 3) YouTube 解析元件
if (-not (Test-Path "$T\deno.exe")) {
  Get-Once 'https://github.com/denoland/deno/releases/latest/download/deno-x86_64-pc-windows-msvc.zip' "$B\dl\deno.zip"
  if (Test-Path "$B\dl\deno.zip") { & "$T\7z.exe" e -y -bso0 "-o$T" "$B\dl\deno.zip" deno.exe }
}
# 4) 視窗元件 WebView2 的安裝程式（只在極少數沒有內建的 Windows 10 上才會用到）
Get-Once 'https://go.microsoft.com/fwlink/p/?LinkId=2124703' "$T\MicrosoftEdgeWebview2Setup.exe"

# ---------------------------------------------------------------- 免安裝版（整個資料夾壓成 zip，解壓縮就能用）
$P = "$R\輸出\轉檔工廠_免安裝版.zip"
if (Test-Path $P) { Remove-Item $P }
Push-Location $R
& "$T\7z.exe" a -tzip -mx=5 -mmt=on -bso0 -bsp1 $P "轉檔工廠.exe" "_internal" "tools" "使用說明.md" "授權說明.md" "使用授權條款.md" -xr!logs -xr!settings.json -xr!hw_cache.json -xr!watch_state.json
Pop-Location
Write-Host "完成：$R\轉檔工廠.exe（可直接執行）、$P（免安裝版）。安裝程式請用 Inno Setup 編譯 setup.iss。"
