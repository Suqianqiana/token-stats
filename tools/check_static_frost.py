# -*- coding: utf-8 -*-
"""第97轮后半14: 静态底纹切换回归 —— 切到 static 必须真的撤掉 DWM 实况模糊。

bug(浅猫: "静态主题配的却是毛玻璃的图"): _set_material 没有调 _sync_acrylic,
启动时 ACRYLIC["on"] 已为 True, 切 static 后没人撤 → paint_frost_fill 直接
return, 静态纹理永远画不出来(重启后才正常)。
"""
import os, sys, tempfile
sys.dont_write_bytecode = True
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from PySide6.QtWidgets import QApplication
import card_app as ca

ca.SETTINGS_FILE = os.path.join(tempfile.mkdtemp(), "s.json")
ca.theme_state.update({"dark": True, "glass": False, "frost": True, "frost_static": False,
                       "source": "wb", "window_size": "default", "pet": False,
                       "pet_theme": "v3", "glass_transparency": "balanced",
                       "frost_custom": False, "always_top": True})
ca.refresh_palette()
app = QApplication(sys.argv)

fails = []
def check(name, ok, extra=""):
    print(("PASS " if ok else "FAIL ") + name + (("  " + extra) if extra else ""), flush=True)
    if not ok:
        fails.append(name)

w = ca.CardWindow()
w.refresh = lambda *a, **k: None
w.apply_styles()
w.show()
app.processEvents()

# 启动即毛玻璃(实时模糊)
check("启动时 ACRYLIC 已挂上(实况毛玻璃)", ca.ACRYLIC["on"] is True)

# 切静态 → 必须撤掉 ACRYLIC, 让静态纹理得以绘制
w._set_material("static")
app.processEvents()
check("切到静态后 ACRYLIC 已撤(静态纹理才会被画)",
      ca.ACRYLIC["on"] is False and ca.theme_state["frost_static"] is True)

# 切回毛玻璃 → 必须重新挂上
w._set_material("frost")
app.processEvents()
check("切回毛玻璃后 ACRYLIC 重新挂上", ca.ACRYLIC["on"] is True)

# 静态 → 毛玻璃 → 静态 连续切换都正确
for i in range(3):
    w._set_material("static"); app.processEvents()
    ok_static = (ca.ACRYLIC["on"] is False)
    w._set_material("frost"); app.processEvents()
    ok_frost = (ca.ACRYLIC["on"] is True)
    if not (ok_static and ok_frost):
        check("连续切换第 %d 轮" % (i + 1), False)
        break
else:
    check("静态⇄毛玻璃 连续 3 轮切换状态都正确", True)

# 明暗切换不应破坏静态态
w._set_material("static")
w.set_dark(False)
app.processEvents()
check("静态模式下切浅色, 仍是静态(ACRYLIC 不复活)",
      ca.ACRYLIC["on"] is False and ca.theme_state["frost_static"] is True)
w.set_dark(True)

print()
print("DONE fails=%d" % len(fails))
sys.exit(1 if fails else 0)
