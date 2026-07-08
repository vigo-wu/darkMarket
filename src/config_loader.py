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
class Resolution:
    width: int
    height: int


@dataclass
class RegionsConfig:
    window_title: str
    market_list: Region
    refresh_button: Point
    buy_button: Point
    trade_dialog: dict[str, Point]
    row_height: int
    ocr: OcrConfig
    reference_resolution: Resolution | None = None


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


def scale_point(
    x: int,
    y: int,
    reference: Resolution | None,
    window_size: tuple[int, int] | None,
) -> tuple[int, int]:
    if not reference or not window_size:
        return x, y
    sx = window_size[0] / reference.width
    sy = window_size[1] / reference.height
    return int(x * sx), int(y * sy)


def scale_region(
    region: Region,
    reference: Resolution | None,
    window_size: tuple[int, int] | None,
) -> Region:
    if not reference or not window_size:
        return region
    sx = window_size[0] / reference.width
    sy = window_size[1] / reference.height
    return Region(
        int(region.left * sx),
        int(region.top * sy),
        int(region.width * sx),
        int(region.height * sy),
    )


def scale_value(
    value: int,
    reference: Resolution | None,
    window_size: tuple[int, int] | None,
    axis: str = "y",
) -> int:
    if not reference or not window_size:
        return value
    ratio = window_size[0] / reference.width if axis == "x" else window_size[1] / reference.height
    return int(value * ratio)


def _load_trade_dialog(data: dict[str, Any]) -> dict[str, Point]:
    if "trade_dialog" in data:
        td = data["trade_dialog"]
        return {
            "submit_button": Point(td["submit_button"]["x"], td["submit_button"]["y"]),
            "complete_button": Point(td["complete_button"]["x"], td["complete_button"]["y"]),
        }
    cd = data["confirm_dialog"]
    confirm = Point(cd["confirm_button"]["x"], cd["confirm_button"]["y"])
    return {
        "submit_button": confirm,
        "complete_button": confirm,
    }


def _load_reference_resolution(data: dict[str, Any]) -> Resolution | None:
    ref = data.get("reference_resolution")
    if not ref:
        return None
    return Resolution(int(ref["width"]), int(ref["height"]))


def load_regions(path: Path | None = None) -> RegionsConfig:
    path = path or CONFIG_DIR / "regions.yaml"
    data = _load_yaml(path)

    ml = data["market_list"]
    rb = data["refresh_button"]
    bb = data["buy_button"]
    ocr = data.get("ocr", {})

    return RegionsConfig(
        window_title=data.get("window_title", ""),
        market_list=Region(ml["left"], ml["top"], ml["width"], ml["height"]),
        refresh_button=Point(rb["x"], rb["y"]),
        buy_button=Point(bb["x"], bb["y"]),
        trade_dialog=_load_trade_dialog(data),
        row_height=int(data.get("row_height", 40)),
        ocr=OcrConfig(
            lang=ocr.get("lang", "chi_sim+eng"),
            psm=int(ocr.get("psm", 6)),
            whitelist=ocr.get("whitelist", ""),
        ),
        reference_resolution=_load_reference_resolution(data),
    )


def watchlist_to_dict(config: WatchlistConfig) -> dict[str, Any]:
    return {
        "items": [
            {
                "name": item.name,
                "max_price": item.max_price,
                "enabled": item.enabled,
                **({"template": item.template} if item.template else {}),
            }
            for item in config.items
        ],
        "settings": {
            "refresh_interval": config.settings.refresh_interval,
            "click_delay": config.settings.click_delay,
            "dry_run": config.settings.dry_run,
            "fuzzy_match_threshold": config.settings.fuzzy_match_threshold,
            "price_tolerance": config.settings.price_tolerance,
        },
    }


def watchlist_from_dict(data: dict[str, Any]) -> WatchlistConfig:
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


def regions_to_dict(config: RegionsConfig) -> dict[str, Any]:
    return {
        "window_title": config.window_title,
        "market_list": {
            "left": config.market_list.left,
            "top": config.market_list.top,
            "width": config.market_list.width,
            "height": config.market_list.height,
        },
        "refresh_button": {
            "x": config.refresh_button.x,
            "y": config.refresh_button.y,
        },
        "buy_button": {
            "x": config.buy_button.x,
            "y": config.buy_button.y,
        },
        "trade_dialog": {
            "submit_button": {
                "x": config.trade_dialog["submit_button"].x,
                "y": config.trade_dialog["submit_button"].y,
            },
            "complete_button": {
                "x": config.trade_dialog["complete_button"].x,
                "y": config.trade_dialog["complete_button"].y,
            },
        },
        "row_height": config.row_height,
        **(
            {
                "reference_resolution": {
                    "width": config.reference_resolution.width,
                    "height": config.reference_resolution.height,
                }
            }
            if config.reference_resolution
            else {}
        ),
        "ocr": {
            "lang": config.ocr.lang,
            "psm": config.ocr.psm,
            "whitelist": config.ocr.whitelist,
        },
    }


def regions_from_dict(data: dict[str, Any]) -> RegionsConfig:
    ml = data["market_list"]
    rb = data["refresh_button"]
    bb = data["buy_button"]
    ocr = data.get("ocr", {})
    return RegionsConfig(
        window_title=data.get("window_title", ""),
        market_list=Region(ml["left"], ml["top"], ml["width"], ml["height"]),
        refresh_button=Point(rb["x"], rb["y"]),
        buy_button=Point(bb["x"], bb["y"]),
        trade_dialog=_load_trade_dialog(data),
        row_height=int(data.get("row_height", 40)),
        ocr=OcrConfig(
            lang=ocr.get("lang", "chi_sim+eng"),
            psm=int(ocr.get("psm", 6)),
            whitelist=ocr.get("whitelist", ""),
        ),
        reference_resolution=_load_reference_resolution(data),
    )


def _save_yaml(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(
            data,
            f,
            allow_unicode=True,
            default_flow_style=False,
            sort_keys=False,
        )


def save_watchlist(config: WatchlistConfig, path: Path | None = None) -> None:
    path = path or CONFIG_DIR / "watchlist.yaml"
    _save_yaml(path, watchlist_to_dict(config))


def save_regions(config: RegionsConfig, path: Path | None = None) -> None:
    path = path or CONFIG_DIR / "regions.yaml"
    _save_yaml(path, regions_to_dict(config))
