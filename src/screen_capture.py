"""屏幕捕获模块"""

from __future__ import annotations

import ctypes
from ctypes import wintypes
from dataclasses import dataclass

import mss
import numpy as np
from PIL import Image

_dpi_awareness_enabled = False


def enable_dpi_awareness() -> None:
    """确保窗口坐标与 pyautogui 点击使用同一套物理像素"""
    global _dpi_awareness_enabled
    if _dpi_awareness_enabled:
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass
    _dpi_awareness_enabled = True


enable_dpi_awareness()


@dataclass
class WindowInfo:
    left: int
    top: int
    width: int
    height: int
    title: str
    hwnd: int = 0
    is_fullscreen: bool = False


class MONITORINFOEX(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("rcMonitor", wintypes.RECT),
        ("rcWork", wintypes.RECT),
        ("dwFlags", wintypes.DWORD),
        ("szDevice", wintypes.WCHAR * 32),
    ]


def _monitor_for_hwnd(hwnd: int) -> dict[str, int]:
    user32 = ctypes.windll.user32
    MONITOR_DEFAULTTONEAREST = 2
    hmon = user32.MonitorFromWindow(hwnd, MONITOR_DEFAULTTONEAREST)
    info = MONITORINFOEX()
    info.cbSize = ctypes.sizeof(MONITORINFOEX)
    user32.GetMonitorInfoW(hmon, ctypes.byref(info))
    rect = info.rcMonitor
    return {
        "left": rect.left,
        "top": rect.top,
        "width": rect.right - rect.left,
        "height": rect.bottom - rect.top,
    }


def _window_info_from_hwnd(hwnd: int, title: str) -> WindowInfo:
    user32 = ctypes.windll.user32

    client = wintypes.RECT()
    user32.GetClientRect(hwnd, ctypes.byref(client))
    origin = wintypes.POINT(0, 0)
    user32.ClientToScreen(hwnd, ctypes.byref(origin))

    width = client.right - client.left
    height = client.bottom - client.top
    monitor = _monitor_for_hwnd(hwnd)

    is_fullscreen = (
        width >= monitor["width"] - 10
        and height >= monitor["height"] - 10
    )
    if is_fullscreen:
        return WindowInfo(
            left=monitor["left"],
            top=monitor["top"],
            width=monitor["width"],
            height=monitor["height"],
            title=title,
            hwnd=hwnd,
            is_fullscreen=True,
        )

    return WindowInfo(
        left=origin.x,
        top=origin.y,
        width=width,
        height=height,
        title=title,
        hwnd=hwnd,
        is_fullscreen=False,
    )


def _find_window_by_title(title: str) -> WindowInfo | None:
    """通过窗口标题查找游戏窗口，坐标基于客户区/全屏显示器"""
    user32 = ctypes.windll.user32
    result: list[WindowInfo] = []

    def callback(hwnd, _):
        if user32.IsWindowVisible(hwnd):
            length = user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                buf = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buf, length + 1)
                if title.lower() in buf.value.lower():
                    result.append(_window_info_from_hwnd(hwnd, buf.value))
        return True

    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)
    user32.EnumWindows(WNDENUMPROC(callback), 0)

    if not result:
        return None

    result.sort(key=lambda w: w.width * w.height, reverse=True)
    return result[0]


def find_window_by_title(title: str) -> WindowInfo | None:
    return _find_window_by_title(title)


def get_primary_monitor() -> dict[str, int]:
    """获取 Windows 主显示器的屏幕区域"""
    user32 = ctypes.windll.user32
    MONITOR_DEFAULTTOPRIMARY = 1
    hmon = user32.MonitorFromPoint(wintypes.POINT(0, 0), MONITOR_DEFAULTTOPRIMARY)
    info = MONITORINFOEX()
    info.cbSize = ctypes.sizeof(MONITORINFOEX)
    user32.GetMonitorInfoW(hmon, ctypes.byref(info))
    rect = info.rcMonitor
    return {
        "left": rect.left,
        "top": rect.top,
        "width": rect.right - rect.left,
        "height": rect.bottom - rect.top,
    }


def window_to_monitor(window: WindowInfo) -> dict[str, int]:
    return {
        "left": window.left,
        "top": window.top,
        "width": window.width,
        "height": window.height,
    }


class ScreenCapture:
    def __init__(self, window_title: str = ""):
        self.window_title = window_title
        self._window: WindowInfo | None = None
        self._sct = mss.mss()

    def refresh_window(self) -> WindowInfo | None:
        if self.window_title:
            self._window = _find_window_by_title(self.window_title)
        return self._window

    @property
    def offset(self) -> tuple[int, int]:
        if self._window:
            return (self._window.left, self._window.top)
        return (0, 0)

    @property
    def window_size(self) -> tuple[int, int] | None:
        if self._window:
            return (self._window.width, self._window.height)
        return None

    @property
    def window_info(self) -> WindowInfo | None:
        return self._window

    def capture_region(
        self,
        left: int,
        top: int,
        width: int,
        height: int,
    ) -> Image.Image:
        """捕获指定区域，坐标相对于游戏窗口"""
        if self.window_title and not self._window:
            self.refresh_window()
        ox, oy = self.offset
        monitor = {
            "left": left + ox,
            "top": top + oy,
            "width": width,
            "height": height,
        }
        screenshot = self._sct.grab(monitor)
        return Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")

    def capture_full_window(self) -> Image.Image | None:
        if not self._window and self.window_title:
            self.refresh_window()
        if self._window:
            return self.capture_region(0, 0, self._window.width, self._window.height)
        return None

    def to_cv2(self, image: Image.Image) -> np.ndarray:
        return np.array(image)[:, :, ::-1].copy()
