"""模板图像匹配模块"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
from PIL import Image


class TemplateMatcher:
    def __init__(self, confidence: float = 0.8):
        self.confidence = confidence

    def find_template(
        self,
        screen: Image.Image,
        template_path: str | Path,
    ) -> list[tuple[int, int, float]]:
        """在屏幕截图中查找模板，返回 [(x, y, confidence), ...]"""
        template_path = Path(template_path)
        if not template_path.exists():
            return []

        screen_cv = np.array(screen)[:, :, ::-1]
        template = cv2.imread(str(template_path))
        if template is None:
            return []

        result = cv2.matchTemplate(screen_cv, template, cv2.TM_CCOEFF_NORMED)
        locations = np.where(result >= self.confidence)

        h, w = template.shape[:2]
        matches = []
        for pt in zip(*locations[::-1]):
            conf = result[pt[1], pt[0]]
            # 取模板中心点
            cx = pt[0] + w // 2
            cy = pt[1] + h // 2
            matches.append((cx, cy, float(conf)))

        # 非极大值抑制：去除重叠匹配
        return self._nms(matches, w, h)

    @staticmethod
    def _nms(
        matches: list[tuple[int, int, float]],
        template_w: int,
        template_h: int,
        overlap_thresh: float = 0.5,
    ) -> list[tuple[int, int, float]]:
        if not matches:
            return []

        matches.sort(key=lambda m: m[2], reverse=True)
        kept: list[tuple[int, int, float]] = []

        for mx, my, conf in matches:
            dominated = False
            for kx, ky, _ in kept:
                dx = abs(mx - kx)
                dy = abs(my - ky)
                if dx < template_w * overlap_thresh and dy < template_h * overlap_thresh:
                    dominated = True
                    break
            if not dominated:
                kept.append((mx, my, conf))

        return kept
