"""OCR 单次测试：截图、保存预处理图、终端输出识别结果"""

from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path

import cv2
from PIL import Image, ImageDraw

from src.config_loader import RegionsConfig, WatchlistConfig, scale_region
from src.ocr_engine import OcrEngine
from src.paths import log_dir
from src.price_parser import extract_item_price_pairs, fuzzy_match
from src.screen_capture import ScreenCapture
from src.utils.logger import setup_logger

logger = setup_logger()


def _print_section(title: str) -> None:
    print()
    print("=" * 50)
    print(title)
    print("=" * 50)


def _save_annotated(image: Image.Image, boxes: list[dict], path: Path) -> None:
    annotated = image.copy()
    draw = ImageDraw.Draw(annotated)
    for box in boxes:
        x, y, w, h = box["x"], box["y"], box["w"], box["h"]
        draw.rectangle([x, y, x + w, y + h], outline="lime", width=2)
        label = f"{box['text']} ({box['conf']:.0f}%)"
        draw.text((x, max(y - 14, 0)), label, fill="lime")
    annotated.save(path)


def run_ocr_test(
    regions: RegionsConfig,
    watchlist: WatchlistConfig | None = None,
    delay: float = 3.0,
) -> bool:
    """单次 OCR 测试，返回是否成功。"""
    output_dir = log_dir() / "ocr_test"
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    capture = ScreenCapture(regions.window_title)
    window = capture.refresh_window()
    if regions.window_title and not window:
        logger.error(f"未找到游戏窗口: {regions.window_title}")
        return False

    if window:
        mode = "全屏" if window.is_fullscreen else "窗口"
        print(f"游戏窗口: {window.title} ({window.width}x{window.height}) [{mode}]")
        ref = regions.reference_resolution
        if ref and (ref.width != window.width or ref.height != window.height):
            print(f"坐标缩放: {ref.width}x{ref.height} -> {window.width}x{window.height}")

    print(f"{delay:.0f} 秒后截图，请切换到游戏市场界面...")
    time.sleep(delay)

    scaled = scale_region(
        regions.market_list,
        regions.reference_resolution,
        capture.window_size,
    )
    print(
        f"截图区域: left={scaled.left}, top={scaled.top}, "
        f"width={scaled.width}, height={scaled.height}"
    )

    image = capture.capture_region(scaled.left, scaled.top, scaled.width, scaled.height)
    ocr = OcrEngine(regions.ocr)

    capture_path = output_dir / f"{stamp}_capture.png"
    preprocessed_path = output_dir / f"{stamp}_preprocessed.png"
    annotated_path = output_dir / f"{stamp}_annotated.png"

    image.save(capture_path)
    processed = ocr.preprocess(image)
    cv2.imwrite(str(preprocessed_path), processed)

    raw_text = ocr.read_text(image)
    lines = ocr.read_lines(image)
    pairs = extract_item_price_pairs(lines)
    boxes = ocr.read_data_with_boxes(image)
    _save_annotated(image, boxes, annotated_path)

    _print_section("OCR 配置")
    print(f"  lang:      {regions.ocr.lang}")
    print(f"  psm:       {regions.ocr.psm}")
    print(f"  whitelist: {regions.ocr.whitelist or '(无)'}")

    _print_section("原始 OCR 文本")
    print(raw_text if raw_text else "(空)")

    _print_section(f"逐行识别 ({len(lines)} 行)")
    if lines:
        for i, line in enumerate(lines, 1):
            print(f"  [{i:02d}] {line}")
    else:
        print("  (无)")

    _print_section(f"解析结果 ({len(pairs)} 条)")
    valid_count = 0
    for i, (name, price) in enumerate(pairs, 1):
        if price is not None:
            valid_count += 1
            print(f"  [{i:02d}] {name} -> {price} gold")
        else:
            print(f"  [{i:02d}] {name} -> (未识别到价格)")

    _print_section(f"文字框 ({len(boxes)} 个, 置信度 > 30%)")
    if boxes:
        for box in boxes:
            print(
                f"  ({box['x']:4d},{box['y']:4d}) "
                f"{box['text']!r:20s} conf={box['conf']:5.1f}%"
            )
    else:
        print("  (无)")

    if watchlist:
        settings = watchlist.settings
        enabled = [i for i in watchlist.items if i.enabled]
        _print_section(f"监控匹配 ({len(enabled)} 个监控项)")
        matched_any = False
        for item in enabled:
            hits = [
                (name, price)
                for name, price in pairs
                if price is not None
                and fuzzy_match(item.name, name, settings.fuzzy_match_threshold)
            ]
            if hits:
                matched_any = True
                for name, price in hits:
                    flag = " ★ 低价!" if price <= item.max_price + settings.price_tolerance else ""
                    print(
                        f"  {item.name} <- {name} ({price} gold, "
                        f"上限 {item.max_price}){flag}"
                    )
            else:
                print(f"  {item.name} <- (未匹配)")

        if not matched_any:
            print("  提示: 名称未匹配时可调低 fuzzy_match_threshold 或检查 whitelist")

    _print_section("已保存文件")
    print(f"  原图:     {capture_path}")
    print(f"  预处理:   {preprocessed_path}")
    print(f"  标注图:   {annotated_path}")
    print()
    print("对照游戏画面检查 capture 与 annotated 图，确认区域与识别文字是否正确。")

    return True
