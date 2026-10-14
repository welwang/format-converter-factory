# 轉檔工廠 build script (build-time only)
$ErrorActionPreference='Continue'
$B='E:\轉檔工廠\_build'; $R='E:\轉檔工廠'; cd $B
.\venv\Scripts\pyinstaller --noconfirm --windowed --onedir --name ZDGC --icon logo.ico --add-data "src\ui;ui" --add-data "src\zhdict;zhdict" --hidden-import tools --hidden-import capture --hidden-import zhconv `
  --collect-all pillow_heif --collect-all pypdfium2 --collect-all rawpy --collect-all psd_tools --collect-all resvg_py --collect-all trimesh `
  --collect-submodules webview --exclude-module tkinter --exclude-module matplotlib --exclude-module setuptools --exclude-module pip --exclude-module test --distpath dist --workpath work --exclude-module _test src\app.py 2>&1 | select -last 1
if(Test-Path "$R\_internal"){Remove-Item -Recurse -Force "$R\_internal"}
Copy-Item -Recurse dist\ZDGC\_internal $R; Copy-Item dist\ZDGC\ZDGC.exe "$R\轉檔工廠.exe" -Force
