# -*- coding: utf-8 -*-
"""
Token 统计卡片 V8.7 — iOS 27 液态玻璃 (Pure Crystal Glass) + 精致双尺寸仪表盘
核心规范:
  - 产品标识全面更名为「Token 统计」
  - 彻底去除色相色散畸变，回归纯净物理级菲涅尔镜面高光与透明晶体折射
  - 修复标准尺寸下 QSS 误用 pt 导致的「今日概况」超大字体与换行挤压缺陷
  - 顶部指标卡核心数字垂直重心上移，消除贴底压迫感，留出黄金透气间隙
  - 重构舒适大窗口 (1180×730) 字体层级体系，字重与行高开阔舒展，拒绝粗暴放大
  - 三档玻璃通透度无级调谐 + 右键多入口切换 + 每日柱状图鼠标锚点滚轮缩放与平移
"""
import json
import os
import random
import sys
import threading
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)
import scanner  # noqa: E402

from PySide6.QtCore import (Qt, QRectF, QObject, Signal, QTimer, QPoint, QRect,
                            QPointF)
from PySide6.QtGui import (QColor, QFont, QPainter, QPen, QBrush, QPainterPath,
                           QLinearGradient, QImage, QGuiApplication)
from PySide6.QtWidgets import (QApplication, QWidget, QLabel, QVBoxLayout,
                               QHBoxLayout, QGridLayout, QFrame, QPushButton,
                               QScrollArea, QMenu, QSizePolicy, QPlainTextEdit,
                               QStackedWidget, QLineEdit)

# ============================================================ 窗口尺寸与排版度量衡体系
SIZE_METRICS = {
    "default": {
        "name": "标准模式 (990×610)",
        "win_w": 990, "win_h": 610, "sidebar_w": 190,
        "stat_h": 72, "stat_val_pt": 13.2, "stat_lbl_pt": 8.5, "stat_hint_pt": 8.5,
        "stat_val_y": 28,  # 重心明显上提，距底边界留出 15px+ 舒适余量
        "row_h": 28, "name_w": 110, "total_w": 100, "pct_w": 38, "hit_w": 44, "req_w": 48,
        "row_pt": 8.8, "row_head_pt": 8.5,
        "chart_min_h": 130, "heat_min_h": 105, "heat_cell": 10.0, "heat_gap": 2.5,
        "today_h": 28, "today_px": 11,
        "nav_btn_h": 38, "nav_btn_pt": 9.2,
        "title_pt": 12.0, "subtitle_pt": 9.0, "opt_btn_h": 28, "opt_btn_px": 11, "refresh_h": 34,
        "sn_prog_h": 10, "sn_input_h": 42, "sn_title_pt": 10.5, "sn_sub_pt": 8.8, "sn_date_pt": 8.0,
        "promo_val_pt": 12.0,
    },
    "large": {
        "name": "舒适大窗口 (1180×730)",
        "win_w": 1180, "win_h": 730, "sidebar_w": 220,
        "stat_h": 84, "stat_val_pt": 15.8, "stat_lbl_pt": 9.0, "stat_hint_pt": 8.8,
        "stat_val_y": 34,  # 大窗口下同样重心居中偏上，比例舒展
        "row_h": 34, "name_w": 134, "total_w": 112, "pct_w": 44, "hit_w": 50, "req_w": 54,
        "row_pt": 9.2, "row_head_pt": 8.8,  # 表格行高拉开，文字保持干练清秀
        "chart_min_h": 155, "heat_min_h": 120, "heat_cell": 11.5, "heat_gap": 2.8,
        "today_h": 32, "today_px": 12,
        "nav_btn_h": 42, "nav_btn_pt": 9.8,
        "title_pt": 13.0, "subtitle_pt": 9.6, "opt_btn_h": 30, "opt_btn_px": 11, "refresh_h": 38,
        "sn_prog_h": 12, "sn_input_h": 46, "sn_title_pt": 11.2, "sn_sub_pt": 9.2, "sn_date_pt": 8.5,
        "promo_val_pt": 13.5,
    }
}

# ============================================================ 纯净液态玻璃通透度规范
GLASS_PRESETS = {
    "crystal": {
        "name": "晶透水滴 (高通透)",
        "desc": "极高透明度，清晰透出桌面壁纸",
        "bg_alpha_dark": (95, 60, 42),
        "bg_alpha_light": (115, 68, 48),
        "pod_alpha_dark": (180, 150),
        "pod_alpha_light": (195, 170),
        "rim_mult": 1.25,
    },
    "balanced": {
        "name": "标准液态 (推荐)",
        "desc": "晶体微折射与文字高清晰度黄金平衡",
        "bg_alpha_dark": (145, 105, 88),
        "bg_alpha_light": (165, 115, 92),
        "pod_alpha_dark": (225, 200),
        "pod_alpha_light": (235, 215),
        "rim_mult": 1.0,
    },
    "frosted": {
        "name": "柔和微透 (防眩光)",
        "desc": "微透磨砂质感，抵御复杂桌面干扰",
        "bg_alpha_dark": (195, 160, 140),
        "bg_alpha_light": (210, 160, 140),
        "pod_alpha_dark": (245, 230),
        "pod_alpha_light": (248, 238),
        "rim_mult": 0.85,
    }
}

# ============================================================ 色板与视觉系统
THEMES = {
    "light": dict(
        BG=(246, 248, 251), CARD=(255, 255, 255), BORDER=(226, 231, 240),
        TEXT=(20, 24, 33), TEXT2=(92, 100, 115), TEXT3=(150, 158, 172),
        TRACK=(237, 241, 247), HOVER=(236, 242, 252), ZEBRA=(250, 251, 254),
        SIDEBAR=(239, 243, 248),
    ),
    "dark": dict(
        BG=(18, 20, 24), CARD=(28, 31, 38), BORDER=(46, 51, 62),
        TEXT=(240, 243, 248), TEXT2=(205, 211, 222), TEXT3=(140, 148, 162),
        TRACK=(38, 43, 53), HOVER=(38, 44, 56), ZEBRA=(24, 27, 33),
        SIDEBAR=(23, 25, 31),
    ),
}

GLASS_ALPHA = {"light": dict(BG=125, CARD=238, SIDEBAR=140),
               "dark": dict(BG=115, CARD=228, SIDEBAR=130)}

theme_state = {
    "dark": False, "glass": False, "source": "wb", "pet": False,
    "pet_theme": "v2", "window_size": "default", "glass_transparency": "balanced"
}
SETTINGS_FILE = os.path.join(scanner.PLUGIN_DATA_DIR, "settings.json")

BLUE   = QColor("#3b6fe0")
GREEN  = QColor("#3fa45b")
RED    = QColor("#e05252")
PURPLE = QColor("#8b5cd6")
YELLOW = QColor("#d6a72c")
CYAN   = QColor("#2fa8bc")
PINK   = QColor("#e06fb8")
ORANGE = QColor("#e0813f")
GRAY   = QColor("#8a929e")

MODEL_COLORS = [BLUE, GREEN, RED, PURPLE, YELLOW, CYAN, PINK, ORANGE, GRAY,
                QColor("#5b7ee5"), QColor("#6fbf8f"), QColor("#c96f6f"),
                QColor("#a58cff"), QColor("#7fbf7f")]


def curr_metric():
    sz = theme_state.get("window_size", "default")
    return SIZE_METRICS.get(sz, SIZE_METRICS["default"])


def curr_glass_preset():
    tr = theme_state.get("glass_transparency", "balanced")
    return GLASS_PRESETS.get(tr, GLASS_PRESETS["balanced"])


def refresh_palette():
    name = "dark" if theme_state["dark"] else "light"
    t = THEMES[name]
    g = GLASS_ALPHA[name] if theme_state["glass"] else None

    def mk(rgb, a=255):
        return QColor(rgb[0], rgb[1], rgb[2], a)

    globals().update(
        BG=mk(t["BG"], g["BG"] if g else 255),
        SIDEBAR=mk(t["SIDEBAR"], g["SIDEBAR"] if g else 255),
        CARD=mk(t["CARD"], g["CARD"] if g else 255),
        BORDER=mk(t["BORDER"]),
        TEXT=mk(t["TEXT"]),
        TEXT2=mk(t["TEXT2"]),
        TEXT3=mk(t["TEXT3"]),
        TRACK=mk(t["TRACK"], (g["CARD"] if g else 255)),
        HOVER=mk(t["HOVER"], (g["CARD"] if g else 255)),
        ZEBRA=mk(t["ZEBRA"], (g["CARD"] if g else 255)),
    )


def qrgba(c, alpha=None):
    a = c.alpha() if alpha is None else alpha
    return f"rgba({c.red()},{c.green()},{c.blue()},{a})"


def qname(c):
    return f"#{c.red():02x}{c.green():02x}{c.blue():02x}"


refresh_palette()


# ============================================================ 菜单与全局样式
def menu_qss():
    dark = theme_state["dark"]
    if dark:
        return f"""
        QMenu {{ background:{qrgba(QColor(34,37,43),246)}; border:1px solid #3a3f47;
                 border-radius:12px; padding:6px; }}
        QMenu::item {{ padding:8px 24px 8px 14px; border-radius:8px;
                       color:#e8eaed; font-size:12px; }}
        QMenu::item:selected {{ background:{qrgba(QColor(91,126,229),60)};
                                color:#ffffff; }}
        QMenu::separator {{ height:1px; background:#3a3f47; margin:5px 8px; }}
        """
    return """
    QMenu { background:#ffffff; border:1px solid #e6e9ee; border-radius:12px; padding:6px; }
    QMenu::item { padding:8px 24px 8px 14px; border-radius:8px; color:#171a20; font-size:12px; }
    QMenu::item:selected { background:#eef3ff; color:#2f5ec4; }
    QMenu::separator { height:1px; background:#eef0f4; margin:5px 8px; }
    """


def make_menu(parent):
    m = QMenu(parent)
    m.setStyleSheet(menu_qss())
    m.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
    m.setAttribute(Qt.WA_TranslucentBackground)
    return m


def apply_app_qss():
    handle = "#d3d9e2" if not theme_state["dark"] else "#3d434c"
    handle_h = "#b8c2d0" if not theme_state["dark"] else "#4d545f"
    QApplication.instance().setStyleSheet(f"""
      QScrollBar:vertical {{ background:transparent; width:6px; margin:2px 1px; }}
      QScrollBar::handle:vertical {{ background:{handle}; border-radius:3px; min-height:24px; }}
      QScrollBar::handle:vertical:hover {{ background:{handle_h}; }}
      QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height:0; }}
      QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background:transparent; }}
      QScrollBar:horizontal {{ background:transparent; height:6px; margin:1px 2px; }}
      QScrollBar::handle:horizontal {{ background:{handle}; border-radius:3px; min-width:24px; }}
      QScrollBar::handle:horizontal:hover {{ background:{handle_h}; }}
      QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width:0; }}
      QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{ background:transparent; }}
      QToolTip {{ background:{qname(CARD)}; color:{qname(TEXT)}; border:1px solid {qname(BORDER)};
                  border-radius:6px; padding:5px 8px; font-size:11.5px; }}
    """)


def fmt(n):
    n = int(n)
    if n >= 1e8: return f"{n/1e8:.2f} 亿"
    if n >= 1e4: return f"{n/1e4:.1f} 万"
    return f"{n:,}"


def fmt_full(n):
    return f"{int(n):,}"


# ============================================================ 纯净 iOS 27 液态玻璃光学底板
class LiquidGlassFrame(QFrame):
    """纯净物理级液态玻璃底板 (银白双层高光 + 菲涅尔镜面边缘，无任何彩色杂斑)"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.sep_x = float(curr_metric()["sidebar_w"])

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        rect = QRectF(0.5, 0.5, w - 1.0, h - 1.0)
        path = QPainterPath()
        path.addRoundedRect(rect, 14, 14)

        dark = theme_state["dark"]
        glass = theme_state["glass"]

        if glass:
            gp = curr_glass_preset()
            a_top, a_mid, a_bot = gp["bg_alpha_dark"] if dark else gp["bg_alpha_light"]
            mult = gp["rim_mult"]

            # 1. 纯净微折射双层对角渐变
            bg_grad = QLinearGradient(0, 0, w, h)
            if dark:
                bg_grad.setColorAt(0.0, QColor(38, 43, 56, a_top))
                bg_grad.setColorAt(0.42, QColor(22, 25, 32, a_mid))
                bg_grad.setColorAt(1.0, QColor(14, 16, 22, a_bot))
            else:
                bg_grad.setColorAt(0.0, QColor(255, 255, 255, a_top))
                bg_grad.setColorAt(0.45, QColor(242, 246, 253, a_mid))
                bg_grad.setColorAt(1.0, QColor(225, 234, 248, a_bot))
            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(bg_grad))
            p.drawPath(path)

            # 2. 侧边栏玻璃分型槽线
            sep_x = self.sep_x
            sep_grad = QLinearGradient(sep_x, 0, sep_x, h)
            if dark:
                sep_grad.setColorAt(0.0, QColor(255, 255, 255, int(50 * mult)))
                sep_grad.setColorAt(0.5, QColor(255, 255, 255, int(16 * mult)))
                sep_grad.setColorAt(1.0, QColor(255, 255, 255, int(30 * mult)))
            else:
                sep_grad.setColorAt(0.0, QColor(255, 255, 255, int(130 * mult)))
                sep_grad.setColorAt(0.5, QColor(205, 215, 230, int(85 * mult)))
                sep_grad.setColorAt(1.0, QColor(255, 255, 255, int(90 * mult)))
            p.setPen(QPen(QBrush(sep_grad), 1.0))
            p.drawLine(QPointF(sep_x, 1.0), QPointF(sep_x, h - 1.0))

            # 3. 菲涅尔双层镜面高光边缘
            rim_grad = QLinearGradient(0, 0, 0, h)
            if dark:
                rim_grad.setColorAt(0.0, QColor(255, 255, 255, int(115 * mult)))
                rim_grad.setColorAt(0.4, QColor(255, 255, 255, int(25 * mult)))
                rim_grad.setColorAt(1.0, QColor(255, 255, 255, int(60 * mult)))
            else:
                rim_grad.setColorAt(0.0, QColor(255, 255, 255, int(230 * mult)))
                rim_grad.setColorAt(0.4, QColor(190, 202, 220, int(95 * mult)))
                rim_grad.setColorAt(1.0, QColor(255, 255, 255, int(140 * mult)))
            p.setBrush(Qt.NoBrush)
            p.setPen(QPen(QBrush(rim_grad), 1.2))
            p.drawPath(path)

            # 4. 顶部 1px 纯白镜面光弧
            arc_grad = QLinearGradient(16, 1.2, w - 16, 1.2)
            arc_grad.setColorAt(0.0, QColor(255, 255, 255, 0))
            top_a = int((95 if dark else 175) * mult)
            arc_grad.setColorAt(0.3, QColor(255, 255, 255, top_a))
            arc_grad.setColorAt(0.7, QColor(255, 255, 255, top_a))
            arc_grad.setColorAt(1.0, QColor(255, 255, 255, 0))
            p.setPen(QPen(QBrush(arc_grad), 1.0))
            p.drawLine(QPointF(16, 1.2), QPointF(w - 16, 1.2))
        else:
            p.setPen(QPen(BORDER, 1.0))
            p.setBrush(QBrush(BG))
            p.drawPath(path)


class GlassPodFrame(QFrame):
    """iOS 27 纯净悬浮透镜子卡片 (Frosted Glass Pod)"""
    def __init__(self, radius=10, parent=None):
        super().__init__(parent)
        self.radius = radius

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        r = self.radius
        rect = QRectF(0.5, 0.5, w - 1.0, h - 1.0)
        path = QPainterPath()
        path.addRoundedRect(rect, r, r)

        dark = theme_state["dark"]
        glass = theme_state["glass"]

        if glass:
            gp = curr_glass_preset()
            a_top, a_bot = gp["pod_alpha_dark"] if dark else gp["pod_alpha_light"]
            mult = gp["rim_mult"]

            # 背景固化背板 (透光不透杂物，保护文字极高清晰度)
            grad = QLinearGradient(0, 0, 0, h)
            if dark:
                grad.setColorAt(0.0, QColor(36, 40, 50, a_top))
                grad.setColorAt(1.0, QColor(25, 28, 35, a_bot))
            else:
                grad.setColorAt(0.0, QColor(255, 255, 255, a_top))
                grad.setColorAt(1.0, QColor(246, 249, 254, a_bot))
            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(grad))
            p.drawPath(path)

            # 菲涅尔切角外边框
            rim = QLinearGradient(0, 0, 0, h)
            if dark:
                rim.setColorAt(0.0, QColor(255, 255, 255, int(75 * mult)))
                rim.setColorAt(0.5, QColor(255, 255, 255, int(18 * mult)))
                rim.setColorAt(1.0, QColor(255, 255, 255, int(40 * mult)))
            else:
                rim.setColorAt(0.0, QColor(255, 255, 255, int(210 * mult)))
                rim.setColorAt(0.5, QColor(210, 218, 230, int(95 * mult)))
                rim.setColorAt(1.0, QColor(255, 255, 255, int(135 * mult)))
            p.setBrush(Qt.NoBrush)
            p.setPen(QPen(QBrush(rim), 1.0))
            p.drawPath(path)

            # 顶部微切角镜面反射线
            top_hl = QLinearGradient(r, 1.2, w - r, 1.2)
            top_hl.setColorAt(0.0, QColor(255, 255, 255, 0))
            top_a = int((80 if dark else 145) * mult)
            top_hl.setColorAt(0.3, QColor(255, 255, 255, top_a))
            top_hl.setColorAt(0.7, QColor(255, 255, 255, top_a))
            top_hl.setColorAt(1.0, QColor(255, 255, 255, 0))
            p.setPen(QPen(QBrush(top_hl), 1.0))
            p.drawLine(QPointF(r, 1.2), QPointF(w - r, 1.2))
        else:
            p.setPen(QPen(BORDER, 1.0))
            p.setBrush(QBrush(CARD))
            p.drawPath(path)


# ============================================================ 头部组件
class CardHeader(QWidget):
    def __init__(self, text, accent=BLUE, parent=None):
        super().__init__(parent)
        self.text = text
        self.accent = accent
        self.setFixedHeight(22)

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(self.accent)
        p.drawRoundedRect(QRectF(0, 9, 16, 3), 1.5, 1.5)
        p.setPen(TEXT)
        m = curr_metric()
        f = QFont("Microsoft YaHei UI", m["row_head_pt"])
        f.setBold(True)
        p.setFont(f)
        p.drawText(QRectF(22, 0, self.width() - 24, self.height()),
                   Qt.AlignLeft | Qt.AlignVCenter, self.text)


# ============================================================ 悬浮提示卡
class ChartTip(QWidget):
    _instance = None

    @classmethod
    def instance(cls):
        if cls._instance is None:
            cls._instance = ChartTip()
        return cls._instance

    ROW_H = 20
    PAD = 12
    GAP = 12
    VAL_MIN = 64

    def __init__(self):
        super().__init__(None, Qt.ToolTip | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)  # 鼠标穿透: 悬浮框不拦截鼠标, 根治 enter/leave 闪烁
        self.rows = []
        self.title_text = ""
        self.accent = BLUE

    def show_tip(self, title, rows, accent, global_pos):
        # 去重: 内容 + 位置未变则跳过, 避免 mouseMoveEvent 高频重复 resize/move 引入闪烁
        key = (title, accent, global_pos.x(), global_pos.y(),
               tuple((r[0] if isinstance(r, tuple) else None,
                      r[1] if isinstance(r, tuple) else r,
                      r[2] if isinstance(r, tuple) else "") for r in rows))
        if key == getattr(self, "_last_key", None) and self.isVisible():
            return
        self._last_key = key

        self.title_text = title
        self.accent = accent
        norm = []
        for r in rows:
            norm.append(r if isinstance(r, tuple) else (None, r, ""))
        self.rows = norm

        p = QPainter(self)
        m = curr_metric()
        f = QFont("Microsoft YaHei UI", m["row_head_pt"])
        p.setFont(f)
        fm = p.fontMetrics()
        lab_w = max((fm.horizontalAdvance(lb) for _, lb, _ in norm), default=0)
        val_w = max((fm.horizontalAdvance(vl) for _, _, vl in norm), default=0)
        val_w = max(val_w, fm.horizontalAdvance(title))
        self._label_x = self.PAD + 12
        self._value_right = self.PAD + 12 + lab_w + self.GAP + max(val_w, self.VAL_MIN)
        w = self._value_right + self.PAD
        h = 32 + self.ROW_H * len(norm) + 6
        self.resize(w, h)

        x, y = global_pos.x() + 12, global_pos.y() + 14
        screen = QGuiApplication.screenAt(global_pos) or QApplication.primaryScreen()
        scr = screen.availableGeometry()
        if x + w > scr.right():
            x = global_pos.x() - w - 8
        if y + h > scr.bottom():
            y = global_pos.y() - h - 8
        x = max(scr.left() + 4, x)
        y = max(scr.top() + 4, y)
        self.move(x, y)
        self.show()
        self.update()

    def hide_tip(self):
        self.hide()

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect().adjusted(0, 0, -1, -1)), 9, 9)
        p.setPen(QPen(BORDER, 1))
        p.setBrush(QColor(CARD.red(), CARD.green(), CARD.blue(), 250))
        p.drawPath(path)

        p.setPen(Qt.NoPen)
        p.setBrush(self.accent)
        p.drawRoundedRect(QRectF(6, 8, 3, 14), 1.5, 1.5)
        m = curr_metric()
        f = QFont("Microsoft YaHei UI", m["row_head_pt"], QFont.Bold)
        p.setFont(f)
        p.setPen(TEXT)
        p.drawText(QRectF(self.PAD, 6, self.width() - self.PAD - 6, 18),
                   Qt.AlignLeft | Qt.AlignVCenter, self.title_text)

        f2 = QFont("Microsoft YaHei UI", m["row_pt"])
        p.setFont(f2)
        y = 28
        for color, lb, vl in self.rows:
            cy = y + self.ROW_H / 2
            if color is not None:
                p.setPen(Qt.NoPen)
                p.setBrush(color)
                p.drawEllipse(QRectF(self.PAD + 1, cy - 3, 6, 6))
            p.setPen(TEXT2)
            p.drawText(QRectF(self._label_x, y,
                              self._value_right - self.GAP - self._label_x, self.ROW_H),
                       Qt.AlignLeft | Qt.AlignVCenter, lb)
            if vl:
                fv = QFont("Consolas", m["row_pt"], QFont.Bold)
                p.setFont(fv)
                p.setPen(TEXT if color is not None else TEXT2)
                p.drawText(QRectF(self._value_right - 300, y, 300, self.ROW_H),
                           Qt.AlignRight | Qt.AlignVCenter, vl)
                p.setFont(f2)
            y += self.ROW_H


# ============================================================ 汇总指标卡 (数字重心上移 + 排版舒展)
class StatCard(GlassPodFrame):
    def __init__(self, label, accent, parent=None):
        super().__init__(radius=10, parent=parent)
        self.label_text = label
        self.accent = accent
        self.value_text = "—"
        self.hint_text = ""
        self.apply_size()

    def apply_size(self):
        m = curr_metric()
        self.setFixedHeight(m["stat_h"])
        self.update()

    def set_value(self, value, hint=""):
        self.value_text = value
        self.hint_text = hint
        self.update()

    def set_label(self, label):
        if self.label_text != label:
            self.label_text = label
            self.update()

    def paintEvent(self, ev):
        super().paintEvent(ev)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        m = curr_metric()

        # 顶栏装饰条与指标名称 (距离顶边界留出 10px 间距)
        p.setPen(Qt.NoPen)
        p.setBrush(self.accent)
        p.drawRoundedRect(QRectF(14, 10, 16, 3), 1.5, 1.5)

        p.setPen(TEXT2)
        p.setFont(QFont("Microsoft YaHei UI", m["stat_lbl_pt"]))
        p.drawText(QRectF(14, 15, w - 28, 16), Qt.AlignLeft | Qt.AlignVCenter, self.label_text)

        if self.hint_text:
            p.setPen(TEXT3)
            p.setFont(QFont("Consolas", m["stat_hint_pt"]))
            p.drawText(QRectF(14, 15, w - 28, 16), Qt.AlignRight | Qt.AlignVCenter, self.hint_text)

        # 核心数字区域：大幅上移 (避免贴底，形成下部自然透气感)
        p.setPen(TEXT)
        f = QFont("Microsoft YaHei UI", m["stat_val_pt"], QFont.Bold)
        p.setFont(f)
        val_y = m["stat_val_y"]
        p.drawText(QRectF(14, val_y, w - 28, 34), Qt.AlignLeft | Qt.AlignVCenter, self.value_text)


# ============================================================ 模型明细表
PAD = 6


class TableHeader(QWidget):
    def __init__(self, req_label="请求", parent=None):
        super().__init__(parent)
        self.req_label = req_label
        self.apply_size()

    def apply_size(self):
        m = curr_metric()
        self.setFixedHeight(m["row_h"] - 4)
        self.update()

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        m = curr_metric()
        p.setFont(QFont("Microsoft YaHei UI", m["row_head_pt"]))

        name_w = m["name_w"]
        total_w = m["total_w"]
        pct_w = m["pct_w"]
        hit_w = m["hit_w"]
        req_w = m["req_w"]

        cols = [
            (PAD, name_w, "模型", Qt.AlignLeft | Qt.AlignVCenter),
            (w - PAD - req_w - hit_w - pct_w - total_w, total_w, "Tokens", Qt.AlignRight | Qt.AlignVCenter),
            (w - PAD - req_w - hit_w - pct_w, pct_w, "占比", Qt.AlignRight | Qt.AlignVCenter),
            (w - PAD - req_w - hit_w, hit_w, "缓存率", Qt.AlignRight | Qt.AlignVCenter),
            (w - PAD - req_w, req_w, self.req_label, Qt.AlignRight | Qt.AlignVCenter),
        ]
        for x, cw, text, align in cols:
            p.setPen(TEXT3)
            p.drawText(QRectF(x, 0, cw, h), align, text)
        p.setPen(QPen(BORDER, 1))
        p.drawLine(0, h - 1, w, h - 1)


class ModelRow(QWidget):
    def __init__(self, name, color, ratio, total, pct, hit_rate, requests,
                 input_tok=0, output_tok=0, cached_tok=0, zebra=False, parent=None):
        super().__init__(parent)
        self.name = name
        self.color = color
        self.ratio = max(0.008, min(1.0, ratio))
        self.total = total
        self.pct = pct
        self.hit_rate = hit_rate
        self.requests = requests
        self.input_tok = input_tok
        self.output_tok = output_tok
        self.cached_tok = cached_tok
        self._zebra = zebra
        self.setMouseTracking(True)
        if zebra:
            self.setStyleSheet(f"background:{qrgba(ZEBRA)};")
        self.apply_size()

    def apply_size(self):
        m = curr_metric()
        self.setFixedHeight(m["row_h"])
        self.update()

    def enterEvent(self, ev):
        self.setStyleSheet(f"background:{qrgba(HOVER)};")
        self._show_tip(ev.globalPosition().toPoint())

    def leaveEvent(self, ev):
        self.setStyleSheet(f"background:{qrgba(ZEBRA)};" if self._zebra else "")
        ChartTip.instance().hide_tip()

    def mouseMoveEvent(self, ev):
        # 跟随鼠标持续更新悬浮框(与柱状图一致), 避免 enter/leave 抖动 + 固定位置不跟随导致的闪烁
        self._show_tip(ev.globalPosition().toPoint())

    def _show_tip(self, global_pos=None):
        if global_pos is None:
            global_pos = self.mapToGlobal(QPoint(int(self.width() / 2), 2))
        rows = [
            (None, "输入", fmt_full(self.input_tok)),
            (None, "输出", fmt_full(self.output_tok)),
            (None, "缓存命中", f"{fmt_full(self.cached_tok)} ({self.hit_rate:.1f}%)"),
            (None, "请求次数", f"{self.requests:,}"),
            (self.color, "Tokens 总量", f"{fmt_full(self.total)} ({self.pct:.1f}%)"),
        ]
        ChartTip.instance().show_tip(self.name, rows, self.color, global_pos)

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        cy = h / 2
        m = curr_metric()

        p.setPen(Qt.NoPen)
        p.setBrush(self.color)
        p.drawEllipse(QRectF(PAD, cy - 3.5, 7, 7))

        p.setPen(TEXT)
        p.setFont(QFont("Consolas", m["row_pt"]))
        name_w = m["name_w"]
        total_w = m["total_w"]
        pct_w = m["pct_w"]
        hit_w = m["hit_w"]
        req_w = m["req_w"]

        name_rect = QRectF(PAD + 11, 0, name_w - 14, h)
        fm = p.fontMetrics()
        elided = fm.elidedText(self.name, Qt.ElideRight, int(name_rect.width()))
        p.drawText(name_rect, Qt.AlignVCenter | Qt.AlignLeft, elided)

        bar_right = w - PAD - req_w - hit_w - pct_w - total_w - 8
        bar_left = PAD + name_w
        bw = bar_right - bar_left
        if bw > 12:
            track = QPainterPath()
            track.addRoundedRect(QRectF(bar_left, cy - 4, bw, 8), 4, 4)
            p.setPen(Qt.NoPen)
            p.setBrush(TRACK)
            p.drawPath(track)
            fill_w = max(8, bw * self.ratio)
            grad = QLinearGradient(bar_left, 0, bar_left + fill_w, 0)
            grad.setColorAt(0, self.color.lighter(112))
            grad.setColorAt(1, self.color)
            fillp = QPainterPath()
            fillp.addRoundedRect(QRectF(bar_left, cy - 4, fill_w, 8), 4, 4)
            p.setBrush(QBrush(grad))
            p.drawPath(fillp)

        def right_text(text, col_w, x_right, color, bold=False):
            p.setPen(color)
            f = QFont("Consolas", m["row_pt"], QFont.Bold if bold else QFont.Normal)
            p.setFont(f)
            p.drawText(QRectF(x_right - col_w, 0, col_w, h),
                       Qt.AlignVCenter | Qt.AlignRight, text)

        x1 = w - PAD - req_w - hit_w - pct_w
        right_text(fmt_full(self.total), total_w, x1, TEXT, bold=True)
        right_text(f"{self.pct:.1f}%", pct_w, x1 + pct_w, TEXT2)
        right_text(f"{self.hit_rate:.0f}%", hit_w, x1 + pct_w + hit_w,
                   GREEN if self.hit_rate >= 80 else TEXT2)
        right_text(f"{self.requests:,}", req_w, x1 + pct_w + hit_w + req_w, TEXT2)


# ============================================================ 柱状图组件 (支持滚轮缩放 & 拖动平移)
class StackedBarChart(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.all_data = []
        self.data = []
        self.colors = {}
        self.view_start = 0.0
        self.view_count = 35.0
        self._drag_start_x = None
        self._drag_start_view = 0.0
        self.setMouseTracking(True)
        self.apply_size()

    def apply_size(self):
        m = curr_metric()
        self.setMinimumHeight(m["chart_min_h"])
        self.update()

    def set_data(self, daily, models_rank):
        top = [m for m, _ in models_rank[:8]]
        self.colors = {m: MODEL_COLORS[i % len(MODEL_COLORS)] for i, m in enumerate(top)}
        days = sorted(d for d in daily if d != "unknown")
        
        self.all_data = []
        for d in days:
            parts = []
            for m in top:
                v = daily[d].get(m, {}).get("total", 0)
                if v:
                    parts.append((m, self.colors[m], v))
            self.all_data.append({"date": d, "parts": parts})

        total = len(self.all_data)
        default_len = min(35.0, float(total)) if total > 0 else 35.0
        self.view_count = default_len
        self.view_start = float(max(0, total - int(default_len)))
        self._sync_slice()

    def _sync_slice(self):
        total = len(self.all_data)
        if total == 0:
            self.data = []
            self.update()
            return

        self.view_count = max(5.0, min(float(total), self.view_count))
        self.view_start = max(0.0, min(float(total - self.view_count), self.view_start))
        
        s = int(round(self.view_start))
        c = int(round(self.view_count))
        self.data = self.all_data[s : s + c]
        self.update()

    def _geom(self):
        w, h = self.width(), self.height()
        is_lg = theme_state.get("window_size") == "large"
        padL = 42 if is_lg else 38
        padB = 18 if is_lg else 16
        return w, h, padL, 8, 4, padB

    def wheelEvent(self, ev):
        if not self.all_data or len(self.all_data) <= 5:
            super().wheelEvent(ev)
            return

        delta = ev.angleDelta().y()
        if delta == 0:
            return

        w, h, padL, padR, padT, padB = self._geom()
        iw = max(10, w - padL - padR)
        mx = ev.position().x()

        anchor_ratio = max(0.0, min(1.0, (mx - padL) / iw))
        total = float(len(self.all_data))
        anchor_idx = self.view_start + anchor_ratio * self.view_count

        scale = 0.80 if delta > 0 else 1.25
        new_count = max(5.0, min(total, self.view_count * scale))
        new_start = anchor_idx - anchor_ratio * new_count

        self.view_count = new_count
        self.view_start = new_start
        self._sync_slice()

        ChartTip.instance().hide_tip()
        ev.accept()

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        padL, padR, padT, padB = self._geom()[2:]
        iw, ih = w - padL - padR, h - padT - padB
        if not self.data:
            p.setPen(TEXT3)
            p.drawText(self.rect(), Qt.AlignCenter, "暂无数据")
            return

        is_lg = theme_state.get("window_size") == "large"
        maxV = max((sum(v for _, _, v in d["parts"]) for d in self.data), default=1) or 1
        p.setFont(QFont("Consolas", 8.0 if is_lg else 7.5))
        for k in range(3):
            y = padT + ih - ih * k / 2
            p.setPen(QPen(BORDER, 1))
            p.drawLine(int(padL), int(y), int(w - padR), int(y))
            p.setPen(TEXT3)
            v = maxV * k / 2
            label = f"{v/1e8:.1f}亿" if v >= 1e8 else (f"{v/1e4:.0f}万" if v >= 1e4 else f"{v:.0f}")
            p.drawText(QRectF(0, y - 8, padL - 4, 16), Qt.AlignRight | Qt.AlignVCenter, label)

        n = len(self.data)
        slot = iw / n
        bw = max(3.0, min(16.0, slot * 0.6))
        p.setFont(QFont("Consolas", 7.8 if is_lg else 7.0))
        step = max(1, n // 7)
        for i, d in enumerate(self.data):
            cx = padL + slot * i + slot / 2
            y_cur = padT + ih
            for _m, color, v in d["parts"]:
                hh = v / maxV * ih
                p.setPen(Qt.NoPen)
                p.setBrush(color)
                p.drawRect(QRectF(cx - bw / 2, y_cur - hh, bw, hh))
                y_cur -= hh
            if i % step == 0 or i == n - 1:
                p.setPen(TEXT3)
                p.drawText(QRectF(cx - 24, h - padB + 1, 48, 14),
                           Qt.AlignCenter, d["date"][5:].replace("-", "/"))

    def mousePressEvent(self, ev):
        if ev.button() in (Qt.LeftButton, Qt.RightButton):
            self._drag_start_x = ev.position().x()
            self._drag_start_view = self.view_start

    def mouseMoveEvent(self, ev):
        if self._drag_start_x is not None and (ev.buttons() & (Qt.LeftButton | Qt.RightButton)):
            w, h, padL, padR, padT, padB = self._geom()
            iw = max(10, w - padL - padR)
            dx = ev.position().x() - self._drag_start_x
            shift_items = -(dx / iw) * self.view_count
            self.view_start = self._drag_start_view + shift_items
            self._sync_slice()
            ChartTip.instance().hide_tip()
            return

        if not self.data:
            return
        gp = ev.globalPosition().toPoint()
        x = ev.position().x()
        w, h, padL, padR, padT, padB = self._geom()
        iw = w - padL - padR
        
        # 边界防错：鼠标移出图表有效区域时不触发悬浮提示
        if padL <= x <= padL + iw and len(self.data) > 0:
            slot = iw / len(self.data)
            idx = int((x - padL) / slot)
            if 0 <= idx < len(self.data):
                d = self.data[idx]
                total = sum(v for _, _, v in d["parts"])
                rows = []
                for m, color, v in sorted(d["parts"], key=lambda t: -t[2]):
                    pct = v / total * 100 if total else 0
                    rows.append((color, m, f"{fmt_full(v)} ({pct:.1f}%)"))
                rows.append((None, "合计", fmt_full(total)))
                ChartTip.instance().show_tip(d["date"], rows, BLUE, gp)
                return
        ChartTip.instance().hide_tip()

    def mouseReleaseEvent(self, ev):
        self._drag_start_x = None

    def leaveEvent(self, ev):
        self._drag_start_x = None
        ChartTip.instance().hide_tip()


class HeatMap(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.daily = {}
        self.setMouseTracking(True)
        self._cells = []
        self.apply_size()

    def apply_size(self):
        m = curr_metric()
        self.setMinimumHeight(m["heat_min_h"])
        self.update()

    def set_data(self, daily):
        self.daily = {d: a for d, a in daily.items() if d != "unknown"}
        self.update()

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        m = curr_metric()
        cell, gap = m["heat_cell"], m["heat_gap"]
        unit = cell + gap
        self._cells = []
        if not self.daily:
            p.setPen(TEXT3)
            p.drawText(self.rect(), Qt.AlignCenter, "暂无数据")
            return
        maxV = max((sum(a.get("total", 0) for a in dm.values()) for dm in self.daily.values()),
                   default=1) or 1

        def level(v):
            r = v / maxV
            if r <= 0: return 0
            if r < 0.25: return 1
            if r < 0.5: return 2
            if r < 0.75: return 3
            return 4

        LV = [TRACK, QColor("#c8e8c9"), QColor("#7cc87f"),
              QColor("#3fa45b"), QColor("#1e6b33")]
        if theme_state["dark"]:
            LV = [TRACK, QColor("#0e4429"), QColor("#006d32"),
                  QColor("#26a641"), QColor("#39d353")]

        from collections import defaultdict
        months = defaultdict(list)
        for d in sorted(self.daily):
            months[d[:7]].append(d)

        fit_m = max(2, int((w - 20) / (7 * unit + 10)))
        recent_m = sorted(months.keys())[-fit_m:]

        x = 8
        top = 22
        is_lg = theme_state.get("window_size") == "large"
        p.setFont(QFont("Microsoft YaHei UI", 8.8 if is_lg else 8.0))
        import datetime as _dt
        for ym in recent_m:
            dlist = months[ym]
            p.setPen(TEXT2)
            p.drawText(QRectF(x, 1, 7 * unit, 16), Qt.AlignLeft | Qt.AlignVCenter, f"{int(ym[5:7])}月")
            first = _dt.date(int(ym[:4]), int(ym[5:7]), 1)
            first_wd = first.weekday()
            for d in dlist:
                try:
                    dd = _dt.date(int(d[:4]), int(d[5:7]), int(d[8:10]))
                except Exception:
                    continue
                row = (first_wd + dd.day - 1) // 7
                col = dd.weekday()
                tot = sum(a.get("total", 0) for a in self.daily[d].values())
                cx, cy = x + col * unit, top + row * unit
                self._cells.append((cx, cy, cell, cell, d, tot))
                p.setPen(Qt.NoPen)
                p.setBrush(LV[level(tot)])
                p.drawRoundedRect(QRectF(cx, cy, cell, cell), 2.5, 2.5)
            x += 7 * unit + 12

        p.setPen(TEXT3)
        p.setFont(QFont("Microsoft YaHei UI", 8.2 if is_lg else 7.5))
        p.drawText(QRectF(8, h - 15, 64, 14), Qt.AlignLeft | Qt.AlignVCenter, "少 → 多")
        for i, c in enumerate(LV):
            p.setPen(Qt.NoPen)
            p.setBrush(c)
            p.drawRoundedRect(QRectF(64 + i * (cell + 2), h - 14, cell - 1, cell - 1), 1.5, 1.5)

    def mouseMoveEvent(self, ev):
        pos = ev.position()
        hit = None
        for cx, cy, cw, ch, d, tot in self._cells:
            if cx <= pos.x() <= cx + cw and cy <= pos.y() <= cy + ch:
                hit = (d, tot)
                break
        if hit:
            d, tot = hit
            dm = self.daily.get(d, {})
            rows = []
            for m, a in sorted(dm.items(), key=lambda kv: -kv[1].get("total", 0))[:5]:
                rows.append((None, m, fmt_full(a.get("total", 0))))
            if len(dm) > 5:
                rows.append((None, f"… 共 {len(dm)} 个模型", ""))
            rows.append((None, "合计", fmt_full(tot)))
            ChartTip.instance().show_tip(d, rows, GREEN, ev.globalPosition().toPoint())
        else:
            ChartTip.instance().hide_tip()

    def leaveEvent(self, ev):
        ChartTip.instance().hide_tip()


# ============================================================ DSH 数据层
def dsh_ledger_path():
    base = os.environ.get("DSH_HOME") or os.path.expanduser("~/.dsh")
    return os.path.join(base, "storages", "cost-meter", "ledger.json")


def load_dsh_stats():
    path = dsh_ledger_path()
    if not os.path.exists(path):
        return {"error": f"DSH 账本不存在: {path}", "source": "dsh"}
    try:
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
    except Exception as e:
        return {"error": f"读取 DSH 账本失败: {e}", "source": "dsh"}

    daily = {}
    daily_sessions = {}
    session_ids = set()
    first = last = None
    total_cost = 0.0
    days = d.get("days", {})
    for date, day in days.items():
        if date == "unknown":
            continue
        if first is None or date < first: first = date
        if last is None or date > last: last = date
        dm = daily.setdefault(date, {})
        day_sids = {ss.get("id") for ss in (day.get("sessions") or [])
                    if isinstance(ss, dict) and ss.get("id")}
        session_ids |= day_sids
        daily_sessions[date] = len(day_sids)
        for model, b in day.get("byProviderModel", {}).items():
            mk = model.replace(":", "/")
            mi = b.get("input", 0)
            mo = b.get("output", 0)
            mcr = b.get("cacheRead", 0)
            mcw = b.get("cacheWrite", 0)
            mt = mi + mo + mcr + mcw
            if mt <= 0 and b.get("calls", 0) <= 0:
                continue
            dm[mk] = {"requests": b.get("calls", 0),
                      "input": mi + mcr + mcw, "output": mo,
                      "cached": mcr, "cacheWrite": mcw, "total": mt}
        total_cost += day.get("cost", 0.0)

    today = time.strftime("%Y-%m-%d")
    t_mod = daily.get(today, {})
    t_in = t_out = t_cr = t_cw = 0
    for b in t_mod.values():
        t_in += b["input"]
        t_out += b["output"]
        t_cr += b["cached"]
        t_cw += b["cacheWrite"]
    today_led = days.get(today, {})
    today_sess = len({ss.get("id") for ss in (today_led.get("sessions") or [])
                      if isinstance(ss, dict) and ss.get("id")})
    today_rec = {"requests": today_led.get("calls", 0),
                 "input": t_in, "output": t_out,
                 "cached": t_cr, "cacheWrite": t_cw,
                 "total": t_in + t_out,
                 "sessions": today_sess,
                 "cost": today_led.get("cost", 0.0)}

    return {
        "source": "dsh", "dsh": True,
        "daily": daily, "dailySessions": daily_sessions,
        "sessionsTotal": len(session_ids), "today": today_rec,
        "totalCost": round(total_cost, 2),
        "firstDay": first, "lastDay": last,
    }


# ============================================================ 商汤积分数据层
SN_WINDOW_HOURS = 5
SN_KNOWN_QUOTA = {
    "sensenova-6.8-flash-lite": 1500, "sensenova-6.7-flash-lite": 1500,
    "sensenova-u1-fast": 1500, "sensenova-u1.5-lite": 1500,
    "deepseek-v4-flash": 500, "glm-5.2": 500,
}
SN_POOL_WINDOW_QUOTA = 60000
SN_POOL_WEEKLY_QUOTA = 600000

SN_AUTOSYNC_FILE = os.path.join(scanner.PLUGIN_DATA_DIR, "sn_autosync.json")
SN_AUTOSYNC_TTL = 300
_autosync_mem = {"ts": 0.0, "values": None, "error": None}


def load_sn_autosync():
    try:
        with open(SN_AUTOSYNC_FILE, encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) and d.get("url") else None
    except Exception:
        return None


def save_sn_autosync(d):
    try:
        with open(SN_AUTOSYNC_FILE, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False)
        return True
    except Exception:
        return False


def clear_sn_autosync():
    try:
        if os.path.exists(SN_AUTOSYNC_FILE):
            os.remove(SN_AUTOSYNC_FILE)
    except Exception:
        pass
    try:
        with open(SN_AUTOSYNC_FILE, "w", encoding="utf-8") as f:
            f.write("{}")
    except Exception:
        pass


def _curl_tokens(text):
    text = text.replace("\r\n", "\n")
    out, cur, quote = [], [], None
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c in ("\\", "^") and i + 1 < n and text[i + 1] == "\n":
            i += 2
            continue
        if c == "^":
            i += 1
            continue
        if quote is None and c in ("'", '"'):
            quote = c
            i += 1
            continue
        if quote is not None:
            if c == "\\" and quote == '"' and i + 1 < n and text[i + 1] == '"':
                cur.append('"')
                i += 2
                continue
            if c == quote:
                quote = None
                i += 1
                continue
            cur.append(c)
            i += 1
            continue
        if c.isspace():
            if cur:
                out.append("".join(cur))
                cur = []
            i += 1
            continue
        cur.append(c)
        i += 1
    if cur:
        out.append("".join(cur))
    return out


def parse_curl(text):
    toks = _curl_tokens(text)
    url, method, body = None, None, None
    headers = {}
    i = 0
    while i < len(toks):
        t = toks[i]
        tl = t.lower()
        if tl in ("-h", "--header") and i + 1 < len(toks):
            kv = toks[i + 1]
            k, _, v = kv.partition(":")
            headers[k.strip()] = v.strip()
            i += 2
            continue
        if tl in ("-x", "--request") and i + 1 < len(toks):
            method = toks[i + 1].upper()
            i += 2
            continue
        if tl in ("-b", "--cookie") and i + 1 < len(toks):
            headers["Cookie"] = toks[i + 1]
            i += 2
            continue
        if tl in ("-d", "--data", "--data-raw", "--data-binary", "--data-ascii") and i + 1 < len(toks):
            body = toks[i + 1]
            i += 2
            continue
        if t.startswith("http://") or t.startswith("https://"):
            url = t
            i += 1
            continue
        i += 1
    if not url:
        return None
    if method is None:
        method = "POST" if body is not None else "GET"
    return {"url": url, "method": method, "headers": headers, "body": body}


def _find_value_paths(node, target, path=""):
    """在 JSON 树中递归寻找数值等于 target 的字段, 返回路径列表 (如 'data.general.week').

    数字与"可解析为数字的字符串"都参与匹配 — 商汤接口的余额字段是字符串数字
    (如 "52919.02288"), 不处理字符串会永远匹配不上。
    """
    hits = []
    if isinstance(node, dict):
        for k, v in node.items():
            hits += _find_value_paths(v, target, f"{path}.{k}" if path else str(k))
    elif isinstance(node, list):
        for idx, v in enumerate(node):
            hits += _find_value_paths(v, target, f"{path}[{idx}]")
    elif isinstance(node, (int, float)) and not isinstance(node, bool):
        try:
            if abs(float(node) - float(target)) < 1e-6:
                hits.append(path)
        except (TypeError, ValueError):
            pass
    elif isinstance(node, str):
        try:
            if abs(float(node) - float(target)) < 1e-6:
                hits.append(path)
        except ValueError:
            pass
    return hits


def _get_path(node, path):
    import re
    cur = node
    for part in re.findall(r"[^\.\[\]]+|\[\d+\]", path):
        if part.startswith("["):
            idx = int(part[1:-1])
            if not isinstance(cur, list) or idx >= len(cur): return None
            cur = cur[idx]
        else:
            if not isinstance(cur, dict) or part not in cur: return None
            cur = cur[part]
    if isinstance(cur, str):
        try: return float(cur)
        except ValueError: return cur
    return cur


def _enrich_paths(data, paths):
    import re
    seen = {}
    for _key, p in paths.items():
        mm = re.match(r"^(.*pools\[\d+\])", p)
        if mm and mm.group(1) not in seen:
            nd = _get_path(data, mm.group(1))
            if isinstance(nd, dict):
                seen[mm.group(1)] = nd
    for node_path, nd in seen.items():
        pfx = {"default": "general", "dedicated": "flash"}.get(nd.get("pool_type"))
        if not pfx: continue
        w5, w7 = nd.get("window_5h"), nd.get("window_7d")
        if isinstance(w5, dict) and "reset_at" in w5:
            paths[f"{pfx}_reset5"] = f"{node_path}.window_5h.reset_at"
        if isinstance(w7, dict) and "reset_at" in w7:
            paths[f"{pfx}_resetw"] = f"{node_path}.window_7d.reset_at"
        if pfx == "general":
            if "grant_balance" in nd:
                paths["promo"] = f"{node_path}.grant_balance"
            if "nearest_grant_expiry" in nd:
                paths["promo_exp_ts"] = f"{node_path}.nearest_grant_expiry"
            if "nearest_grant_expiring_balance" in nd:
                paths["promo_exp_bal"] = f"{node_path}.nearest_grant_expiring_balance"
    return paths


def _detect_paths_by_structure(data):
    pools = data.get("pools") if isinstance(data, dict) else None
    if not isinstance(pools, list): return None
    paths = {}
    for i, nd in enumerate(pools):
        if not isinstance(nd, dict): continue
        pt = nd.get("pool_type")
        nm = str(nd.get("name", ""))
        if pt == "default" or "通用" in nm:
            pfx = "general"
        elif pt == "dedicated" or "flash" in nm.lower():
            pfx = "flash"
        else:
            continue
        w5, w7 = nd.get("window_5h"), nd.get("window_7d")
        if isinstance(w5, dict) and "remaining" in w5:
            paths[f"{pfx}_5h"] = f"pools[{i}].window_5h.remaining"
        if isinstance(w7, dict) and "remaining" in w7:
            paths[f"{pfx}_w"] = f"pools[{i}].window_7d.remaining"
    if "general_w" in paths or "general_5h" in paths:
        return _enrich_paths(data, paths)
    return None


def _http_json(req):
    import urllib.request, urllib.error

    def _do(opener):
        r = urllib.request.Request(req["url"], method=req["method"])
        for k, v in req.get("headers", {}).items():
            if k.lower() in ("content-length", "host", "accept-encoding"): continue
            r.add_header(k, v)
        data = None
        if req.get("body") is not None:
            data = req["body"].encode("utf-8")
            if not any(k.lower() == "content-type" for k in req["headers"]):
                r.add_header("Content-Type", "application/json")
        with opener.open(r, data=data, timeout=10) as resp:
            return resp.status, resp.read(2_000_000).decode("utf-8", "replace")

    try:
        status, raw = _do(urllib.request.build_opener())
    except urllib.error.HTTPError as e:
        return e.code, None, f"HTTP {e.code}"
    except urllib.error.URLError as e:
        reason = str(getattr(e, "reason", "")) + str(e)
        if "10061" in reason:
            try:
                direct = urllib.request.build_opener(urllib.request.ProxyHandler({}))
                status, raw = _do(direct)
            except urllib.error.HTTPError as e2: return e2.code, None, f"HTTP {e2.code}"
            except Exception as e2: return 0, None, f"{str(e2)[:60]} (直连失败)"
        else:
            return 0, None, str(e)[:80]
    except Exception as e:
        return 0, None, str(e)[:80]
    try:
        return status, json.loads(raw), None
    except Exception:
        return status, None, "响应不是 JSON"


# ============================================================ 商汤积分自动同步 (Playwright 持久登录态 + token 直连)
SN_EDGE_PATH = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
SN_LOGIN_STATE = os.path.join(scanner.PLUGIN_DATA_DIR, "sn_login_state.json")
SN_ACCOUNT_FILE = os.path.join(scanner.PLUGIN_DATA_DIR, "sn_account.json")
SN_TOKEN_FILE = os.path.join(scanner.PLUGIN_DATA_DIR, "sn_token.json")
SN_POOL_API = "/lite/console/v1/tokenplan/pool-usage"
SN_POOL_URL = "https://platform.sensenova.cn" + SN_POOL_API
SN_CONSOLE_URL = "https://platform.sensenova.cn/console"
SN_USE_PLAYWRIGHT = True   # 真自动抓取开关 (测试环境置 False 走 cURL mock)


def _sn_load_token():
    """从登录态/缓存读取 access_token (优先 sn_token.json 缓存, 回退 login_state)"""
    # 1) 优先读独立缓存
    try:
        with open(SN_TOKEN_FILE, "r", encoding="utf-8") as f:
            d = json.load(f)
        tok = d.get("access_token")
        if tok:
            return tok
    except Exception:
        pass
    # 2) 回退从 login_state 的 origins.localStorage 提取
    try:
        with open(SN_LOGIN_STATE, "r", encoding="utf-8") as f:
            st = json.load(f)
        for origin in st.get("origins", []):
            for item in origin.get("localStorage", []):
                if item.get("name") == "access_token" and item.get("value"):
                    return item["value"]
    except Exception:
        pass
    return None


def _sn_save_token(tok):
    try:
        with open(SN_TOKEN_FILE, "w", encoding="utf-8") as f:
            json.dump({"access_token": tok}, f)
    except Exception:
        pass


def _sn_parse_pool_data(data):
    """零指纹解析 pool-usage 数据 → values dict (与旧 sn_autosync_fetch 一致)"""
    paths = _detect_paths_by_structure(data)
    if not paths:
        return None
    values = {}
    for key, p in paths.items():
        v = _get_path(data, p)
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            values[key] = float(v)
    return values or None


def _sn_playwright_ready():
    """Playwright 是否可用(已安装 + 系统 Edge 存在)"""
    try:
        import playwright  # noqa: F401
        return os.path.exists(SN_EDGE_PATH)
    except Exception:
        return False


def _sn_direct_fetch(token):
    """用 access_token urllib 直连 pool-usage, 返回 (data_dict, error)。401 返回 (None, '401')"""
    import urllib.request, urllib.error
    ctx = None
    try:
        import ssl
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    except Exception:
        pass
    req = urllib.request.Request(SN_POOL_URL, headers={
        "Authorization": "Bearer " + token,
        "accept": "application/json",
        "User-Agent": "Mozilla/5.0",
    })
    try:
        if ctx is not None:
            resp = urllib.request.urlopen(req, timeout=15, context=ctx)
        else:
            resp = urllib.request.urlopen(req, timeout=15)
        body = resp.read(2_000_000).decode("utf-8", "replace")
        data = json.loads(body)
        if isinstance(data, dict) and data.get("pools"):
            return data, None
        return None, "积分接口无 pools 数据"
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            return None, "401"
        return None, f"HTTP {e.code}"
    except Exception as e:
        return None, str(e)[:120]


def _sn_playwright_login_and_fetch():
    """Playwright 登录(必要时自动填账号密码) → 刷新 access_token → 抓取数据。返回 (data, token, error)"""
    if not _sn_playwright_ready():
        return None, None, "playwright 未安装或未找到系统 Edge"
    if not os.path.exists(SN_LOGIN_STATE):
        return None, None, "未登录 (请在商汤页填写账号密码或运行 sn_login.py)"
    try:
        from playwright.sync_api import sync_playwright
    except Exception as e:
        return None, None, f"playwright 导入失败: {str(e)[:80]}"

    username = password = ""
    try:
        with open(SN_ACCOUNT_FILE, "r", encoding="utf-8-sig") as f:
            acct = json.load(f)
        username = acct.get("username", "")
        password = acct.get("password", "")
    except Exception:
        pass

    captured = {}
    token = None
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path=SN_EDGE_PATH, headless=True)
            ctx = browser.new_context(storage_state=SN_LOGIN_STATE)
            page = ctx.new_page()

            def on_response(resp):
                u = resp.url
                if SN_POOL_API in u and resp.status == 200:
                    try:
                        d = json.loads(resp.text())
                    except Exception:
                        return
                    if isinstance(d, dict) and d.get("pools"):
                        captured["data"] = d

            page.on("response", on_response)
            page.goto(SN_CONSOLE_URL, timeout=30000)
            page.wait_for_timeout(5000)

            # 登录态失效 → 自动重登
            if not captured.get("data") and "/login" in page.url:
                if not username or not password:
                    browser.close()
                    return None, None, "登录态已过期且未配置账号密码"
                try:
                    page.get_by_text("账号密码登录", exact=True).click(timeout=8000)
                    page.wait_for_timeout(1500)
                    page.get_by_placeholder("请设置用户名").fill(username)
                    page.get_by_placeholder("请输入密码").fill(password)
                    page.wait_for_timeout(400)
                    page.get_by_role("button", name="登录", exact=True).click(timeout=8000)
                    page.wait_for_timeout(8000)
                except Exception as e:
                    browser.close()
                    return None, None, f"自动重登失败: {str(e)[:100]}"

            # 提取 access_token
            try:
                token = page.evaluate("() => localStorage.getItem('access_token')")
            except Exception:
                pass

            if not captured.get("data"):
                browser.close()
                return None, token, "未捕获到积分数据"

            # 保存刷新后的登录态 + token 缓存
            try:
                ctx.storage_state(path=SN_LOGIN_STATE)
            except Exception:
                pass
            if token:
                _sn_save_token(token)
            browser.close()
    except Exception as e:
        return None, None, f"playwright 抓取异常: {str(e)[:120]}"

    data = captured.get("data")
    return data, token, None


def sn_playwright_fetch():
    """商汤积分真自动抓取: token 直连优先(快) → 401 时 Playwright 重登刷新(慢兜底)。

    返回 (values_dict, error)。
    """
    # 快路径: 用缓存 access_token 直连
    token = _sn_load_token()
    if token:
        data, err = _sn_direct_fetch(token)
        if data is not None:
            values = _sn_parse_pool_data(data)
            if values:
                _sn_save_token(token)   # 缓存 token, 避免每次从 login_state 解析
                return values, None
        # 401 或解析失败 → 走 Playwright 重登刷新
    elif not os.path.exists(SN_LOGIN_STATE):
        return None, "未登录 (请在商汤页填写账号密码完成首次登录)"

    # 慢路径: Playwright 登录/重登 + 抓取
    data, new_token, err = _sn_playwright_login_and_fetch()
    if data is None:
        return None, err or "抓取失败"
    values = _sn_parse_pool_data(data)
    if not values:
        return None, "积分接口响应结构无法识别"
    return values, None



def sn_autosync_fetch(force=False):
    # 优先 Playwright 真自动抓取 (持久登录态, 免 3h 手动抓包)
    if SN_USE_PLAYWRIGHT and _sn_playwright_ready() and os.path.exists(SN_LOGIN_STATE):
        now = time.time()
        if not force and now - _autosync_mem["ts"] < SN_AUTOSYNC_TTL and _autosync_mem["values"] is not None:
            return _autosync_mem["values"]
        vals, err = sn_playwright_fetch()
        if vals:
            _autosync_mem.update(ts=now, values=vals, error=None)
            return vals
        # Playwright 失败则回退 cURL (旧半自动方案兜底)
        _autosync_mem.update(ts=now, values=None, error=err)
    cfg = load_sn_autosync()
    if not cfg: return None
    now = time.time()
    if not force and now - _autosync_mem["ts"] < SN_AUTOSYNC_TTL and _autosync_mem["values"] is not None:
        return _autosync_mem["values"]
    paths = cfg.get("paths") or {}
    if not paths:
        _autosync_mem.update(ts=now, values=None, error="未配置字段路径")
        return None
    status, data, err = _http_json(cfg)
    if err:
        _autosync_mem.update(ts=now, values=None, error=f"{err} (凭据过期? 重新抓包)")
        return None
    values = {}
    for key, p in paths.items():
        v = _get_path(data, p)
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            values[key] = float(v)
    if not values:
        _autosync_mem.update(ts=now, values=None, error="接口响应结构变化")
        return None
    _autosync_mem.update(ts=now, values=values, error=None)
    cfg["last_ok_ts"] = now
    cfg["last_values"] = values
    save_sn_autosync(cfg)
    return values


SN_EVENTS_CACHE_FILE = os.path.join(scanner.PLUGIN_DATA_DIR, "sn_events_cache.json")


def _load_sn_events_cache():
    try:
        with open(SN_EVENTS_CACHE_FILE, encoding="utf-8") as f:
            d = json.load(f)
        if isinstance(d, dict) and d.get("v") == 1:
            return d.get("files", {})
    except Exception:
        pass
    return {}


def _save_sn_events_cache(files_map):
    try:
        with open(SN_EVENTS_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump({"v": 1, "files": files_map}, f, ensure_ascii=False)
    except Exception:
        pass


def _sn_events_all():
    cache = _load_sn_events_cache()
    files = {}
    dirty = False
    for path in scanner._iter_jsonl_files():
        try:
            st = os.stat(path)
            size, mtime = st.st_size, int(st.st_mtime)
        except OSError:
            continue
        ent = cache.get(path)
        if ent and ent.get("size") == size and ent.get("mtime") == mtime:
            files[path] = ent["events"]
            continue
        events = []
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                for line in f:
                    for e in scanner._extract_usage_from_line(line):
                        m = (e.get("model") or "").lower()
                        if not is_sn_model(m): continue
                        t = _ts_to_epoch(e.get("ts"))
                        if t is not None: events.append([t, m])
        except OSError:
            continue
        cache[path] = {"size": size, "mtime": mtime, "events": events}
        files[path] = events
        dirty = True
    for p in list(cache):
        if p not in files:
            del cache[p]
            dirty = True
    if dirty:
        _save_sn_events_cache(cache)
    return files


def is_sn_model(name):
    s = (name or "").lower()
    if "sensenova" in s: return True
    return ("/" not in s) and s in ("deepseek-v4-flash", "glm-5.2")


def sn_canonical(name):
    s = (name or "").lower()
    if s.startswith("sensenova/"): s = s[len("sensenova/"):]
    if s in ("deepseek-v4-flash", "glm-5.2"): return s
    if s.startswith("sensenova-"): return s
    return "sensenova-" + s


def sn_window_bounds(now=None):
    import datetime as _dt
    now = now if now is not None else time.time()
    dt = _dt.datetime.fromtimestamp(now)
    mins = dt.hour * 60 + dt.minute
    start_mins = (mins // (SN_WINDOW_HOURS * 60)) * SN_WINDOW_HOURS * 60
    start = _dt.datetime(dt.year, dt.month, dt.day) + _dt.timedelta(minutes=start_mins)
    end = start + _dt.timedelta(hours=SN_WINDOW_HOURS)
    return start.timestamp(), end.timestamp()


def _ts_to_epoch(ts):
    import datetime as _dt
    if ts is None or ts == "": return None
    if isinstance(ts, (int, float)):
        v = float(ts)
        return v / 1000.0 if v > 1e12 else v
    s = str(ts)
    try:
        dt = _dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
        if dt.tzinfo is not None: dt = dt.astimezone()
        return dt.timestamp()
    except Exception: pass
    for fmt_str in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try: return time.mktime(time.strptime(s[:19], fmt_str))
        except Exception: continue
    return None


def _load_wb_stats():
    try:
        with open(scanner.STATS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _fmt_reset(ts):
    import datetime as _dt
    dt = _dt.datetime.fromtimestamp(ts)
    return f"{dt.month}月{dt.day}日 {dt:%H:%M}"


def _next_weekly_reset_str():
    import datetime as _dt
    anchor = _dt.datetime(2026, 8, 28)
    now = _dt.datetime.now()
    week = _dt.timedelta(days=7)
    nxt = anchor if now < anchor else anchor + (int((now - anchor) // week) + 1) * week
    return f"{nxt.month}月{nxt.day}日 {nxt:%H:%M}"


def load_sn_stats(force=False):
    import collections
    wb = _load_wb_stats()
    candidates = {sn_canonical(n) for n in SN_KNOWN_QUOTA}
    if wb:
        for m in wb.get("models", {}):
            if is_sn_model(m): candidates.add(sn_canonical(m))
    dsh = None
    try: dsh = load_dsh_stats()
    except Exception: dsh = None
    if dsh and "error" not in dsh:
        for dm in dsh.get("daily", {}).values():
            for m in dm:
                if is_sn_model(m): candidates.add(sn_canonical(m))

    ws, we = sn_window_bounds()
    canon_used = collections.defaultdict(int)
    canon_since = collections.defaultdict(int)
    canon_win_since = collections.defaultdict(int)
    sync = None
    sync_src = None
    auto_vals = sn_autosync_fetch(force=force)
    if auto_vals:
        sync = {"ts": _autosync_mem["ts"],
                "general_w": auto_vals.get("general_w"),
                "general_5h": auto_vals.get("general_5h"),
                "flash_w": auto_vals.get("flash_w"),
                "flash_5h": auto_vals.get("flash_5h"),
                "general_reset5": auto_vals.get("general_reset5"),
                "general_resetw": auto_vals.get("general_resetw"),
                "flash_reset5": auto_vals.get("flash_reset5"),
                "flash_resetw": auto_vals.get("flash_resetw"),
                "promo": auto_vals.get("promo") if "promo" in auto_vals else None,
                "promo_exp_ts": auto_vals.get("promo_exp_ts"),
                "promo_exp_bal": auto_vals.get("promo_exp_bal")}
        sync_src = "auto"
    sync_ts = sync["ts"] if sync else None
    cands_low = {c.lower() for c in candidates}
    if candidates:
        for events in _sn_events_all().values():
            for t, m in events:
                if m not in cands_low: continue
                in_win = ws <= t <= we
                after = sync_ts is not None and t >= sync_ts
                if in_win:
                    canon_used[sn_canonical(m)] += 1
                    if after: canon_win_since[sn_canonical(m)] += 1
                if after: canon_since[sn_canonical(m)] += 1

    canon_dsh = collections.defaultdict(int)
    if dsh and "error" not in dsh:
        today = time.strftime("%Y-%m-%d")
        for m, b in dsh.get("daily", {}).get(today, {}).items():
            if is_sn_model(m):
                canon_dsh[sn_canonical(m)] += b.get("requests", 0)

    flash_lite = {"sensenova-6.8-flash-lite", "sensenova-6.7-flash-lite"}
    def pool_of(c): return "flash_lite" if c in flash_lite else "general"

    acc = {"general": [0, 0], "flash_lite": [0, 0]}
    acc_since = {"general": 0, "flash_lite": 0}
    for c in candidates:
        pk = pool_of(c)
        acc[pk][0] += canon_used.get(c, 0)
        acc[pk][1] += canon_used.get(c, 0) + canon_dsh.get(c, 0)
        acc_since[pk] += canon_since.get(c, 0)

    # 增量扣除同步时刻后的调用
    sync_time_str = None
    if sync:
        try: sync_time_str = time.strftime("%H:%M", time.localtime(sync["ts"]))
        except Exception: sync_time_str = None
        for pid, wkey, hkey in (("general", "general_w", "general_5h"),
                                ("flash_lite", "flash_w", "flash_5h")):
            wk = sync.get(wkey)
            if isinstance(wk, (int, float)) and wk >= 0:
                acc[pid][1] = max(0, SN_POOL_WEEKLY_QUOTA - wk) + acc_since[pid]
            hk = sync.get(hkey)
            if isinstance(hk, (int, float)) and hk >= 0:
                if sync_ts is not None and sync_ts >= ws:
                    in_win_after = sum(canon_win_since.get(c, 0) for c in candidates if pool_of(c) == pid)
                    acc[pid][0] = max(0, SN_POOL_WINDOW_QUOTA - hk) + in_win_after

    exact = {}
    if sync_src == "auto" and sync:
        for pid, pfx in (("general", "general"), ("flash_lite", "flash")):
            e = {}
            r5, rw = sync.get(f"{pfx}_5h"), sync.get(f"{pfx}_w")
            if isinstance(r5, (int, float)) and r5 >= 0: e["w5"] = r5
            if isinstance(rw, (int, float)) and rw >= 0: e["w7"] = rw
            if e: exact[pid] = e

    reset_5h_ts = None
    reset_w_ts = None
    if sync:
        for k in ("general_reset5", "flash_reset5"):
            v = sync.get(k)
            if isinstance(v, (int, float)) and v > 0: reset_5h_ts = v; break
        for k in ("general_resetw", "flash_resetw"):
            v = sync.get(k)
            if isinstance(v, (int, float)) and v > 0: reset_w_ts = v; break

    def build_pool(pid, name, scope, color, a):
        ex = exact.get(pid) or {}
        w5_rem = ex.get("w5", max(0, SN_POOL_WINDOW_QUOTA - a[0]))
        w7_rem = ex.get("w7", max(0, SN_POOL_WEEKLY_QUOTA - a[1]))
        return {
            "id": pid, "name": name, "scope": scope, "color": color,
            "window_total": SN_POOL_WINDOW_QUOTA,
            "window_remaining": max(0, w5_rem),
            "weekly_total": SN_POOL_WEEKLY_QUOTA,
            "weekly_remaining": float(max(0, w7_rem)),
            "window_reset": (_fmt_reset(reset_5h_ts) if isinstance(reset_5h_ts, (int, float)) and reset_5h_ts > 0 else _fmt_reset(we)),
            "next_weekly_reset": (_fmt_reset(reset_w_ts) if isinstance(reset_w_ts, (int, float)) and reset_w_ts > 0 else _next_weekly_reset_str()),
            "synced": sync is not None, "sync_time": sync_time_str,
        }

    promo_total = sync.get("promo") if sync else None
    promo_expire = sync.get("promo_expire") if sync else None
    promo_total = promo_total if isinstance(promo_total, (int, float)) else 0
    promo_expire = promo_expire if isinstance(promo_expire, str) and promo_expire else "—"
    exp_ts = sync.get("promo_exp_ts") if sync else None
    exp_bal = sync.get("promo_exp_bal") if sync else None
    if isinstance(exp_ts, (int, float)) and exp_ts > 0:
        try:
            promo_expire = _fmt_reset(exp_ts)
            if isinstance(exp_bal, (int, float)) and exp_bal > 0:
                bal_s = f"{exp_bal:.3f}".rstrip("0").rstrip(".")
                promo_expire += f" · {bal_s}"
        except Exception:
            pass

    pools = [
        build_pool("general", "通用积分池", "所有 Free 模型可用", "purple", acc["general"]),
        build_pool("flash_lite", "Flash-Lite 专属积分池", "仅 Flash-Lite 系列模型", "orange", acc["flash_lite"]),
        {"id": "promo", "name": "活动固定积分",
         "total_balance": promo_total, "nearest_expire": promo_expire,
         "synced": sync is not None, "sync_time": sync_time_str},
    ]
    return {
        "source": "sn", "window_start": ws, "window_end": we,
        "pools": pools, "synced": sync is not None, "sync_time": sync_time_str,
        "sync_src": sync_src, "autosync_error": _autosync_mem["error"],
    }


# ============================================================ 商汤积分池卡片 (双进度对称仪表)
SN_PURPLE = QColor("#7c67ff")
SN_PURPLE_DARK = QColor("#9d8eff")
SN_ORANGE = QColor("#ff7043")
SN_ORANGE_DARK = QColor("#ff8a65")


class SNProgressBar(QWidget):
    """通栏圆角细进度条"""
    def __init__(self, ratio=0.0, color="purple", parent=None):
        super().__init__(parent)
        self.ratio = ratio
        self.color = color
        self.apply_size()

    def apply_size(self):
        m = curr_metric()
        self.setFixedHeight(m["sn_prog_h"])
        self.update()

    def set_ratio(self, r):
        self.ratio = max(0.0, min(1.0, r))
        self.update()

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        r = h / 2.0

        p.setPen(Qt.NoPen)
        p.setBrush(TRACK)
        p.drawRoundedRect(QRectF(0, 0, w, h), r, r)

        fill_w = max(h, w * self.ratio)
        dark = theme_state["dark"]
        fill = (SN_ORANGE_DARK if dark else SN_ORANGE) if self.color == "orange" \
            else (SN_PURPLE_DARK if dark else SN_PURPLE)

        p.setBrush(fill)
        p.drawRoundedRect(QRectF(0, 0, fill_w, h), r, r)


class SNPoolCard(GlassPodFrame):
    """商汤积分池卡片: 周周期与 5h 窗口额度对称呈现，通栏舒展"""
    def __init__(self, pool, parent=None):
        super().__init__(radius=12, parent=parent)
        self.pool = pool
        self.setObjectName("sn_pool_card")
        self._build_ui()
        self.apply_theme()

    def _build_ui(self):
        v = QVBoxLayout(self)
        v.setContentsMargins(16, 13, 16, 13)
        v.setSpacing(9)

        # 1. 顶栏
        top = QHBoxLayout()
        top.setSpacing(8)

        self.tag_badge = QLabel()
        self.tag_badge.setFont(QFont("Microsoft YaHei UI", 8.5, QFont.Bold))
        top.addWidget(self.tag_badge)

        self.name_lbl = QLabel(self.pool["name"])
        top.addWidget(self.name_lbl)
        top.addStretch(1)

        self.scope_lbl = QLabel(self.pool.get("scope", ""))
        top.addWidget(self.scope_lbl)
        v.addLayout(top)

        # 2. 周周期额度
        week_box = QVBoxLayout()
        week_box.setSpacing(3)

        w_top = QHBoxLayout()
        self.week_title = QLabel("周周期额度")
        w_top.addWidget(self.week_title)
        w_top.addStretch(1)

        wt_week = self.pool.get("weekly_total", 0)
        r_week = self.pool["weekly_remaining"] / wt_week if wt_week else 0
        self.week_val_lbl = QLabel(f"{self.pool['weekly_remaining']:,.0f} / {wt_week:,} ({r_week * 100:.1f}%)")
        w_top.addWidget(self.week_val_lbl)
        week_box.addLayout(w_top)

        self.bar_week = SNProgressBar(r_week, color=self.pool.get("color", "purple"))
        week_box.addWidget(self.bar_week)

        w_bot = QHBoxLayout()
        w_bot.addStretch(1)
        nr = self.pool.get("next_weekly_reset", "—")
        self.week_reset_lbl = QLabel(f"周额度重置于: {nr}")
        w_bot.addWidget(self.week_reset_lbl)
        week_box.addLayout(w_bot)

        v.addLayout(week_box)

        # 3. 5h 滑动窗口额度
        win_box = QVBoxLayout()
        win_box.setSpacing(3)

        win_top = QHBoxLayout()
        self.window_title = QLabel("5h 窗口额度")
        win_top.addWidget(self.window_title)
        win_top.addStretch(1)

        wt_win = self.pool.get("window_total", 0)
        r_win = self.pool["window_remaining"] / wt_win if wt_win else 0
        self.window_val_lbl = QLabel(f"{self.pool['window_remaining']:,.0f} / {wt_win:,} ({r_win * 100:.1f}%)")
        win_top.addWidget(self.window_val_lbl)
        win_box.addLayout(win_top)

        self.bar_win = SNProgressBar(r_win, color=self.pool.get("color", "purple"))
        win_box.addWidget(self.bar_win)

        win_bot = QHBoxLayout()
        win_bot.addStretch(1)
        self.window_reset_lbl = QLabel(f"5h窗口重置于: {self.pool.get('window_reset', '—')}")
        win_bot.addWidget(self.window_reset_lbl)
        win_box.addLayout(win_bot)

        v.addLayout(win_box)

    def apply_size(self):
        m = curr_metric()
        self.name_lbl.setFont(QFont("Microsoft YaHei UI", m["sn_title_pt"], QFont.Bold))
        self.scope_lbl.setFont(QFont("Microsoft YaHei UI", m["sn_sub_pt"]))
        self.week_title.setFont(QFont("Microsoft YaHei UI", m["sn_sub_pt"]))
        self.window_title.setFont(QFont("Microsoft YaHei UI", m["sn_sub_pt"]))
        self.week_val_lbl.setFont(QFont("Consolas", m["sn_sub_pt"], QFont.Bold))
        self.window_val_lbl.setFont(QFont("Consolas", m["sn_sub_pt"], QFont.Bold))
        self.week_reset_lbl.setFont(QFont("Microsoft YaHei UI", m["sn_date_pt"]))
        self.window_reset_lbl.setFont(QFont("Microsoft YaHei UI", m["sn_date_pt"]))
        self.bar_week.apply_size()
        self.bar_win.apply_size()
        self.update()

    def apply_theme(self):
        dark = theme_state["dark"]
        is_orange = self.pool.get("color") == "orange"
        accent = (SN_ORANGE_DARK if dark else SN_ORANGE) if is_orange \
            else (SN_PURPLE_DARK if dark else SN_PURPLE)

        self.setStyleSheet("#sn_pool_card { background:transparent; border:none; }")

        badge_bg = qrgba(accent, 35 if dark else 24)
        badge_text = qname(accent)
        self.tag_badge.setText("Flash-Lite" if is_orange else "通用池")
        self.tag_badge.setStyleSheet(
            f"background:{badge_bg}; color:{badge_text}; border-radius:5px; padding:2px 7px;")

        self.name_lbl.setStyleSheet(f"color:{qname(TEXT)};")
        self.week_val_lbl.setStyleSheet(f"color:{badge_text};")
        self.window_val_lbl.setStyleSheet(f"color:{badge_text};")

        for lbl in (self.week_title, self.window_title, self.scope_lbl):
            lbl.setStyleSheet(f"color:{qname(TEXT3)};")

        for lbl in (self.week_reset_lbl, self.window_reset_lbl):
            lbl.setStyleSheet(f"color:{qname(TEXT2)};")

        self.apply_size()
        self.bar_week.update()
        self.bar_win.update()
        self.update()


class SNSyncPanel(GlassPodFrame):
    """纯净极简同步面板"""
    saved = Signal()
    cleared = Signal()
    save_finished = Signal(bool, str)

    def __init__(self, parent=None):
        super().__init__(radius=12, parent=parent)
        self.setObjectName("sn_sync_panel")
        self._status_mode = "none"
        self._status_msg = "未配置自动同步"
        self._sync_test = False
        self.save_finished.connect(self._on_save_finished)
        self._build_ui()
        self.apply_theme()

    def _build_ui(self):
        v = QVBoxLayout(self)
        v.setContentsMargins(16, 11, 16, 11)
        v.setSpacing(7)

        head = QHBoxLayout()
        head.setSpacing(8)

        self.title_lbl = QLabel("控制台 cURL 自动同步")
        head.addWidget(self.title_lbl)

        self.status_lbl = QLabel("")
        head.addWidget(self.status_lbl)

        head.addStretch(1)

        self.guide_lbl = QLabel("F12 复制「积分额度」请求的 cURL 粘贴于此 (每 5 分钟自动更新)")
        head.addWidget(self.guide_lbl)
        v.addLayout(head)

        self.curl_edit = QPlainTextEdit()
        self.curl_edit.setPlaceholderText('粘贴 cURL 命令 (curl "https://platform.sensenova.cn/lite/console/...")')
        v.addWidget(self.curl_edit)

        row = QHBoxLayout()
        row.setSpacing(8)

        self.err_lbl = QLabel("")
        row.addWidget(self.err_lbl, 1)

        self.btn_clear = QPushButton("清除凭据")
        self.btn_clear.setCursor(Qt.PointingHandCursor)
        self.btn_clear.clicked.connect(self._on_clear)
        row.addWidget(self.btn_clear)

        self.btn_save = QPushButton("保存并同步")
        self.btn_save.setCursor(Qt.PointingHandCursor)
        self.btn_save.clicked.connect(self._on_save)
        row.addWidget(self.btn_save)

        v.addLayout(row)

    def apply_size(self):
        m = curr_metric()
        self.title_lbl.setFont(QFont("Microsoft YaHei UI", m["sn_title_pt"], QFont.Bold))
        self.status_lbl.setFont(QFont("Microsoft YaHei UI", m["sn_sub_pt"], QFont.Bold))
        self.guide_lbl.setFont(QFont("Microsoft YaHei UI", m["sn_sub_pt"]))
        self.err_lbl.setFont(QFont("Microsoft YaHei UI", m["sn_sub_pt"]))
        self.curl_edit.setFixedHeight(m["sn_input_h"])
        self.btn_clear.setFixedHeight(m["opt_btn_h"])
        self.btn_save.setFixedHeight(m["opt_btn_h"])
        self.update()

    def set_status(self, s):
        if s.get("autosync_error"):
            self._status_mode = "error"
            self._status_msg = f"⚠ 同步异常: {s['autosync_error'][:22]}"
        elif s.get("sync_src") == "auto":
            self._status_mode = "success"
            t = s.get("sync_time", time.strftime("%H:%M"))
            self._status_msg = f"✓ 自动同步 {t}"
        else:
            self._status_mode = "none"
            self._status_msg = "未配置自动同步"
        self.apply_theme()

    def set_syncing(self, msg="正在同步积分…"):
        """同步中进度态 (避免更新按钮灰色无反馈的卡顿感)"""
        self._status_mode = "syncing"
        self._status_msg = f"⟳ {msg}"
        self.apply_theme()

    def _on_clear(self):
        clear_sn_autosync()
        _autosync_mem.update(ts=0.0, values=None, error=None)
        self.curl_edit.clear()
        self.err_lbl.setText("已清除配置")
        self.cleared.emit()

    def _on_save(self):
        text = self.curl_edit.toPlainText().strip()
        if not text:
            self.err_lbl.setText("请先粘贴 cURL")
            return
        req = parse_curl(text)
        if not req:
            self.err_lbl.setText("解析失败: 未找到有效 URL")
            return
        self.err_lbl.setText("正在连接接口…")
        self.btn_save.setEnabled(False)
        self.btn_clear.setEnabled(False)

        def worker():
            try:
                status, data, err = _http_json(req)
                if err:
                    ok, msg = False, f"调用失败: {err}"
                else:
                    paths = _detect_paths_by_structure(data)
                    if not paths:
                        ok, msg = False, "未识别到商汤 pools 结构，请确认复制的是积分额度请求"
                    else:
                        cfg = {"v": 1, "url": req["url"], "method": req["method"],
                               "headers": req["headers"], "body": req["body"],
                               "paths": paths, "saved_ts": time.time()}
                        save_sn_autosync(cfg)
                        sn_autosync_fetch(force=True)
                        ok, msg = True, "✓ 保存成功，数据已刷新"
            except Exception as e:
                ok, msg = False, f"异常: {str(e)[:45]}"
            self.save_finished.emit(ok, msg)

        if self._sync_test:
            worker()
            return
        threading.Thread(target=worker, daemon=True).start()

    def _on_save_finished(self, ok, msg):
        self.btn_save.setEnabled(True)
        self.btn_clear.setEnabled(True)
        self.err_lbl.setText(msg)
        if ok:
            self.saved.emit()

    def apply_theme(self):
        dark = theme_state["dark"]
        border = qrgba(BORDER)
        text, text2, text3 = qname(TEXT), qname(TEXT2), qname(TEXT3)
        m = curr_metric()

        self.setStyleSheet(
            "#sn_sync_panel { background:transparent; border:none; }"
            f"QPlainTextEdit {{ background:{qrgba(TRACK)}; color:{text}; border:1px solid {border};"
            f" border-radius:6px; padding:6px 8px; font-family:Consolas, monospace; font-size:{m['opt_btn_px']}px; }}"
            f"QPlainTextEdit:focus {{ border:1px solid #3b6fe0; }}"
        )
        self.title_lbl.setStyleSheet(f"color:{text};")
        self.guide_lbl.setStyleSheet(f"color:{text3};")

        mode = self._status_mode
        if mode == "success":
            st_color = "#34d399" if dark else "#059669"
            st_bg = "rgba(52, 211, 153, 0.16)" if dark else "rgba(5, 150, 105, 0.10)"
        elif mode == "error":
            st_color = "#f87171" if dark else "#dc2626"
            st_bg = "rgba(248, 113, 113, 0.16)" if dark else "rgba(220, 38, 38, 0.10)"
        elif mode == "syncing":
            st_color = "#f59e0b" if dark else "#d97706"
            st_bg = "rgba(245, 158, 11, 0.16)" if dark else "rgba(217, 119, 6, 0.12)"
        else:
            st_color = text3
            st_bg = qrgba(TRACK)
        self.status_lbl.setText(self._status_msg)
        self.status_lbl.setStyleSheet(
            f"background:{st_bg}; color:{st_color}; border-radius:5px; padding:2px 8px;")

        self.err_lbl.setStyleSheet("color:#34d399;" if "✓" in self.err_lbl.text() else "color:#f87171;")

        self.btn_clear.setStyleSheet(
            f"QPushButton{{ background:transparent; color:{text2}; border:1px solid {border};"
            f" border-radius:6px; padding:3px 12px; font-size:{m['opt_btn_px']}px; }}"
            f"QPushButton:hover{{ background:{qrgba(HOVER)}; color:{text}; }}")
        self.btn_save.setStyleSheet(
            "QPushButton{ background:#3b6fe0; color:white; border:none; border-radius:6px;"
            f" padding:4px 16px; font-size:{m['opt_btn_px']}px; font-weight:600; }}"
            "QPushButton:hover{ background:#2f5ec4; }")
        self.apply_size()
        self.update()


class SNAccountCard(GlassPodFrame):
    """账号密码卡片: 输入后持久化保存到 sn_account.json, 供自动登录/换账号使用"""
    saved = Signal()

    def __init__(self, parent=None):
        super().__init__(radius=12, parent=parent)
        self.setObjectName("sn_account_card")
        self._build_ui()
        self._load_account()
        self.apply_theme()

    def _build_ui(self):
        v = QVBoxLayout(self)
        v.setContentsMargins(16, 11, 16, 11)
        v.setSpacing(7)

        head = QHBoxLayout()
        head.setSpacing(8)
        self.title_lbl = QLabel("🔐 账号密码 (自动登录)")
        head.addWidget(self.title_lbl)
        head.addStretch(1)
        self.status_lbl = QLabel("")
        head.addWidget(self.status_lbl)
        v.addLayout(head)

        # 账号 + 密码 同一行
        form = QHBoxLayout()
        form.setSpacing(8)
        self.user_tag = QLabel("账号")
        self.user_tag.setFixedWidth(32)
        form.addWidget(self.user_tag)
        self.user_edit = QLineEdit()
        self.user_edit.setPlaceholderText("商汤账号")
        form.addWidget(self.user_edit, 3)
        self.pwd_tag = QLabel("密码")
        self.pwd_tag.setFixedWidth(32)
        form.addWidget(self.pwd_tag)
        self.pwd_edit = QLineEdit()
        self.pwd_edit.setEchoMode(QLineEdit.Password)
        self.pwd_edit.setPlaceholderText("商汤密码")
        form.addWidget(self.pwd_edit, 3)
        self.btn_show = QPushButton("显示")
        self.btn_show.setCheckable(True)
        self.btn_show.setCursor(Qt.PointingHandCursor)
        self.btn_show.clicked.connect(self._toggle_pwd)
        form.addWidget(self.btn_show)
        v.addLayout(form)

        # 说明 + 保存按钮
        brow = QHBoxLayout()
        brow.setSpacing(8)
        self.guide_lbl = QLabel("仅存本机, 用于凭证过期自动重登")
        brow.addWidget(self.guide_lbl, 1)
        self.btn_save = QPushButton("保存账号")
        self.btn_save.setCursor(Qt.PointingHandCursor)
        self.btn_save.clicked.connect(self._on_save)
        brow.addWidget(self.btn_save)
        v.addLayout(brow)

    def _toggle_pwd(self):
        if self.btn_show.isChecked():
            self.pwd_edit.setEchoMode(QLineEdit.Normal)
            self.btn_show.setText("隐藏")
        else:
            self.pwd_edit.setEchoMode(QLineEdit.Password)
            self.btn_show.setText("显示")

    def _load_account(self):
        try:
            with open(SN_ACCOUNT_FILE, "r", encoding="utf-8-sig") as f:
                d = json.load(f)
            self.user_edit.setText(d.get("username", ""))
            self.pwd_edit.setText(d.get("password", ""))
        except Exception:
            pass

    def _on_save(self):
        username = self.user_edit.text().strip()
        password = self.pwd_edit.text()
        if not username or not password:
            self.status_lbl.setText("请填写账号和密码")
            self._status_color = "#e05252"
            self.apply_theme()
            return
        try:
            with open(SN_ACCOUNT_FILE, "w", encoding="utf-8") as f:
                json.dump({"username": username, "password": password}, f, ensure_ascii=False)
        except Exception as e:
            self.status_lbl.setText(f"保存失败: {str(e)[:30]}")
            self._status_color = "#e05252"
            self.apply_theme()
            return
        self.status_lbl.setText("✓ 已保存")
        self._status_color = "#34d399"
        self.apply_theme()
        self.saved.emit()

    def apply_size(self):
        m = curr_metric()
        self.title_lbl.setFont(QFont("Microsoft YaHei UI", m["sn_title_pt"], QFont.Bold))
        self.status_lbl.setFont(QFont("Microsoft YaHei UI", m["sn_sub_pt"]))
        self.guide_lbl.setFont(QFont("Microsoft YaHei UI", m["sn_sub_pt"]))
        self.user_tag.setFont(QFont("Microsoft YaHei UI", m["sn_sub_pt"]))
        self.pwd_tag.setFont(QFont("Microsoft YaHei UI", m["sn_sub_pt"]))
        self.user_edit.setFixedHeight(m["sn_input_h"])
        self.pwd_edit.setFixedHeight(m["sn_input_h"])
        self.btn_show.setFixedHeight(m["sn_input_h"])
        self.btn_show.setFixedWidth(44)
        self.btn_save.setFixedHeight(m["opt_btn_h"])
        self.update()

    def apply_theme(self):
        dark = theme_state["dark"]
        border = qrgba(BORDER)
        text, text2, text3 = qname(TEXT), qname(TEXT2), qname(TEXT3)
        m = curr_metric()
        self.setStyleSheet(
            "#sn_account_card { background:transparent; border:none; }"
            f"QLineEdit {{ background:{qrgba(TRACK)}; color:{text}; border:1px solid {border};"
            f" border-radius:6px; padding:5px 8px; font-size:{m['opt_btn_px']}px; }}"
            f"QLineEdit:focus {{ border:1px solid #3b6fe0; }}"
        )
        self.title_lbl.setStyleSheet(f"color:{text};")
        self.guide_lbl.setStyleSheet(f"color:{text3};")
        self.user_tag.setStyleSheet(f"color:{text2};")
        self.pwd_tag.setStyleSheet(f"color:{text2};")
        sc = getattr(self, "_status_color", text3)
        self.status_lbl.setStyleSheet(f"color:{sc};")
        self.btn_show.setStyleSheet(
            f"QPushButton{{ background:transparent; color:{text3}; border:none;"
            f" border-radius:6px; font-size:{m['sn_sub_pt']}px; padding:0 6px; }}"
            f"QPushButton:hover{{ color:#3b6fe0; }}"
            "QPushButton:checked{ color:#3b6fe0; font-weight:600; }")
        self.btn_save.setStyleSheet(
            "QPushButton{ background:#3b6fe0; color:white; border:none; border-radius:6px;"
            f" padding:4px 16px; font-size:{m['opt_btn_px']}px; font-weight:600; }}"
            "QPushButton:hover{ background:#2f5ec4; }")
        self.apply_size()
        self.update()


class SNQuotaPage(QWidget):
    """商汤日日新展示页 (赠送积分双行分栏，易读性全面优化)"""
    saved = Signal()
    cleared = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(10)

        # 1. 左右并排双池
        self.pools_layout = QHBoxLayout()
        self.pools_layout.setSpacing(10)
        v.addLayout(self.pools_layout)

        # 2. 活动固定积分优雅双行卡片
        self.promo_card = GlassPodFrame(radius=10)
        self.promo_card.setObjectName("sn_promo_card")
        self.promo_bar = self.promo_card
        pv = QVBoxLayout(self.promo_card)
        pv.setContentsMargins(16, 9, 16, 9)
        pv.setSpacing(6)

        row1 = QHBoxLayout()
        row1.setSpacing(6)
        self.promo_icon = QLabel("🎁")
        row1.addWidget(self.promo_icon)

        self.promo_title = QLabel("活动固定积分")
        row1.addWidget(self.promo_title)

        self.promo_rule = QLabel("Flash-Lite 1:1 消费返赠 · 30天有效")
        row1.addWidget(self.promo_rule)
        row1.addStretch(1)
        pv.addLayout(row1)

        row2 = QHBoxLayout()
        row2.setSpacing(8)

        self.promo_val_tag = QLabel("可用总额:")
        row2.addWidget(self.promo_val_tag)

        self.promo_val = QLabel("0.00")
        row2.addWidget(self.promo_val)

        row2.addStretch(1)

        self.promo_exp_tag = QLabel("最近到期:")
        row2.addWidget(self.promo_exp_tag)

        self.promo_exp = QLabel("—")
        row2.addWidget(self.promo_exp)

        pv.addLayout(row2)
        v.addWidget(self.promo_card)

        # 3. 极简同步面板
        self.sync_panel = SNSyncPanel()
        self.sync_panel.saved.connect(self.saved)
        self.sync_panel.cleared.connect(self.cleared)
        v.addWidget(self.sync_panel)

        # 3.5. 账号密码卡片 (自动登录/换账号)
        self.account_card = SNAccountCard()
        self.account_card.saved.connect(self._on_account_saved)
        v.addWidget(self.account_card)

        # 4. 底部微型注释
        self.foot_lbl = QLabel("注: 上限为官方公开的公测期固定额度 (60,000/5h · 600,000/周)；数据均以控制台实际调用与配额为准。")
        self.foot_lbl.setStyleSheet(f"color:{qname(TEXT3)};")
        v.addWidget(self.foot_lbl)

        v.addStretch(1)

    def apply_size(self):
        m = curr_metric()
        self.promo_title.setFont(QFont("Microsoft YaHei UI", m["sn_title_pt"], QFont.Bold))
        self.promo_rule.setFont(QFont("Microsoft YaHei UI", m["sn_sub_pt"]))
        self.promo_val_tag.setFont(QFont("Microsoft YaHei UI", m["sn_sub_pt"]))
        self.promo_val.setFont(QFont("Consolas", m["promo_val_pt"], QFont.Bold))
        self.promo_exp_tag.setFont(QFont("Microsoft YaHei UI", m["sn_sub_pt"]))
        self.promo_exp.setFont(QFont("Consolas", m["sn_sub_pt"], QFont.Bold))
        self.foot_lbl.setFont(QFont("Microsoft YaHei UI", m["sn_date_pt"]))

        for i in range(self.pools_layout.count()):
            w = self.pools_layout.itemAt(i).widget()
            if isinstance(w, SNPoolCard):
                w.apply_size()
        self.sync_panel.apply_size()
        self.account_card.apply_size()
        self.update()

    def _on_account_saved(self):
        """账号保存后: 清除旧 token/登录态缓存, 下次刷新会用新账号重新登录"""
        try:
            if os.path.exists(SN_TOKEN_FILE):
                os.remove(SN_TOKEN_FILE)
        except Exception:
            pass
        _autosync_mem.update(ts=0.0, values=None, error=None)

    def render(self, s):
        while self.pools_layout.count():
            it = self.pools_layout.takeAt(0)
            w = it.widget()
            if w:
                w.deleteLater()

        pools = s.get("pools", [])
        if not pools:
            empty_lbl = QLabel("未检测到商汤模型调用记录。\n可在下方配置官网 cURL 开启实时自动同步。")
            empty_lbl.setAlignment(Qt.AlignCenter)
            empty_lbl.setStyleSheet(f"color:{qname(TEXT3)}; padding: 36px; font-size:11.5px;")
            self.pools_layout.addWidget(empty_lbl)
        else:
            for p in pools:
                if p.get("id") in ("general", "flash_lite"):
                    self.pools_layout.addWidget(SNPoolCard(p), 1)
                elif p.get("id") == "promo":
                    tot = p.get("total_balance", 0)
                    exp = p.get("nearest_expire", "—")
                    self.promo_val.setText(f"{tot:,.2f}" if isinstance(tot, (int, float)) else str(tot))
                    self.promo_exp.setText(f"{exp}")

        self.sync_panel.set_status(s)
        self.apply_theme()

    def apply_theme(self):
        self.promo_card.setStyleSheet("#sn_promo_card { background:transparent; border:none; }")
        self.promo_title.setStyleSheet(f"color:{qname(TEXT)};")
        self.promo_rule.setStyleSheet(f"color:{qname(TEXT3)};")
        self.promo_val_tag.setStyleSheet(f"color:{qname(TEXT3)};")
        self.promo_val.setStyleSheet(f"color:{qname(TEXT)};")
        self.promo_exp_tag.setStyleSheet(f"color:{qname(TEXT3)};")
        self.promo_exp.setStyleSheet(f"color:{qname(TEXT2)};")
        self.foot_lbl.setStyleSheet(f"color:{qname(TEXT3)};")

        for i in range(self.pools_layout.count()):
            w = self.pools_layout.itemAt(i).widget()
            if isinstance(w, SNPoolCard):
                w.apply_theme()

        self.sync_panel.apply_theme()
        self.account_card.apply_theme()
        self.apply_size()
        self.promo_card.update()


# ============================================================ 导航按钮
class NavButton(QPushButton):
    def __init__(self, text, icon_str="", parent=None):
        super().__init__(f"  {icon_str}  {text}", parent)
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.apply_size()

    def apply_size(self):
        m = curr_metric()
        self.setFixedHeight(m["nav_btn_h"])
        self.setFont(QFont("Microsoft YaHei UI", m["nav_btn_pt"]))


# ============================================================ 刷新信号桥
class RefreshBridge(QObject):
    done = Signal(str, object)


# ============================================================ 主窗口 (双尺寸自适应架构)
class CardWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)

        self._drag = None
        self._scanning = False
        self._pending_refresh = False
        self._sn_cache = None
        self.source = theme_state["source"]
        self.range = "all"
        self.stats = None

        self.bridge = RefreshBridge()
        self.bridge.done.connect(self._on_scan_done)

        self._build_ui()
        self.apply_size_mode(theme_state.get("window_size", "default"), save=False)
        self.apply_styles()

    def _build_ui(self):
        outer = QHBoxLayout(self)
        outer.setContentsMargins(10, 10, 10, 10)

        # 核心主底板: iOS 27 液态玻璃
        self.card = LiquidGlassFrame()
        self.card.setObjectName("main_card")
        outer.addWidget(self.card)

        main_layout = QHBoxLayout(self.card)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ---- 1. 左侧菜单栏 (Sidebar)
        self.sidebar = QFrame()
        self.sidebar.setObjectName("sidebar")
        side_lay = QVBoxLayout(self.sidebar)
        side_lay.setContentsMargins(14, 16, 14, 16)
        side_lay.setSpacing(8)

        brand = QHBoxLayout()
        self.dot_logo = QLabel("●")
        self.dot_logo.setStyleSheet("color:#3b6fe0; font-size:14px;")
        brand.addWidget(self.dot_logo)
        self.app_title = QLabel("Token 统计")
        brand.addWidget(self.app_title)
        brand.addStretch(1)
        side_lay.addLayout(brand)

        side_lay.addSpacing(12)

        self.src_head = QLabel("数据源")
        self.src_head.setStyleSheet(f"color:{qname(TEXT3)}; padding-left:4px;")
        side_lay.addWidget(self.src_head)

        self.btn_nav_wb = NavButton("WorkBuddy", "📘")
        self.btn_nav_dsh = NavButton("DSH 本地", "🗄️")
        self.btn_nav_sn = NavButton("商汤额度", "⚡")

        for b in (self.btn_nav_wb, self.btn_nav_dsh, self.btn_nav_sn):
            side_lay.addWidget(b)
            b.clicked.connect(lambda _=False, bb=b: self._switch_nav(bb))

        self.btn_nav_wb.setChecked(self.source == "wb")
        self.btn_nav_dsh.setChecked(self.source == "dsh")
        self.btn_nav_sn.setChecked(self.source == "sn")

        side_lay.addStretch(1)

        self.btn_refresh = QPushButton("⟳  刷新数据")
        self.btn_refresh.setCursor(Qt.PointingHandCursor)
        self.btn_refresh.clicked.connect(lambda: self.refresh(force=True))
        side_lay.addWidget(self.btn_refresh)

        bar_opts = QHBoxLayout()
        self.btn_theme_toggle = QPushButton("🌙 暗色" if not theme_state["dark"] else "☀️ 亮色")
        self.btn_theme_toggle.setCursor(Qt.PointingHandCursor)
        self.btn_theme_toggle.clicked.connect(lambda: self.set_dark(not theme_state["dark"]))
        bar_opts.addWidget(self.btn_theme_toggle)

        self.btn_glass_toggle = QPushButton("液态玻璃")
        self.btn_glass_toggle.setCheckable(True)
        self.btn_glass_toggle.setChecked(theme_state["glass"])
        self.btn_glass_toggle.setCursor(Qt.PointingHandCursor)
        self.btn_glass_toggle.clicked.connect(lambda: self.set_glass(not theme_state["glass"]))
        bar_opts.addWidget(self.btn_glass_toggle)
        side_lay.addLayout(bar_opts)

        main_layout.addWidget(self.sidebar)

        # ---- 2. 右侧工作区
        self.workspace = QWidget()
        self.workspace.setObjectName("workspace")
        work_lay = QVBoxLayout(self.workspace)
        work_lay.setContentsMargins(18, 14, 18, 14)
        work_lay.setSpacing(10)

        top_bar = QHBoxLayout()
        self.subtitle = QLabel("加载中…")
        top_bar.addWidget(self.subtitle, 1)

        self.range_box = QWidget()
        rb_lay = QHBoxLayout(self.range_box)
        rb_lay.setContentsMargins(0, 0, 0, 0)
        rb_lay.setSpacing(4)
        self.btn_today = self._tab_btn("今日")
        self.btn_7 = self._tab_btn("7天")
        self.btn_30 = self._tab_btn("30天")
        self.btn_all = self._tab_btn("全部")
        self.btn_all.setChecked(True)
        for b in (self.btn_today, self.btn_7, self.btn_30, self.btn_all):
            rb_lay.addWidget(b)
        top_bar.addWidget(self.range_box)

        top_bar.addSpacing(6)
        self.btn_min = QPushButton("–")
        self.btn_min.setFixedSize(26, 26)
        self.btn_min.setCursor(Qt.PointingHandCursor)
        self.btn_min.clicked.connect(self.showMinimized)
        top_bar.addWidget(self.btn_min)

        self.btn_close = QPushButton("✕")
        self.btn_close.setFixedSize(26, 26)
        self.btn_close.setCursor(Qt.PointingHandCursor)
        self.btn_close.clicked.connect(self.hide)
        top_bar.addWidget(self.btn_close)

        work_lay.addLayout(top_bar)

        self.stack = QStackedWidget()

        # Page 0: 常规统计仪表盘
        page_dash = QWidget()
        dash_lay = QVBoxLayout(page_dash)
        dash_lay.setContentsMargins(0, 0, 0, 0)
        dash_lay.setSpacing(10)

        stat_grid = QHBoxLayout()
        stat_grid.setSpacing(10)
        self.card_total = StatCard("合计 Token", BLUE)
        self.card_cache = StatCard("缓存命中", GREEN)
        self.card_io = StatCard("输入 / 输出", YELLOW)
        self.card_sess = StatCard("会话 / 请求", PURPLE)
        for c in (self.card_total, self.card_cache, self.card_io, self.card_sess):
            stat_grid.addWidget(c, 1)
        dash_lay.addLayout(stat_grid)

        self.today_bar = QLabel("")
        dash_lay.addWidget(self.today_bar)

        body_split = QHBoxLayout()
        body_split.setSpacing(10)

        self.table_card = GlassPodFrame(radius=10)
        self.table_card.setObjectName("table_card")
        tv = QVBoxLayout(self.table_card)
        tv.setContentsMargins(8, 6, 8, 6)
        tv.setSpacing(0)
        self.model_area = QScrollArea()
        self.model_area.setWidgetResizable(True)
        self.model_area.setFrameShape(QFrame.NoFrame)
        self.model_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.model_host = QWidget()
        self.model_lay = QVBoxLayout(self.model_host)
        self.model_lay.setContentsMargins(0, 0, 0, 0)
        self.model_lay.setSpacing(0)
        self.model_area.setWidget(self.model_host)
        tv.addWidget(self.model_area)
        body_split.addWidget(self.table_card, 56)

        charts_col = QVBoxLayout()
        charts_col.setSpacing(10)

        self.chart_card = GlassPodFrame(radius=10)
        self.chart_card.setObjectName("chart_card")
        cv = QVBoxLayout(self.chart_card)
        cv.setContentsMargins(10, 6, 8, 6)
        cv.setSpacing(0)
        cv.addWidget(CardHeader("每日用量分布 (滚轮缩放/拖动平移)", BLUE))
        self.chart = StackedBarChart()
        cv.addWidget(self.chart)
        charts_col.addWidget(self.chart_card, 56)

        self.heat_card = GlassPodFrame(radius=10)
        self.heat_card.setObjectName("heat_card")
        hv = QVBoxLayout(self.heat_card)
        hv.setContentsMargins(10, 6, 8, 6)
        hv.setSpacing(0)
        hv.addWidget(CardHeader("近期活跃热力", GREEN))
        self.heat = HeatMap()
        hv.addWidget(self.heat)
        charts_col.addWidget(self.heat_card, 44)

        body_split.addLayout(charts_col, 44)
        dash_lay.addLayout(body_split, 1)

        self.stack.addWidget(page_dash)

        # Page 1: 商汤额度页
        self.sn_page = SNQuotaPage()
        self.sn_page.saved.connect(self._on_sn_sync_saved)
        self.sn_page.cleared.connect(self._on_sn_sync_saved)
        self.stack.addWidget(self.sn_page)

        work_lay.addWidget(self.stack, 1)
        main_layout.addWidget(self.workspace, 1)

    # ---------------- 动态尺寸适配器 ----------------
    def apply_size_mode(self, mode_name, save=True):
        if mode_name not in SIZE_METRICS:
            mode_name = "default"
        theme_state["window_size"] = mode_name
        if save:
            save_settings()

        m = SIZE_METRICS[mode_name]
        self.setFixedSize(m["win_w"], m["win_h"])
        self.resize(m["win_w"], m["win_h"])

        self.sidebar.setFixedWidth(m["sidebar_w"])
        self.card.sep_x = float(m["sidebar_w"])

        self.app_title.setFont(QFont("Microsoft YaHei UI", m["title_pt"], QFont.Bold))
        self.subtitle.setFont(QFont("Microsoft YaHei UI", m["subtitle_pt"]))
        self.src_head.setFont(QFont("Microsoft YaHei UI", m["sn_date_pt"]))

        for b in (self.btn_nav_wb, self.btn_nav_dsh, self.btn_nav_sn):
            b.apply_size()

        self.btn_refresh.setFixedHeight(m["refresh_h"])
        self.btn_refresh.setFont(QFont("Microsoft YaHei UI", m["nav_btn_pt"], QFont.Bold))

        self.btn_theme_toggle.setFixedHeight(m["opt_btn_h"])
        self.btn_glass_toggle.setFixedHeight(m["opt_btn_h"])

        for c in (self.card_total, self.card_cache, self.card_io, self.card_sess):
            c.apply_size()

        self.today_bar.setFixedHeight(m["today_h"])
        self.chart.apply_size()
        self.heat.apply_size()
        self.sn_page.apply_size()

        if self.isVisible():
            screen = QGuiApplication.screenAt(self.geometry().center()) or QApplication.primaryScreen()
            scr = screen.availableGeometry()
            x = max(scr.left() + 8, min(self.x(), scr.right() - self.width() - 8))
            y = max(scr.top() + 8, min(self.y(), scr.bottom() - self.height() - 8))
            self.move(x, y)

        self.render()
        self.apply_styles()
        self.card.update()

    def set_glass_transparency(self, level, save=True):
        if level not in GLASS_PRESETS:
            level = "balanced"
        theme_state["glass_transparency"] = level
        if save:
            save_settings()
        self.card.update()
        for w in self.findChildren(GlassPodFrame):
            w.update()
        self.update()

    # ---------------- 多显示器感知与智能吸附展开 ----------------
    def popup_from(self, pet_geometry: QRect):
        screen = QGuiApplication.screenAt(pet_geometry.center()) or QApplication.primaryScreen()
        scr = screen.availableGeometry()
        card_w, card_h = self.width(), self.height()
        MARGIN_X = 14

        pet_cx = pet_geometry.center().x()
        screen_cx = scr.center().x()

        space_right = scr.right() - pet_geometry.right()
        space_left = pet_geometry.left() - scr.left()

        if pet_cx >= screen_cx:
            if space_left >= card_w + MARGIN_X:
                x = pet_geometry.left() - card_w - MARGIN_X
            elif space_right >= card_w + MARGIN_X:
                x = pet_geometry.right() + MARGIN_X
            else:
                x = scr.right() - card_w - MARGIN_X
        else:
            if space_right >= card_w + MARGIN_X:
                x = pet_geometry.right() + MARGIN_X
            elif space_left >= card_w + MARGIN_X:
                x = pet_geometry.left() - card_w - MARGIN_X
            else:
                x = scr.left() + MARGIN_X

        y = pet_geometry.center().y() - card_h // 2
        x = max(scr.left() + 8, min(x, scr.right() - card_w - 8))
        y = max(scr.top() + 8, min(y, scr.bottom() - card_h - 8))

        self.move(x, y)
        self.show()
        self.raise_()
        self.activateWindow()
        self.setWindowState((self.windowState() & ~Qt.WindowMinimized) | Qt.WindowActive)

    # ---------------- 样式刷新 ----------------
    def apply_styles(self):
        dark = theme_state["dark"]
        glass = theme_state["glass"]
        m = curr_metric()

        self.card.setStyleSheet("#main_card { background:transparent; border:none; }")
        self.sidebar.setStyleSheet(
            f"#sidebar {{ background:{'transparent' if glass else qrgba(SIDEBAR)};"
            f" border-top-left-radius:14px; border-bottom-left-radius:14px;"
            f" border-right:{'none' if glass else f'1px solid {qrgba(BORDER)}'}; }}")

        self.app_title.setStyleSheet(f"color:{qname(TEXT)};")
        self.subtitle.setStyleSheet(f"color:{qname(TEXT3)};")

        if glass:
            tb_bg = "rgba(255, 255, 255, 0.08)" if dark else "rgba(255, 255, 255, 0.45)"
            tb_border = "rgba(255, 255, 255, 0.18)" if dark else "rgba(255, 255, 255, 0.70)"
        else:
            tb_bg = qrgba(CARD)
            tb_border = qrgba(BORDER)

        # 核心修正：使用 px 单位严格控制，消除 pt 单位换算导致突兀放大的 Bug
        self.today_bar.setStyleSheet(
            f"background:{tb_bg}; border:1px solid {tb_border}; border-radius:6px;"
            f" padding:4px 10px; color:{qname(TEXT2)}; font-size:{m['today_px']}px;")

        for w in (self.table_card, self.chart_card, self.heat_card):
            w.setStyleSheet("background:transparent; border:none;")

        self.btn_refresh.setStyleSheet(
            "QPushButton{ background:#3b6fe0; color:white; border:none; border-radius:8px; font-weight:600; }"
            "QPushButton:hover{ background:#2f5ec4; }"
            "QPushButton:disabled{ background:#aebfd8; }")

        ctrl = (f"QPushButton{{ background:{qrgba(TRACK)}; color:{qname(TEXT2)}; border:none;"
                f" border-radius:6px; font-size:12px; font-weight:700; }}")
        self.btn_min.setStyleSheet(ctrl + f"QPushButton:hover{{ background:{qrgba(HOVER)}; }}")
        self.btn_close.setStyleSheet(ctrl + "QPushButton:hover{ background:#e05252; color:white; }")

        btn_opt_style = (
            f"QPushButton{{ background:{qrgba(TRACK)}; color:{qname(TEXT2)}; border:none; border-radius:6px;"
            f" font-size:{m['opt_btn_px']}px; }}"
            f"QPushButton:hover{{ background:{qrgba(HOVER)}; color:{qname(TEXT)}; }}"
            "QPushButton:checked{ background:#3b6fe0; color:white; }")
        self.btn_theme_toggle.setStyleSheet(btn_opt_style)
        self.btn_theme_toggle.setText("🌙 暗色" if not dark else "☀️ 亮色")
        self.btn_glass_toggle.setStyleSheet(btn_opt_style)
        self.btn_glass_toggle.setChecked(theme_state["glass"])

        for b in (self.btn_today, self.btn_7, self.btn_30, self.btn_all):
            b.setStyleSheet(
                f"QPushButton{{ background:{qrgba(TRACK)}; color:{qname(TEXT2)}; border:none;"
                f" border-radius:6px; padding:4px 9px; font-size:{m['opt_btn_px']}px; }}"
                f"QPushButton:checked{{ background:#3b6fe0; color:white; font-weight:600; }}"
                f"QPushButton:hover{{ color:{qname(TEXT)}; }}"
                "QPushButton:checked:hover{ color:white; }")

        nav_style = (
            f"QPushButton{{ background:transparent; color:{qname(TEXT2)}; border:none; border-radius:8px;"
            f" text-align:left; padding-left:10px; }}"
            f"QPushButton:hover{{ background:{qrgba(HOVER)}; color:{qname(TEXT)}; }}"
            f"QPushButton:checked{{ background:{qrgba(BLUE, 30 if dark else 20)}; color:#3b6fe0; font-weight:700; }}")
        for b in (self.btn_nav_wb, self.btn_nav_dsh, self.btn_nav_sn):
            b.setStyleSheet(nav_style)

        self.model_area.setStyleSheet("background:transparent; border:none;")
        self.model_host.setStyleSheet("background:transparent;")
        self.sn_page.apply_theme()
        self.update()

    def set_dark(self, dark):
        theme_state["dark"] = dark
        refresh_palette()
        self.apply_styles()
        apply_app_qss()
        self._update_all()
        save_settings()

    def set_glass(self, enabled):
        theme_state["glass"] = enabled
        refresh_palette()
        self.apply_styles()
        self._update_all()
        save_settings()

    def _update_all(self):
        for w in QApplication.allWidgets():
            w.update()
        tip = ChartTip._instance
        if tip is not None and tip.isVisible():
            tip.update()

    def _tab_btn(self, text):
        b = QPushButton(text)
        b.setCheckable(True)
        b.setCursor(Qt.PointingHandCursor)
        b.clicked.connect(lambda _=False, bb=b: self._switch_range(bb))
        return b

    def _switch_range(self, btn):
        for b in (self.btn_today, self.btn_7, self.btn_30, self.btn_all):
            b.setChecked(b is btn)
        self.range = {id(self.btn_today): "today", id(self.btn_7): "7",
                      id(self.btn_30): "30", id(self.btn_all): "all"}[id(btn)]
        self.render()

    def _switch_nav(self, btn):
        ChartTip.instance().hide_tip()
        for b in (self.btn_nav_wb, self.btn_nav_dsh, self.btn_nav_sn):
            b.setChecked(b is btn)
        if btn is self.btn_nav_dsh:
            self.source = "dsh"
        elif btn is self.btn_nav_sn:
            self.source = "sn"
        else:
            self.source = "wb"
        theme_state["source"] = self.source
        save_settings()
        self.load_initial()

    # ---------------- 异步刷新链路 ----------------
    def refresh(self, force=False):
        if self._scanning:
            self._pending_refresh = True
            return
        self._scanning = True
        self.btn_refresh.setEnabled(False)
        src = self.source
        if src == "dsh": self.subtitle.setText("正在读取 DSH 账本…")
        elif src == "sn":
            # 进度反馈: 同步面板显示进度态, 避免更新按钮灰色像卡住
            self.sn_page.sync_panel.set_syncing("正在自动获取凭证并同步…" if force else "正在同步积分数据…")
            self.subtitle.setText("正在自动同步商汤积分 (获取凭证)…" if force else "正在同步商汤积分…")
        else: self.subtitle.setText("正在扫描 WorkBuddy 会话数据…")

        def work():
            try:
                if src == "dsh": s = load_dsh_stats()
                elif src == "sn": s = load_sn_stats(force=force)
                else: s = scanner.scan_full()
            except Exception as e:
                s = {"error": str(e)}
            self.bridge.done.emit(src, s)

        threading.Thread(target=work, daemon=True).start()

    def _on_scan_done(self, src, s):
        self._scanning = False
        self.btn_refresh.setEnabled(True)
        if isinstance(s, dict) and "error" in s:
            if src == self.source:
                self.subtitle.setText(f"加载失败: {s['error'][:50]}")
            self._kick_pending()
            return
        if src == self.source:
            self.stats = s
            if src == "sn": self._sn_cache = s
            self.render()
            if src == "dsh":
                self.subtitle.setText(f"DSH · {s.get('firstDay','—')} ~ {s.get('lastDay','—')} · 累计花费 ¥{s.get('totalCost', 0):.2f} · 已更新 {time.strftime('%H:%M:%S')}")
            elif src == "sn":
                ws = time.strftime("%H:%M", time.localtime(s.get("window_start", 0)))
                we = time.strftime("%H:%M", time.localtime(s.get("window_end", 0)))
                self.subtitle.setText(f"商汤 · 积分额度 · 窗口 {ws}–{we} · 已更新 {time.strftime('%H:%M:%S')}")
            else:
                self.subtitle.setText(f"WorkBuddy · {s.get('firstDay','—')} ~ {s.get('lastDay','—')} · 真实 usage · 已更新 {time.strftime('%H:%M:%S')}")
        elif src == "sn":
            self._sn_cache = s
        self._kick_pending()

    def _kick_pending(self):
        if self._pending_refresh and not self._scanning:
            self._pending_refresh = False
            QTimer.singleShot(0, self.refresh)

    def load_initial(self):
        if self.source == "sn":
            self.stats = self._sn_cache or {"source": "sn", "pools": []}
        elif self.source == "dsh":
            self.stats = load_dsh_stats()
        else:
            try:
                with open(scanner.STATS_FILE, "r", encoding="utf-8") as f:
                    self.stats = json.load(f)
            except Exception:
                self.stats = {"source": "wb", "daily": {}, "dailySessions": {}, "sessionsTotal": 0, "today": {}}
        self.render()
        QTimer.singleShot(100, self.refresh)

    def _on_sn_sync_saved(self):
        self.refresh(force=True)

    def _filtered_daily(self):
        s = self.stats
        daily = s.get("daily", {})
        if self.range == "all": return daily
        if self.range == "today":
            today = time.strftime("%Y-%m-%d")
            return {d: a for d, a in daily.items() if d == today}
        import datetime
        cut = (datetime.date.today() - datetime.timedelta(days=int(self.range))).isoformat()
        return {d: a for d, a in daily.items() if d != "unknown" and d >= cut}

    def render(self):
        s = self.stats
        if not s:
            self.subtitle.setText("暂无数据，点击刷新")
            return

        if self.source == "sn":
            self.stack.setCurrentIndex(1)
            self.range_box.setVisible(False)
            self.sn_page.render(s)
            return

        self.stack.setCurrentIndex(0)
        self.range_box.setVisible(True)

        daily = self._filtered_daily()
        agg = {}
        for a_map in daily.values():
            for m, a in a_map.items():
                b = agg.setdefault(m, {"requests": 0, "input": 0, "output": 0,
                                       "cached": 0, "cacheWrite": 0, "total": 0})
                for k in b: b[k] += a.get(k, 0)
        tot = {"input": 0, "output": 0, "cached": 0, "cacheWrite": 0, "total": 0, "requests": 0}
        for a in agg.values():
            for k in tot: tot[k] += a.get(k, 0)

        self.card_total.set_value(fmt_full(tot["total"]))
        rate = tot["cached"] / tot["input"] * 100 if tot["input"] else 0
        self.card_cache.set_value(fmt_full(tot["cached"]), f"命中率 {rate:.1f}%")
        self.card_io.set_value(fmt_full(tot["input"]), f"出 {fmt(tot['output'])}")
        ds = s.get("dailySessions", {})
        n_sess = s.get("sessionsTotal", 0) if self.range == "all" else sum(v for d, v in ds.items() if d in daily)
        self.card_sess.set_value(f"{n_sess:,}", f"请求 {tot['requests']:,}")

        td = s.get("today", {})
        trate = td.get("cached", 0) / td.get("input", 1) * 100 if td.get("input") else 0
        cost_txt = f" · 今日花费 ¥{td.get('cost', 0.0):.2f}" if s.get("dsh") else ""
        self.today_bar.setText(
            f"今日概况: 请求 {td.get('requests',0):,} 次 · 输入 {fmt(td.get('input',0))} · 输出 {fmt(td.get('output',0))} "
            f"· 会话 {td.get('sessions',0)} 个 · 缓存命中 {trate:.0f}%{cost_txt}")

        while self.model_lay.count():
            it = self.model_lay.takeAt(0)
            w = it.widget()
            if w: w.deleteLater()

        self.model_lay.addWidget(TableHeader("调用" if s.get("dsh") else "请求"))
        rows = sorted(agg.items(), key=lambda kv: -kv[1]["total"])
        max_total = rows[0][1]["total"] if rows else 1
        for i, (m, a) in enumerate(rows):
            hit = a["cached"] / a["input"] * 100 if a["input"] else 0
            row = ModelRow(m, MODEL_COLORS[i % len(MODEL_COLORS)],
                           a["total"] / max_total, a["total"],
                           a["total"] / tot["total"] * 100 if tot["total"] else 0,
                           hit, a["requests"],
                           input_tok=a.get("input", 0), output_tok=a.get("output", 0),
                           cached_tok=a.get("cached", 0), zebra=(i % 2 == 1))
            self.model_lay.addWidget(row)
        self.model_lay.addStretch(1)

        self.chart.set_data(daily, rows)
        self.heat.set_data(self.stats.get("daily", {}))

    # ---------------- 交互与右键菜单 ----------------
    def hideEvent(self, ev):
        super().hideEvent(ev)
        ChartTip.instance().hide_tip()

    def mousePressEvent(self, ev):
        if ev.button() == Qt.LeftButton and ev.position().y() < 50:
            self._drag = ev.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, ev):
        if self._drag is not None and ev.buttons() & Qt.LeftButton:
            self.move(ev.globalPosition().toPoint() - self._drag)

    def mouseReleaseEvent(self, ev):
        self._drag = None

    def keyPressEvent(self, ev):
        if ev.key() == Qt.Key_Escape:
            ChartTip.instance().hide_tip()
            self.hide()

    def contextMenuEvent(self, ev):
        menu = make_menu(self)
        act_hide = menu.addAction("⌫  隐藏窗口 (Esc)")
        act_dark = menu.addAction(("◉ " if theme_state["dark"] else "○ ") + "深色模式")
        act_blur = menu.addAction(("◉ " if theme_state["glass"] else "○ ") + "液态玻璃 (iOS 27)")

        # 玻璃通透度调节菜单
        tr_menu = menu.addMenu("🔮  玻璃通透度")
        cur_tr = theme_state.get("glass_transparency", "balanced")
        act_tr_c = tr_menu.addAction(("● " if cur_tr == "crystal" else "○ ") + "💎 晶透水滴 (高通透)")
        act_tr_b = tr_menu.addAction(("● " if cur_tr == "balanced" else "○ ") + "💧 标准液态 (默认)")
        act_tr_f = tr_menu.addAction(("● " if cur_tr == "frosted" else "○ ") + "🌫️ 柔和微透 (防眩光)")

        # 窗口尺寸切换菜单
        sz_menu = menu.addMenu("📐  窗口尺寸")
        cur_sz = theme_state.get("window_size", "default")
        act_sz_def = sz_menu.addAction(("● " if cur_sz != "large" else "○ ") + "标准尺寸 (990×610)")
        act_sz_lg = sz_menu.addAction(("● " if cur_sz == "large" else "○ ") + "舒适大窗口 (1180×730)")

        act_auto = menu.addAction(("◉ " if autostart_enabled() else "○ ") + "开机自启动")
        menu.addSeparator()
        act_quit = menu.addAction("✕  退出程序")

        chosen = menu.exec(ev.globalPos())
        if chosen == act_hide:
            self.hide()
        elif chosen == act_dark:
            self.set_dark(not theme_state["dark"])
        elif chosen == act_blur:
            self.set_glass(not theme_state["glass"])
        elif chosen == act_tr_c:
            self.set_glass_transparency("crystal")
        elif chosen == act_tr_b:
            self.set_glass_transparency("balanced")
        elif chosen == act_tr_f:
            self.set_glass_transparency("frosted")
        elif chosen == act_sz_def:
            self.apply_size_mode("default")
        elif chosen == act_sz_lg:
            self.apply_size_mode("large")
        elif chosen == act_auto:
            new_state = not autostart_enabled()
            set_autostart(new_state)
        elif chosen == act_quit:
            os._exit(0)


# ============================================================ 开机自启 (双轨保险)
VBS_PATH = os.path.join(os.environ.get("APPDATA", ""),
                        "Microsoft", "Windows", "Start Menu", "Programs",
                        "Startup", "TokenAuditCard.vbs")
_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_RUN_NAME = "TokenAuditCard"


def _autostart_command():
    pythonw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    if not os.path.exists(pythonw): pythonw = sys.executable
    return f'"{pythonw}" "{os.path.abspath(__file__)}"'


def autostart_enabled():
    if os.path.exists(VBS_PATH):
        return True
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY) as k:
            winreg.QueryValueEx(k, _RUN_NAME)
            return True
    except OSError:
        return False


def set_autostart(enable):
    if enable:
        cmd = _autostart_command()
        try:
            content = f'CreateObject("WScript.Shell").Run "{cmd.replace(chr(34), chr(34)+chr(34))}", 0, False\r\n'
            with open(VBS_PATH, "w", encoding="ascii") as f:
                f.write(content)
            return os.path.exists(VBS_PATH)
        except OSError:
            pass
        try:
            import winreg
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, _RUN_KEY) as k:
                winreg.SetValueEx(k, _RUN_NAME, 0, winreg.REG_SZ, cmd)
            return autostart_enabled()
        except OSError:
            return False
    else:
        removed = True
        try:
            if os.path.exists(VBS_PATH): os.remove(VBS_PATH)
        except OSError:
            removed = False
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
                winreg.DeleteValue(k, _RUN_NAME)
        except OSError:
            pass
        return removed and not autostart_enabled()


# ============================================================ 设置持久化
def save_settings():
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(theme_state, f)
    except Exception:
        pass


def load_settings():
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            d = json.load(f)
        theme_state["dark"] = bool(d.get("dark"))
        theme_state["glass"] = bool(d.get("glass"))
        theme_state["source"] = d.get("source", "wb")
        theme_state["pet"] = bool(d.get("pet"))
        theme_state["pet_theme"] = d.get("pet_theme", "v2")
        theme_state["window_size"] = d.get("window_size", "default")
        theme_state["glass_transparency"] = d.get("glass_transparency", "balanced")
    except Exception:
        pass


# ============================================================ 桌宠形态 (DeepSeek 娘)
PET_THEMES = {
    "v2": {"name": "新版素材 (高清)", "dir": os.path.join(BASE_DIR, "assets", "pet_v2")},
    "v1": {"name": "经典素材 (旧版)", "dir": os.path.join(BASE_DIR, "assets", "pet")},
}
PET_ANIMS = ("idle", "sleep", "drag", "click", "other", "special")
PET_W, PET_H = 118, 148
PET_SLEEP_AFTER = 60
PET_OTHER_EVERY = (150, 420)
PET_MS = {"idle": 240, "sleep": 1500, "drag": 140, "click": 300, "other": 300, "special": 360}
APP_BUILD = "v8.8-auto-sync"


def _pet_idle_seq(n):
    n = max(1, int(n))
    seq = [0] * random.randint(25, 70)
    if n >= 2: seq += [1, 0]
    if n >= 3 and random.random() < 0.40:
        seq += [0] * random.randint(15, 40)
        seq += random.choice([[k, 0] for k in range(2, n)])
    return [f % n for f in seq]


def load_pet_frames(theme=None):
    theme = theme or theme_state.get("pet_theme", "v2")
    if theme not in PET_THEMES: theme = "v2"
    frames = {}
    try:
        od_root = PET_THEMES[theme]["dir"]
        for anim in PET_ANIMS:
            od = os.path.join(od_root, anim)
            if not os.path.isdir(od): continue
            lst = []
            for fn in sorted(os.listdir(od)):
                if not fn.lower().endswith(".png"): continue
                img = QImage(os.path.join(od, fn))
                if not img.isNull(): lst.append(img)
            if lst: frames[anim] = lst
    except OSError:
        return None
    for need in ("idle", "sleep", "drag", "click"):
        if need not in frames: return None
    return frames or None


# ============================================================ 悬浮球 / 桌宠
class BallWindow(QWidget):
    def __init__(self, card):
        super().__init__()
        self.card = card
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)

        self.pet_theme = theme_state.get("pet_theme", "v2")
        self.pet_frames = None
        if theme_state.get("pet"):
            # 桌宠模式启动: 立即加载素材 (懒加载: 非桌宠模式先不加载, 加快启动)
            self.pet_frames = self._load_frames()
        self._loaded_pet_theme = self.pet_theme
        self.pet = False
        self._last_drawn = -1
        self._state = "idle"
        n_idle = len(self.pet_frames["idle"]) if self.pet_frames else 1
        self._seq = _pet_idle_seq(n_idle)
        self._si = 0
        self._idle_t = time.time()
        self._next_other = time.time() + random.randint(*PET_OTHER_EVERY)
        self._tm = QTimer(self)
        self._tm.timeout.connect(self._pet_tick)
        self._tm.start(PET_MS["idle"])

        self.resize(54, 54)
        self.hover = False
        self._moved = False
        self._press_time = 0.0
        self._press_origin = QPoint()

        pos = None
        try:
            with open(os.path.join(scanner.PLUGIN_DATA_DIR, "ball_pos.json")) as f:
                pos = json.load(f)
        except Exception:
            pass
        screen = QApplication.primaryScreen().availableGeometry()
        if pos:
            self.move(int(pos["x"]), int(pos["y"]))
        else:
            self.move(screen.right() - self.width() - 20, screen.bottom() - self.height() - 40)

        self.setToolTip("Token 统计 — 单击/双击打开统计面板 / 右键菜单")
        self.show()
        if self.pet_frames is not None and theme_state.get("pet"):
            self.pet = True
            self._pet_apply(True)

    def _load_frames(self):
        """按当前主题加载素材 (含 v2→v1 回退); 结果缓存到 self.pet_frames"""
        if self.pet_frames is not None and self._loaded_pet_theme == self.pet_theme:
            return self.pet_frames
        fr = load_pet_frames(self.pet_theme)
        if fr is None and self.pet_theme != "v1":
            self.pet_theme = "v1"
            fr = load_pet_frames("v1")
        self.pet_frames = fr
        self._loaded_pet_theme = self.pet_theme
        return fr

    def _frames_of(self, st):
        fr = self.pet_frames or {}
        return fr.get(st) or fr.get("idle") or []

    def _pet_state(self, st, seq=None):
        self._state = st
        if seq is not None: self._seq = seq
        elif st == "idle": self._seq = _pet_idle_seq(len(self._frames_of("idle")))
        elif st == "sleep": self._seq = [0] * 12
        elif st == "drag":
            fr = self._frames_of("drag")
            i = random.randrange(len(fr)) if fr else 0
            self._seq = [i] * 10
        self._si = 0
        self._tm.start(PET_MS.get(st, 240))
        self.update()

    def _pet_tick(self):
        if not self.pet or self.pet_frames is None: return
        if self._state == "idle":
            now = time.time()
            if now - self._idle_t > PET_SLEEP_AFTER:
                self._pet_state("sleep")
                return
            if now >= self._next_other and "other" in self.pet_frames:
                self._next_other = now + random.randint(*PET_OTHER_EVERY)
                n = len(self.pet_frames["other"])
                i = random.randrange(n)
                self._pet_state("other", seq=[i, (i + 1) % n, i])
                return
        self._si += 1
        if self._si >= len(self._seq):
            if self._state == "idle":
                self._seq = _pet_idle_seq(len(self._frames_of("idle")))
                self._si = 0
            elif self._state in ("sleep", "drag"):
                self._si = 0
            else:
                self._pet_state("idle")
                return
        # 流畅性: 帧号未变化(静止帧)时跳过重绘, 大幅降低桌宠常驻时的 CPU/绘制开销
        cur = self._seq[self._si % len(self._seq)] if self._seq else -1
        if cur != getattr(self, "_last_drawn", -1):
            self._last_drawn = cur
            self.update()

    def _pet_click(self):
        fr = self._frames_of("click")
        i = random.randrange(len(fr)) if fr else 0
        self._pet_state("click", seq=[i, i, i])

    def _pet_special(self):
        fr = self._frames_of("special")
        if not fr: return
        i = random.randrange(len(fr))
        self._idle_t = time.time()
        self._pet_state("special", seq=[i, i, (i + 1) % len(fr)])

    def set_pet_theme(self, theme):
        if theme not in PET_THEMES: return
        old_theme = self.pet_theme
        self.pet_theme = theme
        fr = self._load_frames()
        if fr is None:
            self.pet_theme = old_theme
            return
        theme_state["pet_theme"] = theme
        save_settings()
        if self.pet:
            self._pet_apply(True)
        self.update()

    def set_pet(self, on):
        if on:
            self._load_frames()   # 懒加载: 首次开启桌宠时才读素材
        on = bool(on) and self.pet_frames is not None
        self.pet = on
        theme_state["pet"] = on
        save_settings()
        self._pet_apply(on)

    def _pet_apply(self, on):
        if on:
            self.resize(PET_W, PET_H)
            self._idle_t = time.time()
            self._pet_state("idle")
            self.setToolTip("DeepSeek 娘 · 单击互动 / 双击打开统计 / 右键菜单")
        else:
            self.resize(54, 54)
            self.setToolTip("Token 统计 — 单击打开面板 / 右键菜单")
        self._clamp_pos()
        self.update()

    def _clamp_pos(self):
        screen = QGuiApplication.screenAt(self.geometry().center()) or QApplication.primaryScreen()
        scr = screen.availableGeometry()
        x = max(scr.left(), min(self.x(), scr.right() - self.width()))
        y = max(scr.top(), min(self.y(), scr.bottom() - self.height()))
        self.move(x, y)

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        if self.pet and self.pet_frames is not None:
            frames = self._frames_of(self._state)
            if not frames: return
            frame_no = self._seq[self._si % len(self._seq)]
            img = frames[frame_no % len(frames)]
            iw, ih = img.width(), img.height()
            scale = min(138.0 / ih, (PET_W - 10.0) / iw)
            dw, dh = iw * scale, ih * scale
            p.drawImage(QRectF((PET_W - dw) / 2.0, PET_H - 4 - dh, dw, dh), img)
            return

        w = self.width()
        R = QRectF(3, 3, w - 6, w - 6)
        dark = theme_state["dark"]
        glass = theme_state["glass"]

        if glass:
            rim = QLinearGradient(0, 0, 0, w)
            if dark:
                rim.setColorAt(0.0, QColor(255, 255, 255, 140))
                rim.setColorAt(1.0, QColor(255, 255, 255, 45))
            else:
                rim.setColorAt(0.0, QColor(255, 255, 255, 240))
                rim.setColorAt(1.0, QColor(190, 202, 220, 110))
            p.setPen(QPen(QBrush(rim), 1.4))
        else:
            p.setPen(QPen(QColor(255, 255, 255, 50) if dark else QColor(15, 17, 22, 50), 1.2))
        p.drawEllipse(R.adjusted(0.6, 0.6, -0.6, -0.6))

        grad = QLinearGradient(0, 3, 0, w - 3)
        c_top = QColor(80, 84, 92, 230) if dark else QColor(255, 255, 255, 242)
        c_bot = QColor(20, 22, 26, 245) if dark else QColor(210, 214, 222, 248)
        if self.hover:
            c_top = c_top.lighter(110)
        grad.setColorAt(0, c_top)
        grad.setColorAt(1, c_bot)
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(grad))
        p.drawEllipse(R)

        cx, cy = w / 2.0, w / 2.0
        bolt = [(0.58, 0.0), (0.12, 0.55), (0.42, 0.55), (0.30, 1.0), (0.88, 0.40), (0.55, 0.40)]
        scale = 22.0
        bp = QPainterPath()
        for i, (px, py) in enumerate(bolt):
            x = cx + (px - 0.5) * scale
            y = cy + (py - 0.5) * scale
            if i == 0: bp.moveTo(x, y)
            else: bp.lineTo(x, y)
        bp.closeSubpath()
        p.setBrush(QColor(255, 255, 255, 240) if dark else QColor(24, 26, 32, 240))
        p.drawPath(bp)

    def enterEvent(self, ev):
        self.hover = True
        self.update()

    def leaveEvent(self, ev):
        self.hover = False
        self.update()

    def mousePressEvent(self, ev):
        if ev.button() == Qt.LeftButton:
            self._drag = ev.globalPosition().toPoint() - self.frameGeometry().topLeft()
            self._moved = False
            self._press_time = time.time()
            self._press_origin = ev.globalPosition().toPoint()
            if self.pet: self._idle_t = time.time()

    def mouseMoveEvent(self, ev):
        if ev.buttons() & Qt.LeftButton:
            moved_now = (ev.globalPosition().toPoint() - self._press_origin).manhattanLength() > 4
            if not self._moved and moved_now and self.pet:
                self._moved = True
                self._pet_state("drag")
            if self._moved:
                self.move(ev.globalPosition().toPoint() - self._drag)

    def mouseReleaseEvent(self, ev):
        if ev.button() != Qt.LeftButton: return
        self._clamp_pos()
        try:
            with open(os.path.join(scanner.PLUGIN_DATA_DIR, "ball_pos.json"), "w") as f:
                json.dump({"x": self.x(), "y": self.y()}, f)
        except Exception: pass

        if self.pet:
            self._idle_t = time.time()
            dur_ms = (time.time() - self._press_time) * 1000
            if not self._moved and dur_ms < 250:
                self._pet_click()
            else:
                self._pet_state("idle")
            return

        if not self._moved:
            self._trigger_popup()

    def mouseDoubleClickEvent(self, ev):
        self._trigger_popup()

    def _trigger_popup(self):
        if self.card is not None:
            self.card.popup_from(self.frameGeometry())

    def contextMenuEvent(self, ev):
        menu = make_menu(self)
        a_ver = menu.addAction(f"版本: {APP_BUILD}")
        a_ver.setEnabled(False)
        menu.addSeparator()
        a1 = menu.addAction("📊  打开统计面板" + (" (双击桌宠也可以)" if self.pet else ""))
        a2 = menu.addAction("⟳  立即刷新数据")
        a_restart = menu.addAction("🔄  一键重启")
        menu.addSeparator()

        # 悬浮球右键调节通透度
        tr_menu = menu.addMenu("🔮  玻璃通透度")
        cur_tr = theme_state.get("glass_transparency", "balanced")
        act_tr_c = tr_menu.addAction(("● " if cur_tr == "crystal" else "○ ") + "💎 晶透水滴 (高通透)")
        act_tr_b = tr_menu.addAction(("● " if cur_tr == "balanced" else "○ ") + "💧 标准液态 (默认)")
        act_tr_f = tr_menu.addAction(("● " if cur_tr == "frosted" else "○ ") + "🌫️ 柔和微透 (防眩光)")

        # 悬浮球快捷切换窗口尺寸
        sz_menu = menu.addMenu("📐  窗口尺寸")
        cur_sz = theme_state.get("window_size", "default")
        act_sz_def = sz_menu.addAction(("● " if cur_sz != "large" else "○ ") + "标准尺寸 (990×610)")
        act_sz_lg = sz_menu.addAction(("● " if cur_sz == "large" else "○ ") + "舒适大窗口 (1180×730)")
        menu.addSeparator()

        a_pet = a_head = a_theme_menu = None
        # 显示条件用「素材目录存在」而非「已加载」: 懒加载后未开启桌宠时
        # pet_frames 为 None, 若按旧条件判断会导致桌宠开关从菜单消失
        _pet_dir = (PET_THEMES.get(self.pet_theme) or {}).get("dir")
        if _pet_dir and os.path.isdir(_pet_dir):
            a_pet = menu.addAction("🐳  桌宠形态 (DeepSeek 娘)")
            a_pet.setCheckable(True)
            a_pet.setChecked(self.pet)
            if self.pet:
                a_theme_menu = menu.addMenu("🎨  素材版本")
                for key in ("v2", "v1"):
                    act = a_theme_menu.addAction(PET_THEMES[key]["name"])
                    act.setCheckable(True)
                    act.setChecked(self.pet_theme == key)
                    act.setData(key)
                a_head = menu.addAction("🤗  摸摸头")
        menu.addSeparator()
        a_quit = menu.addAction("✕  退出")

        chosen = menu.exec(ev.globalPos())
        if chosen is not None and chosen.data() in PET_THEMES:
            self.set_pet_theme(chosen.data())
        elif chosen == a1:
            self._trigger_popup()
        elif chosen == a2:
            if self.card:
                self.card.popup_from(self.frameGeometry())
                self.card.refresh()
        elif chosen == act_tr_c:
            if self.card:
                self.card.set_glass_transparency("crystal")
        elif chosen == act_tr_b:
            if self.card:
                self.card.set_glass_transparency("balanced")
        elif chosen == act_tr_f:
            if self.card:
                self.card.set_glass_transparency("frosted")
        elif chosen == act_sz_def:
            if self.card:
                self.card.apply_size_mode("default")
        elif chosen == act_sz_lg:
            if self.card:
                self.card.apply_size_mode("large")
        elif a_pet is not None and chosen == a_pet:
            self.set_pet(not self.pet)
        elif a_head is not None and chosen == a_head:
            self._pet_special()
        elif chosen == a_restart:
            _restart_app()
        elif chosen == a_quit:
            os._exit(0)


def _restart_app():
    try:
        import subprocess
        pythonw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
        if not os.path.exists(pythonw): pythonw = sys.executable
        script = os.path.abspath(__file__)
        subprocess.Popen([pythonw, script], cwd=os.path.dirname(script),
                         creationflags=0x00000008 | 0x00000200)
    except Exception: pass
    # 150ms 足够新实例完成 pid 接管(_kill_stale_instance 兜底杀旧进程), 又远快于 300ms
    QTimer.singleShot(150, os._exit, 0)


# ============================================================ 单实例治理与启动
def _kill_stale_instance():
    pid_file = os.path.join(scanner.PLUGIN_DATA_DIR, "ball.pid")
    try:
        with open(pid_file) as f:
            old = int(f.read().strip())
        if old != os.getpid():
            import ctypes
            k32 = ctypes.windll.kernel32
            h = k32.OpenProcess(0x0001, False, old)
            if h:
                k32.TerminateProcess(h, 0)
                k32.CloseHandle(h)
    except Exception: pass
    try:
        with open(pid_file, "w") as f:
            f.write(str(os.getpid()))
    except Exception: pass


def main():
    _kill_stale_instance()
    app = QApplication(sys.argv)
    app.setApplicationName("Token 统计")
    app.setStyle("Fusion")
    load_settings()
    refresh_palette()
    apply_app_qss()

    card = CardWindow()
    ball = BallWindow(card)
    QTimer.singleShot(0, card.load_initial)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()