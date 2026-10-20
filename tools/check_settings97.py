# -*- coding: utf-8 -*-
"""第97轮后半: 设置页交互回归 —— 只验逻辑, 不碰真实数据目录。

① 进设置页后触发 _apply_page()(刷新链路每次都走), 时间区间条**必须仍然隐藏**;
② 退出设置页后区间条恢复;
③ **局部刷新**: 切主题/切材质/切桌宠主题后, 控件不被销毁(同一个对象还在),
   且选中态/文案同步正确 —— 这就是"不再弹一下"的判据;
④ 桌宠关闭时主题行隐藏、开启时显示(用显隐而非重建);
⑤ 亮/暗 × 毛玻璃/液态/默认 下都能构建成功。
"""
import os, sys, tempfile
sys.dont_write_bytecode = True
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from PySide6.QtWidgets import QApplication
import card_app as ca

ca.SETTINGS_FILE = os.path.join(tempfile.mkdtemp(), "settings.json")
ca.theme_state.update({"glass": False, "frost": True, "frost_static": False, "dark": True,
                       "source": "wb", "window_size": "default", "pet": False,
                       "pet_theme": "v3", "glass_transparency": "balanced",
                       "frost_custom": False, "always_top": True})
ca.refresh_palette()
app = QApplication(sys.argv)

fails = []
def check(name, ok):
    print(("PASS " if ok else "FAIL ") + name, flush=True)
    if not ok:
        fails.append(name)

w = ca.CardWindow()
w.refresh = lambda *a, **k: None
w.apply_styles()
w.show()
app.processEvents()

# ① 进设置页
w.btn_nav_set.click()
app.processEvents()
pg = w.page_settings
check("进设置页后区间条隐藏", not w.range_box.isVisible())
check("设置标题可见", w.lbl_set_title.isVisible())

# 模拟刷新链路: _apply_page() 每次都会被 load_initial/refresh 走到
w._apply_page()
app.processEvents()
check("刷新链路后区间条仍隐藏(泄漏bug)", not w.range_box.isVisible())

# ② 退出
w.btn_nav_wb.click()
app.processEvents()
check("退出后区间条恢复", w.range_box.isVisible())
w.btn_nav_set.click()
app.processEvents()

# ③ 局部刷新: 切主题不销毁控件
mat_btn_before = dict(pg._mat_btns)
lbl_obj = pg._lbl_mat
w.set_dark(False)
app.processEvents()
check("切主题后控件仍是同一对象(不重建)",
      dict(pg._mat_btns) == mat_btn_before and pg._lbl_mat is lbl_obj)
check("切主题后文案仍是材质名(没被清空)", "当前：" in pg._lbl_mat.text())

# 切材质 → 选中态同步
w._set_material("glass")
app.processEvents()
picked = [k for k, b in pg._mat_btns if b.isChecked()]
check("切液态后材质组选中 glass", picked == ["glass"])
w._set_material("frost")
app.processEvents()

# 切桌宠主题 → 网格选中态同步 + 文案同步
pg._set_pet(True)
app.processEvents()
pet_obj = dict(pg._pet_btns)
pg._set_pet_theme("v4")
app.processEvents()
picked = [k for k, b in pg._pet_btns if b.isChecked()]
check("切 v4 后网格选中 v4", picked == ["v4"])
check("切 v4 后副标题更新", "V4Pro" in pg._lbl_pet.text())
check("切桌宠主题后网格控件未重建", dict(pg._pet_btns) == pet_obj)

# ④ 桌宠开关 → 主题行显隐(不重建)
pet_row_vis_on = all(x.isVisible() for x in pg._pet_row)
pg._set_pet(False)
app.processEvents()
pet_row_vis_off = all(not x.isVisible() for x in pg._pet_row)
pg._set_pet(True)
app.processEvents()
pet_row_vis_on2 = all(x.isVisible() for x in pg._pet_row)
check("桌宠开启时主题行可见", pet_row_vis_on and pet_row_vis_on2)
check("桌宠关闭时主题行隐藏", pet_row_vis_off)

# ⑤ 全材质矩阵构建
ok = True
for dark in (True, False):
    for frost, glass in ((True, False), (False, True), (False, False)):
        ca.theme_state["dark"] = dark
        ca.theme_state["frost"] = frost
        ca.theme_state["glass"] = glass
        ca.refresh_palette()
        try:
            pg.refresh()
            app.processEvents()
        except Exception as e:
            ok = False
            print("   build error:", dark, frost, glass, repr(e), flush=True)
check("6 种材质组合刷新无异常", ok)

print("DONE fails=%d" % len(fails))
sys.exit(1 if fails else 0)
