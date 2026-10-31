# -*- coding: utf-8 -*-
"""把桌宠悬浮气泡渲染成预览图（给浅浅猫看效果，不是截图工具）。

用法::

    QT_QPA_PLATFORM=offscreen python -uB tools/preview_bubble.py

数据来源: 直接读真实 stats.json（只读），DSH 可用时也读真实数据；
         取不到就显示"今日暂无数据" —— 那也是真实 UI 状态，不编数字。
输出: docs/previews/bubble_preview.png
"""
import os, sys, json, time, tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")
sys.dont_write_bytecode = True

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
sys.path.insert(0, _ROOT)

import scanner  # noqa: E402
_TMP = tempfile.mkdtemp(prefix="bubble_preview_")
scanner.PLUGIN_DATA_DIR = _TMP

import card_app as ca  # noqa: E402
from PySide6.QtCore import Qt, QRectF, QPointF, QRect  # noqa: E402
from PySide6.QtGui import (QGuiApplication, QImage, QPainter, QColor, QFont,  # noqa: E402
                           QFontDatabase, QPixmap)
from PySide6.QtWidgets import QApplication, QWidget  # noqa: E402

app = QApplication.instance() or QApplication([])
for _fp in (r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\msyhbd.ttc"):
    if os.path.exists(_fp):
        QFontDatabase.addApplicationFont(_fp)


# ---------------- 取真实数据 ----------------
def _real_wb():
    p = os.path.join(scanner.PLUGIN_DATA_DIR.replace(_TMP, ""), "")
    real = os.path.join(os.path.expanduser("~"), ".workbuddy", "plugins", "data",
                        "token-usage-stats", "stats.json")
    try:
        with open(real, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print("  (读不到真实 stats.json: %s)" % e)
        return {}


def _real_dsh():
    try:
        d = ca.load_dsh_stats()
        return d or {}
    except Exception as e:
        print("  (DSH 读取失败: %s)" % e)
        return {}


WB = _real_wb()
DSH = _real_dsh()
snaps = {"wb": WB, "dsh": DSH}
today = time.strftime("%Y-%m-%d")
for k, s in snaps.items():
    day = ((s or {}).get("daily") or {}).get(today) or {}
    tot = sum(int((v or {}).get("total", 0) or 0) for v in day.values()) if isinstance(day, dict) else 0
    tops = sorted(((m, int((v or {}).get("total", 0) or 0)) for m, v in day.items()),
                  key=lambda x: -x[1])[:2] if isinstance(day, dict) else []
    print("  %-3s 今日合计 %-12s 前二: %s" % (k, ca.fmt_compact(tot), tops))


# ---------------- 桩对象 ----------------
class _FakeCard:
    def __init__(self, s, src="wb"):
        self._stats_by_src = s
        self.source = src
        self.stats = s.get(src, {})


class _FakeBall(QWidget):
    def __init__(self, card):
        super().__init__(None)
        self.card = card
        self._bh = {}

    def _bubble_cancel_hide(self):
        pass

    def _bubble_start_hide(self):
        pass

    def set_bubble_pin(self, on):
        ca.theme_state["bubble_pin"] = bool(on)


# ---------------- 渲染 ----------------
def render_bubble(pet_w, pet_h, pinned=False, hover=None, sn=None):
    ca.theme_state["bubble_manual"] = False
    ca.theme_state["bubble_pin"] = pinned
    # 用她的真实默认: 跟随 + 相对偏移(-150, -111) —— 这样预览里的尖角就是她看到的角度
    ca.theme_state["bubble_follow"] = True
    ca.theme_state["bubble_dx"] = -150
    ca.theme_state["bubble_dy"] = -111
    ball = _FakeBall(_FakeCard(sn or snaps))
    ball.resize(pet_w, pet_h)          # 让 _follow_scale 读到桌宠高度
    # 挪到屏幕右侧 —— 她真机上桌宠就在右边缘, 这样气泡会落在**左边**、尖角朝右,
    # 跟实际观感一致(默认 0,0 会让 place_near 以为左边没地方, 尖角变到左边去)
    ball.move(760 - pet_w, 240)
    b = ca.PetBubble(ball)
    b.refresh_data()
    b.apply_size()
    b.place_near(ball.geometry())
    b._fade = 1.0                      # 跳过淡入
    b._hover = hover
    b._layout()
    pm = b.grab()
    print("    气泡 %dx%d  pointer=%s  pos=%s" % (b.width(), b.height(), b._pointer, (b.x(), b.y())))
    return pm, b.width(), b.height(), (b.x(), b.y())


def pet_pix(path, box_w, box_h):
    img = QImage(path)
    if img.isNull():
        return QPixmap()
    sc = min((box_w - 6.0) / img.width(), (box_h - 6.0) / img.height())
    return QPixmap.fromImage(img).scaled(int(img.width() * sc), int(img.height() * sc),
                                         Qt.KeepAspectRatio, Qt.SmoothTransformation)


BG = QColor(18, 20, 24)        # 与面板 dark 主题 BG 一致
CARD_BG = QColor(26, 29, 35)
frm = os.path.join(_ROOT, "assets", "pet_v6", "idle", "idle_01.png")

CANVAS_W, ROW_H, PAD = 860, 430, 26
canvas = QImage(CANVAS_W, ROW_H * 3 + 60, QImage.Format_ARGB32)
canvas.fill(BG)
cp = QPainter(canvas)
cp.setRenderHint(QPainter.Antialiasing)
cp.setRenderHint(QPainter.SmoothPixmapTransform)
cp.setRenderHint(QPainter.TextAntialiasing)

# 标题
f = QFont("Microsoft YaHei UI")
f.setPixelSize(13)
cp.setFont(f)
cp.setPen(QColor(150, 158, 172))
cp.drawText(QRect(PAD, 6, CANVAS_W - PAD * 2, 24), Qt.AlignLeft | Qt.AlignVCenter,
            "桌宠悬浮气泡 · 预览（数据取自今天的真实 stats.json，非示意数字）")

# 第三行换成 10-30 的 DSH 数据, 只为展示「两个来源都满」时的完整布局
_snaps_full = {"wb": WB, "dsh": DSH}
_d = dict(DSH or {})
_dd = dict(_d.get("daily") or {})
if "2026-10-30" in _dd:
    _dd[today] = _dd["2026-10-30"]
    _d["daily"] = _dd
    _snaps_full["dsh"] = _d

rows = [
    ("① 默认尺寸 · 跟随桌宠缩放 1.00（桌宠 118×148）· DSH 今天没有数据，显示空态",
     118, 148, False, None, snaps),
    ("② 你当前尺寸 · 跟随缩放 1.15（桌宠 140×174）", 140, 174, False, None, snaps),
    ("③ 常驻 + 右下角拖拽手柄 · 此行 DSH 借用 10-30 数据，只为展示两源都满的完整布局",
     140, 174, True, "grip", _snaps_full),
]
for i, (label, pw, ph, pinned, hv, _sn) in enumerate(rows):
    top = 40 + i * ROW_H
    cp.setPen(QColor(120, 128, 142))
    f2 = QFont("Microsoft YaHei UI")
    f2.setPixelSize(12)
    cp.setFont(f2)
    cp.drawText(QRect(PAD, top, CANVAS_W - PAD * 2, 20), Qt.AlignLeft | Qt.AlignVCenter, label)

    bub, bw, bh, bpos = render_bubble(pw, ph, pinned, hv, _sn)
    # 桌宠放在画布右下方; 气泡位置用 place_near 真实算出来的相对关系还原
    pet_right = CANVAS_W - PAD - 30
    pet_x = pet_right - pw
    pet_y = top + 34 + 200
    bx = pet_x + (bpos[0] - (760 - pw))
    by = pet_y + (bpos[1] - 240)
    # 圆角底板, 让桌宠有个落点
    cp.setPen(Qt.NoPen)
    cp.setBrush(CARD_BG)
    cp.drawRoundedRect(QRectF(pet_x - 8, pet_y - 10, pw + 16, ph + 20), 10, 10)
    pp = pet_pix(frm, pw, ph)
    cp.drawPixmap(int(pet_x + (pw - pp.width()) / 2), int(pet_y + (ph - pp.height()) / 2), pp)
    # 气泡
    cp.drawPixmap(int(bx), int(by), bub)
    cp.setPen(QColor(90, 98, 112))
    f3 = QFont("Microsoft YaHei UI")
    f3.setPixelSize(11)
    cp.setFont(f3)
    cp.drawText(QRect(0, int(by + bh + 4), int(bx + bw), 16),
                Qt.AlignRight | Qt.AlignVCenter, "%d × %d" % (bw, bh))
cp.end()

out_dir = os.path.join(_ROOT, "docs", "previews")
os.makedirs(out_dir, exist_ok=True)
out = os.path.join(out_dir, "bubble_preview.png")
canvas.save(out)
print("\n已生成:", out, canvas.width(), "x", canvas.height())
