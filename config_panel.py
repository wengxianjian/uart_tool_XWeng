from PyQt6.QtWidgets import (
    QWidget, QLabel, QComboBox, QPushButton,
    QGroupBox, QGridLayout, QVBoxLayout, QInputDialog
)
from PyQt6.QtCore import pyqtSignal
from serial_manager import SerialConfig


class ConfigPanel(QWidget):
    connect_requested    = pyqtSignal(SerialConfig)
    disconnect_requested = pyqtSignal()
    refresh_requested    = pyqtSignal()

    BAUDRATES    = ["1200", "2400", "4800", "9600", "19200", "38400",
                    "57600", "115200", "230400", "460800", "921600"]
    CUSTOM_ITEM  = "自定义..."
    DATABITS   = ["5", "6", "7", "8"]
    PARITIES   = ["N (无)", "E (偶)", "O (奇)", "M (标记)", "S (空格)"]
    PARITY_MAP = {
        "N (无)": "N", "E (偶)": "E", "O (奇)": "O",
        "M (标记)": "M", "S (空格)": "S"
    }
    STOPBITS   = ["1", "1.5", "2"]
    FLOWCTRLS  = ["无", "RTS/CTS", "XON/XOFF"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._connected = False
        self._init_ui()

    def _init_ui(self) -> None:
        group = QGroupBox("串口配置")
        grid  = QGridLayout(group)
        grid.setSpacing(6)

        self._port_combo   = QComboBox()
        self._refresh_btn  = QPushButton("刷新")
        self._refresh_btn.setMinimumWidth(52)
        self._baud_combo   = QComboBox()
        self._data_combo   = QComboBox()
        self._parity_combo = QComboBox()
        self._stop_combo   = QComboBox()
        self._flow_combo   = QComboBox()
        self._connect_btn  = QPushButton("打开串口")
        self._connect_btn.setObjectName("connectBtn")
        self._connect_btn.setMinimumHeight(30)

        self._baud_combo.addItems(self.BAUDRATES)
        self._baud_combo.addItem(self.CUSTOM_ITEM)
        self._baud_combo.setCurrentText("115200")
        self._baud_combo.currentIndexChanged.connect(self._on_baud_changed)
        self._data_combo.addItems(self.DATABITS)
        self._data_combo.setCurrentText("8")
        self._parity_combo.addItems(self.PARITIES)
        self._stop_combo.addItems(self.STOPBITS)
        self._flow_combo.addItems(self.FLOWCTRLS)

        rows = [
            ("端口:",   [self._port_combo, self._refresh_btn]),
            ("波特率:", [self._baud_combo]),
            ("数据位:", [self._data_combo]),
            ("校验位:", [self._parity_combo]),
            ("停止位:", [self._stop_combo]),
            ("流控:",   [self._flow_combo]),
        ]
        for row, (label, widgets) in enumerate(rows):
            grid.addWidget(QLabel(label), row, 0)
            if len(widgets) == 1:
                grid.addWidget(widgets[0], row, 1, 1, 2)
            else:
                grid.addWidget(widgets[0], row, 1)
                grid.addWidget(widgets[1], row, 2)

        grid.addWidget(self._connect_btn, len(rows), 0, 1, 3)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(group)

        self._refresh_btn.clicked.connect(self.refresh_requested)
        self._connect_btn.clicked.connect(self._on_connect_toggle)

    def _current_baudrate(self) -> str:
        text = self._baud_combo.currentText()
        return text if text != self.CUSTOM_ITEM else "115200"

    def _on_baud_changed(self, index: int) -> None:
        if self._baud_combo.currentText() != self.CUSTOM_ITEM:
            return
        value, ok = QInputDialog.getInt(
            self, "自定义波特率", "请输入波特率 (300 ~ 10000000):",
            115200, 300, 10_000_000
        )
        if ok:
            custom = str(value)
            pos = self._baud_combo.findText(custom)
            if pos >= 0:
                self._baud_combo.setCurrentIndex(pos)
            else:
                insert_at = self._baud_combo.count() - 1   # 插到"自定义..."前
                self._baud_combo.insertItem(insert_at, custom)
                self._baud_combo.setCurrentIndex(insert_at)
        else:
            self._baud_combo.setCurrentText("115200")

    def _on_connect_toggle(self) -> None:
        if not self._connected:
            self.connect_requested.emit(self._build_config())
        else:
            self.disconnect_requested.emit()

    def _build_config(self) -> SerialConfig:
        stop_map = {"1": 1, "1.5": 1.5, "2": 2}
        flow     = self._flow_combo.currentText()
        return SerialConfig(
            port     = self._port_combo.currentText(),
            baudrate = int(self._current_baudrate()),
            bytesize = int(self._data_combo.currentText()),
            parity   = self.PARITY_MAP[self._parity_combo.currentText()],
            stopbits = stop_map[self._stop_combo.currentText()],
            xonxoff  = (flow == "XON/XOFF"),
            rtscts   = (flow == "RTS/CTS"),
        )

    def populate_ports(self, ports: list[str]) -> None:
        current = self._port_combo.currentText()
        self._port_combo.clear()
        self._port_combo.addItems(ports)
        if current in ports:
            self._port_combo.setCurrentText(current)

    def set_connected(self, connected: bool) -> None:
        self._connected = connected
        self._connect_btn.setText("关闭串口" if connected else "打开串口")
        self._connect_btn.setProperty("connected", "true" if connected else "false")
        self._connect_btn.style().unpolish(self._connect_btn)
        self._connect_btn.style().polish(self._connect_btn)
        for w in [self._port_combo, self._refresh_btn, self._baud_combo,
                  self._data_combo, self._parity_combo, self._stop_combo,
                  self._flow_combo]:
            w.setEnabled(not connected)

    def get_config_dict(self) -> dict:
        return {
            "port":     self._port_combo.currentText(),
            "baudrate": self._current_baudrate(),
            "bytesize": self._data_combo.currentText(),
            "parity":   self._parity_combo.currentText(),
            "stopbits": self._stop_combo.currentText(),
            "flow":     self._flow_combo.currentText(),
        }

    def restore_config_dict(self, cfg: dict) -> None:
        if cfg.get("baudrate"):
            baud = cfg["baudrate"]
            pos  = self._baud_combo.findText(baud)
            if pos >= 0:
                self._baud_combo.setCurrentIndex(pos)
            else:
                insert_at = self._baud_combo.count() - 1
                self._baud_combo.insertItem(insert_at, baud)
                self._baud_combo.setCurrentIndex(insert_at)
        if cfg.get("bytesize"):
            self._data_combo.setCurrentText(cfg["bytesize"])
        if cfg.get("parity"):
            self._parity_combo.setCurrentText(cfg["parity"])
        if cfg.get("stopbits"):
            self._stop_combo.setCurrentText(cfg["stopbits"])
        if cfg.get("flow"):
            self._flow_combo.setCurrentText(cfg["flow"])
