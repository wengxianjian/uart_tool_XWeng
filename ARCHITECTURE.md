# 程序架构说明

串口调试工具 —— 基于 PyQt6 + pyserial 的 GUI 桌面应用。

## 1. 总体设计

应用为**单进程、事件驱动**架构，由 Qt 信号/槽串联各模块。整体遵循一条铁律：

> **UI 面板从不直接操作串口。** 面板只通过 `pyqtSignal` 发出用户意图，由 `MainWindow` 统一接收并编排，再调用串口层。

这条规则保证了面板之间零耦合，所有协调逻辑集中在 `MainWindow`，便于维护和扩展。

## 2. 模块清单

| 模块 | 文件 | 职责 |
|------|------|------|
| 程序入口 | `main.py` | 创建 `QApplication`、加载图标、应用暗色主题、构造并显示 `MainWindow` |
| 协调中心 | `main_window.py` | 唯一的调度中心：构建 UI/菜单/状态栏、连接信号、编排收发与持久化 |
| 串口同步层 | `serial_manager.py` | `SerialManager` 封装 `serial.Serial`，负责连接/断开/发送/端口扫描；`SerialConfig` 为配置 dataclass |
| 串口读取线程 | `serial_worker.py` | `SerialWorker`（`QThread`），独立线程每 10ms 轮询 `in_waiting` 读数据 |
| 串口配置面板 | `config_panel.py` | 端口/波特率/数据位/校验/停止位/流控的选择 UI；发出连接/断开/刷新信号 |
| 接收显示面板 | `receive_panel.py` | 接收区显示、ASCII/HEX 切换、时间戳、搜索、高亮叠加、日志保存 |
| 发送面板 | `send_panel.py` | 发送数据输入、ASCII/HEX 编码、换行符附加、循环定时发送 |
| 高亮管理 | `highlight_manager.py` | `HighlightManager` 维护常驻关键词规则，生成 `QTextEdit.ExtraSelection` |
| 日志管理 | `log_manager.py` | `LogManager`，原始数据落盘能力（当前休眠，见下文 §6） |
| 持久化 | `settings.py` | `AppSettings` 通过 `QSettings` 读写配置（Windows 上即注册表） |
| 主题 | `theme.py` | 暗色样式表与配色常量 |

## 3. 分层结构

```
┌─────────────────────────────────────────────┐
│                  main.py                     │  入口层
└───────────────────────┬───────────────────────┘
                        │
┌───────────────────────▼───────────────────────┐
│                MainWindow                     │  协调层
│   _connect_signals() / 各槽函数 / 状态计数      │
└──┬──────────┬──────────┬──────────┬───────────┘
   │          │          │          │
┌──▼───┐  ┌───▼────┐  ┌──▼─────┐  ┌─▼────────┐
│Config│  │Receive │  │ Send   │  │Highlight │  UI / 业务层
│Panel │  │Panel   │  │ Panel  │  │Manager   │
└──────┘  └────────┘  └────────┘  └──────────┘
   │                                            
┌──▼──────────────────────────────────────────┐
│  SerialManager  ←→  SerialWorker(QThread)     │  串口层
└──┬───────────────────────────────────────────┘
   │
┌──▼──────────────────────────────────────────┐
│        pyserial (serial.Serial)              │  硬件接口层
└───────────────────────────────────────────────┘

持久化横切：AppSettings(QSettings)  ←  MainWindow 读写
```

## 4. 串口的双层结构

串口访问刻意拆成两层，以避免阻塞 GUI 线程：

- **`SerialManager`（同步层）** —— 运行在主线程，提供 `connect/disconnect/send/scan_ports`。所有写操作和端口管理走这里。
- **`SerialWorker`（线程层）** —— `QThread` 子类。`run()` 循环中每 10ms 检查 `in_waiting`，有数据就 `read()` 并通过 `data_received(bytes)` 信号发回主线程。

**关键约束：读串口必须在 `SerialWorker` 线程内完成，绝不能放到 GUI 线程。** 信号跨线程自动切回主线程槽，因此 `MainWindow._on_data_received` 在主线程安全更新 UI。

## 5. 核心数据流

### 5.1 接收数据流

```
串口硬件
  → SerialWorker.run()  轮询 in_waiting / read()        [工作线程]
  → data_received(bytes) 信号                            [跨线程]
  → MainWindow._on_data_received()                       [主线程]
      ├→ 累加 _rx_count，更新状态栏
      ├→ ReceivePanel.append_data()   显示
      └→ LogManager.write_raw()       落盘（当前休眠）
```

### 5.2 发送数据流

```
用户点击"发送" / 循环定时器触发
  → SendPanel._do_send()  按 ASCII/HEX 编码 + 附加换行符
  → send_requested(bytes) 信号
  → MainWindow._on_send()
      ├→ SerialManager.send()  写串口
      └→ 累加 _tx_count，更新状态栏
```

### 5.3 连接 / 断开流程

```
ConfigPanel "打开串口"
  → connect_requested(SerialConfig) 信号
  → MainWindow._on_connect()
      ├→ SerialManager.connect()  打开 serial.Serial
      ├→ 创建 SerialWorker 并 start()
      ├→ 绑定 worker 的 data_received / error_occurred / disconnected
      ├→ ConfigPanel.set_connected(True) / SendPanel.set_enabled(True)
      └→ AppSettings.save_serial_config()  保存配置
```

断开可由三种来源触发，统一汇入 `MainWindow._on_disconnect()`：用户点击"关闭串口"、`SerialWorker` 检测到串口异常、窗口关闭。

## 6. 关键机制说明

### 显示模式差异（`ReceivePanel.append_data`）
- **HEX 模式**：每个数据块独立成行，逐条 `"%02X"` 输出。
- **ASCII 模式**：用 `_byte_buffer` 累积字节，遇 `\n` 才切行输出。**切换显示模式会清空该缓冲区。**

### 高亮叠加机制
`ReceivePanel._refresh_highlights()` 把三类 `ExtraSelection` 叠加渲染：
1. 常驻关键词高亮（`HighlightManager` 生成）
2. 搜索全部匹配项
3. 当前选中的搜索项（更深配色）

每追加一行都会重建全部高亮。

### 循环发送
`SendPanel` 内置 `QTimer`，勾选"循环发送"后按间隔反复调用 `_do_send()`；HEX 格式错误会自动取消循环。

### 持久化
`AppSettings` 经 `QSettings`（组织 `DIY` / 应用 `UartTool`，Windows 上即注册表）保存：串口配置、高亮规则、窗口几何、分隔条状态。复杂对象以 JSON 字符串存入。

### LogManager 休眠状态
`LogManager.write_raw()` 已接入接收数据流，但 `start_auto_save()` 从未被调用、也无 UI 开关，因此**自动保存实际不落盘**。当前日志保存只走 `ReceivePanel.save_log_dialog`（Ctrl+S，直接写 `QTextEdit` 文本）。

## 7. 扩展指引

新增功能时遵循既有模式：

1. **面板发信号，`MainWindow` 接信号** —— 在面板上定义 `pyqtSignal`，在 `MainWindow._connect_signals()` 接到槽。
2. **不要让面板互相耦合**，也不要让面板直接访问 `SerialManager`。
3. **读串口的逻辑放进 `SerialWorker` 线程**，写串口走 `SerialManager`。
4. 需要持久化的状态，加到 `AppSettings` 并在 `_restore_settings()` / `closeEvent()` 中读写。
