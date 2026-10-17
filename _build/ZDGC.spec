# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules
from PyInstaller.utils.hooks import collect_all

datas = [('src/ui', 'ui'), ('src/zhdict', 'zhdict')]
binaries = []
hiddenimports = ['app', 'tools', 'capture', 'workflows', 'validation', 'system_tools', 'health_check', 'zhconv', 'selftest', 'cryptography', 'pdf_schema', 'pdf_tools', 'pdf_local_engines', 'file_actions', 'pdf_selftest', 'smart_tools']
tmp_ret = collect_all('cryptography')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('pypdfium2')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('rawpy')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('psd_tools')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('resvg_py')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('trimesh')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


for package in ['pymupdf','pikepdf','docx','pptx','openpyxl','pyhanko','pyhanko_certvalidator','qrcode','lxml','tzdata','aiohttp']:
    extra = collect_all(package)
    datas += extra[0]; binaries += extra[1]; hiddenimports += extra[2]

a = Analysis(
    ['src/core.py'],
    pathex=['vendor', 'src'],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['pillow_heif', 'tkinter', 'matplotlib', 'setuptools', 'pip', 'test', 'webview', 'pythonnet', 'clr_loader', 'clr', 'proxy_tools', 'bottle'],
    noarchive=False,
    optimize=0,
)
# The same MuPDF DLL is auto-collected both at root and inside the package.
# Python extension loading searches its package directory; retain that copy only.
a.binaries = [b for b in a.binaries if b[0].replace('\\','/').lower() != 'mupdfcpp64.dll']
# C headers / link libraries are development resources, unused at runtime.
a.datas = [d for d in a.datas if '/mupdf-devel/' not in ('/'+d[0].replace('\\','/'))]
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='swbd-core',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,       # no window of its own: started hidden by 四維八德.exe, talks over stdin / stdout
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='logo.ico',
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='swbd-core',
)
