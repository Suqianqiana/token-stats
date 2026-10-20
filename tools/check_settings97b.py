# -*- coding: utf-8 -*-
"""第97轮后半2: 设置页两项修复验证。

① 卡片不重复(从头到尾只有一套设置卡片);
② 浅色模式下字体/控件配色真的跟上(不再残留深色字色)。
"""
import os, sys, tempfile
sys.dont_write_bytecode = True
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from PySide6.QtWidgets import QApplication, QLabel
import card_app as ca

ca.SETTINGS_FILE = os.path.join(tempfile.mkdtemp(), "settings.json")
ca.theme_state.update({"glass": False, "frost": True, "frost_static": False, "dark": True,
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

w.btn_nav_set.click()
app.processEvents()
pg = w.page_settings

# ① 卡片不重复: 统计 GlassPodFrame 卡片数(应为 4: 外观/窗口与启动/桌宠/关于)
def count_cards(page):
    n = 0
    host = page.area.widget()
    for ch in host.findChildren(ca.GlassPodFrame):
        n += 1
    return n

n1 = count_cards(pg)
w.btn_nav_wb.click()
app.processEvents()
w.btn_nav_set.click()
app.processEvents()
n2 = count_cards(pg)
w.btn_nav_wb.click()
app.processEvents()
w.btn_nav_set.click()
app.processEvents()
n3 = count_cards(pg)
check("设置卡片只有一套(4 张)", n1 == 4 and n2 == 4 and n3 == 4,
      "进出三次: %d/%d/%d" % (n1, n2, n3))

# 顺带: 卡片内分组标题也只出现一次(CardHeader 是自绘控件, 文字在 .text 属性里)
hdrs = [h.text for h in pg.area.widget().findChildren(ca.CardHeader)]
check("分组标题各只出现一次", len(hdrs) == 4 and len(set(hdrs)) == 4, str(hdrs))

# ② 浅色适配: 取一个副标题 label, 切主题后颜色必须变
sub = pg._lbl_mat
dark_ss = sub.styleSheet()
ca.theme_state["dark"] = False
ca.refresh_palette()
w.set_dark(False)
app.processEvents()
light_ss = sub.styleSheet()
check("切浅色后副标题字色已更新", dark_ss != light_ss,
      "%s -> %s" % (dark_ss[:30], light_ss[:30]))

# 且浅色下字色应该比深色下"更暗"(浅底深字)
def lum(ss):
    import re
    m = re.search(r"color:\s*#([0-9a-fA-F]{6})", ss)
    if m:
        h = m.group(1)
        return (int(h[0:2], 16) + int(h[2:4], 16) + int(h[4:6], 16)) / 3.0
    m = re.search(r"color:\s*rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)", ss)
    if m:
        return (int(m.group(1)) + int(m.group(2)) + int(m.group(3))) / 3.0
    return None
ld, ll = lum(dark_ss), lum(light_ss)
check("浅色模式字色更暗(浅底深字)", ld is not None and ll is not None and ll < ld,
      "lum %.0f -> %.0f" % (ld or 0, ll or 0))

# 再切回深色, 应恢复
ca.theme_state["dark"] = True
ca.refresh_palette()
w.set_dark(True)
app.processEvents()
check("切回深色后字色恢复", sub.styleSheet() == dark_ss)

print()
print("DONE fails=%d" % len(fails))
sys.exit(1 if fails else 0)
