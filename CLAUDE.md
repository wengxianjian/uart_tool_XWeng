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

**数据流（接收）**：`SerialWorker.data_received` → `MainWindow._on_data_received` → 累加 `_rx_count` + `LogManager.write_raw`（自动落盘）→ 追加到 `_rx_pending` 缓存 → 50ms 定时器 `_flush_rx()` 分批交给 `ReceivePanel.append_data`（显示）。左侧栏「发送」模块下方的「自动落盘」开关决定是否落盘（`log/enabled` 持久化），目录可自定义（`log/directory`），留空用应用数据目录下的 `logs/uart_log_<时间戳>.txt`；分组框内的「打开目录」按钮（单独一行）可直接在资源管理器中打开当前落盘目录（`open_log_dir_requested` → `MainWindow._on_open_log_dir()`）；已连接时切换开关或改目录立即生效，断开时 `stop_auto_save()` 关闭文件。落盘发生在丢缓存之前，所以界面丢弃数据不影响日志完整性；日志文件是 UTF-8 文本（关闭换行转换），二进制数据会以替换字符体现。

**数据流（发送）**：`SendPanel.send_requested(bytes)` → `MainWindow._on_send` → `SerialManager.send`。

**显示模式差异**（`ReceivePanel.append_data`）：HEX 模式每 32 字节成一行；ASCII 模式用 `_byte_buffer` 累积字节、按 `\n` 切行后再输出——切换模式会清空该缓冲区。

**高亮机制**：`HighlightManager.apply_highlights()` 只扫描本次新增区间，把常驻关键词高亮直接写入文档字符格式（独立 block 光标 + `beginEditBlock` 合并重排版）。`ReceivePanel._refresh_highlights()` 只用 `ExtraSelection` 渲染搜索匹配与当前搜索项。文档块数由 `MAX_BLOCKS` 封顶。

**持久化**：`AppSettings`（`settings.py`）通过 `QSettings` 存储（Windows 上即注册表，组织 `DIY` / 应用 `UartTool`）。保存串口配置、高亮规则、窗口几何与分隔条状态。复杂对象以 JSON 字符串存入。

## 注意事项

- `main.py` 的 `_app_icon()` 用 `sys._MEIPASS` 兼容 PyInstaller 打包后的资源路径；`uart_tool.spec` 的 `datas` 必须同步包含图标文件。
- 自定义波特率：`ConfigPanel` 的波特率下拉含「自定义...」项，选中会弹输入框并把新值插入到列表末项之前。
- 全屏日志模式（F11）通过隐藏左侧面板、发送面板和接收区工具栏实现，状态由 `MainWindow._log_focus_mode` 跟踪。
