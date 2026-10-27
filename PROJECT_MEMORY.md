# 串口调试工具 (UartTool) — 项目记忆

## 项目概述

基于 **PyQt6 + pyserial** 的串口调试 GUI 桌面应用。单进程事件驱动架构，代码与注释全部使用中文。

- **技术栈**: Python 3.x + PyQt6 >= 6.6.0 + pyserial >= 3.5
- **入口文件**: `main.py`
- **打包方式**: PyInstaller，配置见 `uart_tool.spec`
- **持久化**: `QSettings`（Windows 上存注册表，组织 `DIY` / 应用 `UartTool`）
- **主题**: 暗色 Catppuccin 风格，定义在 `theme.py`

---

## 文件清单与职责

| 文件 | 代码行数 | 职责 | 关键类/函数 |
|------|---------|------|------------|
| `main.py` | 38 | 程序入口，创建 QApplication、加载图标、应用主题、启动 MainWindow | `main()`, `_app_icon()` |
| `main_window.py` | 401 | 唯一的协调中心，构建 UI/菜单/状态栏，连接所有信号槽 | `MainWindow` |
| `serial_manager.py` | 51 | 同步封装 pyserial，负责连接/断开/发送/端口扫描 | `SerialManager`, `SerialConfig` |
| `serial_worker.py` | 34 | QThread 子类，独立线程轮询读取串口数据 | `SerialWorker` |
| `config_panel.py` | 170 | 串口配置 UI：端口/波特率/数据位/校验/停止位/流控 | `ConfigPanel` |
| `send_panel.py` | 123 | 发送数据输入、ASCII/HEX 编码、换行符、循环定时发送 | `SendPanel` |
| `receive_panel.py` | 422 | 接收区显示、ASCII/HEX 切换、搜索高亮、日志保存；另提供「自动落盘」分组框供主窗口放到左侧栏 | `ReceivePanel`, `ReceiveTextEdit` |
| `highlight_manager.py` | 100 | 常驻关键词高亮规则管理，直接写入文档字符格式 | `HighlightManager`, `HighlightRule` |
| `log_manager.py` | 57 | 接收数据自动落盘（受 UI 开关控制，目录可自定义，断开时关闭） | `LogManager` |
| `settings.py` | 68 | QSettings 封装，读写串口配置/高亮规则/落盘配置/窗口几何 | `AppSettings` |
| `theme.py` | 272 | 暗色样式表（QSS）与配色常量 | `apply_dark_theme()` |
| `create_icon.py` | 124 | 生成 app_icon.png / app_icon.ico | `draw_icon()` |
| `uart_tool.spec` | 40 | PyInstaller 打包配置（单文件 exe） | — |
| `requirements.txt` | 2 | 依赖声明 | — |
| `ARCHITECTURE.md` | 136 | 程序架构说明文档 | — |
| `FLOWCHART.md` | 166 | Mermaid 流程图文档 | — |
| `CLAUDE.md` | 54 | AI 编程助手指引 | — |

---

## 核心架构规则

### 铁律：UI 面板不直接操作串口

所有面板通过 `pyqtSignal` 发出用户意图，`MainWindow` 统一接收并编排，再调用串口层。面板之间零耦合。

### 分层结构

```
入口层:    main.py
协调层:    MainWindow（唯一的调度中心）
UI/业务层: ConfigPanel / ReceivePanel / SendPanel / HighlightManager
串口层:    SerialManager（同步）+ SerialWorker（QThread 异步读）
硬件层:    pyserial (serial.Serial)
横切层:    AppSettings(QSettings) / LogManager
```

### 串口双层设计

- **SerialManager（主线程）**: `connect()` / `disconnect()` / `send()` / `scan_ports()` — 所有写操作
- **SerialWorker（QThread）**: `run()` 循环中每 10ms 检查 `in_waiting`，有数据就 `read()` 并通过 `data_received(bytes)` 信号发回主线程

---

## 核心数据流

### 接收数据流

```
串口硬件 → SerialWorker.run() [工作线程] 轮询 in_waiting / read()
  → data_received(bytes) 信号 [跨线程]
  → MainWindow._on_data_received() [主线程]
    ├→ 累加 _rx_count
    ├→ LogManager.write_raw() 自动落盘（先于缓存，保证丢数据也能留存）
    └→ 追加到 _rx_pending（超过 MAX_RX_PENDING 丢弃最旧数据）
         └→ QTimer 50ms 分批刷新 _flush_rx()
              ├→ ReceivePanel.append_data() 显示（增量高亮）
              └→ 状态栏 "RX: N 字节"
```

### 发送数据流

```
用户点击发送 / 循环定时器 → SendPanel._do_send()
  → 按 ASCII/HEX 编码 + 附加换行符
  → send_requested(bytes) 信号
  → MainWindow._on_send()
    ├→ SerialManager.send() 写串口
    └→ 累加 _tx_count，更新状态栏 "TX: N 字节"
```

### 连接/断开流程

- **连接**: ConfigPanel → `connect_requested(SerialConfig)` → `MainWindow._on_connect()` → SerialManager.connect() + 创建 SerialWorker + 绑定信号 + 保存配置
- **断开（三种触发源）**: 用户点击关闭 / SerialWorker 检测异常 / 窗口关闭 → 统一汇入 `MainWindow._on_disconnect()`

---

## 各模块关键细节

### main.py
- `_app_icon()` 用 `sys._MEIPASS` 兼容 PyInstaller 打包后资源路径
- 应用名 `UartTool`，组织名 `DIY`（对应 QSettings 路径）

### MainWindow (`main_window.py`)
- 窗口尺寸 1200×800，左侧面板固定 300px
- 维护状态: `_rx_count`, `_tx_count`, `_rx_paused`, `_log_focus_mode`
- 菜单: 文件(保存日志 Ctrl+S / 退出) / 视图(F11 全屏日志 / 清空 Ctrl+L / 搜索 Ctrl+F) / 帮助
- `_connect_signals()` 连接所有面板信号（4 个信号连接）
- `closeEvent()` 保存窗口几何 + 断开串口

### ConfigPanel (`config_panel.py`)
- 信号: `connect_requested`, `disconnect_requested`, `refresh_requested`
- 波特率下拉含"自定义..."项，选中弹 `QInputDialog`，自定义值插入列表末项之前
- 连接后禁用所有配置控件，按钮变红（通过 `connectBtn[connected="true"]` 样式）
- `get_config_dict()` / `restore_config_dict()` 用于持久化往返

### SendPanel (`send_panel.py`)
- 信号: `send_requested(bytes)`
- 格式: ASCII（utf-8 编码）或 HEX（空格分隔如 `AA BB 0D`）
- 换行符: 无 / `\r\n` / `\n` / `\r`
- 循环发送: QTimer，间隔 10~99999ms，勾选后禁用发送按钮
- HEX 格式错误自动取消循环发送
- 未连接时整体禁用

### ReceivePanel (`receive_panel.py`)
- 信号: `pause_toggled(bool)`
- 自定义 `ReceiveTextEdit`: 支持 Ctrl+滚轮缩放字体（8~36pt）
- 显示模式:
  - **HEX**: 每块数据独立成行 `"%02X"`
  - **ASCII**: `_byte_buffer` 累积字节，遇 `\n` 切行输出；切换模式清空缓冲区
- 搜索: 搜索框与「上一个/下一个」内联在接收区工具栏的「自动滚动」之后（不单独占一行，搜索框固定宽度 180px，其后的弹性留白把搜索区与右侧「暂停/清空/保存」按钮隔开），遍历 document 查找匹配，生成 ExtraSelection（上限 `MAX_SEARCH_MATCHES`），支持上一个/下一个循环
- 高亮: 常驻关键词高亮**直接写入文档字符格式**（不再占用 ExtraSelection）；ExtraSelection 只用于搜索匹配(橙色 #fe8019) 与当前项(深橙 #d65d0e)
- 性能约束: `MAX_BLOCKS=20000` 限制文档块数；`_byte_buffer` 超过 `MAX_LINE_BUFFER`(1MB) 强制成行；追加后只对新增区间做增量高亮
- 暂停: 阻止 `_on_data_received` 更新 UI，但数据仍在后台接收
- 清空: `clear()` 发出 `clear_requested`，由 MainWindow 一并重置 RX 计数与待刷新缓存
- 日志保存: `save_log_dialog()` 直接写 QTextEdit 文本到文件

### HighlightManager (`highlight_manager.py`)
- `HighlightRule`: keyword + color + enabled
- 6 种轮转颜色 (HIGHLIGHT_COLORS)
- 关键词去重
- `apply_highlights(document, start, end)` 只扫描指定区间，用独立 block 光标 + `beginEditBlock` 把匹配的格式修改合并成一次重排版（`MAX_APPLY_MATCHES` 限制单次匹配数）
- `clear_highlights(document)` 全选文档并重置字符格式

### LogManager (`log_manager.py`)
- 由左侧栏「发送」模块下方「自动落盘」分组框的开关控制：勾选且已连接时 `MainWindow._start_auto_log()` 调用 `start_auto_save(dir)` 开始落盘，取消勾选或断开时 `stop_auto_save()`
- 该分组框由 `ReceivePanel._build_log_panel()` 构建，通过 `auto_log_panel()` 交给主窗口插入左侧布局；日志目录可在分组框内自定义（「…」按钮弹出 `QFileDialog`），下一行的「打开目录」按钮可直接在文件资源管理器中打开当前落盘目录（`open_log_dir_requested` → `MainWindow._on_open_log_dir()`，目录不存在时先创建）；留空则用 `QStandardPaths.AppDataLocation/logs`（Windows 上 `%APPDATA%\DIY\UartTool\logs`），文件名为 `uart_log_<时间戳>.txt`
- 开关状态与目录持久化在 `QSettings` 的 `log/enabled`、`log/directory`（`AppSettings.save_log_config/load_log_config`）
- 写盘在 `_on_data_received` 中、丢弃缓存之前完成，界面丢数据不影响日志完整性
- 文件以 UTF-8 + `newline=""` 打开（不做换行转换）；写失败自动停止落盘
- 手动保存仍走 `ReceivePanel.save_log_dialog`（Ctrl+S）

### AppSettings (`settings.py`)
- QSettings key 前缀: `serial/config`, `highlight/rules`, `window/geometry`, `window/splitter`
- 复杂对象以 JSON 字符串存入
- 注意: `save_splitter_state()` / `load_splitter_state()` 已定义但 MainWindow 中未使用（无 QSplitter）

### theme.py
- Catppuccin Mocha 风格暗色主题
- 颜色常量: COLOR_BG_DARK(#1e1e2e), COLOR_ACCENT(#89b4fa), COLOR_SUCCESS(#a6e3a1), COLOR_ERROR(#f38ba8) 等
- 6 种高亮轮转色: 黄/青/紫/绿/橙/红
- QSS 覆盖所有常用控件: QPushButton, QComboBox, QLineEdit, QTextEdit, QScrollBar, QMenu, QStatusBar 等

---

## 快捷键

| 快捷键 | 功能 |
|--------|------|
| Ctrl+S | 保存日志 |
| Ctrl+F | 搜索焦点 |
| Ctrl+L | 清空接收区 |
| F11 | 全屏日志模式（隐藏左侧面板和发送面板） |
| Ctrl+滚轮 | 调整接收区字体大小 |
| Enter (搜索框) | 下一个匹配 |
| Shift+Enter (搜索框) | 上一个匹配 |
| Alt+F4 | 退出 |

---

## 常用命令

```bash
pip install -r requirements.txt   # 安装依赖
python main.py                     # 运行
python create_icon.py              # 重新生成图标
pyinstaller uart_tool.spec         # 打包为 dist/uart_tool.exe
python _smoke.py                   # 冒烟测试（依赖已打包的 exe）
```

---

## 已知问题与注意事项

1. **自动落盘为文本格式**: 日志按 UTF-8 文本写入，二进制数据会以替换字符体现；需要精确字节时请切到 HEX 后手动保存
2. **无单元测试**: 无 pytest/unittest 配置，`_smoke.py` 是唯一自动化验证（且依赖打包产物）
3. **splitter_state 持久化**: AppSettings 有读写方法但 MainWindow 中未使用 QSplitter，故未调用
4. **图标资源**: `uart_tool.spec` 的 `datas` 必须包含 `app_icon.ico` 和 `app_icon.png`，否则打包后图标丢失
5. **ASCII 缓冲区**: 切换显示模式会清空 `_byte_buffer`，可能导致未切行的数据丢失
6. **暂停行为**: 暂停期间数据仍在后台接收（SerialWorker 不停），只是不更新 UI 显示

---

## 扩展指引

新增功能时遵循模式:
1. 面板定义 `pyqtSignal`，在 `MainWindow._connect_signals()` 连接槽
2. 不要让面板互相耦合或直接访问 `SerialManager`
3. 读串口逻辑放 `SerialWorker` 线程，写串口走 `SerialManager`
4. 持久化配置加到 `AppSettings`，在 `_restore_settings()` / `closeEvent()` 中读写