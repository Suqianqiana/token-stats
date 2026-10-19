# -*- coding: utf-8 -*-
"""第88轮: 毛玻璃边角残留材质的**自动化核验**(像素差分法)。

背景: 第82~85轮我多次用"截屏肉眼看"做核验, 结果漏掉了外圈矩形框(浅猫纠正)。
本工具把核验变成**客观判据**:
  1. 铺一张**高对比 2px 竖条纹**假桌面(被模糊→均匀灰; 未被模糊→黑白分明);
  2. 先截"无应用"参考图, 再把主窗口以指定材质放到固定位置, 再截一张;
  3. 对三类敏感区域逐像素求平均绝对差:
       · 外圈 10px 环带(四条直边中段) —— 当初"矩形外框"就该在这里被抓出来;
       · 四角圆角缺口(面板圆角外的直角区) —— 第86轮残留的"圆角处一点材质";
       · 面板内中心(对照项: 这里**应该**大差值 = 模糊确实生效)。
  判读: 环带/缺口 差值≈0 → 露出真实桌面(正确); 差值大 → 被材质填充(残留)。

用法:
  python tools/verify_frost_corners.py                  # 用代码当前配置
  python tools/verify_frost_corners.py --inset 6 --corner 0
      --inset   背板相对面板再内缩几像素
      --corner  背板是否用 Win11 系统圆角(1/0)
注意: 必须在**真实屏幕**上跑(不能用 offscreen), 否则 DWM 材质不存在。
"""
import os, sys, tempfile, argparse
sys.dont_write_bytecode = True
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from PySide6.QtWidgets import QApplication, QWidget
from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtTest import QTest
import card_app as ca
import win_backdrop as wb

WIN_X, WIN_Y = 260, 220
REGIONS = [
    ("外环·上", lambda x, y, w, h: (x + 60, y, 300, 9)),
    ("外环·下", lambda x, y, w, h: (x + 60, y + h - 9, 300, 9)),
    ("外环·左", lambda x, y, w, h: (x, y + 60, 9, 300)),
    ("外环·右", lambda x, y, w, h: (x + w - 9, y + 60, 9, 300)),
    ("圆角缺口·左上", lambda x, y, w, h: (x + 10, y + 10, 4, 4)),
    ("圆角缺口·右上", lambda x, y, w, h: (x + w - 14, y + 10, 4, 4)),
    ("圆角缺口·左下", lambda x, y, w, h: (x + 10, y + h - 14, 4, 4)),
    ("圆角缺口·右下", lambda x, y, w, h: (x + w - 14, y + h - 14, 4, 4)),
    ("面板内·对照", lambda x, y, w, h: (x + 200, y + 200, 60, 60)),
]
MODES = [
    ("默认", dict(glass=False, frost=False, frost_static=False, dark=True)),
    ("液态玻璃", dict(glass=True, frost=False, frost_static=False, dark=True)),
    ("静态背景", dict(glass=False, frost=True, frost_static=True, dark=True)),
    ("毛玻璃/暗", dict(glass=False, frost=True, frost_static=False, dark=True)),
    ("毛玻璃/亮", dict(glass=False, frost=True, frost_static=False, dark=False)),
]


def mean_abs_diff(a, b):
    tot = n = 0
    for yy in range(min(a.height(), b.height())):
        for xx in range(min(a.width(), b.width())):
            pa, pb = a.pixelColor(xx, yy), b.pixelColor(xx, yy)
            tot += (abs(pa.red() - pb.red()) + abs(pa.green() - pb.green())
                    + abs(pa.blue() - pb.blue()))
            n += 3
    return tot / max(1, n)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--inset", type=int, default=-1)
    ap.add_argument("--corner", type=int, default=-1)
    args, _ = ap.parse_known_args()

    if args.inset >= 0:
        def _pos(self, _extra=args.inset):
            fw = getattr(self, "_frost_win", None)
            if fw is None or not ca.ACRYLIC["on"]:
                return
            try:
                g = self.frameGeometry()
                INSET = 10 + _extra
                fw.setGeometry(g.x() + INSET, g.y() + INSET,
                               max(1, g.width() - INSET * 2), max(1, g.height() - INSET * 2))
            except Exception:
                pass
        ca.CardWindow._position_frost_window = _pos

    if args.corner >= 0:
        _orig = wb.apply_acrylic

        def _apply(hwnd, dark, alpha=None, shadow=False, corner=False):
            return _orig(hwnd, dark, alpha, shadow, bool(args.corner))
        wb.apply_acrylic = _apply

    app = QApplication(sys.argv)
    scr = QGuiApplication.primaryScreen()

    bg = QWidget()
    bg.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
    bg.setStyleSheet("background:#000000;")
    bg.setGeometry(40, 40, 1500, 980)
    bg.show()
    st = QWidget(bg)
    st.setGeometry(0, 0, 1500, 980)
    st.setStyleSheet("background-color:#ffffff;"
                     "background-image: repeating-linear-gradient("
                     "to right, #000000 0px, #000000 2px, #ffffff 2px, #ffffff 4px);")
    st.show()
    QTest.qWait(250)

    def shot():
        return scr.grabWindow(0).toImage()

    base = shot()

    ca.SETTINGS_FILE = os.path.join(tempfile.gettempdir(), "verify_frost_settings.json")
    ca.theme_state.update({"glass": False, "frost": False, "frost_static": False,
                           "dark": True, "source": "wb", "window_size": "default",
                           "pet": False, "pet_theme": "v3", "glass_transparency": "balanced",
                           "frost_custom": False})
    ca.refresh_palette()
    w = ca.CardWindow()
    w.refresh = lambda *a, **k: None
    w.apply_styles()
    w.apply_size_mode("default", save=False)
    w.move(WIN_X, WIN_Y)
    w.show()
    QTest.qWait(400)

    ratio = base.width() / float(scr.geometry().width())
    print("配置: inset=%s corner=%s  (DPI %.2f)" % (args.inset, args.corner, ratio))
    print("%-10s %-14s %s" % ("材质", "区域", "平均像素差"))
    bad = 0
    for tag, kw in MODES:
        ca.theme_state.update(kw)
        ca.refresh_palette()
        w._set_material("static" if kw["frost_static"] else
                        ("frost" if kw["frost"] else ("glass" if kw["glass"] else None)))
        w.set_dark(kw["dark"])
        # 第91轮: 必须等过"延迟130ms撤材质"并多留余量, 否则会测到切换瞬态(曾误报94)
        QTest.qWait(900)
        shot()                      # 丢弃一帧(强制刷新)
        QTest.qWait(250)
        cur = shot()
        # 第91轮: 必须用 geometry() —— frameGeometry() 在无边框窗口上含 DWM 阴影边距(约10px),
        # 用它算取样区会整体偏移, 之前那批"外环残留"数字其实是量到窗口外面去了。
        g = w.geometry()
        for name, fn in REGIONS:
            rx, ry, rw, rh = fn(g.x(), g.y(), g.width(), g.height())
            ra = base.copy(int(rx * ratio), int(ry * ratio), int(rw * ratio), int(rh * ratio))
            rb = cur.copy(int(rx * ratio), int(ry * ratio), int(rw * ratio), int(rh * ratio))
            d = mean_abs_diff(ra, rb)
            is_ref = (name == "面板内·对照")
            ok = (d > 20) if is_ref else (d < 6.0)
            if not ok:
                bad += 1
            verdict = "OK(模糊生效)" if is_ref and ok else (
                "** 对照异常 **" if is_ref else ("OK" if ok else "** 残留 **"))
            print("%-10s %-14s %6.1f  %s" % (tag, name, d, verdict))
    print("---")
    print("结论:", "全部干净 ✓" if bad == 0 else "%d 处异常 ✗" % bad)
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
