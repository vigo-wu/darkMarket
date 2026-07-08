"""
坐标标注 Overlay — 在游戏窗口上方实时显示配置坐标

用法:
  python tools/coord_overlay.py

说明:
  - 绿色矩形: market_list (OCR 区域)
  - 红色十字: refresh_button
  - 蓝色十字: 各行 buy_button
  - 黄色十字: trade_dialog 按钮
  - 白色虚线: 游戏客户区边界
  - 鼠标点击穿透，不影响游戏操作
  - Ctrl+E 切换 显示/编辑 模式
  - 编辑模式：拖拽标注，Ctrl+S 保存到 config/regions.yaml
  - Esc 退出
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.coord_overlay import run_overlay


def main() -> None:
    print("=" * 50)
    print("darkMark 坐标标注 Overlay")
    print("=" * 50)
    print()
    print("请打开游戏市场界面")
    print("3 秒后在游戏窗口上方显示标注层")
    print("Ctrl+E 切换显示/编辑  |  编辑模式下 Ctrl+S 保存  |  Esc 退出")
    print()
    time.sleep(3)
    run_overlay()


if __name__ == "__main__":
    main()
