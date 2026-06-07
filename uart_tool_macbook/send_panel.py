from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QPushButton,
    QTextEdit, QLabel, QCheckBox, QLineEdit, QComboBox, QMessageBox, QGroupBox
)
from PyQt6.QtCore import QTimer, pyqtSignal, Qt
from PyQt6.QtGui import QIntValidator


class SendPanel(QWidget):
    send_requested = pyqtSignal(bytes)

    NEWLINE_MAP = {
        "无":     b"",
        "\\r\\n": b"\r\n",
        "\\n":    b"\n",
        "\\r":    b"\r",
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self._loop_timer = QTimer(self)
        self._loop_timer.timeout.connect(self._do_send)
        self._init_ui()

    def _init_ui(self) -> None:
        group  = QGroupBox("发送")
        layout = QVBoxLayout(group)
        layout.setSpacing(6)

        fmt_bar = QHBoxLayout()
        self._fmt_combo     = QComboBox()
        self._fmt_combo.addItems(["ASCII", "HEX"])
        self._newline_combo = QComboBox()
        self._newline_combo.addItems(list(self.NEWLINE_MAP.keys()))
        self._newline_combo.setCurrentText("\\r\\n")
        fmt_bar.addWidget(QLabel("格式:"))
        fmt_bar.addWidget(self._fmt_combo)
        fmt_bar.addWidget(QLabel("换行:"))
        fmt_bar.addWidget(self._newline_combo)
        fmt_bar.addStretch()

        self._input = QTextEdit()
        self._input.setFixedHeight(70)
        self._input.setPlaceholderText("输入要发送的数据...")

        btn_bar = QHBoxLayout()
        self._send_btn      = QPushButton("发送")
        self._send_btn.setMinimumWidth(60)
        self._loop_checkbox = QCheckBox("循环发送")
        self._interval_edit = QLineEdit("1000")
        self._interval_edit.setValidator(QIntValidator(10, 99999))
        self._interval_edit.setFixedWidth(60)
        self._interval_edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._interval_label = QLabel("ms")
        btn_bar.addWidget(self._send_btn)
        btn_bar.addStretch()
        btn_bar.addWidget(self._loop_checkbox)
        btn_bar.addWidget(self._interval_edit)
        btn_bar.addWidget(self._interval_label)

        layout.addLayout(fmt_bar)
        layout.addWidget(self._input)
        layout.addLayout(btn_bar)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(group)

        self._send_btn.clicked.connect(self._on_send_clicked)
        self._loop_checkbox.toggled.connect(self._on_loop_toggled)
        self._interval_edit.textChanged.connect(self._on_interval_changed)

        self.set_enabled(False)

    def _on_send_clicked(self) -> None:
        self._do_send()

    def _on_loop_toggled(self, checked: bool) -> None:
        if checked:
            self._start_loop()
            self._send_btn.setEnabled(False)
        else:
            self._loop_timer.stop()
            self._send_btn.setEnabled(True)

    def _on_interval_changed(self) -> None:
        text = self._interval_edit.text()
        if text.isdigit():
            self._loop_timer.setInterval(int(text))

    def _start_loop(self) -> None:
        text = self._interval_edit.text()
        if text.isdigit():
            self._loop_timer.start(int(text))

    def _do_send(self) -> None:
        text = self._input.toPlainText()
        if not text:
            return
        try:
            data = self._encode_input(text)
            self.send_requested.emit(data)
        except ValueError as e:
            QMessageBox.warning(self, "格式错误", str(e))
            self._loop_checkbox.setChecked(False)

    def _encode_input(self, text: str) -> bytes:
        suffix = self.NEWLINE_MAP[self._newline_combo.currentText()]
        if self._fmt_combo.currentText() == "ASCII":
            return text.encode("utf-8") + suffix
        else:
            tokens = text.split()
            try:
                return bytes(int(t, 16) for t in tokens if t)
            except ValueError:
                raise ValueError("HEX 格式无效，请输入如 'AA BB 0D 0A' 的格式")

    def set_enabled(self, enabled: bool) -> None:
        self._send_btn.setEnabled(enabled)
        self._loop_checkbox.setEnabled(enabled)
        self._input.setEnabled(enabled)
        if not enabled:
            self._loop_checkbox.setChecked(False)
