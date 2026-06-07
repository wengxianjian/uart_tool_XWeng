"""生成 macOS 应用图标 app_icon.icns 与 app_icon.png（串口工具风格图标）。

图形与 Windows 版一致：深色圆角底 + UART 方波 + TX(绿)/RX(红) 指示点。
做法：用 PyQt 绘制多尺寸 PNG → 组装标准 .iconset 目录 → 调用系统 iconutil 产出 .icns。
"""
import sys
import os
import shutil
import subprocess
import tempfile

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


# .iconset 需要的 (文件名, 像素尺寸) 列表
ICONSET_SPEC = [
    ("icon_16x16.png",      16),
    ("icon_16x16@2x.png",   32),
    ("icon_32x32.png",      32),
    ("icon_32x32@2x.png",   64),
    ("icon_128x128.png",    128),
    ("icon_128x128@2x.png", 256),
    ("icon_256x256.png",    256),
    ("icon_256x256@2x.png", 512),
    ("icon_512x512.png",    512),
    ("icon_512x512@2x.png", 1024),
]


def main():
    app = QApplication(sys.argv)  # noqa: F841  QPixmap 需要 QApplication

    out_dir = os.path.dirname(os.path.abspath(__file__))

    # 1) 保存 app_icon.png（512，供运行时窗口图标使用）
    png_path = os.path.join(out_dir, "app_icon.png")
    draw_icon(512).save(png_path, "PNG")
    print(f"Saved: {png_path}")

    # 2) 组装 .iconset 目录
    iconset_dir = os.path.join(tempfile.mkdtemp(), "app_icon.iconset")
    os.makedirs(iconset_dir, exist_ok=True)
    for name, size in ICONSET_SPEC:
        draw_icon(size).save(os.path.join(iconset_dir, name), "PNG")
        print(f"  {name}  ({size}x{size})")

    # 3) 调用 iconutil 产出 .icns
    icns_path = os.path.join(out_dir, "app_icon.icns")
    subprocess.run(
        ["iconutil", "-c", "icns", iconset_dir, "-o", icns_path],
        check=True,
    )
    print(f"Saved: {icns_path}")

    shutil.rmtree(os.path.dirname(iconset_dir), ignore_errors=True)


if __name__ == "__main__":
    main()
