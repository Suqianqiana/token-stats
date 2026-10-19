# -*- coding: utf-8 -*-
"""第90轮: 试 **系统级 backdrop 系列 API**(研究里没试过的部分) —— 目标是让 DWM 自己画出
"圆角的实时模糊", 从而同时满足: 缺口无材质 + 外环透桌面 + 边缘无清晰带。

变体(都在背板上, 面板圆角14, 内缩0):
  V1 AccentPolicy(现状基线)
  V2 DWMWA_SYSTEMBACKDROP_TYPE=3 (Acrylic)
  V3 SYSTEMBACKDROP=3 + 系统圆角
  V4 SYSTEMBACKDROP=4 (TransientWindow, Win11 22621+) + 系统圆角
  V5 AccentPolicy + SYSTEMBACKDROP=4 + 系统圆角
  V6 AccentPolicy + 系统圆角(对照: 已知外环会漏)
指标同 sweep: 缺口<6 / 外环<6 / 边缘清晰带<18
"""
import os, sys
sys.dont_write_bytecode = True
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from ctypes import windll, c_int, byref
from PySide6.QtWidgets import QApplication, QWidget, QLabel
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QGuiApplication, QPainter, QColor, QImage, QPixmap
from PySide6.QtTest import QTest
import win_backdrop as wb

DWMWA_SYSTEMBACKDROP_TYPE = 38
DWMSBT_TRANSIENTWINDOW = 4
DWMSBT_MAINWINDOW_ACRYLIC = 3


def set_backdrop(hwnd, mode):
    v = c_int(mode)
    return windll.dwmapi.DwmSetWindowAttribute(int(hwnd), DWMWA_SYSTEMBACKDROP_TYPE,
                                               byref(v), 4)


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


def mean_abs(a, b):
    tot = n = 0
    for yy in range(min(a.height(), b.height())):
        for xx in range(min(a.width(), b.width())):
            pa, pb = a.pixelColor(xx, yy), b.pixelColor(xx, yy)
            tot += (abs(pa.red() - pb.red()) + abs(pa.green() - pb.green())
                    + abs(pa.blue() - pb.blue()))
            n += 3
    return tot / max(1, n)


def lum_std(img):
    vals = []
    for yy in range(0, img.height(), 2):
        for xx in range(0, img.width(), 2):
            c = img.pixelColor(xx, yy)
            vals.append(0.299 * c.red() + 0.587 * c.green() + 0.114 * c.blue())
    m = sum(vals) / len(vals)
    return (sum((v - m) ** 2 for v in vals) / len(vals)) ** 0.5


class Panel(QWidget):
    def __init__(self, rect, radius=14):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setGeometry(*rect)
        self.radius = radius

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setBrush(QColor(255, 255, 255, 150))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(QRectF(10, 10, self.width() - 20, self.height() - 20),
                          self.radius, self.radius)


app = QApplication(sys.argv)
scr = QGuiApplication.primaryScreen()
bg = QWidget()
bg.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
bg.setStyleSheet("background:#000000;")
bg.setGeometry(30, 30, 1520, 1000); bg.show()
st = QLabel(bg); st.setGeometry(0, 0, 1520, 1000)
st.setPixmap(stripe_pixmap(1520, 1000)); st.show()
QTest.qWait(250)
base = scr.grabWindow(0).toImage()
ratio = base.width() / float(scr.geometry().width())

WX, WY, WW, WH = 300, 200, 700, 460
PX, PY, PW, PH = WX + 10, WY + 10, WW - 20, WH - 20


def grab(img, x, y, w, h):
    return img.copy(int(x * ratio), int(y * ratio), int(w * ratio), int(h * ratio))


VARIANTS = [
    ("V1 AccentPolicy", dict(accent=True, backdrop=None, corner=False)),
    ("V2 SYSBACKDROP=3", dict(accent=False, backdrop=DWMSBT_MAINWINDOW_ACRYLIC, corner=False)),
    ("V3 SYSBACKDROP=3+圆角", dict(accent=False, backdrop=DWMSBT_MAINWINDOW_ACRYLIC, corner=True)),
    ("V4 SYSBACKDROP=4+圆角", dict(accent=False, backdrop=DWMSBT_TRANSIENTWINDOW, corner=True)),
    ("V5 Accent+SYSBACKDROP4+圆角", dict(accent=True, backdrop=DWMSBT_TRANSIENTWINDOW, corner=True)),
    ("V6 Accent+圆角(对照)", dict(accent=True, backdrop=None, corner=True)),
]

print("面板 (%d,%d,%d,%d) 圆角14, 背板内缩0" % (PX, PY, PW, PH))
print("%-28s %10s %10s %12s %10s" % ("变体", "缺口", "外环", "边缘清晰带", "面板内(模糊)"))
best = None
for tag, cfg in VARIANTS:
    bd = QWidget()
    bd.setWindowFlags(Qt.FramelessWindowHint | Qt.Window | Qt.WindowStaysOnTopHint)
    bd.setAttribute(Qt.WA_TranslucentBackground)
    bd.setGeometry(PX, PY, PW, PH)
    bd.show()
    QTest.qWait(100)
    hwnd = int(bd.winId())
    if cfg["accent"]:
        wb.apply_acrylic(hwnd, False)
    if cfg["backdrop"] is not None:
        rc = set_backdrop(hwnd, cfg["backdrop"])
        print("   [%s] set_backdrop rc=%s" % (tag, rc), flush=True)
    if cfg["corner"] and wb.effect() is not None:
        wb.effect().set_corner(hwnd, 2)
    pn = Panel((WX, WY, WW, WH)); pn.show(); pn.raise_()
    QTest.qWait(650)
    cur = scr.grabWindow(0).toImage()
    corners = [(PX, PY), (PX + PW - 4, PY), (PX, PY + PH - 4), (PX + PW - 4, PY + PH - 4)]
    notch = sum(mean_abs(grab(base, x, y, 4, 4), grab(cur, x, y, 4, 4))
                for x, y in corners) / 4.0
    rings = [(WX + 60, WY, 300, 9), (WX + 60, WY + WH - 9, 300, 9),
             (WX, WY + 60, 9, 300), (WX + WW - 9, WY + 60, 9, 300)]
    ring = sum(mean_abs(grab(base, x, y, w, h), grab(cur, x, y, w, h))
               for x, y, w, h in rings) / 4.0
    edge = lum_std(grab(cur, WX + 60, PY, 300, 4))
    inner = mean_abs(grab(base, WX + 200, WY + 150, 60, 60),
                     grab(cur, WX + 200, WY + 150, 60, 60))
    ok = (notch < 6 and ring < 6 and edge < 18 and inner > 20)
    print("%-28s %10.1f %10.1f %12.1f %10.1f   %s" % (tag, notch, ring, edge, inner,
                                                      "★达标★" if ok else ""))
    if ok and best is None:
        best = tag
    bd.hide(); pn.hide(); pn.deleteLater(); bd.deleteLater()
    QTest.qWait(120)
print("---")
print("判据: 缺口<6 / 外环<6 / 边缘清晰带<18 / 面板内>20(模糊生效)")
print("达标:", best if best else "无")
