"""自动购买模块"""

from __future__ import annotations

import time

from src.config_loader import RegionsConfig, Settings, scale_point
from src.market_scanner import MarketListing, PriceAlert
from src.mouse_input import game_click
from src.screen_capture import ScreenCapture
from src.utils.logger import setup_logger

logger = setup_logger()


class AutoBuyer:
    def __init__(
        self,
        regions: RegionsConfig,
        settings: Settings,
        capture: ScreenCapture | None = None,
    ):
        self.regions = regions
        self.settings = settings
        self.capture = capture or ScreenCapture(regions.window_title)
        self._purchase_count = 0

    def _scale_point(self, x: int, y: int) -> tuple[int, int]:
        return scale_point(
            x,
            y,
            self.regions.reference_resolution,
            self.capture.window_size,
        )

    def _screen_point(self, x: int, y: int) -> tuple[int, int]:
        if self.regions.window_title:
            self.capture.refresh_window()
        x, y = self._scale_point(x, y)
        ox, oy = self.capture.offset
        return x + ox, y + oy

    def _click_point(self, x: int, y: int, label: str):
        hwnd = 0
        client_x = None
        client_y = None
        if self.capture.window_info:
            hwnd = self.capture.window_info.hwnd
            ox, oy = self.capture.offset
            client_x, client_y = x - ox, y - oy
        try:
            game_click(x, y, hwnd=hwnd, client_x=client_x, client_y=client_y)
            logger.info(f"已点击{label} ({x}, {y})")
        except OSError as exc:
            logger.error(f"点击{label}失败 ({x}, {y}): {exc}")
            raise
        time.sleep(self.settings.click_delay)

    def test_refresh_click(self):
        """测试刷新按钮点击（用于排查鼠标不移动问题）"""
        if not self.capture.refresh_window():
            raise RuntimeError(f"未找到游戏窗口: {self.regions.window_title}")
        w = self.capture.window_info
        mode = "全屏" if w and w.is_fullscreen else "窗口"
        if w:
            logger.info(
                f"游戏窗口: {w.width}x{w.height} [{mode}] "
                f"客户区原点屏幕坐标 ({w.left}, {w.top})"
            )
        x, y = self._screen_point(
            self.regions.refresh_button.x,
            self.regions.refresh_button.y,
        )
        cx, cy = self._scale_point(
            self.regions.refresh_button.x,
            self.regions.refresh_button.y,
        )
        logger.info(
            f"测试点击刷新按钮 -> 屏幕 ({x}, {y})  客户区 ({cx}, {cy})"
        )
        self._click_point(x, y, "刷新(测试)")

    @property
    def purchase_count(self) -> int:
        return self._purchase_count

    def refresh_market(self):
        """点击刷新按钮"""
        x, y = self._screen_point(
            self.regions.refresh_button.x,
            self.regions.refresh_button.y,
        )
        self._click_point(x, y, "刷新")

    def buy_item(self, alert: PriceAlert) -> bool:
        """购买指定物品"""
        listing = alert.listing
        watch = alert.watch_item

        if self.settings.dry_run:
            logger.warning(
                f"[试运行] 发现低价物品: {watch.name} "
                f"价格 {listing.price} <= {watch.max_price}，跳过购买"
            )
            return False

        ml = self.regions.market_list
        row_height = self.regions.row_height

        # 计算购买按钮坐标
        if self.regions.buy_button.y == 0:
            row_y = ml.top + listing.row_index * row_height + row_height // 2
            buy_x, buy_y = self._screen_point(ml.left + self.regions.buy_button.x, row_y)
        else:
            buy_x, buy_y = self._screen_point(
                self.regions.buy_button.x,
                self.regions.buy_button.y,
            )

        logger.info(
            f"正在购买: {watch.name} @ {listing.price} gold "
            f"(节省 {alert.savings}) -> 点击 ({buy_x}, {buy_y})"
        )

        self._click_point(buy_x, buy_y, "购买")
        time.sleep(self.settings.click_delay)

        submit = self.regions.trade_dialog["submit_button"]
        submit_x, submit_y = self._screen_point(submit.x, submit.y)
        self._click_point(submit_x, submit_y, "提交所需物品")

        complete = self.regions.trade_dialog["complete_button"]
        complete_x, complete_y = self._screen_point(complete.x, complete.y)
        self._click_point(complete_x, complete_y, "完成交易")

        self._purchase_count += 1
        logger.info(f"购买完成 #{self._purchase_count}: {watch.name} @ {listing.price}")
        return True

    def buy_all(self, alerts: list[PriceAlert]) -> int:
        """批量购买所有符合条件的物品，返回成功购买数"""
        bought = 0
        # 按价格从低到高排序，优先买最便宜的
        sorted_alerts = sorted(alerts, key=lambda a: a.listing.price)
        for alert in sorted_alerts:
            if self.buy_item(alert):
                bought += 1
                time.sleep(self.settings.click_delay * 2)
        return bought
