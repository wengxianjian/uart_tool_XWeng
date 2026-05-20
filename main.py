import sys
import os
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
from theme import apply_dark_theme
from main_window import MainWindow


def _app_icon() -> QIcon:
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    ico  = os.path.join(base, "app_icon.ico")
    png  = os.path.join(base, "app_icon.png")
    if os.path.exists(ico):
        return QIcon(ico)
    if os.path.exists(png):
        return QIcon(png)
    return QIcon()


def main():
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setApplicationName("UartTool")
    app.setOrganizationName("DIY")
    app.setWindowIcon(_app_icon())

    apply_dark_theme(app)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
