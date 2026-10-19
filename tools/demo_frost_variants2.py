# -*- coding: utf-8 -*-
"""第88轮 demo v2: 三方案 —— 让背板用**系统圆角**, 或把未模糊带压到极限窄。

变体1(新): 背板走 Win11 原生圆角(set_corner), 无内缩 + 面板圆角 8
            → 预期: 无未模糊带、无缺口材质(背板本身是圆的)
变体2(新): 背板走 Win11 原生圆角, 无内缩 + 面板圆角 14
变体3(新): 背板内缩仅 2px + 面板圆角 8
            → 预期: 未模糊带 2px(几乎不可见), 缺口干净
选择写入 %TEMP%/frost_variant_choice.txt
"""
import os, sys, tempfile
sys.dont_write_bytecode = True
sys.path.insert(0, r"C:/Users/a3564/WorkBuddy/2026-08-25-04-20-35/token-stats")
from PySide6.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout, QMessageBox
from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter, QColor, QFont, QPen
import win_backdrop as wb

app = QApplication(sys.argv)

VARIANTS = [("变体1: 系统圆角背板 / 面板圆角8 / 内缩0", 8, 0, True),
            ("变体2: 系统圆角背板 / 面板圆角14 / 内缩0", 14, 0, True),
            ("变体3: 直角背板 / 面板圆角8 / 内缩2", 8, 2, False)]

PW, PH, GAP = 420, 210, 26


class Panel(QWidget):
    def __init__(self, radius, title):
        super().__init__()
        self.radius = radius
        self.title = title
        self.setAttribute(Qt.WA_TranslucentBackground)

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setBrush(QColor(255, 255, 255, 150))
        p.setPen(QPen(QColor(255, 255, 255, 60), 1))
        p.drawRoundedRect(self.rect().adjusted(0, 0, -1, -1), self.radius, self.radius)
        p.setPen(QColor("#20242a"))
        p.setFont(QFont("Microsoft YaHei UI", 12, QFont.Bold))
        p.drawText(22, 36, self.title)
        p.setFont(QFont("Microsoft YaHei UI", 9))
        p.drawText(22, 62, "重点看: 四角是否干净 + 直边有没有未模糊带 + 有没有描边")


class Backdrop(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.inset = 0

    def align_to(self, w):
        g = w.geometry()
        t = w.parentWidget().frameGeometry().topLeft()
        self.setGeometry(t.x() + g.x() + self.inset, t.y() + g.y() + self.inset,
                         max(1, g.width() - self.inset * 2), max(1, g.height() - self.inset * 2))


demo = QWidget()
demo.setWindowFlags(Qt.FramelessWindowHint | Qt.Window | Qt.WindowStaysOnTopHint)
demo.setAttribute(Qt.WA_TranslucentBackground)
lay = QVBoxLayout(demo)
lay.setContentsMargins(30, 26, 30, 30)
lay.setSpacing(GAP)
tit = QLabel("毛玻璃圆角 demo v2 —— 三块下方都是真·实时模糊")
tit.setStyleSheet("color:#ffe040; font-size:15px; font-weight:bold;")
lay.addWidget(tit)
panels = []
for title, radius, inset, syscorner in VARIANTS:
    pn = Panel(radius, title)
    pn.setFixedSize(PW, PH)
    lay.addWidget(pn)
    panels.append((pn, inset, syscorner))
demo.resize(500, 26 + len(VARIANTS) * (PH + GAP) + 20)
demo.move(120, 90)
demo.show()
for _ in range(8):
    app.processEvents()

fx = wb.effect()
for (pn, inset, syscorner), (title, _r, _i, _s) in zip(panels, VARIANTS):
    bd = Backdrop()
    bd.inset = inset
    bd.align_to(pn)
    bd.show()
    hwnd = int(bd.winId())
    ok = wb.apply_acrylic(hwnd, False)
    if syscorner and fx is not None:
        fx.set_corner(hwnd, 2)          # Win11 原生圆角
    print("backdrop[%s] acrylic=%s syscorner=%s" % (title[:3], ok, syscorner), flush=True)
for _ in range(10):
    app.processEvents()

box = QMessageBox(demo)
box.setWindowTitle("毛玻璃圆角方案投票 v2")
box.setText("三块下方都是真·实时模糊。\n\n"
            "请看【四角】(是否露材质角/是否有描边)和【直边】(是否有未模糊带)。\n"
            "哪个观感最自然？若都不行请点最下面那个，我再换方案。")
btns = []
for label in ("变体1 最自然", "变体2 最自然", "变体3 最自然", "都不行"):
    btns.append(box.addButton(label, QMessageBox.AcceptRole))
box.exec()
pick = "?"
for i, b in enumerate(btns):
    if box.clickedButton() is b:
        pick = str(i + 1) if i < 3 else "0"
        break
out = os.path.join(tempfile.gettempdir(), "frost_variant_choice.txt")
with open(out, "w", encoding="utf-8") as f:
    f.write(pick)
print("choice saved:", pick, "->", out, flush=True)
app.quit()
