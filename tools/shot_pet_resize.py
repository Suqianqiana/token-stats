# -*- coding: utf-8 -*-
"""桌宠「调整大小」模式离屏渲染 (第100轮): 虚线框 + 四角手柄 + ✓/✕ + 尺寸胶囊。

按真实窗口尺寸渲染再放大 3 倍拼对照图, 覆盖: 默认尺寸 / 放大中 / 悬停高亮 /
按下态 / 睡觉动画 / 深色主题。
用法: QT_QPA_PLATFORM=offscreen python -B tools/shot_pet_resize.py
"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.dont_write_bytecode = True
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

import card_app as ca
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer, QEvent, QCoreApplication, Qt
from PySide6.QtGui import QImage, QPainter, QColor, QFont, QFontDatabase

app = QApplication.instance() or QApplication([])
for fp in (r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\msyhbd.ttc"):
    if os.path.exists(fp):
        QFontDatabase.addApplicationFont(fp)

SCALE = 3
OUT = os.path.join(BASE, "docs", "_pet_resize_modes.png")


def mk(theme, wh):
    """绕过 __init__ 直接搭一个桌宠窗口(与 shot_pet_v5_seq.py 同手法),
    但第100轮新增的 _rz_* 状态要显式初始化。"""
    w = ca.BallWindow.__new__(ca.BallWindow)
    ca.QWidget.__init__(w, None)
    w.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool)
    w.setAttribute(Qt.WA_TranslucentBackground)
    w.pet_theme = theme
    w.pet_frames = None
    w.pet_seqs = {}
    w._seq_frames = None
    w._loaded_pet_theme = None
    w.pet = True
    w._last_drawn = -1
    w._state = "idle"
    w._si = 0
    w._seq = [0]
    w._tm = QTimer()
    w._idle_t = 0
    w._next_other = 1e18
    w.hover = False
    w._rz_init_state()
    w._ball_wh = wh
    w.pet_frames = w._load_frames()
    w.resize(*wh)
    w.show()
    return w


def grab(w):
    w._last_drawn = -1
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    app.processEvents()
    return w.grab().toImage()


def tile(im, label, sub="", bg=(222, 226, 233)):
    pad = 7
    W = im.width() * SCALE + pad * 2
    H = im.height() * SCALE + pad * 2 + 36
    card = QImage(W, H, QImage.Format_ARGB32)
    card.fill(QColor(*bg))
    p = QPainter(card)
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    p.drawImage(card.rect().adjusted(pad, pad + 32, -pad, -pad),
                im.scaled(im.width() * SCALE, im.height() * SCALE,
                          Qt.IgnoreAspectRatio, Qt.SmoothTransformation))
    p.setPen(QColor(28, 32, 40) if sum(bg) > 300 else QColor(235, 238, 244))
    f = QFont("Microsoft YaHei", 9)
    p.setFont(f)
    p.drawText(pad, 20, label + (("   " + sub) if sub else ""))
    p.end()
    return card


def main():
    cards = []

    def add(w, label, sub="", bg=(222, 226, 233), rz=True, hover=None, press=None):
        if rz:
            w._rz_mode = True
            w._rz_fade = 1.0
            w._rz_hover = hover
            w._rz_press = press
        cards.append(tile(grab(w), label, sub, bg))
        w._rz_mode = False
        w._rz_hover = w._rz_press = None

    # ① 默认尺寸
    w5 = mk("v5", (118, 148))
    add(w5, "① 默认 118×148", "V5 · 待机")

    # ② 放大中
    w5.resize(180, 225)
    add(w5, "② 调整中 180×225", "V5 · 待机")

    # ③ 悬停右下角柄
    add(w5, "③ 悬停右下角柄", "高亮+双箭头光标", hover="br")

    # ④ ✓ 悬停/按下
    add(w5, "④ ✓ 确认键", "悬停态(微放大+提亮)", hover="ok", press="ok")

    # ⑤ ✕ 悬停
    add(w5, "⑤ ✕ 取消键", "悬停态", hover="cancel")

    # ⑥ v3 睡觉动画(第8帧) + 虚线框
    w3 = mk("v3", (160, 200))
    grp = w3.pet_seqs["sleep"][0]
    w3._seq_frames = grp["frames"]
    w3._seq = list(range(len(grp["frames"])))
    w3._si = 3
    w3._state = "sleep"
    add(w3, "⑥ v3 睡觉动作帧 4/8", "动画播放中也可调")

    # ⑦ 深色主题
    ca.theme_state["dark"] = True
    ca.refresh_palette()
    w5b = mk("v5", (180, 225))
    add(w5b, "⑦ 深色主题 180×225", "配色跟随主题", bg=(38, 41, 48))
    ca.theme_state["dark"] = False
    ca.refresh_palette()

    # ⑧ 最小尺寸(布局不能散)
    w5.resize(72, 90)
    add(w5, "⑧ 最小 72×90", "手柄/胶囊不重叠")

    # ⑨ 淡入中(动画中间帧)
    w5.resize(118, 148)
    w5._rz_mode = True
    w5._rz_fade = 0.5
    cards.append(tile(grab(w5), "⑨ 淡入中 (50%)", "~85ms 处"))
    w5._rz_mode = False
    w5._rz_fade = 0.0

    cols = 4
    rows = (len(cards) + cols - 1) // cols
    cw, ch = cards[0].width(), cards[0].height()
    sheet = QImage(cw * cols, ch * rows, QImage.Format_ARGB32)
    sheet.fill(QColor(200, 204, 212))
    p = QPainter(sheet)
    for i, c in enumerate(cards):
        p.drawImage((i % cols) * cw, (i // cols) * ch, c)
    p.end()
    sheet.save(OUT)
    print("->", OUT, sheet.width(), "x", sheet.height(), "tiles =", len(cards))


if __name__ == "__main__":
    main()
