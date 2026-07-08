"""自动购买模块"""

from __future__ import annotations

import time

import pyautogui

from src.config_loader import RegionsConfig, Settings
from src.market_scanner import MarketListing, PriceAlert
from src.screen_capture import ScreenCapture
from src.utils.logger import setup_logger

logger = setup_logger()

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.05


class AutoBuyer:
    def __init__(self, regions: RegionsConfig, settings: Settings):
        self.regions = regions
        self.settings = settings
        self.capture = ScreenCapture(regions.window_title)
        self._purchase_count = 0

    @property
    def purchase_count(self) -> int:
        return self._purchase_count

    def refresh_market(self):
        """点击刷新按钮"""
        ox, oy = self.capture.offset
        x = self.regions.refresh_button.x + ox
        y = self.regions.refresh_button.y + oy
        pyautogui.click(x, y)
        time.sleep(self.settings.click_delay)
        logger.debug(f"已点击刷新 ({x}, {y})")

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

        ox, oy = self.capture.offset
        ml = self.regions.market_list

        # 计算购买按钮坐标
        if self.regions.buy_button.y == 0:
            row_y = ml.top + listing.row_index * self.regions.row_height + self.regions.row_height // 2
            buy_x = ml.left + self.regions.buy_button.x + ox
            buy_y = row_y + oy
        else:
            buy_x = self.regions.buy_button.x + ox
            buy_y = self.regions.buy_button.y + oy

        logger.info(
            f"正在购买: {watch.name} @ {listing.price} gold "
            f"(节省 {alert.savings}) -> 点击 ({buy_x}, {buy_y})"
        )

        pyautogui.click(buy_x, buy_y)
        time.sleep(self.settings.click_delay)

        # 确认对话框
        confirm = self.regions.confirm_dialog["confirm_button"]
        pyautogui.click(confirm.x + ox, confirm.y + oy)
        time.sleep(self.settings.click_delay)

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
