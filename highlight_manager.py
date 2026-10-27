from dataclasses import dataclass
from PyQt6.QtGui import QColor, QTextCharFormat, QTextCursor
from theme import HIGHLIGHT_COLORS


@dataclass
class HighlightRule:
    keyword: str
    color:   str
    enabled: bool = True


class HighlightManager:
    # 单次调用最多应用的高亮匹配数，避免极端数据下格式化操作拖住 UI 线程
    MAX_APPLY_MATCHES = 2000

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

    def apply_highlights(self, document, start: int = 0, end: int = -1) -> None:
        """把常驻关键词高亮直接写入文档的字符格式。

        参数:
            document: 目标文档（QTextDocument）
            start:    扫描起始字符位置，用于只处理本次新增的文本片段
            end:      扫描结束字符位置（不含），-1 表示直到文档末尾
        说明:
            高亮直接写入字符格式而不是使用 ExtraSelection，避免每次追加文本时
            调整大量选区光标；同时用 EditBlock 把多次格式修改合并成一次布局更新，
            否则每个匹配都会触发一次文档重排版，高数据量下会明显拖慢界面。
        """
        rules = [r for r in self._rules if r.enabled and r.keyword]
        if not rules:
            return

        max_pos = max(document.characterCount() - 1, 0)
        begin   = min(max(start, 0), max_pos)
        limit   = end if end >= 0 else max_pos
        if begin >= limit:
            return

        block   = QTextCursor(document)
        applied = 0
        block.beginEditBlock()
        try:
            for rule in rules:
                fmt = QTextCharFormat()
                fmt.setBackground(QColor(rule.color))
                fmt.setForeground(QColor("#1e1e2e"))
                cursor = QTextCursor(document)
                cursor.setPosition(begin)
                while applied < self.MAX_APPLY_MATCHES:
                    cursor = document.find(rule.keyword, cursor)
                    if cursor.isNull():
                        break
                    # 超出本次扫描范围则停止，避免每次追加都扫描整篇文档
                    if cursor.selectionStart() >= limit:
                        break
                    cursor.mergeCharFormat(fmt)
                    applied += 1
        finally:
            block.endEditBlock()

    def clear_highlights(self, document) -> None:
        """清除文档中已有的高亮字符格式。

        参数:
            document: 目标文档（QTextDocument）
        """
        cursor = QTextCursor(document)
        cursor.select(QTextCursor.SelectionType.Document)
        cursor.setCharFormat(QTextCharFormat())
