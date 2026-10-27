import json
from PyQt6.QtCore import QSettings

APP_NAME = "UartTool"
ORG_NAME = "DIY"


class AppSettings:
    def __init__(self):
        self._s = QSettings(ORG_NAME, APP_NAME)

    def save_serial_config(self, config: dict) -> None:
        self._s.setValue("serial/config", json.dumps(config))

    def load_serial_config(self) -> dict:
        raw = self._s.value("serial/config", "{}")
        try:
            return json.loads(raw)
        except Exception:
            return {}

    def save_highlight_rules(self, rules: list[dict]) -> None:
        self._s.setValue("highlight/rules", json.dumps(rules))

    def load_highlight_rules(self) -> list[dict]:
        raw = self._s.value("highlight/rules", "[]")
        try:
            return json.loads(raw)
        except Exception:
            return []

    def save_log_config(self, enabled: bool, directory: str) -> None:
        """保存自动落盘配置。

        参数:
            enabled: 自动落盘开关状态
            directory: 用户指定的日志目录，空字符串表示使用默认目录
        """
        self._s.setValue("log/enabled", enabled)
        self._s.setValue("log/directory", directory)

    def load_log_config(self) -> dict:
        """读取自动落盘配置。

        返回:
            字典 {"enabled": bool, "directory": str}，
            未保存过时默认开启并使用默认目录
        """
        return {
            "enabled":   self._s.value("log/enabled", True, type=bool),
            "directory": self._s.value("log/directory", "", type=str) or "",
        }

    def save_geometry(self, geometry: bytes) -> None:
        self._s.setValue("window/geometry", geometry)

    def load_geometry(self) -> bytes | None:
        return self._s.value("window/geometry")

    def save_splitter_state(self, state: bytes) -> None:
        self._s.setValue("window/splitter", state)

    def load_splitter_state(self) -> bytes | None:
        return self._s.value("window/splitter")
