from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QSplitter, QVBoxLayout, QHBoxLayout,
    QLabel, QGroupBox, QListWidget, QListWidgetItem,
    QPushButton, QInputDialog, QMessageBox, QStatusBar
)
from PyQt6.QtCore import Qt, pyqtSlot, QByteArray
from PyQt6.QtGui import QAction, QKeySequence

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
        self._rx_count       = 0
        self._tx_count       = 0

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
        left_layout.addStretch()
        self._left_panel.setFixedWidth(280)

        self._splitter = QSplitter(Qt.Orientation.Vertical)
        self._splitter.addWidget(self._receive_panel)
        self._splitter.addWidget(self._send_panel)
        self._splitter.setStretchFactor(0, 7)
        self._splitter.setStretchFactor(1, 3)

        main_h.addWidget(self._left_panel)
        main_h.addWidget(self._splitter, stretch=1)
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
        view_menu.addAction(self._make_action("清空接收区(&C)", self._receive_panel.clear, "Ctrl+L"))
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
            self._rx_count = 0
            self._tx_count = 0
            self._status_rx.setText("RX: 0 字节")
            self._status_tx.setText("TX: 0 字节")
            self._status_port.setText(f"已连接  {config.port} @ {config.baudrate}")
            self._status_port.setObjectName("statusConnected")
            self._status_port.setStyleSheet(f"color: {COLOR_SUCCESS}; font-weight: bold;")

            self._settings.save_serial_config(self._config_panel.get_config_dict())
        except Exception as e:
            QMessageBox.critical(self, "连接失败", str(e))

    @pyqtSlot()
    def _on_disconnect(self) -> None:
        if self._worker:
            self._worker.stop()
            self._worker = None
        self._serial_mgr.disconnect()
        self._config_panel.set_connected(False)
        self._send_panel.set_enabled(False)
        self._status_port.setText("未连接")
        self._status_port.setStyleSheet(f"color: {COLOR_TEXT_DIM};")

    @pyqtSlot(bytes)
    def _on_data_received(self, data: bytes) -> None:
        self._rx_count += len(data)
        self._status_rx.setText(f"RX: {self._rx_count} 字节")
        self._receive_panel.append_data(data)
        self._log_mgr.write_raw(data)

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

        splitter_state = self._settings.load_splitter_state()
        if splitter_state:
            self._splitter.restoreState(QByteArray(splitter_state))

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
        self._settings.save_splitter_state(bytes(self._splitter.saveState()))
        self._on_disconnect()
        event.accept()
