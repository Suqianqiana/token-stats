# -*- coding: utf-8 -*-
"""第89轮: (内缩 x 系统圆角) 二维扫描 —— 找"缺口干净 + 外环干净 + 边缘无清晰带"的组合。

与 probe_backdrop_shapes 的区别: 本脚本**带面板**(再现主程序结构: 主窗口 10px 外圈 + 圆角面板 +
半透明罩层), 并新增"边缘清晰带"指标:
  · 边缘清晰带 = 面板直边内侧 0~4px 条带的亮度标准差 —— 高=露出未模糊的桌面(她不接受);
                                                   低=模糊一直铺到边缘(理想)
指标: 缺口≈0(圆角缺口无材质) / 外环≈0(10px 环带透出桌面) / 边缘标准差低
"""
import os, sys
sys.dont_write_bytecode = True
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from PySide6.QtWidgets import QApplication, QWidget, QLabel
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import (QGuiApplication, QPainter, QColor, QImage, QPixmap)
from PySide6.QtTest import QTest
import win_backdrop as wb


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


def mean_abs_diff(a, b):
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
    if not vals:
        return 0.0
    m = sum(vals) / len(vals)
    return (sum((v - m) ** 2 for v in vals) / len(vals)) ** 0.5


class Panel(QWidget):
    """再现主窗口: 10px 外圈(不画) + 圆角面板 + 半透明罩层。"""

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
bg.setGeometry(30, 30, 1520, 1000)
bg.show()
st = QLabel(bg); st.setGeometry(0, 0, 1520, 1000)
st.setPixmap(stripe_pixmap(1520, 1000)); st.show()
QTest.qWait(250)
base = scr.grabWindow(0).toImage()
ratio = base.width() / float(scr.geometry().width())

WX, WY, WW, WH = 300, 200, 700, 460       # 主窗口矩形(面板 = 内缩10)
panel_rect = (WX + 10, WY + 10, WW - 20, WH - 20)


def grab(img, x, y, w, h):
    return img.copy(int(x * ratio), int(y * ratio), int(w * ratio), int(h * ratio))


print("主窗口 (%d,%d,%d,%d)  面板圆角14  外圈10px" % (WX, WY, WW, WH))
print("%-8s %-6s %10s %10s %12s" % ("内缩", "系统圆角", "缺口", "外环", "边缘清晰带"))
best = None
for corner in (0, 1):
    for inset in (0, 2, 4, 6, 8):
        bd = QWidget()
        bd.setWindowFlags(Qt.FramelessWindowHint | Qt.Window | Qt.WindowStaysOnTopHint)
        bd.setAttribute(Qt.WA_TranslucentBackground)
        bx, by = panel_rect[0] + inset, panel_rect[1] + inset
        bw, bh = panel_rect[2] - inset * 2, panel_rect[3] - inset * 2
        bd.setGeometry(bx, by, bw, bh)
        bd.show()
        QTest.qWait(100)
        wb.apply_acrylic(int(bd.winId()), False)
        if corner and wb.effect() is not None:
            wb.effect().set_corner(int(bd.winId()), 2)
        pn = Panel((WX, WY, WW, WH))
        pn.show()
        pn.raise_()
        QTest.qWait(600)
        cur = scr.grabWindow(0).toImage()
        # 缺口: 四个角尖(圆角曲线之外), 取平均
        corners = [(WX + 10, WY + 10), (WX + WW - 14, WY + 10),
                   (WX + 10, WY + WH - 14), (WX + WW - 14, WY + WH - 14)]
        notch = sum(mean_abs_diff(grab(base, x, y, 4, 4), grab(cur, x, y, 4, 4))
                    for x, y in corners) / 4.0
        # 外环: 四条边中段(10px 环带), 取平均
        rings = [(WX + 60, WY, 300, 9), (WX + 60, WY + WH - 9, 300, 9),
                 (WX, WY + 60, 9, 300), (WX + WW - 9, WY + 60, 9, 300)]
        ring = sum(mean_abs_diff(grab(base, x, y, w, h), grab(cur, x, y, w, h))
                   for x, y, w, h in rings) / 4.0
        # 边缘清晰带: 面板上边内侧 0~4px(宽 300)的亮度标准差 —— 高=露出未模糊桌面
        strip = grab(cur, WX + 60, WY + 10, 300, 4)
        edge = lum_std(strip)
        ok = (notch < 6 and ring < 6 and edge < 18)
        print("%-8d %-6d %10.1f %10.1f %12.1f   %s" % (inset, corner, notch, ring, edge,
                                                       "★达标★" if ok else ""))
        if ok and (best is None or inset < best[0]):
            best = (inset, corner, notch, ring, edge)
        bd.hide(); pn.hide(); pn.deleteLater(); bd.deleteLater()
        QTest.qWait(120)
print("---")
print("判据: 缺口<6(无材质角) / 外环<6(透出桌面) / 边缘清晰带<18(模糊铺到边缘)")
print("最佳:", best if best else "无达标组合")
