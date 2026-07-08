"""
屏幕区域选取工具

用法:
  python tools/region_picker.py

操作说明:
  1. 运行后会全屏截图
  2. 用鼠标拖拽选取区域
  3. 按 Enter 确认，按 Esc 取消
  4. 选取完成后会输出 YAML 配置片段
"""

from __future__ import annotations

import sys
from pathlib import Path

import cv2
import mss
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


class RegionPicker:
    def __init__(self):
        self.start_point: tuple[int, int] | None = None
        self.end_point: tuple[int, int] | None = None
        self.drawing = False
        self.regions: list[dict] = []
        self.current_label = "market_list"

    def _mouse_callback(self, event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            self.drawing = True
            self.start_point = (x, y)
            self.end_point = (x, y)
        elif event == cv2.EVENT_MOUSEMOVE and self.drawing:
            self.end_point = (x, y)
        elif event == cv2.EVENT_LBUTTONUP:
            self.drawing = False
            self.end_point = (x, y)

    def pick_region(self, screenshot: np.ndarray, label: str) -> dict | None:
        self.start_point = None
        self.end_point = None
        self.current_label = label

        window_name = f"选取区域: {label} (Enter=确认 Esc=取消)"
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
        cv2.setMouseCallback(window_name, self._mouse_callback)

        while True:
            display = screenshot.copy()
            if self.start_point and self.end_point:
                cv2.rectangle(display, self.start_point, self.end_point, (0, 255, 0), 2)
                x1, y1 = self.start_point
                x2, y2 = self.end_point
                w, h = abs(x2 - x1), abs(y2 - y1)
                cv2.putText(
                    display, f"{w}x{h}",
                    (min(x1, x2), min(y1, y2) - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2,
                )

            cv2.imshow(window_name, display)
            key = cv2.waitKey(1) & 0xFF

            if key == 13 and self.start_point and self.end_point:  # Enter
                x1, y1 = self.start_point
                x2, y2 = self.end_point
                region = {
                    "label": label,
                    "left": min(x1, x2),
                    "top": min(y1, y2),
                    "width": abs(x2 - x1),
                    "height": abs(y2 - y1),
                }
                cv2.destroyWindow(window_name)
                return region
            elif key == 27:  # Esc
                cv2.destroyWindow(window_name)
                return None

    def pick_point(self, screenshot: np.ndarray, label: str) -> dict | None:
        point: list[int] = []

        def callback(event, x, y, flags, param):
            if event == cv2.EVENT_LBUTTONDOWN:
                point.clear()
                point.extend([x, y])

        window_name = f"点击位置: {label} (Enter=确认 Esc=取消)"
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
        cv2.setMouseCallback(window_name, callback)

        while True:
            display = screenshot.copy()
            if point:
                cv2.circle(display, (point[0], point[1]), 8, (0, 0, 255), -1)
                cv2.putText(
                    display, f"({point[0]}, {point[1]})",
                    (point[0] + 15, point[1]),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2,
                )
            cv2.imshow(window_name, display)
            key = cv2.waitKey(1) & 0xFF

            if key == 13 and point:
                cv2.destroyWindow(window_name)
                return {"label": label, "x": point[0], "y": point[1]}
            elif key == 27:
                cv2.destroyWindow(window_name)
                return None


def main():
    print("=" * 50)
    print("darkMark 屏幕区域选取工具")
    print("=" * 50)
    print()
    print("请确保游戏市场界面已打开并可见")
    print("3 秒后开始截图...")
    print()

    import time
    time.sleep(3)

    with mss.mss() as sct:
        monitor = sct.monitors[1]
        screenshot = np.array(sct.grab(monitor))
        screenshot = cv2.cvtColor(screenshot, cv2.COLOR_BGRA2BGR)

    picker = RegionPicker()
    results: list[dict] = []

    steps = [
        ("region", "market_list", "市场列表区域（包含物品名和价格）"),
        ("point", "refresh_button", "刷新按钮位置"),
        ("point", "buy_button", "购买按钮位置（选第一个列表项的购买按钮）"),
        ("point", "confirm_button", "确认购买对话框的确认按钮"),
    ]

    for step_type, label, desc in steps:
        print(f"\n>>> {desc}")
        if step_type == "region":
            result = picker.pick_region(screenshot, label)
        else:
            result = picker.pick_point(screenshot, label)
        if result:
            results.append(result)
            print(f"    已记录: {result}")
        else:
            print("    已跳过")

    cv2.destroyAllWindows()

    print("\n" + "=" * 50)
    print("生成的配置 (复制到 config/regions.yaml):")
    print("=" * 50)

    for r in results:
        if "width" in r:
            print(f"\n{r['label']}:")
            print(f"  left: {r['left']}")
            print(f"  top: {r['top']}")
            print(f"  width: {r['width']}")
            print(f"  height: {r['height']}")
        else:
            print(f"\n{r['label']}:")
            print(f"  x: {r['x']}")
            print(f"  y: {r['y']}")

    print()


if __name__ == "__main__":
    main()
