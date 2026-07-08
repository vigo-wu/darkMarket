"""OCR 文字识别模块"""

from __future__ import annotations

import re

import cv2
import numpy as np
import pytesseract
from PIL import Image

from src.config_loader import OcrConfig


class OcrEngine:
    def __init__(self, config: OcrConfig):
        self.config = config

    def preprocess(self, image: Image.Image) -> np.ndarray:
        """预处理图像以提高 OCR 准确率"""
        img = np.array(image)
        gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)

        # 放大图像
        scale = 2
        gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)

        # 二值化
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        return binary

    def read_text(self, image: Image.Image) -> str:
        processed = self.preprocess(image)
        config_str = f"--psm {self.config.psm}"
        if self.config.whitelist:
            config_str += f" -c tessedit_char_whitelist={self.config.whitelist}"

        text = pytesseract.image_to_string(
            processed,
            lang=self.config.lang,
            config=config_str,
        )
        return text.strip()

    def read_lines(self, image: Image.Image) -> list[str]:
        text = self.read_text(image)
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        return lines

    def read_data_with_boxes(self, image: Image.Image) -> list[dict]:
        """返回带位置信息的 OCR 结果"""
        processed = self.preprocess(image)
        config_str = f"--psm {self.config.psm}"
        if self.config.whitelist:
            config_str += f" -c tessedit_char_whitelist={self.config.whitelist}"

        data = pytesseract.image_to_data(
            processed,
            lang=self.config.lang,
            config=config_str,
            output_type=pytesseract.Output.DICT,
        )

        results = []
        n = len(data["text"])
        for i in range(n):
            text = data["text"][i].strip()
            if text and int(data["conf"][i]) > 30:
                results.append({
                    "text": text,
                    "x": data["left"][i] // 2,  # 还原缩放
                    "y": data["top"][i] // 2,
                    "w": data["width"][i] // 2,
                    "h": data["height"][i] // 2,
                    "conf": data["conf"][i],
                })
        return results
