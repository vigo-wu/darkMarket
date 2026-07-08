"""市场扫描模块 - 检测物品价格变化"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from src.config_loader import RegionsConfig, WatchItem, WatchlistConfig, scale_region, scale_value
from src.ocr_engine import OcrEngine
from src.price_parser import extract_item_price_pairs, fuzzy_match, parse_price
from src.screen_capture import ScreenCapture
from src.template_matcher import TemplateMatcher
from src.utils.logger import setup_logger

logger = setup_logger()


@dataclass
class MarketListing:
    name: str
    price: int
    row_index: int = 0
    detected_at: datetime = field(default_factory=datetime.now)
    match_source: str = "ocr"  # "ocr" | "template"


@dataclass
class PriceAlert:
    watch_item: WatchItem
    listing: MarketListing
    savings: int  # max_price - actual_price


class MarketScanner:
    def __init__(
        self,
        watchlist: WatchlistConfig,
        regions: RegionsConfig,
        capture: ScreenCapture | None = None,
    ):
        self.watchlist = watchlist
        self.regions = regions
        self.capture = capture or ScreenCapture(regions.window_title)
        self.ocr = OcrEngine(regions.ocr)
        self.matcher = TemplateMatcher()
        self._price_history: dict[str, list[tuple[int, datetime]]] = {}
        self._running = False

    def start(self) -> bool:
        window = self.capture.refresh_window()
        if self.regions.window_title and not window:
            logger.error(f"未找到游戏窗口: {self.regions.window_title}")
            return False
        if window:
            mode = "全屏" if window.is_fullscreen else "窗口"
            logger.info(
                f"已定位游戏窗口: {window.title} ({window.width}x{window.height}) "
                f"[{mode}] @ ({window.left}, {window.top})"
            )
            ref = self.regions.reference_resolution
            if ref:
                if ref.width != window.width or ref.height != window.height:
                    logger.info(
                        f"坐标缩放: 参考 {ref.width}x{ref.height} -> "
                        f"当前 {window.width}x{window.height}"
                    )
            else:
                logger.warning(
                    "未设置 reference_resolution，请运行 "
                    "python tools/region_picker.py 重新校准坐标"
                )
        self._running = True
        return True

    def stop(self):
        self._running = False

    @property
    def is_running(self) -> bool:
        return self._running

    def scan_market(self) -> list[MarketListing]:
        """扫描市场列表区域，返回检测到的物品"""
        r = scale_region(
            self.regions.market_list,
            self.regions.reference_resolution,
            self.capture.window_size,
        )
        row_height = scale_value(
            self.regions.row_height,
            self.regions.reference_resolution,
            self.capture.window_size,
            axis="y",
        )
        image = self.capture.capture_region(r.left, r.top, r.width, r.height)

        listings: list[MarketListing] = []

        # OCR 扫描
        lines = self.ocr.read_lines(image)
        pairs = extract_item_price_pairs(lines)

        for idx, (name, price) in enumerate(pairs):
            if price is not None:
                listings.append(MarketListing(name=name, price=price, row_index=idx))

        # 模板匹配补充
        for item in self.watchlist.items:
            if not item.enabled or not item.template:
                continue
            matches = self.matcher.find_template(image, item.template)
            for mx, my, conf in matches:
                # 在模板附近区域 OCR 读取价格
                price_region = self._extract_price_near(image, mx, my)
                price = parse_price(price_region) if price_region else None
                if price is not None:
                    row_idx = my // row_height
                    listings.append(
                        MarketListing(
                            name=item.name,
                            price=price,
                            row_index=row_idx,
                            match_source="template",
                        )
                    )

        self._update_price_history(listings)
        return listings

    def _extract_price_near(self, image, x: int, y: int) -> str:
        """在模板匹配位置附近截取价格区域进行 OCR"""
        w, h = image.size
        # 假设价格在图标右侧
        left = min(x + 30, w - 100)
        top = max(y - 15, 0)
        crop = image.crop((left, top, min(left + 120, w), min(top + 30, h)))
        return self.ocr.read_text(crop)

    def _update_price_history(self, listings: list[MarketListing]):
        now = datetime.now()
        for listing in listings:
            key = listing.name
            if key not in self._price_history:
                self._price_history[key] = []
            history = self._price_history[key]
            if not history or history[-1][0] != listing.price:
                history.append((listing.price, now))
                logger.info(f"价格变化: {listing.name} -> {listing.price} gold")
            # 保留最近 100 条记录
            if len(history) > 100:
                self._price_history[key] = history[-100:]

    def check_alerts(self, listings: list[MarketListing]) -> list[PriceAlert]:
        """检查是否有物品价格低于设定阈值"""
        alerts: list[PriceAlert] = []
        settings = self.watchlist.settings

        for watch_item in self.watchlist.items:
            if not watch_item.enabled:
                continue

            for listing in listings:
                if not fuzzy_match(watch_item.name, listing.name, settings.fuzzy_match_threshold):
                    continue

                effective_max = watch_item.max_price + settings.price_tolerance
                if listing.price <= effective_max:
                    alerts.append(
                        PriceAlert(
                            watch_item=watch_item,
                            listing=listing,
                            savings=effective_max - listing.price,
                        )
                    )

        return alerts

    def get_price_history(self, item_name: str) -> list[tuple[int, datetime]]:
        return self._price_history.get(item_name, [])
