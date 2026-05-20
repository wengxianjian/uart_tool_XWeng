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
        ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
        name = f"uart_log_{ts}.txt"
        self._file_path = os.path.join(directory, name)
        self._file      = open(self._file_path, "a", encoding="utf-8")
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
