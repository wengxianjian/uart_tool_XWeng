from datetime import datetime
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QTextEdit, QLineEdit, QLabel, QCheckBox, QComboBox,
    QFileDialog
)
from PyQt6.QtGui import QTextCharFormat, QColor, QTextCursor, QFont
from PyQt6.QtCore import Qt
from highlight_manager import HighlightManager


class ReceiveTextEdit(QTextEdit):
    MIN_FONT_SIZE = 8
    MAX_FONT_SIZE = 36

    def wheelEvent(self, event):
        if event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            delta = event.angleDelta().y()
            font  = self.font()
            size  = font.pointSize()
            size  = min(size + 1, self.MAX_FONT_SIZE) if delta > 0 else max(size - 1, self.MIN_FONT_SIZE)
            font.setPointSize(size)
            self.setFont(font)
            event.accept()
        else:
            super().wheelEvent(event)


class ReceivePanel(QWidget):
    def __init__(self, highlight_manager: HighlightManager, parent=None):
        super().__init__(parent)
        self._hm                  = highlight_manager
        self._search_sels: list   = []
        self._search_index        = -1
        self._auto_scroll         = True
        self._display_mode        = "ASCII"
        self._timestamp_enabled   = False
        self._byte_buffer         = bytearray()
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self._toolbar = self._build_toolbar()
        self._search_bar = self._build_search_bar()

        self._text_edit = ReceiveTextEdit()
        self._text_edit.setReadOnly(True)
        self._text_edit.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        font = QFont("Consolas", 12)
        self._text_edit.setFont(font)

        layout.addWidget(self._toolbar)
        layout.addWidget(self._search_bar)
        layout.addWidget(self._text_edit)

    def _build_toolbar(self) -> QWidget:
        bar = QWidget()
        h   = QHBoxLayout(bar)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(8)

        self._mode_combo    = QComboBox()
        self._mode_combo.addItems(["ASCII", "HEX"])
        self._mode_combo.setFixedWidth(70)

        self._ts_checkbox   = QCheckBox("时间戳")
        self._ts_checkbox.setChecked(False)
        self._autoscroll_cb = QCheckBox("自动滚动")
        self._autoscroll_cb.setChecked(True)

        self._clear_btn = QPushButton("清空")
        self._clear_btn.setFixedWidth(50)
        self._save_btn  = QPushButton("保存日志")

        h.addWidget(QLabel("显示:"))
        h.addWidget(self._mode_combo)
        h.addWidget(self._ts_checkbox)
        h.addWidget(self._autoscroll_cb)
        h.addStretch()
        h.addWidget(self._clear_btn)
        h.addWidget(self._save_btn)

        self._mode_combo.currentTextChanged.connect(self._on_mode_changed)
        self._ts_checkbox.toggled.connect(lambda v: setattr(self, "_timestamp_enabled", v))
        self._autoscroll_cb.toggled.connect(lambda v: setattr(self, "_auto_scroll", v))
        self._clear_btn.clicked.connect(self.clear)
        self._save_btn.clicked.connect(self.save_log_dialog)

        return bar

    def _build_search_bar(self) -> QWidget:
        bar = QWidget()
        h   = QHBoxLayout(bar)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(6)

        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("搜索关键词... (Ctrl+F)")
        self._search_input.setClearButtonEnabled(True)

        self._prev_btn     = QPushButton("▲")
        self._prev_btn.setFixedWidth(28)
        self._prev_btn.setToolTip("上一个 (Shift+Enter)")
        self._next_btn     = QPushButton("▼")
        self._next_btn.setFixedWidth(28)
        self._next_btn.setToolTip("下一个 (Enter)")
        self._count_label  = QLabel("0/0")
        self._count_label.setFixedWidth(45)
        self._count_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        h.addWidget(QLabel("搜索:"))
        h.addWidget(self._search_input, stretch=1)
        h.addWidget(self._prev_btn)
        h.addWidget(self._next_btn)
        h.addWidget(self._count_label)

        self._search_input.textChanged.connect(self._on_search_changed)
        self._search_input.returnPressed.connect(self._search_next)
        self._prev_btn.clicked.connect(self._search_prev)
        self._next_btn.clicked.connect(self._search_next)

        return bar

    def append_data(self, raw: bytes) -> None:
        ts = datetime.now().strftime("[%H:%M:%S.%f")[:-3] + "] " if self._timestamp_enabled else ""

        if self._display_mode == "HEX":
            self._append_line(ts + " ".join(f"{b:02X}" for b in raw))
        else:
            self._byte_buffer.extend(raw)
            while b"\n" in self._byte_buffer:
                idx        = self._byte_buffer.index(b"\n")
                line_bytes = self._byte_buffer[:idx]
                del self._byte_buffer[:idx + 1]
                decoded = line_bytes.decode("utf-8", errors="replace").rstrip("\r")
                self._append_line(ts + decoded)

    def _append_line(self, text: str) -> None:
        self._text_edit.append(text)
        self._refresh_highlights()
        if self._auto_scroll:
            sb = self._text_edit.verticalScrollBar()
            sb.setValue(sb.maximum())

    def _on_search_changed(self, text: str) -> None:
        self._build_search_selections(text)
        self._search_index = 0 if self._search_sels else -1
        self._refresh_highlights()
        self._jump_to_current()
        self._update_count_label()

    def _build_search_selections(self, keyword: str) -> None:
        self._search_sels = []
        if not keyword:
            return
        doc = self._text_edit.document()
        fmt = QTextCharFormat()
        fmt.setBackground(QColor("#ffc880"))
        fmt.setForeground(QColor("#1e1e2e"))
        cursor = QTextCursor(doc)
        while True:
            cursor = doc.find(keyword, cursor)
            if cursor.isNull():
                break
            sel        = QTextEdit.ExtraSelection()
            sel.cursor = cursor
            sel.format  = fmt
            self._search_sels.append(sel)

    def _refresh_highlights(self) -> None:
        doc      = self._text_edit.document()
        resident = self._hm.build_extra_selections(doc)

        current_sels = []
        if 0 <= self._search_index < len(self._search_sels):
            cur_fmt = QTextCharFormat()
            cur_fmt.setBackground(QColor("#fe8019"))
            cur_fmt.setForeground(QColor("#1e1e2e"))
            cur_sel        = QTextEdit.ExtraSelection()
            cur_sel.cursor = self._search_sels[self._search_index].cursor
            cur_sel.format  = cur_fmt
            current_sels   = [cur_sel]

        self._text_edit.setExtraSelections(resident + self._search_sels + current_sels)

    def _jump_to_current(self) -> None:
        if 0 <= self._search_index < len(self._search_sels):
            cursor = self._search_sels[self._search_index].cursor
            self._text_edit.setTextCursor(cursor)
            self._text_edit.ensureCursorVisible()

    def _search_step(self, delta: int) -> None:
        if not self._search_sels:
            return
        self._search_index = (self._search_index + delta) % len(self._search_sels)
        self._refresh_highlights()
        self._jump_to_current()
        self._update_count_label()

    def _search_next(self) -> None:
        self._search_step(+1)

    def _search_prev(self) -> None:
        self._search_step(-1)

    def _update_count_label(self) -> None:
        total = len(self._search_sels)
        cur   = self._search_index + 1 if total > 0 else 0
        self._count_label.setText(f"{cur}/{total}")

    def refresh_resident_highlights(self) -> None:
        self._refresh_highlights()

    def clear(self) -> None:
        self._text_edit.clear()
        self._byte_buffer.clear()
        self._search_sels  = []
        self._search_index = -1
        self._update_count_label()

    def save_log_dialog(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "保存日志", "", "文本文件 (*.txt);;所有文件 (*)"
        )
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self._text_edit.toPlainText())

    def set_toolbar_visible(self, visible: bool) -> None:
        self._toolbar.setVisible(visible)

    def _on_mode_changed(self, mode: str) -> None:
        self._display_mode = mode
        self._byte_buffer.clear()

    def focus_search(self) -> None:
        self._search_input.setFocus()
        self._search_input.selectAll()

    def get_text(self) -> str:
        return self._text_edit.toPlainText()
