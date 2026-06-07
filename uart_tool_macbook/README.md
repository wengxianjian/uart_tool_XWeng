# 串口调试工具（macOS）

基于 PyQt6 + pyserial 的串口调试工具，由 Windows 版复刻并适配 macOS。中文界面、暗色主题，主要配合 **CH340** USB 转串口芯片使用。

## 功能

- 串口连接 / 断开 / 配置（端口、波特率、数据位、校验位、停止位、流控；支持自定义波特率）
- ASCII / HEX 数据收发，可选时间戳、自动滚动、暂停显示
- 循环定时发送、发送换行符可选（`\r\n` / `\n` / `\r` / 无）
- 接收区搜索（⌘F）+ 上一个/下一个，常驻关键词高亮
- 全屏日志模式（F11）
- ⌘+滚轮调整字体大小
- 日志保存（⌘S）
- 串口配置 / 高亮规则 / 窗口尺寸自动记忆

## 运行

```bash
# 首次安装依赖（需要 Homebrew 的 python@3.12）
/opt/homebrew/bin/python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt

# 运行
.venv/bin/python main.py
```

## 打包为 .app

```bash
.venv/bin/pip install pyinstaller
.venv/bin/python create_icon.py        # 生成 app_icon.icns / app_icon.png
.venv/bin/pyinstaller uart_tool.spec    # 产物：dist/串口调试工具.app
```

把 `dist/串口调试工具.app` 拖入「应用程序」即可使用。首次打开若提示「未受信任的开发者」，
在「系统设置 → 隐私与安全性」中点「仍要打开」即可（自用未签名应用属正常）。

## CH340 说明

- macOS Big Sur（11）及以上已内置 CH34x 驱动，插上 CH340 后通常无需安装驱动。
- 设备在端口下拉中显示为 `/dev/cu.wchusbserial*`（程序已自动过滤蓝牙等无关串口）。
- 若插入后下拉里看不到设备，点「刷新」重新扫描；仍无则检查数据线/驱动。
