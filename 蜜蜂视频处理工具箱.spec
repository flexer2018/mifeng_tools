# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['main_window.py'],
    pathex=[],
    binaries=[],
    datas=[('ffmpeg', 'ffmpeg'), ('cookies', 'cookies'),('config.ini', '.')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
    ],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='蜜蜂视频处理工具箱',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['runke128.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='蜜蜂视频处理工具箱',
)
