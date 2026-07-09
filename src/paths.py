"""应用路径解析（开发模式与 PyInstaller 打包后通用）"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path


def is_frozen() -> bool:
    return getattr(sys, "frozen", False)


def app_root() -> Path:
    """可写根目录：开发时为项目根，打包后为 exe 所在目录。"""
    if is_frozen():
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


def bundle_root() -> Path:
    """只读资源根目录：开发时为项目根，打包后为 PyInstaller 解压目录。"""
    if is_frozen():
        return Path(sys._MEIPASS)
    return app_root()


def config_dir() -> Path:
    return app_root() / "config"


def log_dir() -> Path:
    return app_root() / "logs"


def assets_dir() -> Path:
    return app_root() / "assets"


def tools_static_dir() -> Path:
    return bundle_root() / "tools" / "static"


def resolve_asset(path: str | Path) -> Path:
    p = Path(path)
    if p.is_absolute():
        return p
    return app_root() / p


def configure_tesseract() -> None:
    """若 exe 旁附带 tesseract，则自动配置 pytesseract。"""
    import pytesseract

    candidates = [
        app_root() / "tesseract" / "tesseract.exe",
        Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe"),
        Path(r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"),
    ]
    for exe in candidates:
        if exe.exists():
            pytesseract.pytesseract.tesseract_cmd = str(exe)
            return


def ensure_runtime_layout() -> None:
    """确保运行目录存在，首次运行从包内复制默认配置。"""
    config_dir().mkdir(parents=True, exist_ok=True)
    log_dir().mkdir(parents=True, exist_ok=True)
    (assets_dir() / "templates").mkdir(parents=True, exist_ok=True)

    bundled_config = bundle_root() / "config"
    if not bundled_config.is_dir():
        return

    for name in ("watchlist.yaml", "regions.yaml"):
        target = config_dir() / name
        if target.exists():
            continue
        source = bundled_config / name
        if source.exists():
            shutil.copy2(source, target)
