from PyQt6.QtGui import QPalette, QColor
from PyQt6.QtWidgets import QApplication

COLOR_BG_DARK       = "#1e1e2e"
COLOR_BG_PANEL      = "#2a2a3e"
COLOR_BG_INPUT      = "#16213e"
COLOR_TEXT_PRIMARY  = "#cdd6f4"
COLOR_TEXT_DIM      = "#6c7086"
COLOR_ACCENT        = "#89b4fa"
COLOR_SUCCESS       = "#a6e3a1"
COLOR_ERROR         = "#f38ba8"
COLOR_HIGHLIGHT_BG  = "#313244"

HIGHLIGHT_COLORS = [
    "#f9e2af",
    "#89dceb",
    "#cba6f7",
    "#a6e3a1",
    "#fab387",
    "#f38ba8",
]


def apply_dark_theme(app: QApplication) -> None:
    _apply_palette(app)
    app.setStyleSheet(_build_stylesheet())


def _apply_palette(app: QApplication) -> None:
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window,          QColor(COLOR_BG_DARK))
    palette.setColor(QPalette.ColorRole.WindowText,      QColor(COLOR_TEXT_PRIMARY))
    palette.setColor(QPalette.ColorRole.Base,            QColor(COLOR_BG_INPUT))
    palette.setColor(QPalette.ColorRole.AlternateBase,   QColor(COLOR_BG_PANEL))
    palette.setColor(QPalette.ColorRole.Text,            QColor(COLOR_TEXT_PRIMARY))
    palette.setColor(QPalette.ColorRole.Button,          QColor(COLOR_BG_PANEL))
    palette.setColor(QPalette.ColorRole.ButtonText,      QColor(COLOR_TEXT_PRIMARY))
    palette.setColor(QPalette.ColorRole.Highlight,       QColor(COLOR_ACCENT))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(COLOR_BG_DARK))
    palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(COLOR_TEXT_DIM))
    palette.setColor(QPalette.ColorRole.BrightText,      QColor(COLOR_ERROR))
    palette.setColor(QPalette.ColorRole.Link,            QColor(COLOR_ACCENT))
    app.setPalette(palette)


def _build_stylesheet() -> str:
    return f"""
        QMainWindow, QWidget {{
            background-color: {COLOR_BG_DARK};
            color: {COLOR_TEXT_PRIMARY};
            font-family: "Consolas", "Fira Code", "Cascadia Code", monospace;
            font-size: 13px;
        }}
        QGroupBox {{
            border: 1px solid {COLOR_ACCENT};
            border-radius: 6px;
            margin-top: 10px;
            padding: 8px 6px 6px 6px;
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            subcontrol-position: top left;
            left: 10px;
            color: {COLOR_ACCENT};
            font-weight: bold;
        }}
        QPushButton {{
            background-color: {COLOR_BG_PANEL};
            border: 1px solid {COLOR_ACCENT};
            border-radius: 4px;
            padding: 4px 12px;
            color: {COLOR_TEXT_PRIMARY};
            min-height: 22px;
        }}
        QPushButton:hover {{
            background-color: {COLOR_ACCENT};
            color: {COLOR_BG_DARK};
        }}
        QPushButton:pressed {{
            background-color: #6c9fd8;
        }}
        QPushButton:disabled {{
            border-color: {COLOR_TEXT_DIM};
            color: {COLOR_TEXT_DIM};
        }}
        QPushButton#connectBtn[connected="true"] {{
            border-color: {COLOR_ERROR};
            color: {COLOR_ERROR};
        }}
        QPushButton#connectBtn[connected="true"]:hover {{
            background-color: {COLOR_ERROR};
            color: {COLOR_BG_DARK};
        }}
        QComboBox {{
            background-color: {COLOR_BG_INPUT};
            border: 1px solid {COLOR_TEXT_DIM};
            border-radius: 4px;
            padding: 3px 6px;
            color: {COLOR_TEXT_PRIMARY};
            min-height: 22px;
        }}
        QComboBox:focus {{
            border-color: {COLOR_ACCENT};
        }}
        QComboBox::drop-down {{
            border: none;
            width: 20px;
        }}
        QComboBox::down-arrow {{
            width: 8px;
            height: 8px;
        }}
        QComboBox QAbstractItemView {{
            background-color: {COLOR_BG_PANEL};
            border: 1px solid {COLOR_ACCENT};
            selection-background-color: {COLOR_ACCENT};
            selection-color: {COLOR_BG_DARK};
            outline: none;
        }}
        QLineEdit {{
            background-color: {COLOR_BG_INPUT};
            border: 1px solid {COLOR_TEXT_DIM};
            border-radius: 4px;
            padding: 3px 6px;
            color: {COLOR_TEXT_PRIMARY};
            min-height: 22px;
        }}
        QLineEdit:focus {{
            border-color: {COLOR_ACCENT};
        }}
        QSpinBox {{
            background-color: {COLOR_BG_INPUT};
            border: 1px solid {COLOR_TEXT_DIM};
            border-radius: 4px;
            padding: 3px 6px;
            color: {COLOR_TEXT_PRIMARY};
            min-height: 22px;
        }}
        QSpinBox:focus {{
            border-color: {COLOR_ACCENT};
        }}
        QTextEdit {{
            background-color: {COLOR_BG_INPUT};
            border: 1px solid {COLOR_TEXT_DIM};
            border-radius: 4px;
            color: {COLOR_TEXT_PRIMARY};
            selection-background-color: {COLOR_HIGHLIGHT_BG};
        }}
        QTextEdit:focus {{
            border-color: {COLOR_ACCENT};
        }}
        QScrollBar:vertical {{
            background: {COLOR_BG_PANEL};
            width: 8px;
            border-radius: 4px;
            margin: 0;
        }}
        QScrollBar::handle:vertical {{
            background: {COLOR_TEXT_DIM};
            border-radius: 4px;
            min-height: 20px;
        }}
        QScrollBar::handle:vertical:hover {{
            background: {COLOR_ACCENT};
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0;
        }}
        QScrollBar:horizontal {{
            background: {COLOR_BG_PANEL};
            height: 8px;
            border-radius: 4px;
            margin: 0;
        }}
        QScrollBar::handle:horizontal {{
            background: {COLOR_TEXT_DIM};
            border-radius: 4px;
            min-width: 20px;
        }}
        QScrollBar::handle:horizontal:hover {{
            background: {COLOR_ACCENT};
        }}
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
            width: 0;
        }}
        QStatusBar {{
            background-color: {COLOR_BG_PANEL};
            border-top: 1px solid {COLOR_TEXT_DIM};
        }}
        QStatusBar QLabel {{
            padding: 2px 8px;
        }}
        QCheckBox {{
            spacing: 6px;
        }}
        QCheckBox::indicator {{
            border: 1px solid {COLOR_ACCENT};
            border-radius: 3px;
            width: 14px;
            height: 14px;
            background: {COLOR_BG_INPUT};
        }}
        QCheckBox::indicator:checked {{
            background: {COLOR_ACCENT};
        }}
        QCheckBox::indicator:hover {{
            border-color: {COLOR_TEXT_PRIMARY};
        }}
        QSplitter::handle {{
            background: {COLOR_TEXT_DIM};
        }}
        QSplitter::handle:vertical {{
            height: 2px;
        }}
        QSplitter::handle:horizontal {{
            width: 2px;
        }}
        QMenuBar {{
            background-color: {COLOR_BG_PANEL};
            border-bottom: 1px solid {COLOR_TEXT_DIM};
        }}
        QMenuBar::item {{
            padding: 4px 10px;
        }}
        QMenuBar::item:selected {{
            background-color: {COLOR_ACCENT};
            color: {COLOR_BG_DARK};
        }}
        QMenu {{
            background-color: {COLOR_BG_PANEL};
            border: 1px solid {COLOR_ACCENT};
        }}
        QMenu::item {{
            padding: 4px 24px;
        }}
        QMenu::item:selected {{
            background-color: {COLOR_ACCENT};
            color: {COLOR_BG_DARK};
        }}
        QMenu::separator {{
            height: 1px;
            background: {COLOR_TEXT_DIM};
            margin: 2px 0;
        }}
        QListWidget {{
            background-color: {COLOR_BG_INPUT};
            border: 1px solid {COLOR_TEXT_DIM};
            border-radius: 4px;
        }}
        QListWidget::item {{
            padding: 4px;
            border-radius: 3px;
        }}
        QListWidget::item:selected {{
            background-color: {COLOR_HIGHLIGHT_BG};
        }}
        QToolTip {{
            background-color: {COLOR_BG_PANEL};
            color: {COLOR_TEXT_PRIMARY};
            border: 1px solid {COLOR_ACCENT};
            padding: 4px;
        }}
        QLabel#statusConnected {{
            color: {COLOR_SUCCESS};
            font-weight: bold;
        }}
        QLabel#statusDisconnected {{
            color: {COLOR_TEXT_DIM};
        }}
    """
