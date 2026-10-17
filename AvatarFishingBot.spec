# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['gui.py'],
    pathex=[],
    binaries=[],
    datas=[('vision/templates', 'vision/templates'), ('vision/windows_ocr.ps1', 'vision'), ('config/mission.json', 'config'), ('ui/assets', 'ui/assets')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
# This application captures still frames through ADB and uses image codecs.
# OpenCV's video backend is not used by the GUI, OCR, or image matching.
a.binaries = [entry for entry in a.binaries
              if not entry[0].replace('\\', '/').rsplit('/', 1)[-1].lower().startswith('opencv_videoio_ffmpeg')]
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='AvatarFishingBot',
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
    contents_directory='.',
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='AvatarFishingBot',
)
