# 程序流程图

本文件用 [Mermaid](https://mermaid.js.org/) 描述串口调试工具的关键流程。
GitHub、VS Code（带 Mermaid 插件）等可直接渲染。

## 1. 应用启动流程

```mermaid
flowchart TD
    A[启动 python main.py] --> B[创建 QApplication]
    B --> C[设置应用名/组织名/图标]
    C --> D[apply_dark_theme 应用暗色主题]
    D --> E[构造 MainWindow]
    E --> E1[创建 SerialManager / HighlightManager<br/>LogManager / AppSettings]
    E1 --> E2[创建 ConfigPanel / ReceivePanel / SendPanel]
    E2 --> F[_init_ui 构建界面]
    F --> G[_build_menu 构建菜单]
    G --> H[_build_status_bar 构建状态栏]
    H --> I[_connect_signals 连接信号槽]
    I --> J[_restore_settings 恢复上次配置]
    J --> K[_refresh_ports 扫描串口]
    K --> L[window.show 显示窗口]
    L --> M[app.exec 进入事件循环]
```

## 2. 串口连接 / 断开流程

```mermaid
flowchart TD
    A[用户点击 打开串口] --> B[ConfigPanel._build_config<br/>组装 SerialConfig]
    B --> C[发出 connect_requested 信号]
    C --> D[MainWindow._on_connect]
    D --> E{SerialManager.connect<br/>打开串口?}
    E -- 失败 --> F[QMessageBox 弹出连接失败]
    E -- 成功 --> G[创建 SerialWorker 线程]
    G --> H[绑定 data_received /<br/>error_occurred / disconnected]
    H --> I[worker.start 启动读线程]
    I --> J[ConfigPanel.set_connected True<br/>SendPanel.set_enabled True]
    J --> K[重置 RX/TX 计数, 更新状态栏]
    K --> L[AppSettings.save_serial_config<br/>保存配置]

    M[用户点击 关闭串口] --> N[发出 disconnect_requested]
    N --> O[MainWindow._on_disconnect]
    P[SerialWorker 检测串口异常] --> O
    Q[窗口关闭 closeEvent] --> O
    O --> R[worker.stop 停止读线程]
    R --> S[SerialManager.disconnect 关闭串口]
    S --> T[面板恢复未连接状态, 更新状态栏]
```

## 3. 数据接收流程（跨线程）

```mermaid
flowchart TD
    subgraph 工作线程 [SerialWorker 工作线程]
        A[run 循环] --> B{in_waiting > 0?}
        B -- 否 --> C[msleep 10ms]
        C --> A
        B -- 是 --> D[read 读取数据]
        D --> E[发出 data_received bytes 信号]
        F{捕获 SerialException?} -.异常.-> G[发出 error_occurred<br/>+ disconnected]
    end

    E ==跨线程信号==> H[MainWindow._on_data_received]

    subgraph 主线程 [GUI 主线程]
        H --> I[累加 _rx_count<br/>更新状态栏 RX]
        H --> J[ReceivePanel.append_data]
        H --> K[LogManager.write_raw<br/>当前休眠不落盘]
        J --> L{显示模式?}
        L -- HEX --> M[每块转 02X 十六进制<br/>逐条成行输出]
        L -- ASCII --> N[字节存入 _byte_buffer]
        N --> O{缓冲区含 \\n?}
        O -- 是 --> P[按 \\n 切行<br/>utf-8 解码后输出]
        O -- 否 --> Q[等待更多数据]
        M --> R[_append_line]
        P --> R
        R --> S[_refresh_highlights 重建高亮]
        S --> T{自动滚动?}
        T -- 是 --> U[滚动到底部]
    end
```

## 4. 数据发送流程

```mermaid
flowchart TD
    A1[用户点击 发送] --> C[SendPanel._do_send]
    A2[循环定时器 QTimer 超时] --> C
    C --> D{输入为空?}
    D -- 是 --> E[直接返回]
    D -- 否 --> F[_encode_input 编码]
    F --> G{发送格式?}
    G -- ASCII --> H[utf-8 编码 + 换行符]
    G -- HEX --> I{HEX 解析成功?}
    I -- 否 --> J[QMessageBox 格式错误<br/>取消循环发送]
    I -- 是 --> K[转为 bytes + 换行符]
    H --> L[发出 send_requested bytes]
    K --> L
    L --> M[MainWindow._on_send]
    M --> N[SerialManager.send 写串口]
    N --> O[累加 _tx_count<br/>更新状态栏 TX]
```

## 5. 搜索与高亮流程

```mermaid
flowchart TD
    A[搜索框文本变化] --> B[_build_search_selections<br/>查找全部匹配]
    B --> C[_search_index 置 0]
    C --> D[_refresh_highlights]
    D --> E[叠加三类高亮选区]
    E --> E1[常驻关键词高亮]
    E --> E2[搜索全部匹配]
    E --> E3[当前选中匹配项]
    D --> F[_jump_to_current 跳转到当前项]
    F --> G[_update_count_label 更新 当前/总数]

    H[点击 上一个/下一个<br/>或回车] --> I[_search_index 循环 +1/-1]
    I --> D

    J[添加/删除常驻关键词] --> K[HighlightManager 增删规则]
    K --> L[refresh_resident_highlights]
    L --> D
    K --> M[AppSettings.save_highlight_rules]
```

## 6. 信号与槽连接关系

```mermaid
flowchart LR
    subgraph Panels [UI 面板 — 发信号]
        CP[ConfigPanel]
        SP[SendPanel]
        SW[SerialWorker]
    end

    subgraph MW [MainWindow — 接信号编排]
        S1[_on_connect]
        S2[_on_disconnect]
        S3[_refresh_ports]
        S4[_on_send]
        S5[_on_data_received]
        S6[_on_serial_error]
    end

    subgraph Core [核心服务]
        SM[SerialManager]
        RP[ReceivePanel]
        LM[LogManager]
    end

    CP -- connect_requested --> S1
    CP -- disconnect_requested --> S2
    CP -- refresh_requested --> S3
    SP -- send_requested --> S4
    SW -- data_received --> S5
    SW -- error_occurred --> S6
    SW -- disconnected --> S2

    S1 --> SM
    S2 --> SM
    S4 --> SM
    S5 --> RP
    S5 --> LM
```
