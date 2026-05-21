import serial
from PyQt6.QtCore import QThread, pyqtSignal


class SerialWorker(QThread):
    data_received  = pyqtSignal(bytes)
    error_occurred = pyqtSignal(str)
    disconnected   = pyqtSignal()

    def __init__(self, serial_port: serial.Serial, parent=None):
        super().__init__(parent)
        self._port    = serial_port
        self._running = False

    def run(self) -> None:
        self._running = True
        while self._running:
            try:
                if self._port.in_waiting > 0:
                    data = self._port.read(self._port.in_waiting)
                    if data:
                        self.data_received.emit(data)
                self.msleep(10)
            except serial.SerialException as e:
                self.error_occurred.emit(str(e))
                self.disconnected.emit()
                break
            except Exception as e:
                self.error_occurred.emit(str(e))
                self.disconnected.emit()
                break

    def stop(self) -> None:
        self._running = False
        self.wait(2000)
