# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

基于 PyQt6 + pyserial 的串口调试工具（macOS 桌面应用）。由 Windows 版（见 `ref/`）复刻并做 macOS 适配，
代码与注释使用中文。主要配合 CH340 USB 转串口芯片使用，自用，不分发。

## 环境与常用命令

项目使用 Python 3.12 虚拟环境（`.venv/`，由 Homebrew `python@3.12` 创建）。

```bash
# 安装依赖（首次）
/opt/homebrew/bin/python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/pip install pyinstaller          # 打包用

# 运行
.venv/bin/python main.py

# 重新生成应用图标（覆盖 app_icon.png / app_icon.icns，用系统 iconutil）
.venv/bin/python create_icon.py

# 打包为 macOS 应用（产物在 dist/串口调试工具.app）
.venv/bin/pyinstaller uart_tool.spec
```

无单元测试框架，无 lint 配置。验证手段为：`.venv/bin/python main.py` 启动后手动操作，
或无头冒烟（`QT_QPA_PLATFORM=offscreen` 构造 MainWindow 验证不崩溃）。

## macOS 适配点（相对 Windows 版 `ref/`）

- 等宽字体 `Consolas` → `Menlo`（`theme.py` 字体族、`receive_panel.py` 接收区字体）。
- 退出快捷键 `Alt+F4` → `QKeySequence.StandardKey.Quit`（macOS 自动为 ⌘Q）；`Ctrl+S/L/F` 由 Qt 自动映射为 ⌘。
- `SerialManager.scan_ports()` 过滤蓝牙串口、优先列出 `/dev/cu.*`（CH340 为 `/dev/cu.wchusbserial*`）。
- 图标 `.ico` → `.icns`（`create_icon.py` 用 `iconutil` 生成）；`main._app_icon()` 优先找 `.icns` / `.png`。
- 打包用 `uart_tool.spec` 的 `BUNDLE` 段生成 `.app`（含 `Info.plist`、`NSHighResolutionCapable`）。
- CH340 驱动：macOS Big Sur（11）及以上已内置 CH34x 驱动，一般免装。

## 架构

应用为单进程事件驱动架构。`main.py` 创建 `QApplication`、应用暗色主题、构造 `MainWindow`。

**`MainWindow` 是唯一的协调中心**：UI 面板从不直接操作串口。各面板通过 `pyqtSignal` 把用户意图发出，
`MainWindow` 在 `_connect_signals()` 把信号接到自己的槽，再调用串口层。新增功能遵循此模式——面板发信号，
`MainWindow` 接信号并编排，不要让面板互相耦合或直接访问 `SerialManager`。

**串口的双层结构**：
- `SerialManager`（`serial_manager.py`）——同步封装 `serial.Serial`，负责 connect/disconnect/send 和端口扫描。`SerialConfig` 是配置 dataclass。
- `SerialWorker`（`serial_worker.py`）——`QThread` 子类，独立线程每 10ms 轮询 `in_waiting` 读数据，通过 `data_received(bytes)` 信号送回主线程。读串口必须在此线程，绝不能阻塞 GUI 线程。

**数据流（接收）**：`SerialWorker.data_received` → `MainWindow._on_data_received` → `ReceivePanel.append_data`（显示）+ `LogManager.write_raw`。`LogManager` 当前休眠（`write_raw` 已接入但 `start_auto_save()` 无 UI 开关，不落盘）；日志保存走 `ReceivePanel.save_log_dialog`（⌘S）。

**数据流（发送）**：`SendPanel.send_requested(bytes)` → `MainWindow._on_send` → `SerialManager.send`。

**断开连接的三个来源**统一汇入 `MainWindow._on_disconnect()`：用户点「关闭串口」、`SerialWorker` 检测异常、窗口关闭。

**循环发送**：`SendPanel` 内置 `QTimer`，勾选「循环发送」后按间隔反复 `_do_send()`；HEX 解析失败弹框并自动取消循环。

**显示模式**（`ReceivePanel.append_data`）：HEX 逐块成行；ASCII 用 `_byte_buffer` 累积、按 `\n` 切行。切换模式清空缓冲区。

**高亮**：`HighlightManager` 生成常驻关键词 `ExtraSelection`；`ReceivePanel._refresh_highlights()` 叠加：常驻 + 搜索全部 + 当前搜索项。

**持久化**：`AppSettings`（`settings.py`）通过 `QSettings`（组织 `DIY` / 应用 `UartTool`，macOS 上即 `~/Library/Preferences`）保存串口配置、高亮规则、窗口几何与分隔条状态，复杂对象以 JSON 字符串存入。

## 扩展指引

1. 在面板上定义 `pyqtSignal`，在 `MainWindow._connect_signals()` 接到槽——面板发信号，`MainWindow` 编排，面板之间零耦合。
2. 读串口逻辑放进 `SerialWorker` 线程；写串口走 `SerialManager`（主线程）。
3. 需要持久化的状态，加到 `AppSettings` 并在 `_restore_settings()` / `closeEvent()` 中读写。

## 注意事项

- `main.py` 的 `_app_icon()` 用 `sys._MEIPASS` 兼容 PyInstaller 打包后的资源路径；`uart_tool.spec` 的 `datas` 必须同步包含 `app_icon.png`。
- 自定义波特率：`ConfigPanel` 波特率下拉含「自定义...」项，选中弹输入框并把新值插入到列表末项之前。
- 全屏日志模式（F11）通过隐藏左侧面板、发送面板、接收区工具栏与底部 statusBar 实现，状态由 `MainWindow._log_focus_mode` 跟踪。进入全屏时 `ReceivePanel.set_toolbar_visible(False, ...)` 把暂停/清空按钮挪到搜索栏右侧，并把状态 label 插到搜索栏最左——一行同时承担工具栏 + 状态栏。
- `ref/` 是原 Windows 版参考实现，仅供对照，不参与运行/打包。
