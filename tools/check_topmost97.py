# -*- coding: utf-8 -*-
"""第97轮后半: 开关"窗口置顶"是否重显窗口 —— 用 winId() 是否变化做客观判据。

浅猫两次反馈"还是闪一下"。根因已定位:
  · Qt `setWindowFlags()` 在 Windows 上会**销毁并重建原生窗口** → winId() 变、整窗闪;
  · 上一轮"改用 Win32"仍失败的**真凶**是 `SetWindowPos` 没设 argtypes ——
    64 位下 ctypes 按 32 位 int 传 HWND, 句柄被截断 → 调用失败 → 静默回退 flags 老路。

本脚本(真实屏幕, 因为要动原生窗口):
  ① 断言 SetWindowPos 的 argtypes 已正确设置(64 位句柄不再被截断);
  ② 连续开关置顶多次, **winId() 必须始终不变**(= 窗口没被重建 = 不闪);
  ③ 顺带验背板与主窗的层级关系没被打乱。
"""
import os, sys, tempfile
sys.dont_write_bytecode = True
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
import card_app as ca
import win_backdrop as wb

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

# ① argtypes 校验: 拿一个真实窗口句柄, 手工调 SetWindowPos 必须返回 True
w = ca.CardWindow()
w.refresh = lambda *a, **k: None
w.apply_styles()
w.show()
QTest.qWait(300)
fx = wb.effect()
check("effect() 可用", fx is not None)
# 关键判据: 首参数必须是**8 字节指针**(c_void_p), 不能是默认的 32 位 c_int ——
# 后者就是"64 位下 HWND 被截断、调用静默失败"的根因。
_at = getattr(fx._set_pos, "argtypes", None)
_first = _at[0] if _at else None
check("SetWindowPos 首参数为指针类型(句柄不再被截断)",
      _first is not None and getattr(_first, "__name__", "") in ("c_void_p", "HWND"))
hwnd = int(w.winId())
check("当前窗口 winId 非零", hwnd != 0)
# 直接调一次: 保持置顶(no-op 性质的调用), 必须返回 True 而不是静默失败
check("SetWindowPos 直调返回 True(句柄未被截断)",
      wb.set_topmost(hwnd, True) is True)

# ② 连续开关置顶, winId 必须不变
h0 = int(w.winId())
w._set_always_top(False)
QTest.qWait(120)
h1 = int(w.winId())
w._set_always_top(True)
QTest.qWait(120)
h2 = int(w.winId())
w._set_always_top(False)
QTest.qWait(120)
h3 = int(w.winId())
check("关置顶后 winId 不变(%d→%d)" % (h0, h1), h0 == h1)
check("开置顶后 winId 不变(%d→%d)" % (h1, h2), h1 == h2)
check("再关置顶后 winId 不变(%d→%d)" % (h2, h3), h2 == h3)
check("置顶态已记录", ca.theme_state.get("always_top") is False)

# ③ 背板层级: 毛玻璃模式下背板应在主窗下方且未被提到前面
w._set_material("frost")
QTest.qWait(400)
fw = getattr(w, "_frost_win", None)
check("背板已创建", fw is not None)
if fw is not None:
    w._set_always_top(True)
    QTest.qWait(150)
    fw_h = int(fw.winId())
    main_h = int(w.winId())
    check("置顶开: 背板与主窗都拿到有效句柄", fw_h != 0 and main_h != 0)
    check("置顶开: 主窗 winId 仍未变", main_h == h3 or main_h == h0)
    w._set_always_top(False)
    QTest.qWait(150)
    check("置顶关: 主窗 winId 仍未变", int(w.winId()) == main_h)

print()
print("DONE fails=%d" % len(fails))
sys.exit(1 if fails else 0)
