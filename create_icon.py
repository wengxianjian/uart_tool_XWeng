"""生成 app_icon.png 和 app_icon.ico（串口工具风格图标）。"""
import sys
import struct
import tempfile
import os

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QPixmap, QPainter, QColor, QPen, QPainterPath, QBrush
from PyQt6.QtCore import Qt


def draw_icon(size: int) -> QPixmap:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)

    p = QPainter(pixmap)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    s = float(size)

    # ── 背景：深色圆角方块 ──────────────────────────────
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(QColor("#1e1e2e")))
    radius = s * 0.18
    p.drawRoundedRect(0, 0, int(s), int(s), radius, radius)

    # ── 串口方波（UART 信号形状） ───────────────────────
    pen = QPen(QColor("#89b4fa"))
    pen.setWidthF(max(1.5, s / 9.5))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.MiterJoin)
    p.setPen(pen)

    ml = s * 0.13   # 左边距
    mr = s * 0.13   # 右边距
    hi = s * 0.24   # 高电平 Y
    lo = s * 0.62   # 低电平 Y
    w  = s - ml - mr

    # 波形节点 X 比例（归一化到 0~1）
    xs = [0.00, 0.18, 0.18, 0.42, 0.42, 0.58, 0.58, 0.82, 0.82, 1.00]
    ys = [lo,   lo,   hi,   hi,   lo,   lo,   hi,   hi,   lo,   lo  ]

    path = QPainterPath()
    path.moveTo(ml + xs[0] * w, ys[0])
    for x, y in zip(xs[1:], ys[1:]):
        path.lineTo(ml + x * w, y)
    p.drawPath(path)

    # ── TX / RX 指示点 ──────────────────────────────────
    p.setPen(Qt.PenStyle.NoPen)
    dr = max(2.0, s * 0.062)
    dot_y = s * 0.75

    # TX 绿点
    p.setBrush(QBrush(QColor("#a6e3a1")))
    p.drawEllipse(int(s * 0.30 - dr), int(dot_y), int(dr * 2), int(dr * 2))

    # RX 红点
    p.setBrush(QBrush(QColor("#f38ba8")))
    p.drawEllipse(int(s * 0.70 - dr), int(dot_y), int(dr * 2), int(dr * 2))

    p.end()
    return pixmap


def pixmap_to_png_bytes(pixmap: QPixmap) -> bytes:
    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    tmp.close()
    pixmap.save(tmp.name, "PNG")
    with open(tmp.name, "rb") as f:
        data = f.read()
    os.unlink(tmp.name)
    return data


def build_ico(png_list: list[tuple[int, bytes]]) -> bytes:
    """将多尺寸 PNG 列表打包为 ICO 文件字节。"""
    count = len(png_list)
    # ICONDIR header
    header = struct.pack("<HHH", 0, 1, count)
    offset = 6 + 16 * count

    entries = b""
    data    = b""
    for size, png_data in png_list:
        w = size if size < 256 else 0
        h = size if size < 256 else 0
        entries += struct.pack("<BBBBHHII",
                               w, h, 0, 0, 1, 32,
                               len(png_data), offset + len(data))
        data += png_data

    return header + entries + data


def main():
    app = QApplication(sys.argv)

    sizes = [16, 32, 48, 64, 128, 256]
    png_list: list[tuple[int, bytes]] = []

    for size in sizes:
        pixmap = draw_icon(size)
        png_data = pixmap_to_png_bytes(pixmap)
        png_list.append((size, png_data))
        print(f"  {size}x{size}  {len(png_data):,} bytes")

    # 保存最大尺寸 PNG（256x256）
    out_dir = os.path.dirname(os.path.abspath(__file__))
    png_path = os.path.join(out_dir, "app_icon.png")
    with open(png_path, "wb") as f:
        f.write(png_list[-1][1])
    print(f"Saved: {png_path}")

    # 保存多尺寸 ICO
    ico_path = os.path.join(out_dir, "app_icon.ico")
    with open(ico_path, "wb") as f:
        f.write(build_ico(png_list))
    print(f"Saved: {ico_path}")


if __name__ == "__main__":
    main()
