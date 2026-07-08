"""屏幕捕获模块"""

from __future__ import annotations

import ctypes
from ctypes import wintypes
from dataclasses import dataclass

import mss
import numpy as np
from PIL import Image


@dataclass
class WindowInfo:
    left: int
    top: int
    width: int
    height: int
    title: str


def _find_window_by_title(title: str) -> WindowInfo | None:
    """通过窗口标题查找游戏窗口"""
    user32 = ctypes.windll.user32

    result: list[WindowInfo] = []

    def callback(hwnd, _):
        if user32.IsWindowVisible(hwnd):
            length = user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                buf = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buf, length + 1)
                if title.lower() in buf.value.lower():
                    rect = wintypes.RECT()
                    user32.GetWindowRect(hwnd, ctypes.byref(rect))
                    result.append(
                        WindowInfo(
                            left=rect.left,
                            top=rect.top,
                            width=rect.right - rect.left,
                            height=rect.bottom - rect.top,
                            title=buf.value,
                        )
                    )
        return True

    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)
    user32.EnumWindows(WNDENUMPROC(callback), 0)

    return result[0] if result else None


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

    def capture_region(
        self,
        left: int,
        top: int,
        width: int,
        height: int,
    ) -> Image.Image:
        """捕获指定区域，坐标相对于游戏窗口"""
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
