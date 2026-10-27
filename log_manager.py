import os
from datetime import datetime
from PyQt6.QtCore import QObject, pyqtSlot


class LogManager(QObject):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._file      = None
        self._file_path = ""
        self._auto_save = False

    def start_auto_save(self, directory: str) -> str:
        """开始自动落盘，返回本次日志文件的绝对路径。

        参数:
            directory: 日志目录，不存在时自动创建
        返回:
            新建日志文件的绝对路径
        """
        # 重复调用时先关闭旧文件，避免文件句柄泄漏
        self.stop_auto_save()

        os.makedirs(directory, exist_ok=True)
        ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
        name = f"uart_log_{ts}.txt"
        self._file_path = os.path.join(directory, name)
        self._file      = open(self._file_path, "a", encoding="utf-8", newline="")
        self._auto_save = True
        return self._file_path

    def stop_auto_save(self) -> None:
        self._auto_save = False
        if self._file:
            self._file.close()
            self._file = None

    @pyqtSlot(bytes)
    def write_raw(self, raw: bytes) -> None:
        if self._auto_save and self._file:
            try:
                self._file.write(raw.decode("utf-8", errors="replace"))
                self._file.flush()
            except OSError:
                self.stop_auto_save()

    def save_text(self, text: str, path: str) -> None:
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)

    @property
    def is_auto_saving(self) -> bool:
        return self._auto_save

    @property
    def file_path(self) -> str:
        return self._file_path
