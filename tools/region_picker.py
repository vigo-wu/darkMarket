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

import argparse
import sys
from pathlib import Path

import cv2
import mss
import numpy as np
from PIL import Image, ImageDraw, ImageFont

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.config_loader import load_regions
from src.screen_capture import find_window_by_title, get_primary_monitor, window_to_monitor

# OpenCV 在 Windows 上不支持 Unicode 窗口标题，使用固定英文名称
WINDOW_NAME = "darkMark Region Picker"

_CN_FONT_CANDIDATES = (
    "C:/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/simhei.ttf",
    "C:/Windows/Fonts/simsun.ttc",
)


def _load_cn_font(size: int = 22) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in _CN_FONT_CANDIDATES:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _draw_hint(image: np.ndarray, text: str) -> np.ndarray:
    """在图像顶部绘制中文提示（OpenCV 窗口标题无法显示中文）。"""
    pil_img = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(pil_img)
    font = _load_cn_font()
    padding = 8
    bbox = draw.textbbox((0, 0), text, font=font)
    text_w, text_h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.rectangle(
        (0, 0, text_w + padding * 2, text_h + padding * 2),
        fill=(0, 0, 0),
    )
    draw.text((padding, padding), text, font=font, fill=(0, 255, 0))
    return cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)


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

        hint = f"选取区域: {label}  |  Enter 确认  |  Esc 取消"
        cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)
        cv2.setMouseCallback(WINDOW_NAME, self._mouse_callback)

        while True:
            display = _draw_hint(screenshot.copy(), hint)
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

            cv2.imshow(WINDOW_NAME, display)
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
                cv2.destroyWindow(WINDOW_NAME)
                return region
            elif key == 27:  # Esc
                cv2.destroyWindow(WINDOW_NAME)
                return None

    def pick_point(self, screenshot: np.ndarray, label: str) -> dict | None:
        point: list[int] = []

        def callback(event, x, y, flags, param):
            if event == cv2.EVENT_LBUTTONDOWN:
                point.clear()
                point.extend([x, y])

        hint = f"点击位置: {label}  |  Enter 确认  |  Esc 取消"
        cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)
        cv2.setMouseCallback(WINDOW_NAME, callback)

        while True:
            display = _draw_hint(screenshot.copy(), hint)
            if point:
                cv2.circle(display, (point[0], point[1]), 8, (0, 0, 255), -1)
                cv2.putText(
                    display, f"({point[0]}, {point[1]})",
                    (point[0] + 15, point[1]),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2,
                )
            cv2.imshow(WINDOW_NAME, display)
            key = cv2.waitKey(1) & 0xFF

            if key == 13 and point:
                cv2.destroyWindow(WINDOW_NAME)
                return {"label": label, "x": point[0], "y": point[1]}
            elif key == 27:
                cv2.destroyWindow(WINDOW_NAME)
                return None


def _capture_target(title: str = "") -> tuple[np.ndarray, dict]:
    """截取游戏窗口；找不到时回退到主显示器"""
    with mss.mss() as sct:
        window = find_window_by_title(title) if title else None
        if window:
            monitor = window_to_monitor(window)
            source = {
                "kind": "window",
                "title": window.title,
                "width": window.width,
                "height": window.height,
                "left": window.left,
                "top": window.top,
            }
            print(f"已定位游戏窗口: {window.title}")
            print(f"  位置: ({window.left}, {window.top})  大小: {window.width}x{window.height}")
            print("  坐标将相对于游戏窗口左上角")
        else:
            monitor = get_primary_monitor()
            source = {
                "kind": "primary",
                "width": monitor["width"],
                "height": monitor["height"],
                "left": monitor["left"],
                "top": monitor["top"],
            }
            if title:
                print(f"未找到窗口 \"{title}\"，改为主显示器截图")
            else:
                print("未配置 window_title，使用主显示器截图")
            print(f"  位置: ({monitor['left']}, {monitor['top']})  大小: {monitor['width']}x{monitor['height']}")
            print("  坐标将相对于主显示器左上角")

        screenshot = np.array(sct.grab(monitor))
        screenshot = cv2.cvtColor(screenshot, cv2.COLOR_BGRA2BGR)
        return screenshot, source


def main():
    parser = argparse.ArgumentParser(description="darkMark 屏幕区域选取工具")
    parser.add_argument(
        "--title",
        help="游戏窗口标题（默认读取 config/regions.yaml 中的 window_title）",
    )
    args = parser.parse_args()

    regions = load_regions()
    window_title = args.title or regions.window_title

    print("=" * 50)
    print("darkMark 屏幕区域选取工具")
    print("=" * 50)
    print()
    print("请确保游戏市场界面已打开并可见")
    print("3 秒后开始截图...")
    print()

    import time
    time.sleep(3)

    screenshot, source = _capture_target(window_title)

    picker = RegionPicker()
    results: list[dict] = []

    steps = [
        ("region", "market_list", "市场列表区域（包含物品名和价格）"),
        ("point", "refresh_button", "刷新按钮位置"),
        ("point", "buy_button", "购买按钮位置（选第一个列表项的购买按钮）"),
        ("point", "submit_button", "交易界面「提交所需物品」按钮"),
        ("point", "complete_button", "交易界面「完成交易」按钮"),
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
    if source.get("kind") == "window":
        print("# 坐标相对于游戏窗口，全屏模式下等同于当前显示器")
    print(f"reference_resolution:")
    print(f"  width: {source['width']}")
    print(f"  height: {source['height']}")
    if window_title:
        print(f"window_title: {window_title}")

    region_data: dict[str, dict] = {}
    point_data: dict[str, dict] = {}
    for r in results:
        if "width" in r:
            region_data[r["label"]] = r
        else:
            point_data[r["label"]] = r

    if "market_list" in region_data:
        ml = region_data["market_list"]
        print("market_list:")
        print(f"  left: {ml['left']}")
        print(f"  top: {ml['top']}")
        print(f"  width: {ml['width']}")
        print(f"  height: {ml['height']}")

    for key in ("refresh_button", "buy_button"):
        if key in point_data:
            p = point_data[key]
            print(f"{key}:")
            print(f"  x: {p['x']}")
            print(f"  y: {p['y']}")

    if "submit_button" in point_data or "complete_button" in point_data:
        print("trade_dialog:")
        if "submit_button" in point_data:
            p = point_data["submit_button"]
            print("  submit_button:")
            print(f"    x: {p['x']}")
            print(f"    y: {p['y']}")
        if "complete_button" in point_data:
            p = point_data["complete_button"]
            print("  complete_button:")
            print(f"    x: {p['x']}")
            print(f"    y: {p['y']}")

    print()


if __name__ == "__main__":
    main()
