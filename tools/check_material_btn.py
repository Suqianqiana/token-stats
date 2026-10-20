# -*- coding: utf-8 -*-
"""第97轮后半4: 设置页「窗口材质」按钮回归。

浅猫反馈的 bug:
  ① 直接点毛玻璃不生效, 会变成默认;
  ② 液态 / 静态下点毛玻璃, 会切到默认。
根因: _build() 里 lambda 闭包捕获了构建时的 cur_mat, 局部刷新不再重建 → 判据永久陈旧。
     (启动时是毛玻璃 → 切液态 → 再点毛玻璃, 被误判成"点已选中" → 传 None → 掉回默认)
修法: 判据改成点击当时实时读 self._cur_mat()。

本脚本既测"首次点击", 也测**连续切换**的真实路径。
"""
import os, sys, tempfile
sys.dont_write_bytecode = True
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from PySide6.QtWidgets import QApplication
import card_app as ca

ca.SETTINGS_FILE = os.path.join(tempfile.mkdtemp(), "settings.json")
app = QApplication(sys.argv)

fails = []
def check(name, ok, extra=""):
    print(("PASS " if ok else "FAIL ") + name + (("  " + extra) if extra else ""), flush=True)
    if not ok:
        fails.append(name)

def snap():
    t = ca.theme_state
    return (bool(t.get("glass")), bool(t.get("frost")), bool(t.get("frost_static")))

def cur_mat():
    g, f, s = snap()
    return "static" if s else ("frost" if f else ("glass" if g else ""))

def session(init):
    """建一个窗口并进设置页"""
    ca.theme_state.update({"glass": False, "frost": False, "frost_static": False,
                           "dark": True, "source": "wb", "window_size": "default",
                           "pet": False, "pet_theme": "v3",
                           "glass_transparency": "balanced", "frost_custom": False,
                           "always_top": True})
    ca.theme_state.update(init)
    ca.refresh_palette()
    w = ca.CardWindow()
    w.refresh = lambda *a, **k: None
    w.apply_styles()
    w.show()
    w.btn_nav_set.click()
    app.processEvents()
    return w, w.page_settings

def click(pg, key):
    for k, b in pg._mat_btns:
        if k == key:
            b.click()
            app.processEvents()
            return
    raise AssertionError("找不到材质按钮 " + repr(key))

# ① 首次点击(三种初始状态)
for init, name in (({"glass": False, "frost": False, "frost_static": False}, "默认"),
                   ({"glass": True, "frost": False, "frost_static": False}, "液态"),
                   ({"glass": False, "frost": True, "frost_static": True}, "静态")):
    w, pg = session(init)
    click(pg, "frost")
    check("从「%s」点毛玻璃 → 切到毛玻璃" % name, cur_mat() == "frost", str(snap()))

# ② ★连续切换(浅猫描述的真实路径)
w, pg = session({"glass": False, "frost": True, "frost_static": False})   # 启动=毛玻璃
click(pg, "glass")
check("毛玻璃 → 液态", cur_mat() == "glass", str(snap()))
click(pg, "frost")
check("液态 → 毛玻璃(★原 bug: 掉回默认)", cur_mat() == "frost", str(snap()))

w, pg = session({"glass": False, "frost": True, "frost_static": False})   # 启动=毛玻璃
click(pg, "static")
check("毛玻璃 → 静态", cur_mat() == "static", str(snap()))
click(pg, "frost")
check("静态 → 毛玻璃(★原 bug: 掉回默认)", cur_mat() == "frost", str(snap()))

# ③ 再点已选中 = 取消回默认(示意图 hint 的语义)
w, pg = session({"glass": False, "frost": True, "frost_static": False})
click(pg, "frost")
check("已在毛玻璃再点一次 → 取消回默认", cur_mat() == "", str(snap()))

# ④ 按钮选中态必须跟着走(原来点完不高亮, 看着像没生效)
w, pg = session({"glass": True, "frost": False, "frost_static": False})
click(pg, "frost")
picked = [k for k, b in pg._mat_btns if b.isChecked()]
check("点完毛玻璃后按钮选中态同步", picked == ["frost"], str(picked))
check("点完毛玻璃后副标题同步", "毛玻璃" in pg._lbl_mat.text(), pg._lbl_mat.text())

# ⑤ 其它按钮点完也要同步选中态(原来没回调设置页)
w, pg = session({"glass": False, "frost": True, "frost_static": False})
for k, b in pg._tr_btns:
    if k == "crystal":
        b.click()
        app.processEvents()
        break
check("透明度点完选中态同步",
      [k for k, b in pg._tr_btns if b.isChecked()] == ["crystal"]
      and ca.theme_state.get("glass_transparency") == "crystal")

print()
print("DONE fails=%d" % len(fails))
sys.exit(1 if fails else 0)
