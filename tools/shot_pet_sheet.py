# -*- coding: utf-8 -*-
"""第97轮后半13: 生成桌宠 V3 素材的高清拼图(README 用)。

把 pet_v3r 下七组动画各取两帧(首帧 + 中间帧), 透明背景排成一行,
每组下方标注动画名与总帧数 —— 一眼看全整套素材。

用法: python -B tools/shot_pet_sheet.py
"""
import os, sys
sys.dont_write_bytecode = True
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QImage, QPainter, QColor, QFont, QPen
from PySide6.QtCore import Qt, QRectF

ASSETS = os.path.join(ROOT, "assets", "pet_v3r")
OUT = os.path.join(ROOT, "docs", "assets", "previews", "pet_v3_sheet.png")

GROUPS = [("idle", "待机"), ("sidle", "特殊待机"), ("sleep", "睡觉"),
          ("wake", "醒来"), ("drag", "拖拽"), ("click", "点击互动"),
          ("pat", "摸摸头")]

app = QApplication(sys.argv)

FRAME_SCALE = 0.52            # 212x347 -> 约 110x180
PAD = 18
LABEL_H = 30

frames = []
for key, cn in GROUPS:
    d = os.path.join(ASSETS, key)
    if not os.path.isdir(d):
        continue
    files = sorted(f for f in os.listdir(d) if f.lower().endswith(".png"))
    if not files:
        continue
    picks = [files[0], files[len(files) // 2]] if len(files) > 1 else [files[0]]
    frames.append((key, cn, len(files), [os.path.join(d, f) for f in picks]))

if not frames:
    print("没找到素材")
    sys.exit(1)

# 量一帧的尺寸(按第一组第一帧)
probe = QImage(frames[0][3][0])
fw, fh = int(probe.width() * FRAME_SCALE), int(probe.height() * FRAME_SCALE)
gap = 26
col_w = max(fw * 2 + gap, 150)
W = PAD * 2 + col_w * len(frames)
H = PAD * 2 + fh + LABEL_H

img = QImage(W, H, QImage.Format_ARGB32)
img.fill(QColor(0, 0, 0, 0))
p = QPainter(img)
p.setRenderHint(QPainter.Antialiasing)
p.setRenderHint(QPainter.TextAntialiasing)

for i, (key, cn, total, paths) in enumerate(frames):
    x0 = PAD + col_w * i
    for j, fp in enumerate(paths):
        fr = QImage(fp)
        dst = QRectF(x0 + j * (fw + gap), PAD, fw, fh)
        p.drawImage(dst, fr)
    # 标注: 动画键 + 中文名 + 总帧数
    f1 = QFont("Microsoft YaHei UI", 12)
    f1.setBold(True)
    p.setFont(f1)
    p.setPen(QColor(24, 28, 36))
    p.drawText(QRectF(x0, PAD + fh + 2, col_w, 18), Qt.AlignCenter,
               "%s · %s" % (key, cn))
    f2 = QFont("Microsoft YaHei UI", 10)
    p.setFont(f2)
    p.setPen(QColor(110, 118, 132))
    p.drawText(QRectF(x0, PAD + fh + 18, col_w, 16), Qt.AlignCenter,
               "%d 帧" % total)

# 底部一行说明
p.setFont(QFont("Microsoft YaHei UI", 10))
p.setPen(QColor(140, 148, 162))
p.drawText(QRectF(PAD, H - 22, W - PAD * 2, 16), Qt.AlignCenter,
           "pet_v3r · 212×347 高清 PNG · 透明背景 · 共七组动画")
p.end()

img.save(OUT)
print("saved", OUT, img.width(), "x", img.height())
print("组数:", len(frames), "|", ", ".join("%s(%d)" % (k, t) for k, _, t, _ in frames))
