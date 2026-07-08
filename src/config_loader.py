"""配置加载模块"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"


@dataclass
class WatchItem:
    name: str
    max_price: int
    enabled: bool = True
    template: str | None = None


@dataclass
class Settings:
    refresh_interval: float = 2.0
    click_delay: float = 0.3
    dry_run: bool = True
    fuzzy_match_threshold: float = 0.7
    price_tolerance: int = 0


@dataclass
class WatchlistConfig:
    items: list[WatchItem]
    settings: Settings


@dataclass
class Region:
    left: int
    top: int
    width: int
    height: int

    @property
    def as_tuple(self) -> tuple[int, int, int, int]:
        return (self.left, self.top, self.width, self.height)


@dataclass
class Point:
    x: int
    y: int


@dataclass
class OcrConfig:
    lang: str = "chi_sim+eng"
    psm: int = 6
    whitelist: str = ""


@dataclass
class RegionsConfig:
    window_title: str
    market_list: Region
    refresh_button: Point
    buy_button: Point
    confirm_dialog: dict[str, Point]
    row_height: int
    ocr: OcrConfig


def _load_yaml(path: Path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_watchlist(path: Path | None = None) -> WatchlistConfig:
    path = path or CONFIG_DIR / "watchlist.yaml"
    data = _load_yaml(path)

    items = [
        WatchItem(
            name=item["name"],
            max_price=int(item["max_price"]),
            enabled=item.get("enabled", True),
            template=item.get("template"),
        )
        for item in data.get("items", [])
    ]

    settings_data = data.get("settings", {})
    settings = Settings(
        refresh_interval=float(settings_data.get("refresh_interval", 2.0)),
        click_delay=float(settings_data.get("click_delay", 0.3)),
        dry_run=bool(settings_data.get("dry_run", True)),
        fuzzy_match_threshold=float(settings_data.get("fuzzy_match_threshold", 0.7)),
        price_tolerance=int(settings_data.get("price_tolerance", 0)),
    )

    return WatchlistConfig(items=items, settings=settings)


def load_regions(path: Path | None = None) -> RegionsConfig:
    path = path or CONFIG_DIR / "regions.yaml"
    data = _load_yaml(path)

    ml = data["market_list"]
    rb = data["refresh_button"]
    bb = data["buy_button"]
    cd = data["confirm_dialog"]
    ocr = data.get("ocr", {})

    return RegionsConfig(
        window_title=data.get("window_title", ""),
        market_list=Region(ml["left"], ml["top"], ml["width"], ml["height"]),
        refresh_button=Point(rb["x"], rb["y"]),
        buy_button=Point(bb["x"], bb["y"]),
        confirm_dialog={
            "confirm_button": Point(cd["confirm_button"]["x"], cd["confirm_button"]["y"]),
            "cancel_button": Point(cd["cancel_button"]["x"], cd["cancel_button"]["y"]),
        },
        row_height=int(data.get("row_height", 40)),
        ocr=OcrConfig(
            lang=ocr.get("lang", "chi_sim+eng"),
            psm=int(ocr.get("psm", 6)),
            whitelist=ocr.get("whitelist", ""),
        ),
    )
