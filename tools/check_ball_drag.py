# -*- coding: utf-8 -*-
"""第97轮后半13: 悬浮球拖动回归 —— 桌宠开/关两种形态都必须能拖, 且拖动不弹面板。

bug: mouseMoveEvent 里 `_moved` 的置位带了 `and self.pet`, 关掉桌宠后 `_moved`
永远是 False → move() 不执行(拖不动), 且松手时 not _moved 成立会误弹面板。
"""
import os, sys, tempfile
sys.dont_write_bytecode = True
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QPointF, QPoint
from PySide6.QtGui import QMouseEvent
from PySide6.QtCore import QEvent

ca = None
import card_app as ca

ca.SETTINGS_FILE = os.path.join(tempfile.mkdtemp(), "s.json")
ca.theme_state.update({"dark": True, "glass": False, "frost": False, "source": "wb",
                       "window_size": "default", "pet": False, "pet_theme": "v3",
                       "glass_transparency": "balanced", "always_top": True})
ca.refresh_palette()
app = QApplication(sys.argv)

fails = []
def check(name, ok, extra=""):
    print(("PASS " if ok else "FAIL ") + name + (("  " + extra) if extra else ""), flush=True)
    if not ok:
        fails.append(name)


def mk_event(etype, gpos, btn=Qt.LeftButton):
    ev = QMouseEvent(etype, QPointF(10, 10), QPointF(10, 10), gpos,
                     btn, btn, Qt.NoModifier)
    return ev


def try_drag(w, dx=60, dy=40):
    """模拟一次拖动: 按下 → 移动若干步 → 返回是否真的移动了。"""
    g0 = QPoint(500, 400)
    w.mousePressEvent(mk_event(QEvent.MouseButtonPress, QPointF(g0)))
    g1 = QPoint(g0.x() + dx // 2, g0.y() + dy // 2)
    w.mouseMoveEvent(mk_event(QEvent.MouseMove, QPointF(g1)))
    g2 = QPoint(g0.x() + dx, g0.y() + dy)
    w.mouseMoveEvent(mk_event(QEvent.MouseMove, QPointF(g2)))
    moved = w._moved
    # 松手(记录弹窗次数)
    w._trigger_popup = lambda: setattr(w, "_popup_fired", True)
    w.mouseReleaseEvent(mk_event(QEvent.MouseButtonRelease, QPointF(g2)))
    return moved, getattr(w, "_popup_fired", False)


ball = ca.BallWindow if hasattr(ca, "BallWindow") else None
if ball is None:
    # 悬浮球类名可能不同, 找带 _trigger_popup 的类
    for nm in dir(ca):
        obj = getattr(ca, nm)
        if isinstance(obj, type) and hasattr(obj, "_trigger_popup") and hasattr(obj, "set_pet"):
            ball = obj
            print("悬浮球类:", nm, flush=True)
            break

w = ball(None)
w.set_pet(False)          # 关闭桌宠 = 悬浮球形态
w.show()
app.processEvents()
w.move(500, 400)
app.processEvents()

x0, y0 = w.x(), w.y()
moved, popup = try_drag(w)
app.processEvents()
dx, dy = w.x() - x0, w.y() - y0
check("悬浮球形态: _moved 被置位", moved)
check("悬浮球形态: 窗口真的移动了", (dx, dy) != (0, 0), "位移=(%d,%d)" % (dx, dy))
check("悬浮球形态: 拖动后不弹面板", not popup)

# 桌宠形态(如果素材在)
w.set_pet(True)
app.processEvents()
x0, y0 = w.x(), w.y()
moved2, popup2 = try_drag(w)
app.processEvents()
check("桌宠形态: 仍可拖动(未破坏原行为)", moved2 and (w.x(), w.y()) != (x0, y0))
check("桌宠形态: 拖动后不弹面板", not popup2)

# 单击仍能弹面板(非桌宠)
w.set_pet(False)
app.processEvents()
w._trigger_popup = lambda: setattr(w, "_popup_fired", True)
g = QPoint(600, 450)
w.mousePressEvent(mk_event(QEvent.MouseButtonPress, QPointF(g)))
w.mouseReleaseEvent(mk_event(QEvent.MouseButtonRelease, QPointF(g)))
check("悬浮球形态: 单击仍弹面板", getattr(w, "_popup_fired", False))

print()
print("DONE fails=%d" % len(fails))
sys.exit(1 if fails else 0)
