# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

datas = [('C:/Users/shouj/AppData/Local/Temp/moyu_pack_8747rg6l/static', 'static'), ('D:/KimiCode工作区/moyu-codex-backup-20260928/docs', 'docs'), ('D:/KimiCode工作区/moyu-codex-backup-20260928/app', 'app')]
binaries = []
hiddenimports = ['clr', 'clr_loader', 'pythonnet', 'webview.platforms.winforms', 'webview.platforms.edgechromium', 'uvicorn.logging', 'uvicorn.loops.auto', 'uvicorn.protocols.http.auto', 'uvicorn.protocols.websockets.auto', 'uvicorn.lifespan.on']
tmp_ret = collect_all('webview')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['D:/KimiCode工作区/moyu-codex-backup-20260928/moyu_entry.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='MoYu-v1.4.0-win64',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version='D:/KimiCode工作区/moyu-codex-backup-20260928/build/version.txt',
    icon=['D:/KimiCode工作区/moyu-codex-backup-20260928/build/icon.ico'],
)
