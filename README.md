# darkMark - PC 游戏市场自动监控与购买

基于 OCR + 屏幕自动化的 PC 客户端游戏市场监控脚本。实时刷新市场、检测价格变化，当物品价格低于设定阈值时自动购买。

> **适用场景**: Dark and Darker 等具有游戏内市场的 PC 客户端游戏。通过配置屏幕区域和监控列表即可适配不同游戏 UI。

## 功能

- 实时刷新市场列表
- OCR 识别物品名称与价格
- 单次 OCR 测试（`--test-ocr`），截图并输出识别结果
- 可选模板图像匹配（比纯 OCR 更可靠）
- 坐标叠加层（`--overlay`），可视化校验屏幕区域
- 价格变化追踪与日志记录
- 低价自动购买（可切换试运行模式）
- 热键控制：F9 暂停/继续，F10 停止
- PyAutoGUI failsafe：鼠标移到屏幕左上角紧急停止
- 支持打包为 Windows 可执行程序（无需安装 Python）

## 环境要求

- Windows 10/11
- Python 3.10+（源码运行）或直接使用打包后的 exe
- [Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki)（需安装并加入 PATH，或放到 exe 同目录 `tesseract/` 下）
  - 中文识别需下载 `chi_sim` 语言包

## 安装

```bash
cd D:\vigo\darkMark
pip install -r requirements.txt
```

验证 Tesseract：

```bash
tesseract --version
tesseract --list-langs   # 应包含 chi_sim
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

将输出复制到 `config/regions.yaml`，或通过配置页面保存。

也可使用坐标叠加层校验区域是否准确：

```bash
python -m src.main --overlay
```

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

### 3. 验证 OCR 识别

正式监控前，建议先运行 OCR 测试，对照游戏画面确认识别是否准确：

```bash
python -m src.main --test-ocr
```

程序会在 3 秒后截取市场列表区域，并在终端输出：

- OCR 配置（lang / psm / whitelist）
- 原始识别文本与逐行结果
- 解析出的「物品名 → 价格」
- 与监控列表的匹配情况

同时会在 `logs/ocr_test/` 保存三张图片：

| 文件 | 说明 |
|------|------|
| `*_capture.png` | 原始截图 |
| `*_preprocessed.png` | OCR 预处理图（二值化） |
| `*_annotated.png` | 带识别框标注的图 |

对照 `capture.png` 与游戏画面，检查区域是否正确；对照终端输出，检查名称与价格是否一致。

### 4. 启动监控

```bash
# 试运行（只检测，不购买）
python -m src.main --dry-run

# 正式运行（自动购买）
python -m src.main --live
```

## 命令参考

| 命令 | 说明 |
|------|------|
| `python -m src.main` | 启动监控（默认试运行） |
| `python -m src.main --dry-run` | 试运行，只检测不购买 |
| `python -m src.main --live` | 正式模式，启用自动购买 |
| `python -m src.main --test-ocr` | 单次 OCR 测试 |
| `python -m src.main --overlay` | 在游戏窗口上显示坐标标注 |
| `python -m src.main --test-click` | 测试刷新按钮点击 |
| `python tools/region_picker.py` | 屏幕区域选取工具 |
| `python tools/config_ui.py` | 可视化配置页面 |
| `python tools/coord_overlay.py` | 坐标叠加层（同 `--overlay`） |

## 打包为可执行程序

无需安装 Python 时，可打包为 Windows exe：

```powershell
.\build.ps1
```

或手动执行：

```powershell
pip install -r requirements-build.txt
python -m PyInstaller darkmark.spec --noconfirm
```

输出目录：`dist/darkMark/`

| 文件 | 说明 |
|------|------|
| `darkMark.exe` | 市场监控 |
| `darkMark-config.exe` | 可视化配置页面 |
| `darkMark-picker.exe` | 屏幕区域选取工具 |

将整个 `dist/darkMark` 文件夹复制到其他电脑即可使用。首次运行会在 exe 旁自动创建 `config/`、`logs/`、`assets/` 目录。

打包版命令示例：

```powershell
.\darkMark.exe --test-ocr
.\darkMark.exe --dry-run
.\darkMark-config.exe
```

## 项目结构

```
darkMark/
├── config/
│   ├── watchlist.yaml      # 监控物品与阈值
│   └── regions.yaml        # 屏幕区域坐标
├── src/
│   ├── main.py             # 入口
│   ├── market_scanner.py   # 市场扫描
│   ├── auto_buyer.py       # 自动购买
│   ├── ocr_engine.py       # OCR 识别
│   ├── ocr_test.py         # OCR 单次测试
│   ├── screen_capture.py   # 屏幕捕获
│   ├── price_parser.py     # 价格解析
│   ├── template_matcher.py
│   └── paths.py            # 路径解析（开发/打包通用）
├── tools/
│   ├── region_picker.py    # 区域选取工具
│   ├── config_ui.py        # 可视化配置页面
│   └── static/             # 配置页面静态资源
├── assets/templates/       # 物品图标模板（可选）
├── logs/                   # 运行日志
│   └── ocr_test/           # OCR 测试截图
├── darkmark.spec           # PyInstaller 打包配置
└── build.ps1               # 一键打包脚本
```

## 高级：OCR 调优

编辑 `config/regions.yaml` 中的 `ocr` 段：

```yaml
ocr:
  lang: chi_sim+eng    # 中文物品名需要 chi_sim
  psm: 6               # 6=整块文本；单行可试 7 或 8
  whitelist: ""        # 验证名称识别时建议留空
```

**注意**：若 `whitelist` 仅包含数字和英文字符，Tesseract 将无法识别中文物品名。需要识别中文时请留空；若只需优化价格识别，可配合模板匹配（见下文）。

常见 OCR 问题排查：

| 现象 | 可能原因 | 处理方式 |
|------|----------|----------|
| 识别结果为空 | 截图区域不对 | 用 `--overlay` 或 `--test-ocr` 检查 `capture.png` |
| 中文名称乱码/缺失 | whitelist 过滤或缺少语言包 | 清空 whitelist，确认已安装 `chi_sim` |
| 价格数字错误 | 区域过大或 psm 不合适 | 缩小 `market_list` 区域，调整 `psm` |
| 名称匹配不上 | 与监控列表差异大 | 调低 `fuzzy_match_threshold`，或使用模板匹配 |

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
2. **首次使用**: 务必先用 `--test-ocr` 和 `--dry-run` 验证检测准确性
3. **分辨率**: 更换分辨率或 UI 缩放后需重新配置区域
4. **Tesseract**: 确保 `tesseract --version` 可正常运行
5. **管理员权限**: 热键（F9/F10）在部分环境下可能需要以管理员身份运行

## 热键

| 按键 | 功能 |
|------|------|
| F9 | 暂停/继续监控 |
| F10 | 停止并退出 |
| 鼠标移到左上角 | PyAutoGUI 紧急停止 |

坐标叠加层（`--overlay`）额外热键：

| 按键 | 功能 |
|------|------|
| Ctrl+E | 切换显示/编辑模式 |
| Ctrl+S | 编辑模式下保存配置 |
| Esc | 退出 |

## License

MIT
