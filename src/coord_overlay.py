"""在游戏窗口上方显示透明坐标标注层（点击穿透 + Ctrl+E 编辑）"""

from __future__ import annotations

import ctypes
import shutil
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path

import keyboard

from src.config_loader import (
    CONFIG_DIR,
    Point,
    Region,
    RegionsConfig,
    Resolution,
    load_regions,
    save_regions,
    scale_point,
    scale_region,
    scale_value,
    unscale_point,
    unscale_region,
    unscale_value,
)
from src.screen_capture import ScreenCapture, WindowInfo, enable_dpi_awareness

enable_dpi_awareness()

user32 = ctypes.windll.user32

GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOPMOST = 0x00000008

TRANSPARENT_COLOR = "#010101"
HIT_RADIUS = 20
HANDLE_SIZE = 8
MAX_BUY_ROWS = 20


@dataclass
class _EditState:
    market_list: Region
    refresh: Point
    buy_client_x: int
    buy_client_y: int
    submit: Point
    complete: Point
    row_height: int


@dataclass
class _Marker:
    key: str
    kind: str  # "rect" | "cross"
    label: str
    color: str
    x1: int
    y1: int
    x2: int = 0
    y2: int = 0
    editable: bool = True


class CoordOverlay:
    CROSS_SIZE = 14
    STATUS_HEIGHT = 28

    def __init__(self, regions: RegionsConfig | None = None):
        self.regions = regions or load_regions()
        self.capture = ScreenCapture(self.regions.window_title)
        self.running = True
        self.edit_mode = False
        self.dirty = False
        self._root: tk.Tk | None = None
        self._canvas: tk.Canvas | None = None
        self._status: tk.Label | None = None
        self._frozen_window: WindowInfo | None = None
        self._edit_state: _EditState | None = None
        self._drag_key: str | None = None
        self._drag_mode: str | None = None  # "move" | "resize" | "point"
        self._drag_offset: tuple[int, int] = (0, 0)

    def _window_size(self) -> tuple[int, int] | None:
        if self._frozen_window:
            return self._frozen_window.width, self._frozen_window.height
        if self.capture.window_info:
            w = self.capture.window_info
            return w.width, w.height
        return None

    def _visible_row_count(self, ml_height: int, row_height: int) -> int:
        if row_height <= 0:
            return 1
        return max(1, min(MAX_BUY_ROWS, ml_height // row_height))

    def _row_center_y(self, ml_top: int, row: int, row_height: int) -> int:
        return ml_top + row * row_height + row_height // 2

    def _sync_edit_from_regions(self, size: tuple[int, int]) -> _EditState:
        ref = self.regions.reference_resolution
        ml = scale_region(self.regions.market_list, ref, size)
        rx, ry = scale_point(
            self.regions.refresh_button.x,
            self.regions.refresh_button.y,
            ref,
            size,
        )
        row_height = scale_value(self.regions.row_height, ref, size)
        buy_x = self.regions.buy_button.x
        if self.regions.buy_button.y == 0:
            buy_cx = ml.left + scale_value(buy_x, ref, size, axis="x")
            buy_cy = self._row_center_y(ml.top, 0, row_height)
        else:
            buy_cx, buy_cy = scale_point(buy_x, self.regions.buy_button.y, ref, size)

        submit = self.regions.trade_dialog["submit_button"]
        complete = self.regions.trade_dialog["complete_button"]
        sx, sy = scale_point(submit.x, submit.y, ref, size)
        cx, cy = scale_point(complete.x, complete.y, ref, size)

        return _EditState(
            market_list=ml,
            refresh=Point(rx, ry),
            buy_client_x=buy_cx,
            buy_client_y=buy_cy,
            submit=Point(sx, sy),
            complete=Point(cx, cy),
            row_height=row_height,
        )

    def _append_buy_row_markers(
        self,
        markers: list[_Marker],
        state: _EditState,
        *,
        edit_mode: bool,
    ) -> None:
        ml = state.market_list
        count = self._visible_row_count(ml.height, state.row_height)
        for row in range(count):
            row_y = self._row_center_y(ml.top, row, state.row_height)
            if row == 0:
                continue  # buy[0] 已单独添加
            editable = edit_mode and row == 1
            markers.append(
                _Marker(
                    "buy_row1" if row == 1 else f"buy_preview_{row}",
                    "cross",
                    f"buy[{row}]",
                    "#66AAFF" if editable else "#3399FF",
                    state.buy_client_x,
                    row_y,
                    editable=editable,
                )
            )

    def _build_markers_from_edit(self, state: _EditState) -> list[_Marker]:
        ml = state.market_list
        markers: list[_Marker] = [
            _Marker("market_list", "rect", "market_list", "#00FF00", ml.left, ml.top, ml.width, ml.height),
            _Marker("refresh", "cross", "refresh", "#FF3333", state.refresh.x, state.refresh.y),
            _Marker("buy", "cross", "buy[0]", "#3399FF", state.buy_client_x, state.buy_client_y),
            _Marker("submit", "cross", "submit", "#FFCC00", state.submit.x, state.submit.y),
            _Marker("complete", "cross", "complete", "#FF9900", state.complete.x, state.complete.y),
        ]

        if self.regions.buy_button.y == 0:
            self._append_buy_row_markers(markers, state, edit_mode=True)
        return markers

    def _build_markers(self, size: tuple[int, int]) -> list[_Marker]:
        if self.edit_mode and self._edit_state:
            return self._build_markers_from_edit(self._edit_state)
        ref = self.regions.reference_resolution
        row_height = scale_value(self.regions.row_height, ref, size)
        ml = scale_region(self.regions.market_list, ref, size)
        markers: list[_Marker] = [
            _Marker(
                "market_list", "rect", "market_list", "#00FF00",
                ml.left, ml.top, ml.width, ml.height,
            ),
        ]
        rx, ry = scale_point(
            self.regions.refresh_button.x,
            self.regions.refresh_button.y,
            ref,
            size,
        )
        markers.append(_Marker("refresh", "cross", "refresh", "#FF3333", rx, ry))

        buy_x = self.regions.buy_button.x
        if self.regions.buy_button.y == 0:
            edit_state = _EditState(
                market_list=ml,
                refresh=Point(0, 0),
                buy_client_x=0,
                buy_client_y=0,
                submit=Point(0, 0),
                complete=Point(0, 0),
                row_height=row_height,
            )
            edit_state.buy_client_x = ml.left + scale_value(buy_x, ref, size, axis="x")
            edit_state.buy_client_y = self._row_center_y(ml.top, 0, row_height)
            markers.append(
                _Marker("buy", "cross", "buy[0]", "#3399FF", edit_state.buy_client_x, edit_state.buy_client_y)
            )
            self._append_buy_row_markers(markers, edit_state, edit_mode=False)
        else:
            bx, by = scale_point(buy_x, self.regions.buy_button.y, ref, size)
            markers.append(_Marker("buy", "cross", "buy", "#3399FF", bx, by))

        for key, color, label in (
            ("submit_button", "#FFCC00", "submit"),
            ("complete_button", "#FF9900", "complete"),
        ):
            pt = self.regions.trade_dialog.get(key)
            if pt:
                tx, ty = scale_point(pt.x, pt.y, ref, size)
                markers.append(
                    _Marker(key.replace("_button", ""), "cross", label, color, tx, ty)
                )
        return markers

    @staticmethod
    def _overlay_hwnd(root: tk.Tk) -> int:
        root.update_idletasks()
        return user32.GetParent(root.winfo_id())

    def _set_click_through(self, root: tk.Tk, enabled: bool) -> None:
        hwnd = self._overlay_hwnd(root)
        style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        base = style | WS_EX_LAYERED | WS_EX_TOPMOST
        if enabled:
            base |= WS_EX_TRANSPARENT
        else:
            base &= ~WS_EX_TRANSPARENT
        user32.SetWindowLongW(hwnd, GWL_EXSTYLE, base)

    def _redraw(self) -> None:
        if not self._canvas or not self._root:
            return
        size = self._window_size()
        if not size:
            return
        width, height = size
        markers = self._build_markers(size)
        self._draw(self._canvas, markers, width, height, self.edit_mode)
        self._update_status_text()

    def _draw(
        self,
        canvas: tk.Canvas,
        markers: list[_Marker],
        width: int,
        height: int,
        edit_mode: bool,
    ) -> None:
        canvas.delete("all")
        canvas.create_rectangle(
            2, 2, width - 2, height - 2,
            outline="#FFFFFF",
            dash=(6, 4),
            width=1,
        )

        for m in markers:
            selected = edit_mode and m.key == self._drag_key
            width_extra = 2 if selected else 0
            if m.kind == "rect":
                x2 = m.x1 + m.x2
                y2 = m.y1 + m.y2
                canvas.create_rectangle(
                    m.x1, m.y1, x2, y2,
                    outline=m.color,
                    width=2 + width_extra,
                )
                if edit_mode and m.editable:
                    canvas.create_rectangle(
                        x2 - HANDLE_SIZE, y2 - HANDLE_SIZE, x2, y2,
                        fill=m.color,
                        outline="#FFFFFF",
                        tags=("handle", m.key),
                    )
                canvas.create_text(
                    m.x1 + 4,
                    max(m.y1 - 14, 4),
                    text=f"{m.label} ({m.x1},{m.y1}) {m.x2}x{m.y2}",
                    fill=m.color,
                    anchor="nw",
                    font=("Consolas", 10, "bold"),
                )
            else:
                s = self.CROSS_SIZE
                x, y = m.x1, m.y1
                color = m.color if m.editable else "#5588CC"
                canvas.create_line(x - s, y, x + s, y, fill=color, width=2 + width_extra)
                canvas.create_line(x, y - s, x, y + s, fill=color, width=2 + width_extra)
                canvas.create_oval(
                    x - 4, y - 4, x + 4, y + 4,
                    outline=color,
                    width=2 + width_extra,
                )
                canvas.create_text(
                    x + s + 4,
                    y - 6,
                    text=f"{m.label} ({x},{y})",
                    fill=color,
                    anchor="w",
                    font=("Consolas", 10, "bold"),
                )

    def _update_status_text(self) -> None:
        if not self._status:
            return
        window = self._frozen_window or self.capture.window_info
        dirty = " *" if self.dirty else ""
        if self.edit_mode:
            hint = f"[编辑{dirty}] 拖拽 buy[0]/buy[1] 调购买按钮 | Ctrl+S 保存 | Ctrl+E 显示 | Esc 退出"
        else:
            hint = f"[显示{dirty}] Ctrl+E 编辑 | Esc 退出"

        if window:
            mode = "全屏" if window.is_fullscreen else "窗口"
            self._status.config(
                text=(
                    f"{window.title.strip()}  {window.width}x{window.height} [{mode}]  "
                    f"屏幕原点 ({window.left},{window.top})  |  {hint}"
                )
            )
        else:
            self._status.config(text=f"未找到游戏窗口  |  {hint}")

    def _hit_test(self, x: int, y: int) -> tuple[str | None, str | None]:
        if not self._edit_state:
            return None, None
        markers = self._build_markers_from_edit(self._edit_state)
        ml = self._edit_state.market_list
        x2, y2 = ml.left + ml.width, ml.top + ml.height

        if abs(x - x2) <= HANDLE_SIZE and abs(y - y2) <= HANDLE_SIZE:
            return "market_list", "resize"

        best_key = None
        best_dist = HIT_RADIUS + 1
        for m in markers:
            if not m.editable or m.kind != "cross":
                continue
            dist = ((x - m.x1) ** 2 + (y - m.y1) ** 2) ** 0.5
            if dist <= HIT_RADIUS and dist < best_dist:
                best_dist = dist
                best_key = m.key
        if best_key:
            return best_key, "point"

        if ml.left <= x <= x2 and ml.top <= y <= y2:
            return "market_list", "move"
        return None, None

    def _on_press(self, event: tk.Event) -> None:
        if not self.edit_mode or not self._edit_state:
            return
        key, mode = self._hit_test(event.x, event.y)
        if not key:
            return
        self._drag_key = key
        self._drag_mode = mode
        if mode == "move":
            ml = self._edit_state.market_list
            self._drag_offset = (event.x - ml.left, event.y - ml.top)
        elif mode == "point":
            self._drag_offset = (0, 0)
        elif mode == "resize":
            self._drag_offset = (0, 0)

    def _on_drag(self, event: tk.Event) -> None:
        if not self.edit_mode or not self._edit_state or not self._drag_key:
            return
        state = self._edit_state
        key = self._drag_key
        mode = self._drag_mode

        if key == "market_list" and mode == "move":
            ml = state.market_list
            dx = event.x - self._drag_offset[0] - ml.left
            dy = event.y - self._drag_offset[1] - ml.top
            state.market_list = Region(ml.left + dx, ml.top + dy, ml.width, ml.height)
            state.buy_client_y = self._row_center_y(state.market_list.top, 0, state.row_height)
        elif key == "market_list" and mode == "resize":
            ml = state.market_list
            w = max(20, event.x - ml.left)
            h = max(20, event.y - ml.top)
            state.market_list = Region(ml.left, ml.top, w, h)
        elif mode == "point":
            if key == "refresh":
                state.refresh = Point(event.x, event.y)
            elif key == "buy":
                state.buy_client_x = event.x
                state.buy_client_y = event.y
                ml = state.market_list
                state.market_list = Region(
                    ml.left,
                    event.y - state.row_height // 2,
                    ml.width,
                    ml.height,
                )
            elif key == "buy_row1":
                state.row_height = max(20, event.y - state.buy_client_y)
            elif key == "submit":
                state.submit = Point(event.x, event.y)
            elif key == "complete":
                state.complete = Point(event.x, event.y)

        self.dirty = True
        self._redraw()

    def _on_release(self, _event: tk.Event) -> None:
        self._drag_key = None
        self._drag_mode = None

    def _apply_edit_to_regions(self) -> None:
        if not self._edit_state or not self._frozen_window:
            return
        size = (self._frozen_window.width, self._frozen_window.height)
        ref = self.regions.reference_resolution or Resolution(size[0], size[1])
        state = self._edit_state
        ml = state.market_list

        self.regions.reference_resolution = Resolution(size[0], size[1])
        self.regions.market_list = unscale_region(ml, ref, size)
        rx, ry = unscale_point(state.refresh.x, state.refresh.y, ref, size)
        self.regions.refresh_button = Point(rx, ry)

        buy_abs_ref_x, buy_row0_ref_y = unscale_point(
            state.buy_client_x, state.buy_client_y, ref, size
        )
        ml_ref = self.regions.market_list
        self.regions.buy_button = Point(buy_abs_ref_x - ml_ref.left, 0)
        self.regions.row_height = unscale_value(state.row_height, ref, size, axis="y")

        # 同步 market_list.top，使首行购买按钮与 buy[0] 垂直位置一致
        rh_ref = self.regions.row_height
        self.regions.market_list = Region(
            ml_ref.left,
            buy_row0_ref_y - rh_ref // 2,
            ml_ref.width,
            ml_ref.height,
        )

        sx, sy = unscale_point(state.submit.x, state.submit.y, ref, size)
        cx, cy = unscale_point(state.complete.x, state.complete.y, ref, size)
        self.regions.trade_dialog["submit_button"] = Point(sx, sy)
        self.regions.trade_dialog["complete_button"] = Point(cx, cy)

        # 更新 reference 为当前窗口，后续 unscale 基准一致
        self.regions.reference_resolution = Resolution(size[0], size[1])

    def _save(self) -> None:
        if not self.edit_mode:
            return
        if not self._edit_state or not self._frozen_window:
            return
        self._apply_edit_to_regions()
        path = CONFIG_DIR / "regions.yaml"
        if path.exists():
            shutil.copy2(path, path.with_suffix(".yaml.bak"))
        save_regions(self.regions, path)
        self.dirty = False
        if self._status:
            self._status.config(text=f"已保存 {path}  |  Ctrl+E 返回显示")

    def _enter_edit_mode(self) -> None:
        window = self.capture.refresh_window()
        if not window:
            return
        self._frozen_window = window
        size = (window.width, window.height)
        self._edit_state = self._sync_edit_from_regions(size)
        self.edit_mode = True
        if self._root:
            self._set_click_through(self._root, False)
            w, h = window.width, window.height
            self._root.geometry(
                f"{w}x{h + self.STATUS_HEIGHT}+{window.left}+{window.top}"
            )
        self._redraw()

    def _leave_edit_mode(self) -> None:
        if self._edit_state and self.dirty:
            self._apply_edit_to_regions()
        self.edit_mode = False
        self._frozen_window = None
        self._edit_state = None
        self._drag_key = None
        if self._root:
            self._set_click_through(self._root, True)
        self._redraw()

    def _toggle_mode(self) -> None:
        if self.edit_mode:
            self._leave_edit_mode()
        else:
            self._enter_edit_mode()

    def _refresh(self) -> None:
        if not self.running or not self._root or not self._canvas:
            return

        if self.edit_mode:
            self._redraw()
            self._root.after(500, self._refresh)
            return

        window = self.capture.refresh_window()
        if not window:
            if self._status:
                self._status.config(text="未找到游戏窗口，等待中…  |  Esc 退出")
            self._root.after(500, self._refresh)
            return

        width, height = window.width, window.height
        self._root.geometry(
            f"{width}x{height + self.STATUS_HEIGHT}+{window.left}+{window.top}"
        )
        self._canvas.config(width=width, height=height)
        markers = self._build_markers((width, height))
        self._draw(self._canvas, markers, width, height, edit_mode=False)
        self._update_status_text()
        self._root.after(500, self._refresh)

    def run(self) -> None:
        root = tk.Tk()
        self._root = root
        root.title("darkMark Coord Overlay")
        root.overrideredirect(True)
        root.attributes("-topmost", True)
        root.configure(bg=TRANSPARENT_COLOR)
        root.attributes("-transparentcolor", TRANSPARENT_COLOR)

        status = tk.Label(
            root,
            text="初始化…",
            bg="#111111",
            fg="#00FF00",
            font=("Microsoft YaHei", 9),
            anchor="w",
            padx=8,
        )
        status.pack(fill="x")
        self._status = status

        canvas = tk.Canvas(
            root,
            bg=TRANSPARENT_COLOR,
            highlightthickness=0,
            bd=0,
        )
        canvas.pack()
        self._canvas = canvas

        canvas.bind("<Button-1>", self._on_press)
        canvas.bind("<B1-Motion>", self._on_drag)
        canvas.bind("<ButtonRelease-1>", self._on_release)
        root.bind("<Escape>", lambda _e: self.stop(root))

        keyboard.add_hotkey("ctrl+e", lambda: root.after(0, self._toggle_mode))
        keyboard.add_hotkey("ctrl+s", lambda: root.after(0, self._save))

        root.after(100, lambda: self._set_click_through(root, True))
        root.after(200, self._refresh)
        try:
            root.mainloop()
        finally:
            keyboard.unhook_all_hotkeys()

    def stop(self, root: tk.Tk | None = None) -> None:
        self.running = False
        keyboard.unhook_all_hotkeys()
        target = root or self._root
        if target is not None:
            target.destroy()


def run_overlay(regions: RegionsConfig | None = None) -> None:
    CoordOverlay(regions).run()
