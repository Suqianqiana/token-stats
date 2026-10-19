# -*- coding: utf-8 -*-
"""第88轮: 毛玻璃圆角方案 **多变体对比 demo** —— 浅猫看完弹窗里直接点哪个最自然。

四个变体(圆角半径 / 背板内缩):
  1) 圆角14 内缩6   (现状)
  2) 圆角10 内缩3
  3) 圆角8  内缩3   (Win11 原生圆角感)
  4) 圆角14 内缩0   (背板与面板同尺寸, 对照组: 圆角缺口露材质)
选择会写入 %TEMP%/frost_variant_choice.txt, 供下一轮按她的选择改主程序。
"""
import os, sys, tempfile
sys.dont_write_bytecode = True
sys.path.insert(0, r"C:/Users/a3564/WorkBuddy/2026-08-25-04-20-35/token-stats")
from PySide6.QtWidgets import (QApplication, QWidget, QLabel, QVBoxLayout,
                               QHBoxLayout, QMessageBox)
from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter, QColor, QFont, QPen
import win_backdrop as wb

app = QApplication(sys.argv)

VARIANTS = [("变体1: 圆角14 / 内缩6 (现状)", 14, 6),
            ("变体2: 圆角10 / 内缩3", 10, 3),
            ("变体3: 圆角8 / 内缩3", 8, 3),
            ("变体4: 圆角14 / 内缩0 (对照组)", 14, 0)]

PW, PH, GAP = 420, 220, 26


class Panel(QWidget):
    """模拟主窗口面板: 半透明罩层 + 圆角(半径可变)。"""

    def __init__(self, radius, title):
        super().__init__()
        self.radius = radius
        self.title = title
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowTitle(title)

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setBrush(QColor(255, 255, 255, 150))
        p.setPen(QPen(QColor(255, 255, 255, 60), 1))
        p.drawRoundedRect(self.rect().adjusted(0, 0, -1, -1), self.radius, self.radius)
        p.setPen(QColor("#20242a"))
        p.setFont(QFont("Microsoft YaHei UI", 12, QFont.Bold))
        p.drawText(24, 40, self.title)
        p.setFont(QFont("Microsoft YaHei UI", 9))
        p.drawText(24, 66, "这段文字下面是实时模糊 —— 看圆角与边缘的过渡是否自然")


class Backdrop(QWidget):
    """垫在某块面板正下方的亚克力背板(可指定内缩)。"""

    def __init__(self, title):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.inset = 0
        self.title = title

    def align_to(self, widget):
        g = widget.geometry()
        top = widget.parentWidget().frameGeometry().topLeft()
        self.setGeometry(top.x() + g.x() + self.inset, top.y() + g.y() + self.inset,
                         max(1, g.width() - self.inset * 2), max(1, g.height() - self.inset * 2))


demo = QWidget()
demo.setWindowFlags(Qt.FramelessWindowHint | Qt.Window | Qt.WindowStaysOnTopHint)
demo.setAttribute(Qt.WA_TranslucentBackground)
lay = QVBoxLayout(demo)
lay.setContentsMargins(30, 30, 30, 30)
lay.setSpacing(GAP)
tit = QLabel("毛玻璃圆角方案对比 —— 4 个面板下方都是真·实时模糊, 请重点看【四角】和【直边】")
tit.setStyleSheet("color:#ffe040; font-size:15px; font-weight:bold;")
lay.addWidget(tit)
panels = []
for title, radius, inset in VARIANTS:
    pn = Panel(radius, title)
    pn.setFixedSize(PW, PH)
    lay.addWidget(pn)
    panels.append((pn, inset))
demo.resize(500, 30 + len(VARIANTS) * (PH + GAP) + 20)
demo.move(120, 90)
demo.show()
for _ in range(8):
    app.processEvents()

backdrops = []
for (pn, inset), (title, radius, _i) in zip(panels, VARIANTS):
    bd = Backdrop(title)
    bd.inset = inset
    bd.align_to(pn)
    bd.show()
    ok = wb.apply_acrylic(int(bd.winId()), False)
    print("backdrop[%s] acrylic=%s" % (title[:3], ok), flush=True)
    backdrops.append(bd)
for _ in range(10):
    app.processEvents()

box = QMessageBox(demo)
box.setWindowTitle("毛玻璃圆角方案投票")
box.setText("四个面板下方都是真·实时模糊。\n\n"
            "请看每个面板的【四角】(是否露出材质角)和【直边】(是否有明显未模糊带)，\n"
            "哪个观感最自然？")
btns = []
for label in ("变体1 最自然", "变体2 最自然", "变体3 最自然", "变体4 最自然", "都不行"):
    b = box.addButton(label, QMessageBox.AcceptRole)
    btns.append(b)
box.exec()
pick = "?"
for i, b in enumerate(btns):
    if box.clickedButton() is b:
        pick = str(i + 1) if i < 4 else "0"
        break
out = os.path.join(tempfile.gettempdir(), "frost_variant_choice.txt")
with open(out, "w", encoding="utf-8") as f:
    f.write(pick)
print("choice saved:", pick, "->", out, flush=True)
app.quit()
