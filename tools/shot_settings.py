# -*- coding: utf-8 -*-
"""第95轮: 真实渲染设置页面并截图(暗/亮 × 毛玻璃/液态), 供浅猫评审。

必须在**真实屏幕**上跑(offscreen 没有 DWM 材质)。
"""
import os, sys, tempfile
sys.dont_write_bytecode = True
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtTest import QTest
import card_app as ca

OUT = os.path.join(ROOT, "docs", "screenshots")
os.makedirs(OUT, exist_ok=True)

ca.SETTINGS_FILE = os.path.join(tempfile.gettempdir(), "shot_settings.json")
ca.theme_state.update({"glass": False, "frost": True, "frost_static": False, "dark": True,
                       "source": "wb", "window_size": "default", "pet": False,
                       "pet_theme": "v3", "glass_transparency": "balanced",
                       "frost_custom": False})
ca.refresh_palette()
app = QApplication(sys.argv)
scr = QGuiApplication.primaryScreen()

w = ca.CardWindow()
w.refresh = lambda *a, **k: None
w.apply_styles()
w.apply_size_mode("default", save=False)
w.move(120, 60)
w.show()
QTest.qWait(600)


def shot(tag):
    QTest.qWait(700)
    img = scr.grabWindow(0).toImage()
    r = img.width() / float(scr.geometry().width())
    g = w.geometry()
    pad = 8
    x = int((g.x() - pad) * r); y = int((g.y() - pad) * r)
    ww = int((g.width() + pad * 2) * r); hh = int((g.height() + pad * 2) * r)
    crop = img.copy(x, y, ww, hh)
    path = os.path.join(OUT, "settings_%s.png" % tag)
    crop.save(path)
    print("saved", path, crop.width(), "x", crop.height(), flush=True)


# 切到设置页
w.btn_settings.setChecked(True)
QTest.qWait(400)

shot("dark_frost")
w.set_dark(False)
shot("light_frost")
w._set_material("glass")
shot("light_glass")
w.set_dark(True)
shot("dark_glass")
print("DONE")
