# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置：生成 darkMark / darkMark-config / darkMark-picker"""

from pathlib import Path

ROOT = Path(SPECPATH)

datas = [
    (str(ROOT / "config"), "config"),
    (str(ROOT / "tools" / "static"), "tools/static"),
]

hiddenimports = [
    "cv2",
    "numpy",
    "PIL",
    "PIL.Image",
    "PIL.ImageDraw",
    "PIL.ImageFont",
    "pytesseract",
    "keyboard",
    "mss",
    "yaml",
    "pyautogui",
    "src",
    "src.auto_buyer",
    "src.config_loader",
    "src.coord_overlay",
    "src.market_scanner",
    "src.mouse_input",
    "src.ocr_engine",
    "src.ocr_test",
    "src.paths",
    "src.price_parser",
    "src.screen_capture",
    "src.template_matcher",
    "src.utils.logger",
]

block_cipher = None

common = dict(
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

a_main = Analysis([str(ROOT / "src" / "main.py")], **common)
a_config = Analysis([str(ROOT / "tools" / "config_ui.py")], **common)
a_picker = Analysis([str(ROOT / "tools" / "region_picker.py")], **common)

MERGE((a_main, "darkMark", "darkMark"), (a_config, "darkMark-config", "darkMark-config"), (a_picker, "darkMark-picker", "darkMark-picker"))

pyz_main = PYZ(a_main.pure, a_main.zipped_data, cipher=block_cipher)
pyz_config = PYZ(a_config.pure, a_config.zipped_data, cipher=block_cipher)
pyz_picker = PYZ(a_picker.pure, a_picker.zipped_data, cipher=block_cipher)

exe_main = EXE(
    pyz_main,
    a_main.scripts,
    [],
    exclude_binaries=True,
    name="darkMark",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

exe_config = EXE(
    pyz_config,
    a_config.scripts,
    [],
    exclude_binaries=True,
    name="darkMark-config",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

exe_picker = EXE(
    pyz_picker,
    a_picker.scripts,
    [],
    exclude_binaries=True,
    name="darkMark-picker",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe_main,
    exe_config,
    exe_picker,
    a_main.binaries,
    a_main.zipfiles,
    a_main.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="darkMark",
)
