from dataclasses import dataclass
from PyQt6.QtGui import QColor, QTextCharFormat, QTextCursor
from PyQt6.QtWidgets import QTextEdit
from theme import HIGHLIGHT_COLORS


@dataclass
class HighlightRule:
    keyword: str
    color:   str
    enabled: bool = True


class HighlightManager:
    def __init__(self):
        self._rules: list[HighlightRule] = []
        self._color_index = 0

    def add_keyword(self, keyword: str) -> HighlightRule | None:
        if any(r.keyword == keyword for r in self._rules):
            return None
        color = HIGHLIGHT_COLORS[self._color_index % len(HIGHLIGHT_COLORS)]
        self._color_index += 1
        rule = HighlightRule(keyword=keyword, color=color)
        self._rules.append(rule)
        return rule

    def remove_keyword(self, keyword: str) -> None:
        self._rules = [r for r in self._rules if r.keyword != keyword]

    def get_rules(self) -> list[HighlightRule]:
        return list(self._rules)

    def build_extra_selections(self, document) -> list:
        selections: list[QTextEdit.ExtraSelection] = []
        for rule in self._rules:
            if not rule.enabled or not rule.keyword:
                continue
            fmt = QTextCharFormat()
            fmt.setBackground(QColor(rule.color))
            fmt.setForeground(QColor("#1e1e2e"))
            cursor = QTextCursor(document)
            while True:
                cursor = document.find(rule.keyword, cursor)
                if cursor.isNull():
                    break
                sel = QTextEdit.ExtraSelection()
                sel.cursor = cursor
                sel.format  = fmt
                selections.append(sel)
        return selections
