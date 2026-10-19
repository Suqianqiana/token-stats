# -*- coding: utf-8 -*-
"""第91轮: **横向排列**且与主程序同口径(带 10px 外圈)的对比 demo。

三块并排, 各自 = 迷你主窗口(10px 外圈 + 圆角14 面板 + 半透明罩层) + 下方真·实时模糊背板:
  左: 内缩6 / 无系统圆角   —— 当前版: 四角干净, 但直边有明显"未模糊带"
  中: 内缩0 / 系统圆角     —— 无未模糊带, 四角尖有少量材质(测量 15.5)
  右: 内缩0 / 无系统圆角   —— 无未模糊带, 四角尖材质明显(测量 86.5)
背景是高对比 2px 竖条纹(模糊->灰, 清晰->黑白分明), 便于直接比较。
"""
import os, sys
sys.dont_write_bytecode = True
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from PySide6.QtWidgets import QApplication, QWidget, QLabel, QHBoxLayout, QVBoxLayout
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QGuiApplication, QPainter, QColor, QImage, QPixmap
from PySide6.QtTest import QTest
import win_backdrop as wb

CARD_W, CARD_H, GAP = 330, 260, 28


def stripe_pixmap(w, h, period=2):
    img = QImage(w, h, QImage.Format_RGB32)
    p = QPainter(img)
    x = 0
    while x < w:
        p.fillRect(x, 0, period, h, QColor(0, 0, 0))
        p.fillRect(x + period, 0, period, h, QColor(255, 255, 255))
        x += period * 2
    p.end()
    return QPixmap.fromImage(img)


class Card(QWidget):
    """迷你主窗口: 10px 外圈(不画) + 圆角面板 + 半透明罩层。"""

    def __init__(self, title, radius=14):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.title = title
        self.radius = radius

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setBrush(QColor(255, 255, 255, 150))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(QRectF(10, 10, self.width() - 20, self.height() - 20),
                          self.radius, self.radius)
        p.setPen(QColor("#20242a"))
        p.drawText(QRectF(24, 22, self.width() - 40, 60), Qt.TextWordWrap, self.title)


app = QApplication(sys.argv)
bg = QWidget()
bg.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
bg.setStyleSheet("background:#000000;")
bg.setGeometry(30, 120, 1520, 620); bg.show()
st = QLabel(bg); st.setGeometry(0, 0, 1520, 620); st.setPixmap(stripe_pixmap(1520, 620)); st.show()
QTest.qWait(250)

CFGS = [("左: 内缩6/无系统圆角\n四角干净, 直边有明显未模糊带", 6, False),
        ("中: 内缩0/系统圆角\n无未模糊带, 四角尖少量材质", 0, True),
        ("右: 内缩0/无系统圆角\n无未模糊带, 四角尖材质明显", 0, False)]

demo = QWidget()
demo.setWindowFlags(Qt.FramelessWindowHint | Qt.Window | Qt.WindowStaysOnTopHint)
demo.setAttribute(Qt.WA_TranslucentBackground)
lay = QHBoxLayout(demo); lay.setContentsMargins(20, 20, 20, 20); lay.setSpacing(GAP)
cards = []
for title, inset, corner in CFGS:
    c = Card(title)
    c.setFixedSize(CARD_W, CARD_H)
    lay.addWidget(c)
    cards.append((c, inset, corner))
demo.resize(20 + len(CFGS) * (CARD_W + GAP) + 20, CARD_H + 40)
demo.move(60, 90)
demo.show()
QTest.qWait(350)
dt = demo.frameGeometry().topLeft()

for (c, inset, corner), (title, _i, _c) in zip(cards, CFGS):
    g = c.geometry()
    bd = QWidget()
    bd.setWindowFlags(Qt.FramelessWindowHint | Qt.Window | Qt.WindowStaysOnTopHint)
    bd.setAttribute(Qt.WA_TranslucentBackground)
    bd.setGeometry(dt.x() + g.x() + 10 + inset, dt.y() + g.y() + 10 + inset,
                   max(1, g.width() - 20 - inset * 2), max(1, g.height() - 20 - inset * 2))
    bd.show()
    QTest.qWait(80)
    hwnd = int(bd.winId())
    ok = wb.apply_acrylic(hwnd, False)
    if corner and wb.effect() is not None:
        wb.effect().set_corner(hwnd, 2)
    print("[%s] acrylic=%s" % (title[:1], ok), flush=True)
for _ in range(12):
    app.processEvents()
print("demo 已就绪(横向三块), 保持打开", flush=True)
app.exec()
