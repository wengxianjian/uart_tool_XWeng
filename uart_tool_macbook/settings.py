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

    def save_geometry(self, geometry: bytes) -> None:
        self._s.setValue("window/geometry", geometry)

    def load_geometry(self) -> bytes | None:
        return self._s.value("window/geometry")

    def save_splitter_state(self, state: bytes) -> None:
        self._s.setValue("window/splitter", state)

    def load_splitter_state(self) -> bytes | None:
        return self._s.value("window/splitter")
