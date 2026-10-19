# -*- coding: utf-8 -*-
"""第89轮: 背板形状穷举实验 —— 找一个"四角干净 + 外环干净 + 无未模糊带"的背板组合。

背景(浅猫要求): 快照方案绝对不用; 技术路线不变(DWM 实时模糊 + 双层窗口)。
矛盾点: DWM 的 AccentPolicy 材质铺满整个窗口矩形, 而面板是圆角 →
        · 背板内缩 → 直边出现"未模糊带"(她不接受)
        · 背板不内缩 → 背板直角在圆角缺口处露出材质(她不接受)
        · 背板用系统圆角 → 带出原生辉光盖住外环(= 又变外框)
⇒ 唯一出路: 让背板**自己变成圆角**且不带辉光。本脚本穷举所有可能组合。

判据(像素差分, 高对比 2px 竖条纹背景):
  缺口/环带 差值≈0 = 露出真实桌面(正确); 差值大 = 材质残留。
"""
import os, sys, tempfile
sys.dont_write_bytecode = True
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from ctypes import windll, wintypes

from PySide6.QtWidgets import QApplication, QWidget
from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtTest import QTest
import win_backdrop as wb

def stripe_pixmap(w, h, period=2):
    """真正的高对比竖条纹(Qt 样式表不支持 repeating-linear-gradient, 必须用 QPainter 画)。

    被模糊 -> 均匀灰(约128); 未被模糊 -> 黑白分明。这样'模糊是否生效'才测得出来。
    """
    from PySide6.QtGui import QImage, QPainter, QColor
    from PySide6.QtGui import QPixmap
    img = QImage(w, h, QImage.Format_RGB32)
    p = QPainter(img)
    x = 0
    while x < w:
        p.fillRect(x, 0, period, h, QColor(0, 0, 0))
        p.fillRect(x + period, 0, period, h, QColor(255, 255, 255))
        x += period * 2
    p.end()
    return QPixmap.fromImage(img)


def mean_abs_diff(a, b):
    tot = n = 0
    for yy in range(min(a.height(), b.height())):
        for xx in range(min(a.width(), b.width())):
            pa, pb = a.pixelColor(xx, yy), b.pixelColor(xx, yy)
            tot += (abs(pa.red() - pb.red()) + abs(pa.green() - pb.green())
                    + abs(pa.blue() - pb.blue()))
            n += 3
    return tot / max(1, n)


def set_round_rgn(hwnd, w, h, r):
    """原生 SetWindowRgn(圆角矩形, 与窗口同尺寸)。"""
    g = windll.gdi32
    rgn = g.CreateRoundRectRgn(0, 0, w, h, r * 2, r * 2)
    rc = windll.user32.SetWindowRgn(int(hwnd), rgn, True)
    return rc


VARIANTS = [
    ("V1 半透明+rgn圆角", dict(translucent=True, rgn=True, corner=False)),
    ("V2 **不透明**+rgn圆角", dict(translucent=False, rgn=True, corner=False)),
    ("V3 半透明+rgn圆角+系统圆角", dict(translucent=True, rgn=True, corner=True)),
    ("V4 不透明+系统圆角", dict(translucent=False, rgn=False, corner=True)),
]

app = QApplication(sys.argv)
scr = QGuiApplication.primaryScreen()

bg = QWidget()
bg.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
bg.setStyleSheet("background:#000000;")
bg.setGeometry(30, 30, 1520, 1000)
bg.show()
from PySide6.QtWidgets import QLabel
st = QLabel(bg); st.setGeometry(0, 0, 1520, 1000)
st.setPixmap(stripe_pixmap(1520, 1000)); st.show()
QTest.qWait(250)
base = scr.grabWindow(0).toImage()

W, H, RAD, PANEL_X, PANEL_Y = 700, 420, 14, 300, 220   # 面板矩形(屏幕坐标)

print("面板矩形: (%d,%d) %dx%d  圆角 %d" % (PANEL_X, PANEL_Y, W, H, RAD))
print("%-26s %10s %10s %10s" % ("变体", "缺口(角尖)", "外环(上)", "面板内(对照)"))
for tag, cfg in VARIANTS:
    bd = QWidget()
    bd.setWindowFlags(Qt.FramelessWindowHint | Qt.Window | Qt.WindowStaysOnTopHint)
    if cfg["translucent"]:
        bd.setAttribute(Qt.WA_TranslucentBackground)
    else:
        bd.setAttribute(Qt.WA_NoSystemBackground)     # 不铺系统底色, 让材质透出
    bd.setGeometry(PANEL_X, PANEL_Y, W, H)
    bd.show()
    QTest.qWait(120)
    hwnd = int(bd.winId())
    if cfg["rgn"]:
        set_round_rgn(hwnd, W, H, RAD)
    _ok = wb.apply_acrylic(hwnd, False)
    print("   [%s] hwnd=%s apply=%s" % (tag, hwnd, _ok), flush=True)
    if cfg["corner"] and wb.effect() is not None:
        wb.effect().set_corner(hwnd, 2)
    QTest.qWait(600)
    cur = scr.grabWindow(0).toImage()
    ratio = cur.width() / float(scr.geometry().width())

    def grab(x, y, w, h):
        return (base.copy(int(x * ratio), int(y * ratio), int(w * ratio), int(h * ratio)),
                cur.copy(int(x * ratio), int(y * ratio), int(w * ratio), int(h * ratio)))

    # 缺口: 面板左上角尖(圆角曲线之外, 直角之内)
    a1, b1 = grab(PANEL_X, PANEL_Y, 4, 4)
    notch = mean_abs_diff(a1, b1)
    # 外环: 面板上方 10px 带(背板若外扩/带辉光就会覆盖这里)
    a2, b2 = grab(PANEL_X + 60, PANEL_Y - 12, 300, 8)
    ring = mean_abs_diff(a2, b2)
    # 面板内对照: 应显著不同(= 模糊生效)
    a3, b3 = grab(PANEL_X + 200, PANEL_Y + 150, 60, 60)
    inner = mean_abs_diff(a3, b3)
    ok = notch < 6 and ring < 6 and inner > 20
    print("%-26s %10.1f %10.1f %10.1f   %s" % (tag, notch, ring, inner,
                                               "★候选★" if ok else ""))
    bd.hide()
    QTest.qWait(120)
print("判据: 缺口<6 且 外环<6 且 面板内>20(模糊生效)")
QTimer_quit = 0
app.quit()
