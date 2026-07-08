"""游戏内鼠标点击（UE 游戏在前台时会拦截光标，需先移后聚焦）"""

from __future__ import annotations

import ctypes
import time
from contextlib import contextmanager
from ctypes import wintypes

from src.screen_capture import enable_dpi_awareness
from src.utils.logger import setup_logger

logger = setup_logger()
enable_dpi_awareness()

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

INPUT_MOUSE = 0
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_ABSOLUTE = 0x8000
MOUSEEVENTF_VIRTUALDESK = 0x4000

WM_MOUSEMOVE = 0x0200
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
MK_LBUTTON = 0x0001

SM_XVIRTUALSCREEN = 76
SM_YVIRTUALSCREEN = 77
SM_CXVIRTUALSCREEN = 78
SM_CYVIRTUALSCREEN = 79


class _POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


class _INPUT_UNION(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT)]


class INPUT(ctypes.Structure):
    _anonymous_ = ("u",)
    _fields_ = [("type", wintypes.DWORD), ("u", _INPUT_UNION)]


def _cursor_pos() -> tuple[int, int]:
    pt = _POINT()
    user32.GetCursorPos(ctypes.byref(pt))
    return pt.x, pt.y


def _virtual_screen() -> tuple[int, int, int, int]:
    left = user32.GetSystemMetrics(SM_XVIRTUALSCREEN)
    top = user32.GetSystemMetrics(SM_YVIRTUALSCREEN)
    width = user32.GetSystemMetrics(SM_CXVIRTUALSCREEN)
    height = user32.GetSystemMetrics(SM_CYVIRTUALSCREEN)
    return left, top, width, height


def _to_absolute(x: int, y: int) -> tuple[int, int]:
    left, top, width, height = _virtual_screen()
    ax = int((x - left) * 65535 / max(width - 1, 1))
    ay = int((y - top) * 65535 / max(height - 1, 1))
    return ax, ay


def _make_lparam(client_x: int, client_y: int) -> int:
    return (client_y & 0xFFFF) << 16 | (client_x & 0xFFFF)


def _send_mouse(flags: int, dx: int = 0, dy: int = 0) -> None:
    inp = INPUT(type=INPUT_MOUSE, mi=MOUSEINPUT(dx=dx, dy=dy, dwFlags=flags))
    sent = user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))
    if sent != 1:
        err = ctypes.get_last_error()
        raise OSError(f"SendInput 失败 (flags={flags:#x}, err={err})")


@contextmanager
def _game_input_context(game_thread: int):
    our_thread = kernel32.GetCurrentThreadId()
    attached = False
    try:
        if game_thread and game_thread != our_thread:
            attached = bool(user32.AttachThreadInput(our_thread, game_thread, True))
        user32.ClipCursor(None)
        user32.ReleaseCapture()
        yield
    finally:
        if attached:
            user32.AttachThreadInput(our_thread, game_thread, False)


def _unlock_cursor() -> None:
    user32.ClipCursor(None)
    user32.ReleaseCapture()


def _set_cursor_pos(x: int, y: int) -> bool:
    ok = bool(user32.SetCursorPos(x, y))
    if not ok:
        err = ctypes.get_last_error()
        logger.debug(f"SetCursorPos 失败: ({x}, {y}), err={err}")
    return ok


def _sendinput_move_absolute(x: int, y: int) -> None:
    ax, ay = _to_absolute(x, y)
    flags = MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK
    _send_mouse(flags, ax, ay)


def _sendinput_move_relative(target_x: int, target_y: int) -> None:
    cx, cy = _cursor_pos()
    dx = target_x - cx
    dy = target_y - cy
    step_limit = 120
    while dx or dy:
        step_x = max(-step_limit, min(step_limit, dx)) if dx else 0
        step_y = max(-step_limit, min(step_limit, dy)) if dy else 0
        if dx:
            dx -= step_x
        if dy:
            dy -= step_y
        _send_mouse(MOUSEEVENTF_MOVE, step_x, step_y)
        time.sleep(0.004)


def _sendinput_click() -> None:
    _send_mouse(MOUSEEVENTF_LEFTDOWN)
    time.sleep(0.02)
    _send_mouse(MOUSEEVENTF_LEFTUP)


def _legacy_click() -> None:
    user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    time.sleep(0.02)
    user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)


def _deepest_child_at(root_hwnd: int, screen_x: int, screen_y: int) -> int:
    current = root_hwnd
    while current:
        pt = _POINT(screen_x, screen_y)
        user32.ScreenToClient(current, ctypes.byref(pt))
        child = user32.ChildWindowFromPoint(current, pt)
        if not child or child == current:
            return current
        current = child
    return root_hwnd


def _screen_to_client(root_hwnd: int, screen_x: int, screen_y: int) -> tuple[int, int]:
    pt = _POINT(screen_x, screen_y)
    user32.ScreenToClient(root_hwnd, ctypes.byref(pt))
    return pt.x, pt.y


def _dispatch_mouse_click(
    hwnd: int,
    client_x: int,
    client_y: int,
    *,
    use_send: bool,
) -> None:
    lparam = _make_lparam(client_x, client_y)
    dispatch = user32.SendMessageW if use_send else user32.PostMessageW
    dispatch(hwnd, WM_MOUSEMOVE, 0, lparam)
    time.sleep(0.012)
    dispatch(hwnd, WM_LBUTTONDOWN, MK_LBUTTON, lparam)
    time.sleep(0.025)
    dispatch(hwnd, WM_LBUTTONUP, 0, lparam)


def _message_click(
    root_hwnd: int,
    screen_x: int,
    screen_y: int,
    client_x: int | None = None,
    client_y: int | None = None,
) -> str:
    child = _deepest_child_at(root_hwnd, screen_x, screen_y)
    attempts: list[tuple[int, int, int, str]] = []

    if client_x is not None and client_y is not None:
        attempts.append((root_hwnd, client_x, client_y, "root+配置客户区坐标"))

    if child != root_hwnd:
        cx, cy = _screen_to_client(child, screen_x, screen_y)
        attempts.append((child, cx, cy, "deepest-child"))

    cx, cy = _screen_to_client(root_hwnd, screen_x, screen_y)
    attempts.append((root_hwnd, cx, cy, "root+屏幕换算"))

    seen: set[tuple[int, int, int]] = set()
    for target_hwnd, cx, cy, label in attempts:
        key = (target_hwnd, cx, cy)
        if key in seen:
            continue
        seen.add(key)

        logger.info(
            f"窗口消息点击: hwnd={target_hwnd} ({label}) "
            f"客户区 ({cx}, {cy})  屏幕 ({screen_x}, {screen_y})"
        )
        _dispatch_mouse_click(target_hwnd, cx, cy, use_send=False)
        return f"PostMessage(hwnd={target_hwnd}, client=({cx},{cy}), {label})"

    return "PostMessage(未发送)"


def log_window_target(root_hwnd: int, screen_x: int, screen_y: int) -> None:
    rect = wintypes.RECT()
    user32.GetWindowRect(root_hwnd, ctypes.byref(rect))
    cx, cy = _screen_to_client(root_hwnd, screen_x, screen_y)
    child = _deepest_child_at(root_hwnd, screen_x, screen_y)
    logger.info(
        f"目标窗口: hwnd={root_hwnd} 屏幕区域 "
        f"({rect.left},{rect.top})-({rect.right},{rect.bottom})"
    )
    logger.info(
        f"点击映射: 屏幕 ({screen_x},{screen_y}) -> 客户区 ({cx},{cy}), "
        f"子窗口 hwnd={child}"
    )


def focus_window(hwnd: int) -> bool:
    if not hwnd:
        return False

    if user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, 9)

    if user32.GetForegroundWindow() == hwnd:
        return True

    fg = user32.GetForegroundWindow()
    fg_thread = user32.GetWindowThreadProcessId(fg, None)
    target_thread = user32.GetWindowThreadProcessId(hwnd, None)

    attached = False
    try:
        if fg_thread != target_thread:
            attached = bool(user32.AttachThreadInput(fg_thread, target_thread, True))
        user32.SetForegroundWindow(hwnd)
        user32.BringWindowToTop(hwnd)
    finally:
        if attached:
            user32.AttachThreadInput(fg_thread, target_thread, False)

    time.sleep(0.08)
    return user32.GetForegroundWindow() == hwnd


def _near(pos: tuple[int, int], x: int, y: int, tolerance: int = 8) -> bool:
    return abs(pos[0] - x) <= tolerance and abs(pos[1] - y) <= tolerance


def _points_near(
    a: tuple[int, int],
    b: tuple[int, int],
    tolerance: int = 8,
) -> bool:
    return abs(a[0] - b[0]) <= tolerance and abs(a[1] - b[1]) <= tolerance


def _move_to_impl(x: int, y: int) -> None:
    _set_cursor_pos(x, y)
    time.sleep(0.01)
    if not _near(_cursor_pos(), x, y):
        _sendinput_move_absolute(x, y)
        time.sleep(0.012)
    if not _near(_cursor_pos(), x, y):
        _sendinput_move_relative(x, y)
        time.sleep(0.012)
    if not _near(_cursor_pos(), x, y):
        _set_cursor_pos(x, y)
        time.sleep(0.01)


def move_to(x: int, y: int, game_thread: int = 0) -> tuple[int, int]:
    x, y = int(x), int(y)
    with _game_input_context(game_thread):
        _unlock_cursor()
        _move_to_impl(x, y)
    return _cursor_pos()


def game_click(
    x: int,
    y: int,
    hwnd: int = 0,
    client_x: int | None = None,
    client_y: int | None = None,
) -> None:
    """先移鼠标再聚焦游戏，避免 UE 在前台时锁死光标"""
    x, y = int(x), int(y)
    before = _cursor_pos()
    logger.info(f"准备点击 ({x}, {y})，当前鼠标 {before}")

    game_thread = 0
    if hwnd:
        game_thread = user32.GetWindowThreadProcessId(hwnd, None)
        log_window_target(hwnd, x, y)

    # 1. 游戏未聚焦时先移动（此时 SetCursorPos 通常可用）
    _unlock_cursor()
    _move_to_impl(x, y)
    pre_focus = _cursor_pos()
    logger.info(f"聚焦前移动: {before} -> {pre_focus}")

    # 2. 再聚焦游戏并点击
    if hwnd:
        focused = focus_window(hwnd)
        if focused:
            logger.debug(f"游戏窗口已置于前台 (thread={game_thread})")
        else:
            logger.warning("未能将游戏窗口切到前台，仍将尝试点击")

    after_focus = _cursor_pos()
    if not _points_near(after_focus, pre_focus, tolerance=3):
        logger.warning(f"聚焦后光标被重置: {pre_focus} -> {after_focus}")

    method = ""
    after_click = after_focus
    after_move = after_focus

    with _game_input_context(game_thread):
        pos = _cursor_pos()
        if not _near(pos, x, y):
            _move_to_impl(x, y)
            pos = _cursor_pos()

        after_move = pos
        time.sleep(0.02)

        if _near(after_move, x, y):
            _sendinput_click()
            time.sleep(0.02)
            if not _near(_cursor_pos(), x, y):
                _legacy_click()
            after_click = _cursor_pos()
            method = "SendInput"
        elif hwnd:
            logger.warning(
                f"光标无法移动到目标 ({x}, {y})，当前 {after_move}，"
                f"改用窗口消息点击"
            )
            method = _message_click(hwnd, x, y, client_x, client_y)
            after_click = _cursor_pos()
        else:
            _sendinput_click()
            after_click = _cursor_pos()
            method = "SendInput(未移动)"

    logger.info(
        f"点击完成 [{method}]: 目标 ({x}, {y})  "
        f"聚焦前 {pre_focus}  移动后 {after_move}  最终 {after_click}"
    )

    if method.startswith("SendInput") and not _near(after_click, x, y, tolerance=15):
        logger.warning(
            f"鼠标可能未到达目标: 偏差 ({after_click[0] - x}, {after_click[1] - y})"
        )
