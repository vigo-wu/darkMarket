"""价格解析模块"""

from __future__ import annotations

import re
from difflib import SequenceMatcher


def parse_price(text: str) -> int | None:
    """从文本中提取金币价格"""
    # 移除常见干扰字符
    cleaned = text.replace(",", "").replace(" ", "")

    patterns = [
        r"(\d+)\s*(?:gold|G|g|金币)",
        r"(?:gold|G|g|金币)\s*[:：]?\s*(\d+)",
        r"^(\d+)$",
        r"(\d{2,})",
    ]

    for pattern in patterns:
        match = re.search(pattern, cleaned, re.IGNORECASE)
        if match:
            return int(match.group(1))
    return None


def fuzzy_match(name: str, target: str, threshold: float = 0.7) -> bool:
    """模糊匹配物品名称"""
    name_lower = name.lower().strip()
    target_lower = target.lower().strip()

    if name_lower in target_lower or target_lower in name_lower:
        return True

    ratio = SequenceMatcher(None, name_lower, target_lower).ratio()
    return ratio >= threshold


def extract_item_price_pairs(lines: list[str]) -> list[tuple[str, int | None]]:
    """从 OCR 行文本中提取 (物品名, 价格) 对"""
    pairs: list[tuple[str, int | None]] = []

    for line in lines:
        price = parse_price(line)
        if price is not None:
            # 尝试分离名称和价格部分
            name_part = re.sub(r"[\d,.\s]+(?:gold|G|g|金币)?", "", line, flags=re.IGNORECASE).strip()
            if not name_part:
                name_part = line
            pairs.append((name_part, price))
        else:
            pairs.append((line, None))

    return pairs
