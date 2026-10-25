# -*- coding: utf-8 -*-
"""桌宠真机尺寸渲染对比图 (第99轮): V5 各场景 + v3r 睡觉动画 8 帧。

offscreen 按 118x148 真实窗口渲染, 再放大 3 倍拼一张对照表。
注意: 截图前必须 sendPostedEvents(DeferredDelete) —— 否则 deleteLater 的控件仍会画在原位。
用法: QT_QPA_PLATFORM=offscreen python -B tools/shot_pet_v5_seq.py
"""
import os
import sys
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.dont_write_bytecode = True
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

import card_app as ca
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer, QEvent, QCoreApplication
from PySide6.QtGui import QImage, QPainter, QColor, QFont, QFontDatabase
from PySide6.QtCore import Qt

ca.SN_USE_PLAYWRIGHT = False
TMP = tempfile.mkdtemp(prefix="tstat_shot_")
ca.SN_AUTOSYNC_FILE = os.path.join(TMP, "sn_autosync.json")
ca.SN_CRED_LOG = os.path.join(TMP, "sn_cred.log")
ca.SETTINGS_FILE = os.path.join(TMP, "settings.json")

app = QApplication.instance() or QApplication([])
for fp in (r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\msyhbd.ttc"):
    if os.path.exists(fp):
        QFontDatabase.addApplicationFont(fp)

SCALE = 3
OUT = os.path.join(BASE, "docs", "_pet_v5_seq_render.png")


def mk(theme):
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
    w.pet_frames = w._load_frames()
    w.resize(ca.PET_W, ca.PET_H)
    w.show()
    return w


def grab(w, state, si=None, seq_frames="keep"):
    if seq_frames != "keep":
        w._seq_frames = seq_frames
    w._state = state
    if si is not None:
        w._si = si
    w._last_drawn = -1
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)   # 见教训: 否则旧控件留在原位
    app.processEvents()
    return w.grab().toImage()


def tile(im, label, sub=""):
    pad = 6
    W = ca.PET_W * SCALE + pad * 2
    H = ca.PET_H * SCALE + pad * 2 + 34
    card = QImage(W, H, QImage.Format_ARGB32)
    card.fill(QColor(246, 247, 250))
    p = QPainter(card)
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    p.drawImage(card.rect().adjusted(pad, pad + 30, -pad, -pad),
                im.scaled(ca.PET_W * SCALE, ca.PET_H * SCALE, Qt.IgnoreAspectRatio,
                          Qt.SmoothTransformation))
    p.setPen(QColor(30, 30, 36))
    f = QFont("Microsoft YaHei", 8)
    p.setFont(f)
    p.drawText(pad, 18, label + (("  " + sub) if sub else ""))
    p.end()
    return card


def main():
    cards = []
    # ---- V5 各场景 ----
    w5 = mk("v5")
    for st in ("idle", "sleep", "click", "wake"):
        if st == "idle":
            for i in range(len(w5.pet_frames["idle"])):
                w5._pet_state("idle")
                im = grab(w5, "idle", si=0)
                w5._seq = [i]
                im = grab(w5, "idle")
                cards.append(tile(im, "V5 idle_%02d" % (i + 1)))
        elif st == "sleep":
            w5._pet_state("sleep")
            for i in range(len(w5.pet_frames["sleep"])):
                w5._seq = [i]
                cards.append(tile(grab(w5, "sleep"), "V5 sleep_%02d" % (i + 1)))
        else:
            w5._pet_state(st)
            cards.append(tile(grab(w5, st, si=0), "V5 " + st))
    # ---- v3r 睡觉动画 8 帧 ----
    w3 = mk("v3")
    w3._pet_state("sleep")
    for i in range(8):
        w3._si = i
        cards.append(tile(grab(w3, "sleep"), "V3 睡觉A %d/8" % (i + 1), "seq"))
    # ---- 对照: v3r idle 一张 ----
    w3._seq_frames = None
    w3._pet_state("idle")
    w3._seq = [0]
    cards.append(tile(grab(w3, "idle"), "V3 idle_01", "参考大小"))

    cols = 6
    rows = (len(cards) + cols - 1) // cols
    cw, ch = cards[0].width(), cards[0].height()
    sheet = QImage(cw * cols, ch * rows, QImage.Format_ARGB32)
    sheet.fill(QColor(232, 234, 240))
    p = QPainter(sheet)
    for i, c in enumerate(cards):
        p.drawImage((i % cols) * cw, (i // cols) * ch, c)
    p.end()
    sheet.save(OUT)
    print("->", OUT, sheet.width(), "x", sheet.height())


if __name__ == "__main__":
    main()
