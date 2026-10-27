import os
from datetime import datetime
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QTextEdit, QLineEdit, QLabel, QCheckBox, QComboBox,
    QFileDialog, QGroupBox
)
from PyQt6.QtGui import QTextCharFormat, QColor, QTextCursor, QFont
from PyQt6.QtCore import Qt, pyqtSignal
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
    pause_toggled    = pyqtSignal(bool)
    clear_requested  = pyqtSignal()
    auto_log_toggled = pyqtSignal(bool)
    log_dir_changed  = pyqtSignal(str)
    # 请求在文件资源管理器中打开自动落盘目录
    open_log_dir_requested = pyqtSignal()

    # 接收区最多保留的文本块（行）数：超出后自动丢弃最旧的内容，
    # 防止长时间高速输出时文档无限增长导致界面越来越慢直至卡死
    MAX_BLOCKS        = 20000
    # 无换行数据缓冲区上限：超过后强制作为一行输出，避免缓冲区无限膨胀
    MAX_LINE_BUFFER   = 1024 * 1024
    # 搜索匹配数量上限：关键词过于常见时避免生成过多高亮选区拖慢界面
    MAX_SEARCH_MATCHES = 2000

    def __init__(self, highlight_manager: HighlightManager, parent=None):
        super().__init__(parent)
        self._hm                  = highlight_manager
        self._search_sels: list   = []
        self._search_index        = -1
        self._auto_scroll         = True
        self._display_mode        = "ASCII"
        self._timestamp_enabled   = False
        self._byte_buffer         = bytearray()
        self._paused              = False
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self._toolbar   = self._build_toolbar()
        self._log_panel = self._build_log_panel()

        self._text_edit = ReceiveTextEdit()
        self._text_edit.setReadOnly(True)
        self._text_edit.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        # 限制文档最大行数，超出后自动丢弃最旧的内容，保证长时间运行不卡顿
        self._text_edit.document().setMaximumBlockCount(self.MAX_BLOCKS)
        font = QFont("Consolas", 12)
        self._text_edit.setFont(font)

        layout.addWidget(self._toolbar)
        layout.addWidget(self._text_edit)

    def _build_toolbar(self) -> QWidget:
        """构建接收区工具栏：显示模式、时间戳、自动滚动、搜索与操作按钮。"""
        bar = QWidget()
        h   = QHBoxLayout(bar)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(6)

        self._mode_combo    = QComboBox()
        self._mode_combo.addItems(["ASCII", "HEX"])
        self._mode_combo.setFixedWidth(70)

        self._ts_checkbox   = QCheckBox("时间戳")
        self._ts_checkbox.setChecked(False)
        self._autoscroll_cb = QCheckBox("自动滚动")
        self._autoscroll_cb.setChecked(True)

        # 搜索控件紧跟在“自动滚动”之后，不再单独占用一行；
        # 宽度固定，避免占满整行把后面的操作按钮挤到边缘
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("搜索关键词... (Ctrl+F)")
        self._search_input.setClearButtonEnabled(True)
        self._search_input.setFixedWidth(180)

        self._prev_btn     = QPushButton("▲")
        self._prev_btn.setFixedWidth(28)
        self._prev_btn.setToolTip("上一个 (Shift+Enter)")
        self._next_btn     = QPushButton("▼")
        self._next_btn.setFixedWidth(28)
        self._next_btn.setToolTip("下一个 (Enter)")
        self._count_label  = QLabel("0/0")
        self._count_label.setFixedWidth(45)
        self._count_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._clear_btn = QPushButton("清空")
        self._clear_btn.setFixedWidth(50)
        self._save_btn  = QPushButton("保存日志")
        self._pause_btn = QPushButton("暂停")
        self._pause_btn.setFixedWidth(50)

        h.addWidget(QLabel("显示:"))
        h.addWidget(self._mode_combo)
        h.addWidget(self._ts_checkbox)
        h.addWidget(self._autoscroll_cb)
        h.addWidget(self._search_input)
        h.addWidget(self._prev_btn)
        h.addWidget(self._next_btn)
        h.addWidget(self._count_label)
        # 搜索区与右侧操作按钮之间留出空白，避免挤在一起
        h.addStretch()
        h.addWidget(self._pause_btn)
        h.addWidget(self._clear_btn)
        h.addWidget(self._save_btn)

        self._mode_combo.currentTextChanged.connect(self._on_mode_changed)
        self._ts_checkbox.toggled.connect(lambda v: setattr(self, "_timestamp_enabled", v))
        self._autoscroll_cb.toggled.connect(lambda v: setattr(self, "_auto_scroll", v))
        self._search_input.textChanged.connect(self._on_search_changed)
        self._search_input.returnPressed.connect(self._search_next)
        self._prev_btn.clicked.connect(self._search_prev)
        self._next_btn.clicked.connect(self._search_next)
        self._clear_btn.clicked.connect(self._on_clear_clicked)
        self._save_btn.clicked.connect(self.save_log_dialog)
        self._pause_btn.clicked.connect(self._on_pause_toggled)

        return bar

    def _build_log_panel(self) -> QGroupBox:
        """构建自动落盘设置面板：开关 + 目录输入 + 目录选择按钮。

        说明:
            该面板由主窗口放到左侧“发送”模块下方，不占用接收区空间。
        """
        group  = QGroupBox("自动落盘")
        layout = QVBoxLayout(group)
        layout.setSpacing(6)

        self._auto_log_cb = QCheckBox("自动落盘")
        self._auto_log_cb.setChecked(True)
        self._auto_log_cb.setToolTip(
            "连接串口后把接收到的原始数据自动写入文件；\n"
            "落盘发生在界面渲染之前，界面因数据过快丢弃内容时日志依然完整"
        )

        self._log_dir_edit = QLineEdit()
        self._log_dir_edit.setPlaceholderText("留空则用默认目录")
        self._log_dir_edit.setClearButtonEnabled(True)
        self._log_dir_edit.setToolTip(
            "自动落盘目录，留空则使用默认的应用数据目录\\logs；\n"
            "修改后按回车或点击其他控件生效"
        )

        self._log_dir_btn = QPushButton("…")
        self._log_dir_btn.setFixedWidth(28)
        self._log_dir_btn.setToolTip("选择自动落盘目录")

        # 直接打开当前落盘目录（留空时为默认目录），方便查看/拷贝日志文件
        self._log_open_btn = QPushButton("打开目录")
        self._log_open_btn.setFixedWidth(80)
        self._log_open_btn.setToolTip("在文件资源管理器中打开自动落盘目录")

        dir_bar = QHBoxLayout()
        dir_bar.setSpacing(6)
        dir_bar.addWidget(QLabel("目录:"))
        dir_bar.addWidget(self._log_dir_edit, stretch=1)
        dir_bar.addWidget(self._log_dir_btn)

        # “打开目录”单独占一行，避免与目录输入框、选择按钮挤在一起
        open_bar = QHBoxLayout()
        open_bar.setSpacing(6)
        open_bar.addWidget(self._log_open_btn)
        open_bar.addStretch()

        layout.addWidget(self._auto_log_cb)
        layout.addLayout(dir_bar)
        layout.addLayout(open_bar)

        self._auto_log_cb.toggled.connect(self.auto_log_toggled)
        self._log_dir_btn.clicked.connect(self._on_choose_log_dir)
        self._log_open_btn.clicked.connect(self.open_log_dir_requested)
        self._log_dir_edit.editingFinished.connect(self._on_log_dir_edited)

        return group

    def auto_log_panel(self) -> QGroupBox:
        """返回自动落盘设置面板，供主窗口放到左侧布局中。"""
        return self._log_panel

    def _on_choose_log_dir(self) -> None:
        """弹出目录选择对话框，选定后写入输入框并通知主窗口。"""
        start = self._log_dir_edit.text().strip() or os.getcwd()
        path  = QFileDialog.getExistingDirectory(self, "选择自动落盘目录", start)
        if path:
            self._log_dir_edit.setText(os.path.normpath(path))
            self._on_log_dir_edited()

    def _on_log_dir_edited(self) -> None:
        """目录输入框编辑完成时，把当前目录通知主窗口。"""
        self.log_dir_changed.emit(self._log_dir_edit.text().strip())

    def set_log_config(self, enabled: bool, directory: str) -> None:
        """恢复自动落盘开关与目录（初始化时调用，不触发信号）。

        参数:
            enabled: 开关状态
            directory: 日志目录，空字符串表示使用默认目录
        """
        self._auto_log_cb.blockSignals(True)
        self._auto_log_cb.setChecked(enabled)
        self._auto_log_cb.blockSignals(False)
        self._log_dir_edit.setText(directory)

    def auto_log_enabled(self) -> bool:
        """返回自动落盘开关是否开启。"""
        return self._auto_log_cb.isChecked()

    def log_directory(self) -> str:
        """返回用户填写的日志目录，空字符串表示使用默认目录。"""
        return self._log_dir_edit.text().strip()

    def append_data(self, raw: bytes) -> None:
        """追加串口接收到的数据。

        参数:
            raw: 本次由主窗口合并后传入的原始字节
        说明:
            一次调用内的所有行合并为一次写入，高亮也只增量计算一次，
            避免高频数据下 GUI 线程被拖死。
        """
        if not raw:
            return

        ts = datetime.now().strftime("[%H:%M:%S.%f")[:-3] + "] "

        if self._display_mode == "HEX":
            # 按 32 字节一行拆分，避免单行文本过长导致文本控件渲染卡顿
            lines = []
            for i in range(0, len(raw), 32):
                hex_str = " ".join(f"{b:02X}" for b in raw[i:i + 32])
                lines.append((ts if self._timestamp_enabled else "") + hex_str)
            self._append_lines(lines)
            return

        self._byte_buffer.extend(raw)
        lines = []
        while True:
            idx = self._byte_buffer.find(b"\n")
            if idx < 0:
                break
            line_bytes = self._byte_buffer[:idx]
            del self._byte_buffer[:idx + 1]
            decoded = line_bytes.decode("utf-8", errors="replace").rstrip("\r")
            lines.append((ts if self._timestamp_enabled else "") + decoded)

        # 长时间收不到换行时缓冲区会持续膨胀，超过阈值强制输出一行
        if len(self._byte_buffer) > self.MAX_LINE_BUFFER:
            decoded = bytes(self._byte_buffer).decode("utf-8", errors="replace")
            self._byte_buffer.clear()
            lines.append((ts if self._timestamp_enabled else "") + decoded)

        self._append_lines(lines)

    def _append_lines(self, lines: list[str]) -> None:
        """批量写入若干行，并只对新增文本做增量高亮。

        参数:
            lines: 待追加的文本行（不含换行符）
        """
        if not lines:
            return

        doc = self._text_edit.document()
        text = "\n".join(lines)
        self._text_edit.append(text)

        # characterCount() = 字符总数 + 1，据此反推本次新增文本的起始位置。
        # 只扫描新增片段，避免每次追加都遍历整篇文档（旧实现的 O(n²) 卡顿根源）。
        end   = doc.characterCount()
        start = max(end - 1 - len(text), 0)
        self._hm.apply_highlights(doc, start, end)

        # 搜索选区是绝对位置，追加文本后需要重新渲染；
        # 未启用搜索时跳过，避免高频数据下无谓的渲染开销
        if self._search_sels:
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
        fmt.setBackground(QColor("#fe8019"))
        fmt.setForeground(QColor("#1e1e2e"))
        cursor = QTextCursor(doc)
        # 限制匹配数量，关键词过于常见时避免高亮选区过多拖慢界面
        while len(self._search_sels) < self.MAX_SEARCH_MATCHES:
            cursor = doc.find(keyword, cursor)
            if cursor.isNull():
                break
            sel        = QTextEdit.ExtraSelection()
            sel.cursor = cursor
            sel.format  = fmt
            self._search_sels.append(sel)

    def _refresh_highlights(self) -> None:
        """渲染搜索匹配与当前搜索项的高亮选区。

        说明:
            常驻关键词高亮已直接写入文档字符格式，不再占用 ExtraSelection，
            这里只需处理搜索相关的选区。
        """
        current_sels = []
        if 0 <= self._search_index < len(self._search_sels):
            cur_fmt = QTextCharFormat()
            cur_fmt.setBackground(QColor("#d65d0e"))
            cur_fmt.setForeground(QColor("#fbf1c7"))
            cur_sel        = QTextEdit.ExtraSelection()
            cur_sel.cursor = self._search_sels[self._search_index].cursor
            cur_sel.format  = cur_fmt
            current_sels   = [cur_sel]

        self._text_edit.setExtraSelections(self._search_sels + current_sels)

    def _jump_to_current(self) -> None:
        if 0 <= self._search_index < len(self._search_sels):
            cursor = self._search_sels[self._search_index].cursor
            self._text_edit.setTextCursor(cursor)
            self._text_edit.ensureCursorVisible()

    def _search_next(self) -> None:
        if not self._search_sels:
            return
        self._search_index = (self._search_index + 1) % len(self._search_sels)
        self._refresh_highlights()
        self._jump_to_current()
        self._update_count_label()

    def _search_prev(self) -> None:
        if not self._search_sels:
            return
        self._search_index = (self._search_index - 1) % len(self._search_sels)
        self._refresh_highlights()
        self._jump_to_current()
        self._update_count_label()

    def _update_count_label(self) -> None:
        total = len(self._search_sels)
        cur   = self._search_index + 1 if total > 0 else 0
        self._count_label.setText(f"{cur}/{total}")

    def refresh_resident_highlights(self) -> None:
        """常驻高亮规则变化时，重刷全文档的字符格式高亮。"""
        doc = self._text_edit.document()
        self._hm.clear_highlights(doc)
        self._hm.apply_highlights(doc)
        if self._search_sels:
            self._refresh_highlights()

    def _on_clear_clicked(self) -> None:
        """通知主窗口执行清空（同时重置接收计数）。"""
        self.clear_requested.emit()

    def clear(self) -> None:
        """清空接收区文本、解码缓冲与搜索状态。"""
        self._text_edit.clear()
        self._byte_buffer.clear()
        self._search_sels  = []
        self._search_index = -1
        self._text_edit.setExtraSelections([])
        self._update_count_label()

    def save_log_dialog(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "保存日志", "", "文本文件 (*.txt);;所有文件 (*)"
        )
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self._text_edit.toPlainText())

    def set_toolbar_visible(self, visible: bool) -> None:
        """显示/隐藏接收区工具栏（日志全屏模式下隐藏）。"""
        self._toolbar.setVisible(visible)

    def _on_pause_toggled(self) -> None:
        """切换暂停/继续状态"""
        self._paused = not self._paused
        if self._paused:
            self._pause_btn.setText("继续")
        else:
            self._pause_btn.setText("暂停")
        self.pause_toggled.emit(self._paused)

    def _on_mode_changed(self, mode: str) -> None:
        self._display_mode = mode
        self._byte_buffer.clear()

    def focus_search(self) -> None:
        self._search_input.setFocus()
        self._search_input.selectAll()

    def get_text(self) -> str:
        return self._text_edit.toPlainText()
