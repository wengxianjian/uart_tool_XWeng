import serial
import serial.tools.list_ports
from dataclasses import dataclass, field


@dataclass
class SerialConfig:
    port:     str   = ""
    baudrate: int   = 115200
    bytesize: int   = 8
    parity:   str   = "N"
    stopbits: float = 1.0
    xonxoff:  bool  = False
    rtscts:   bool  = False
    timeout:  float = 0.1


class SerialManager:
    def __init__(self):
        self._port: serial.Serial | None = None

    @staticmethod
    def scan_ports() -> list[str]:
        # macOS 串口设备为 /dev/cu.*（CH340 通常是 /dev/cu.wchusbserial*）。
        # 排除蓝牙等无关项；若过滤后为空则回退为全部，保证不漏。
        ports = serial.tools.list_ports.comports()
        devices = [p.device for p in ports]
        filtered = [d for d in devices if "Bluetooth" not in d]
        return sorted(filtered if filtered else devices)

    def connect(self, config: SerialConfig) -> serial.Serial:
        self._port = serial.Serial(
            port     = config.port,
            baudrate = config.baudrate,
            bytesize = config.bytesize,
            parity   = config.parity,
            stopbits = config.stopbits,
            xonxoff  = config.xonxoff,
            rtscts   = config.rtscts,
            timeout  = config.timeout,
        )
        return self._port

    def disconnect(self) -> None:
        if self._port and self._port.is_open:
            self._port.close()
        self._port = None

    def send(self, data: bytes) -> None:
        if self._port and self._port.is_open:
            self._port.write(data)

    @property
    def is_connected(self) -> bool:
        return self._port is not None and self._port.is_open
