# darkMark - PC 游戏市场自动监控与购买

基于 OCR + 屏幕自动化的 PC 客户端游戏市场监控脚本。实时刷新市场、检测价格变化，当物品价格低于设定阈值时自动购买。

> **适用场景**: Dark and Darker 等具有游戏内市场的 PC 客户端游戏。通过配置屏幕区域和监控列表即可适配不同游戏 UI。

## 功能

- 实时刷新市场列表
- OCR 识别物品名称与价格
- 可选模板图像匹配（比纯 OCR 更可靠）
- 价格变化追踪与日志记录
- 低价自动购买（可切换试运行模式）
- 热键控制：F9 暂停/继续，F10 停止
- PyAutoGUI  failsafe：鼠标移到屏幕左上角紧急停止

## 环境要求

- Windows 10/11
- Python 3.10+
- [Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki)（需安装并加入 PATH）
  - 中文识别需下载 `chi_sim` 语言包

## 安装

```bash
cd D:\vigo\darkMark
pip install -r requirements.txt
```

## 快速开始

### 1. 配置屏幕区域

打开游戏并进入市场界面，运行区域选取工具：

```bash
python tools/region_picker.py
```

按提示依次选取：
- 市场列表区域
- 刷新按钮位置
- 购买按钮位置
- 确认对话框按钮位置

将输出复制到 `config/regions.yaml`。

### 2. 配置监控物品

**方式 A：可视化配置页面（推荐）**

```bash
python tools/config_ui.py
```

浏览器会自动打开配置中心，可编辑监控物品、全局设置和屏幕区域，点击「保存配置」写入 `config/` 目录。

**方式 B：手动编辑 YAML**

编辑 `config/watchlist.yaml`：

```yaml
items:
  - name: "红宝石戒指"
    max_price: 500
    enabled: true

settings:
  refresh_interval: 2.0
  dry_run: true    # 首次使用建议保持 true
```

### 3. 启动监控

```bash
# 试运行（只检测，不购买）
python -m src.main --dry-run

# 正式运行（自动购买）
python -m src.main --live
```

## 项目结构

```
darkMark/
├── config/
│   ├── watchlist.yaml    # 监控物品与阈值
│   └── regions.yaml      # 屏幕区域坐标
├── src/
│   ├── main.py           # 入口
│   ├── market_scanner.py # 市场扫描
│   ├── auto_buyer.py     # 自动购买
│   ├── ocr_engine.py     # OCR 识别
│   ├── screen_capture.py # 屏幕捕获
│   ├── price_parser.py   # 价格解析
│   └── template_matcher.py
├── tools/
│   ├── region_picker.py  # 区域选取工具
│   ├── config_ui.py      # 可视化配置页面
│   └── static/           # 配置页面静态资源
├── assets/templates/     # 物品图标模板（可选）
└── logs/                 # 运行日志
```

## 高级：模板匹配

若 OCR 识别不准，可截取物品图标作为模板：

1. 游戏中 Win+Shift+S 截取物品图标
2. 保存到 `assets/templates/xxx.png`
3. 在 watchlist 中配置：

```yaml
- name: "红宝石戒指"
  max_price: 500
  template: "assets/templates/ruby_ring.png"
  enabled: true
```

## 注意事项

1. **账号风险**: 自动化操作可能违反游戏 ToS，存在封号风险，请自行评估
2. **首次使用**: 务必先用 `--dry-run` 验证检测准确性
3. **分辨率**: 更换分辨率或 UI 缩放后需重新配置区域
4. **Tesseract**: 确保 `tesseract --version` 可正常运行

## 热键

| 按键 | 功能 |
|------|------|
| F9 | 暂停/继续监控 |
| F10 | 停止并退出 |
| 鼠标移到左上角 | PyAutoGUI 紧急停止 |

## License

MIT
