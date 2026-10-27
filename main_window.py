import os

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QGroupBox, QListWidget, QListWidgetItem,
    QPushButton, QInputDialog, QMessageBox, QStatusBar
)
from PyQt6.QtCore import Qt, pyqtSlot, QByteArray, QTimer, QStandardPaths, QUrl
from PyQt6.QtGui import QAction, QKeySequence, QDesktopServices

from serial_manager   import SerialManager, SerialConfig
from serial_worker    import SerialWorker
from receive_panel    import ReceivePanel
from send_panel       import SendPanel
from config_panel     import ConfigPanel
from highlight_manager import HighlightManager
from log_manager      import LogManager
from settings         import AppSettings
from theme            import COLOR_SUCCESS, COLOR_TEXT_DIM, COLOR_ERROR


class MainWindow(QMainWindow):
    # 待渲染接收数据上限（字节）：串口速率远超界面渲染能力时丢弃最旧数据，
    # 避免缓存无限膨胀把 GUI 线程彻底拖死（此时界面只表现为“卡死”）
    MAX_RX_PENDING = 128 * 1024
    # 单次刷新的最大字节数：把积压数据分摊到多个定时周期，
    # 避免一次向接收区写入过多文本造成界面长时间无响应
    MAX_RX_PER_FLUSH = 64 * 1024
    # 自动落盘的日志子目录名（位于应用数据目录下）
    LOG_DIR_NAME = "logs"

    def __init__(self):
        super().__init__()
        self.setWindowTitle("串口调试工具")
        self.resize(1200, 800)

        self._serial_mgr     = SerialManager()
        self._worker: SerialWorker | None = None
        self._hm             = HighlightManager()
        self._log_mgr        = LogManager(self)
        self._settings       = AppSettings()
        self._log_focus_mode = False
        self._rx_paused      = False
        self._rx_count       = 0
        self._tx_count       = 0
        # 接收数据先缓存，由定时器合并刷新，避免高频数据刷屏拖死 GUI 线程
        self._rx_pending     = bytearray()
        self._rx_flush_timer = QTimer(self)
        self._rx_flush_timer.setInterval(50)
        self._rx_flush_timer.timeout.connect(self._flush_rx)

        self._config_panel   = ConfigPanel(self)
        self._receive_panel  = ReceivePanel(self._hm, self)
        self._send_panel     = SendPanel(self)

        self._init_ui()
        self._build_menu()
        self._build_status_bar()
        self._connect_signals()
        self._restore_settings()
        self._refresh_ports()

    def _init_ui(self) -> None:
        central    = QWidget()
        main_h     = QHBoxLayout(central)
        main_h.setContentsMargins(6, 6, 6, 6)
        main_h.setSpacing(6)

        self._left_panel  = QWidget()
        left_layout = QVBoxLayout(self._left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(6)
        left_layout.addWidget(self._config_panel)
        left_layout.addWidget(self._build_highlight_widget())
        left_layout.addWidget(self._send_panel)
        # 自动落盘设置跟随“发送”模块放在左侧栏，不占用接收区空间
        left_layout.addWidget(self._receive_panel.auto_log_panel())
        left_layout.addStretch()
        self._left_panel.setFixedWidth(300)

        main_h.addWidget(self._left_panel)
        main_h.addWidget(self._receive_panel, stretch=1)
        self.setCentralWidget(central)

    def _build_highlight_widget(self) -> QGroupBox:
        group  = QGroupBox("常驻高亮")
        layout = QVBoxLayout(group)
        layout.setSpacing(4)

        self._hl_list = QListWidget()
        self._hl_list.setMaximumHeight(160)
        self._hl_list.setToolTip("双击条目可删除")

        add_btn = QPushButton("+ 添加关键词")
        hint    = QLabel("双击列表条目可删除")
        hint.setStyleSheet(f"color: {COLOR_TEXT_DIM}; font-size: 11px;")

        layout.addWidget(self._hl_list)
        layout.addWidget(add_btn)
        layout.addWidget(hint)

        add_btn.clicked.connect(self._add_highlight_keyword)
        self._hl_list.itemDoubleClicked.connect(self._remove_highlight_keyword)

        return group

    def _make_action(self, text: str, slot, shortcut: str | None = None) -> QAction:
        act = QAction(text, self)
        act.triggered.connect(slot)
        if shortcut:
            act.setShortcut(QKeySequence(shortcut))
        return act

    def _build_menu(self) -> None:
        mb = self.menuBar()

        file_menu = mb.addMenu("文件(&F)")
        file_menu.addAction(self._make_action("保存日志(&S)", self._receive_panel.save_log_dialog, "Ctrl+S"))
        file_menu.addSeparator()
        file_menu.addAction(self._make_action("退出(&Q)", self.close, "Alt+F4"))

        view_menu = mb.addMenu("视图(&V)")
        focus_act = self._make_action("全屏日志模式(&L)", self._toggle_log_focus)
        focus_act.setShortcut(QKeySequence(Qt.Key.Key_F11))
        view_menu.addAction(focus_act)
        self._focus_action = focus_act

        view_menu.addSeparator()
        view_menu.addAction(self._make_action("清空接收区(&C)", self._on_clear_receive, "Ctrl+L"))
        view_menu.addAction(self._make_action("搜索焦点(&F)", self._receive_panel.focus_search, "Ctrl+F"))

        help_menu = mb.addMenu("帮助(&H)")
        help_menu.addAction("关于(&A)", self._show_about)

    def _build_status_bar(self) -> None:
        sb = self.statusBar()
        self._status_port = QLabel("未连接")
        self._status_port.setObjectName("statusDisconnected")
        self._status_rx   = QLabel("RX: 0 字节")
        self._status_tx   = QLabel("TX: 0 字节")
        sb.addWidget(self._status_port)
        sb.addPermanentWidget(self._status_tx)
        sb.addPermanentWidget(self._status_rx)

    def _connect_signals(self) -> None:
        self._config_panel.connect_requested.connect(self._on_connect)
        self._config_panel.disconnect_requested.connect(self._on_disconnect)
        self._config_panel.refresh_requested.connect(self._refresh_ports)
        self._send_panel.send_requested.connect(self._on_send)
        self._receive_panel.pause_toggled.connect(self._on_pause_toggled)
        self._receive_panel.clear_requested.connect(self._on_clear_receive)
        self._receive_panel.auto_log_toggled.connect(self._on_auto_log_toggled)
        self._receive_panel.log_dir_changed.connect(self._on_log_dir_changed)
        self._receive_panel.open_log_dir_requested.connect(self._on_open_log_dir)

    @pyqtSlot(SerialConfig)
    def _on_connect(self, config: SerialConfig) -> None:
        try:
            port = self._serial_mgr.connect(config)
            self._worker = SerialWorker(port, self)
            self._worker.data_received.connect(self._on_data_received)
            self._worker.error_occurred.connect(self._on_serial_error)
            self._worker.disconnected.connect(self._on_disconnect)
            self._worker.start()

            self._config_panel.set_connected(True)
            self._send_panel.set_enabled(True)
            self._rx_pending.clear()
            self._rx_count = 0
            self._tx_count = 0
            self._status_rx.setText("RX: 0 字节")
            self._status_tx.setText("TX: 0 字节")
            self._status_port.setText(f"已连接  {config.port} @ {config.baudrate}")
            self._status_port.setObjectName("statusConnected")
            self._status_port.setStyleSheet(f"color: {COLOR_SUCCESS}; font-weight: bold;")

            self._settings.save_serial_config(self._config_panel.get_config_dict())
            if self._receive_panel.auto_log_enabled():
                self._start_auto_log()
        except Exception as e:
            QMessageBox.critical(self, "连接失败", str(e))

    def _log_directory(self) -> str:
        """返回自动落盘使用的日志目录。

        用户指定了目录时优先使用；否则使用系统的应用数据目录（打包成 exe 后仍可写），
        该路径不可用时退回到当前工作目录。
        """
        custom = self._receive_panel.log_directory()
        if custom:
            return os.path.normpath(os.path.expanduser(custom))

        base = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)
        return os.path.normpath(os.path.join(base or os.getcwd(), self.LOG_DIR_NAME))

    @pyqtSlot()
    def _on_open_log_dir(self) -> None:
        """在文件资源管理器中打开自动落盘目录（目录不存在时先创建）。"""
        directory = self._log_directory()
        try:
            os.makedirs(directory, exist_ok=True)
        except OSError as e:
            QMessageBox.warning(self, "无法打开目录", f"创建目录失败: {e}")
            return
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(directory)):
            QMessageBox.warning(self, "无法打开目录", f"系统未能打开: {directory}")

    def _start_auto_log(self) -> None:
        """开始自动落盘，并在状态栏提示日志文件位置。

        说明:
            落盘在数据接收处立即执行，因此即使界面因数据过快丢弃了部分显示内容，
            磁盘上的记录依然是完整的。落盘失败不影响串口正常使用。
        """
        try:
            path = self._log_mgr.start_auto_save(self._log_directory())
        except OSError as e:
            self.statusBar().showMessage(f"日志落盘失败: {e}", 5000)
            return
        self.statusBar().showMessage(f"日志记录中: {path}", 5000)

    @pyqtSlot(bool)
    def _on_auto_log_toggled(self, enabled: bool) -> None:
        """自动落盘开关切换：保存设置，已连接时立即开启或停止落盘。

        参数:
            enabled: True 表示开启落盘
        """
        self._settings.save_log_config(enabled, self._receive_panel.log_directory())
        if not self._worker:
            return
        if enabled:
            self._start_auto_log()
        else:
            self._log_mgr.stop_auto_save()
            self.statusBar().showMessage("已停止自动落盘", 3000)

    @pyqtSlot(str)
    def _on_log_dir_changed(self, directory: str) -> None:
        """自动落盘目录变更：保存设置，已连接且开启落盘时切换到新目录。

        参数:
            directory: 新目录，空字符串表示使用默认目录
        """
        self._settings.save_log_config(
            self._receive_panel.auto_log_enabled(), directory
        )
        if self._worker and self._receive_panel.auto_log_enabled():
            self._start_auto_log()

    @pyqtSlot()
    def _on_disconnect(self) -> None:
        if self._worker:
            self._worker.stop()
            self._worker = None
        self._serial_mgr.disconnect()
        self._rx_flush_timer.stop()
        self._flush_rx()
        self._log_mgr.stop_auto_save()
        self._config_panel.set_connected(False)
        self._send_panel.set_enabled(False)
        self._status_port.setText("未连接")
        self._status_port.setStyleSheet(f"color: {COLOR_TEXT_DIM};")

    @pyqtSlot(bytes)
    def _on_data_received(self, data: bytes) -> None:
        if self._rx_paused:
            return
        self._rx_count += len(data)
        # 先落盘再进缓存：后续若因渲染跟不上而丢弃缓存，磁盘记录仍然完整
        self._log_mgr.write_raw(data)
        self._rx_pending.extend(data)
        # 数据量堆积到上限说明渲染跟不上，丢弃最旧的一半，优先保证界面仍可操作
        if len(self._rx_pending) > self.MAX_RX_PENDING:
            drop = len(self._rx_pending) - self.MAX_RX_PENDING // 2
            del self._rx_pending[:drop]
            self.statusBar().showMessage("串口数据过快，已丢弃部分较早的数据", 3000)
        # 数据量较大时立即刷新一次，避免缓存无限堆积
        if not self._rx_flush_timer.isActive():
            self._rx_flush_timer.start()

    def _flush_rx(self) -> None:
        """把缓存的接收数据分批交给接收面板渲染（合并刷新，降低 UI 负载）。

        说明:
            单次最多处理 MAX_RX_PER_FLUSH 字节，剩余数据留到下一个定时周期，
            这样即使瞬间堆积了大量数据，每次重排版的工作量也是有界的。
        """
        if not self._rx_pending:
            self._rx_flush_timer.stop()
            return

        data = bytes(self._rx_pending[: self.MAX_RX_PER_FLUSH])
        del self._rx_pending[: self.MAX_RX_PER_FLUSH]
        self._receive_panel.append_data(data)
        self._status_rx.setText(f"RX: {self._rx_count} 字节")

    @pyqtSlot()
    def _on_clear_receive(self) -> None:
        """清空接收区，并同步清空待刷新数据与接收计数。"""
        self._rx_pending.clear()
        self._rx_flush_timer.stop()
        self._receive_panel.clear()
        self._rx_count = 0
        self._status_rx.setText("RX: 0 字节")

    @pyqtSlot(bool)
    def _on_pause_toggled(self, paused: bool) -> None:
        self._rx_paused = paused

    @pyqtSlot(bytes)
    def _on_send(self, data: bytes) -> None:
        self._serial_mgr.send(data)
        self._tx_count += len(data)
        self._status_tx.setText(f"TX: {self._tx_count} 字节")

    @pyqtSlot(str)
    def _on_serial_error(self, msg: str) -> None:
        self.statusBar().showMessage(f"串口错误: {msg}", 5000)

    def _toggle_log_focus(self) -> None:
        self._log_focus_mode = not self._log_focus_mode
        is_focus = self._log_focus_mode

        self._left_panel.setVisible(not is_focus)
        self._send_panel.setVisible(not is_focus)
        self._receive_panel.set_toolbar_visible(not is_focus)

        label = "退出全屏日志 (F11)" if is_focus else "全屏日志模式 (F11)"
        self._focus_action.setText(label)

    def _add_highlight_keyword(self) -> None:
        text, ok = QInputDialog.getText(self, "添加常驻高亮关键词", "关键词:")
        if not ok or not text.strip():
            return
        rule = self._hm.add_keyword(text.strip())
        if rule is None:
            QMessageBox.information(self, "提示", f"关键词 '{text.strip()}' 已存在")
            return
        item = QListWidgetItem(f"  {rule.keyword}")
        item.setData(Qt.ItemDataRole.UserRole, rule.keyword)
        self._hl_list.addItem(item)
        self._receive_panel.refresh_resident_highlights()
        self._save_highlight_rules()

    def _remove_highlight_keyword(self, item: QListWidgetItem) -> None:
        keyword = item.data(Qt.ItemDataRole.UserRole)
        self._hm.remove_keyword(keyword)
        self._hl_list.takeItem(self._hl_list.row(item))
        self._receive_panel.refresh_resident_highlights()
        self._save_highlight_rules()

    def _save_highlight_rules(self) -> None:
        rules = [{"keyword": r.keyword, "color": r.color}
                 for r in self._hm.get_rules()]
        self._settings.save_highlight_rules(rules)

    def _refresh_ports(self) -> None:
        ports = self._serial_mgr.scan_ports()
        self._config_panel.populate_ports(ports)

    def _restore_settings(self) -> None:
        geo = self._settings.load_geometry()
        if geo:
            self.restoreGeometry(QByteArray(geo))

        cfg = self._settings.load_serial_config()
        if cfg:
            self._config_panel.restore_config_dict(cfg)

        rules = self._settings.load_highlight_rules()
        for r in rules:
            rule = self._hm.add_keyword(r["keyword"])
            if rule:
                rule.color = r["color"]
                item = QListWidgetItem(f"  {rule.keyword}")
                item.setData(Qt.ItemDataRole.UserRole, rule.keyword)
                self._hl_list.addItem(item)

        log_cfg = self._settings.load_log_config()
        self._receive_panel.set_log_config(log_cfg["enabled"], log_cfg["directory"])

    def _show_about(self) -> None:
        QMessageBox.information(
            self, "关于串口调试工具",
            "串口调试工具 v1.0\n\n"
            "技术栈: Python + PyQt6 + pyserial\n\n"
            "功能:\n"
            "  • 串口连接/断开/配置\n"
            "  • ASCII / HEX 数据收发\n"
            "  • 搜索 + 高亮（Ctrl+F）\n"
            "  • 常驻关键词高亮\n"
            "  • 全屏日志模式（F11）\n"
            "  • Ctrl+滚轮调整字体大小\n"
            "  • 日志保存（Ctrl+S）"
        )

    def closeEvent(self, event) -> None:
        self._settings.save_geometry(bytes(self.saveGeometry()))
        self._on_disconnect()
        event.accept()
