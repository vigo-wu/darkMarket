"""
darkMark - PC 游戏市场自动检测与购买脚本

用法:
  python -m src.main              # 启动监控
  python -m src.main --dry-run    # 试运行（只检测不购买）
  python -m src.main --test-ocr   # 单次 OCR 测试（截图并输出识别结果）
  python -m src.main --overlay    # 在游戏窗口上显示坐标标注
  python tools/coord_overlay.py   # 同上（独立工具）
  python tools/region_picker.py   # 配置屏幕区域
"""

from __future__ import annotations

import argparse
import sys
import time

import keyboard

from src.auto_buyer import AutoBuyer
from src.config_loader import load_regions, load_watchlist
from src.market_scanner import MarketScanner
from src.paths import configure_tesseract, ensure_runtime_layout
from src.screen_capture import ScreenCapture
from src.utils.logger import setup_logger

logger = setup_logger()


class MarketBot:
    def __init__(self, dry_run: bool | None = None):
        self.watchlist = load_watchlist()
        self.regions = load_regions()

        if dry_run is not None:
            self.watchlist.settings.dry_run = dry_run

        self.capture = ScreenCapture(self.regions.window_title)
        self.scanner = MarketScanner(self.watchlist, self.regions, self.capture)
        self.buyer = AutoBuyer(self.regions, self.watchlist.settings, self.capture)
        self._paused = False

    def run(self):
        settings = self.watchlist.settings
        enabled_items = [i for i in self.watchlist.items if i.enabled]

        logger.info("=" * 50)
        logger.info("darkMark 市场监控启动")
        logger.info(f"监控物品: {len(enabled_items)} 个")
        for item in enabled_items:
            logger.info(f"  - {item.name} (最高 {item.max_price} gold)")
        logger.info(f"刷新间隔: {settings.refresh_interval}s")
        logger.info(f"模式: {'试运行 (不购买)' if settings.dry_run else '自动购买'}")
        logger.info("热键: F9=暂停/继续  F10=停止")
        logger.info("=" * 50)

        if not self.scanner.start():
            return

        keyboard.add_hotkey("f9", self._toggle_pause)
        keyboard.add_hotkey("f10", self._stop)

        scan_count = 0
        try:
            while self.scanner.is_running:
                if self._paused:
                    time.sleep(0.5)
                    continue

                scan_count += 1
                logger.debug(f"--- 第 {scan_count} 次扫描 ---")

                self.buyer.refresh_market()
                time.sleep(0.5)

                listings = self.scanner.scan_market()
                if listings:
                    logger.info(f"检测到 {len(listings)} 个市场条目")
                    for listing in listings:
                        logger.debug(f"  {listing.name}: {listing.price} gold")

                alerts = self.scanner.check_alerts(listings)
                if alerts:
                    logger.info(f"发现 {len(alerts)} 个低价物品!")
                    for alert in alerts:
                        logger.info(
                            f"  ★ {alert.watch_item.name}: "
                            f"{alert.listing.price} <= {alert.watch_item.max_price} "
                            f"(省 {alert.savings})"
                        )
                    self.buyer.buy_all(alerts)

                time.sleep(settings.refresh_interval)

        except KeyboardInterrupt:
            logger.info("用户中断")
        finally:
            keyboard.unhook_all_hotkeys()
            self.scanner.stop()
            logger.info(
                f"监控结束。共扫描 {scan_count} 次，"
                f"购买 {self.buyer.purchase_count} 次"
            )

    def _toggle_pause(self):
        self._paused = not self._paused
        state = "暂停" if self._paused else "继续"
        logger.info(f"监控已{state}")

    def _stop(self):
        logger.info("收到停止信号")
        self.scanner.stop()


def main():
    ensure_runtime_layout()
    configure_tesseract()

    parser = argparse.ArgumentParser(description="darkMark 游戏市场监控")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="试运行模式，只检测不购买",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="正式模式，启用自动购买",
    )
    parser.add_argument(
        "--test-click",
        action="store_true",
        help="测试刷新按钮点击（3秒后移动鼠标并点击一次）",
    )
    parser.add_argument(
        "--test-ocr",
        action="store_true",
        help="OCR 测试（3秒后截图，终端输出识别结果并保存到 logs/ocr_test/）",
    )
    parser.add_argument(
        "--overlay",
        action="store_true",
        help="在游戏窗口上方显示坐标标注（Esc 退出）",
    )
    args = parser.parse_args()

    if args.test_ocr:
        from src.ocr_test import run_ocr_test

        logger.info("OCR 测试模式：3 秒后截图")
        logger.info("请保持游戏在市场界面，截图后终端会输出识别结果")
        ok = run_ocr_test(load_regions(), load_watchlist())
        sys.exit(0 if ok else 1)

    if args.overlay:
        logger.info("3 秒后在游戏窗口上方显示坐标标注")
        logger.info("Ctrl+E 切换显示/编辑 | 编辑模式下 Ctrl+S 保存 | Esc 退出")
        time.sleep(3)
        from src.coord_overlay import run_overlay

        run_overlay(load_regions())
        return

    dry_run = True
    if args.live:
        dry_run = False
    elif args.dry_run:
        dry_run = True

    bot = MarketBot(dry_run=dry_run)

    if args.test_click:
        logger.info(
            "3 秒后将测试点击刷新按钮。"
            "请保持游戏在市场界面，但不要切到游戏窗口（留在终端即可）。"
        )
        time.sleep(3)
        bot.buyer.test_refresh_click()
        return

    bot.run()


if __name__ == "__main__":
    main()
