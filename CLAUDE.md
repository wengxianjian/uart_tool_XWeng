# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

基于 PyQt6 + pyserial 的串口调试工具（GUI 桌面应用）。代码与注释使用中文。

## 常用命令

```bash
# 安装依赖
pip install -r requirements.txt

# 运行
python main.py

# 重新生成应用图标（修改后会覆盖 app_icon.png / app_icon.ico）
python create_icon.py

# 打包为单文件 exe（产物在 dist/uart_tool.exe）
pyinstaller uart_tool.spec

# 冒烟测试：启动打包后的 exe，验证 5 秒内不崩溃
python _smoke.py
```

无单元测试框架，无 lint 配置。`_smoke.py` 是唯一的自动化验证手段，且依赖已打包的 `dist/uart_tool.exe`。

## 架构

应用为单进程事件驱动架构。`main.py` 创建 `QApplication`、应用暗色主题、构造 `MainWindow`。

**`MainWindow` 是唯一的协调中心**：UI 面板从不直接操作串口。各面板通过 `pyqtSignal` 把用户意图发出，`MainWindow` 在 `_connect_signals()` 把信号接到自己的槽，再调用串口层。新增功能时遵循此模式——面板发信号，`MainWindow` 接信号并编排，不要让面板互相耦合或直接访问 `SerialManager`。

**串口的双层结构**：
- `SerialManager`（`serial_manager.py`）——同步封装 `serial.Serial`，负责 connect/disconnect/send 和端口扫描。`SerialConfig` 是配置 dataclass。
- `SerialWorker`（`serial_worker.py`）——`QThread` 子类，独立线程中每 10ms 轮询 `in_waiting` 读取数据，通过 `data_received(bytes)` 信号把数据送回主线程。读串口必须在此线程，绝不能阻塞 GUI 线程。

**数据流（接收）**：`SerialWorker.data_received` → `MainWindow._on_data_received` → `ReceivePanel.append_data`（显示）+ `LogManager.write_raw`。注意 `LogManager` 当前处于休眠状态——`write_raw` 已接入数据流，但 `start_auto_save()` / `save_text()` 从未被调用、也无 UI 开关，所以自动保存实际不会落盘。日志保存目前只走 `ReceivePanel.save_log_dialog`（Ctrl+S，直接写 `QTextEdit` 文本）。

**数据流（发送）**：`SendPanel.send_requested(bytes)` → `MainWindow._on_send` → `SerialManager.send`。

**断开连接的三个来源**，统一汇入 `MainWindow._on_disconnect()`：用户点击"关闭串口"、`SerialWorker` 检测到串口异常（`error_occurred` + `disconnected` 信号）、窗口关闭（`closeEvent`）。

**循环发送**：`SendPanel` 内置 `QTimer`（`_loop_timer`），勾选"循环发送"后按间隔反复调用 `_do_send()`；HEX 格式解析失败会弹 `QMessageBox` 并自动取消循环（`_loop_checkbox.setChecked(False)`）。

**显示模式差异**（`ReceivePanel.append_data`）：HEX 模式按数据块逐条输出；ASCII 模式用 `_byte_buffer` 累积字节、按 `\n` 切行后再输出——切换模式会清空该缓冲区。

**高亮机制**：`HighlightManager` 持有常驻关键词规则并生成 `QTextEdit.ExtraSelection`。`ReceivePanel._refresh_highlights()` 把三类选区叠加渲染：常驻高亮 + 搜索匹配 + 当前搜索项。每次追加新行都会重建高亮。

**持久化**：`AppSettings`（`settings.py`）通过 `QSettings` 存储（Windows 上即注册表，组织 `DIY` / 应用 `UartTool`）。保存串口配置、高亮规则、窗口几何与分隔条状态。复杂对象以 JSON 字符串存入。

## 扩展指引

新增功能时遵循既有模式：

1. 在面板上定义 `pyqtSignal`，在 `MainWindow._connect_signals()` 接到槽——面板发信号，`MainWindow` 编排，面板之间零耦合。
2. 读串口的逻辑放进 `SerialWorker` 线程；写串口走 `SerialManager`（主线程）。
3. 需要持久化的状态，加到 `AppSettings` 并在 `_restore_settings()` / `closeEvent()` 中读写。

## 注意事项

- `main.py` 的 `_app_icon()` 用 `sys._MEIPASS` 兼容 PyInstaller 打包后的资源路径；`uart_tool.spec` 的 `datas` 必须同步包含图标文件。
- 自定义波特率：`ConfigPanel` 的波特率下拉含「自定义...」项，选中会弹输入框并把新值插入到列表末项之前。
- 全屏日志模式（F11）通过隐藏左侧面板、发送面板和接收区工具栏实现，状态由 `MainWindow._log_focus_mode` 跟踪。
