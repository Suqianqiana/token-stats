# -*- coding: utf-8 -*-
"""
Token 审计卡片 V7 — 分层液态玻璃 + 深色模式
层级设计: 玻璃底板(模糊+半透明) → 子卡片(高不透明度) → 文字(完全不透明)
"""
import json
import os
import sys
import threading
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)
import scanner  # noqa: E402

from PySide6.QtCore import Qt, QRectF, QObject, Signal, QTimer, QPoint
from PySide6.QtGui import (QColor, QFont, QPainter, QPen, QBrush, QPainterPath,
                           QLinearGradient)
from PySide6.QtWidgets import (QApplication, QWidget, QLabel, QVBoxLayout,
                               QHBoxLayout, QGridLayout, QFrame, QPushButton,
                               QScrollArea, QMenu, QSizePolicy, QPlainTextEdit,
                               QLineEdit)

# ============================================================ 主题系统
THEMES = {
    "light": dict(
        BG=(245, 246, 248), CARD=(255, 255, 255), BORDER=(230, 233, 238),
        TEXT=(23, 26, 32), TEXT2=(95, 102, 114), TEXT3=(152, 160, 171),
        TRACK=(238, 241, 245), HOVER=(238, 243, 250), ZEBRA=(250, 251, 253),
    ),
    "dark": dict(
        BG=(18, 20, 24), CARD=(30, 33, 39), BORDER=(48, 52, 60),
        TEXT=(240, 242, 245), TEXT2=(214, 218, 224), TEXT3=(188, 193, 200),
        TRACK=(42, 46, 53), HOVER=(40, 45, 53), ZEBRA=(26, 29, 34),
    ),
}
# 玻璃模式下的 alpha (纯 Qt 分层半透明, 无系统模糊)
# 底板很透(桌面可见) / 卡片较实(保形体与可读) / 文字恒 255
GLASS_ALPHA = {"light": dict(BG=110, CARD=235), "dark": dict(BG=105, CARD=225)}

theme_state = {"dark": False, "glass": False, "source": "wb"}
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


def refresh_palette():
    """根据 theme_state 刷新全局颜色 (BG/CARD/BORDER/TEXT/TEXT2/TEXT3/TRACK/HOVER/ZEBRA)"""
    name = "dark" if theme_state["dark"] else "light"
    t = THEMES[name]
    g = GLASS_ALPHA[name] if theme_state["glass"] else None

    def mk(rgb, a=255):
        return QColor(rgb[0], rgb[1], rgb[2], a)

    globals().update(
        BG=mk(t["BG"], g["BG"] if g else 255),
        CARD=mk(t["CARD"], g["CARD"] if g else 255),
        BORDER=mk(t["BORDER"]),
        TEXT=mk(t["TEXT"]),          # 文字永远全不透明
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

# ============================================================ 精美右键菜单
def menu_qss():
    dark = theme_state["dark"]
    if dark:
        return f"""
        QMenu {{ background:{qrgba(QColor(34,37,43),246)}; border:1px solid #3a3f47;
                 border-radius:12px; padding:6px; }}
        QMenu::item {{ padding:8px 26px 8px 14px; border-radius:8px;
                       color:#e8eaed; font-size:12.5px; }}
        QMenu::item:selected {{ background:{qrgba(QColor(91,126,229),60)};
                                color:#ffffff; }}
        QMenu::separator {{ height:1px; background:#3a3f47; margin:5px 8px; }}
        """
    return """
    QMenu { background:#ffffff; border:1px solid #e6e9ee; border-radius:12px; padding:6px; }
    QMenu::item { padding:8px 26px 8px 14px; border-radius:8px; color:#171a20; font-size:12.5px; }
    QMenu::item:selected { background:#eef3ff; color:#2f5ec4; }
    QMenu::separator { height:1px; background:#eef0f4; margin:5px 8px; }
    """


def make_menu(parent):
    m = QMenu(parent)
    m.setStyleSheet(menu_qss())
    # 三件套: 无边框 + 去系统阴影 + 半透明背景 → 圆角外不露原生方框
    m.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
    m.setAttribute(Qt.WA_TranslucentBackground)
    return m


def apply_app_qss():
    """滚动条 / tooltip 全局样式 (随主题)"""
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
                  border-radius:6px; padding:6px 9px; font-size:11.5px; }}
    """)


def fmt(n):
    n = int(n)
    if n >= 1e8:
        return f"{n/1e8:.2f} 亿"
    if n >= 1e4:
        return f"{n/1e4:.1f} 万"
    return f"{n:,}"


def fmt_full(n):
    return f"{int(n):,}"


# ============================================================ 卡片头
class CardHeader(QWidget):
    """小彩条 + 常规字重标题"""
    def __init__(self, text, accent=BLUE, parent=None):
        super().__init__(parent)
        self.text = text
        self.accent = accent
        self.setFixedHeight(24)

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(self.accent)
        p.drawRoundedRect(QRectF(0, 10.5, 20, 3.5), 1.75, 1.75)
        p.setPen(TEXT)
        p.setFont(QFont("Microsoft YaHei UI", 10))
        p.drawText(QRectF(28, 0, self.width() - 32, self.height()),
                   Qt.AlignLeft | Qt.AlignVCenter, self.text)


# ============================================================ 悬浮提示
class ChartTip(QWidget):
    """悬浮详情卡: 标题 + [色点,标签 …… 数值] 两列对齐, 随主题换肤"""
    _instance = None

    @classmethod
    def instance(cls):
        if cls._instance is None:
            cls._instance = ChartTip()
        return cls._instance

    ROW_H = 20
    PAD = 13
    GAP = 14          # 标签列与数值列最小间距
    VAL_MIN = 64      # 数值列预留宽

    def __init__(self):
        super().__init__(None, Qt.ToolTip | Qt.FramelessWindowHint |
                         Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.rows = []        # [(color|None, label, value)]
        self.title_text = ""
        self.accent = BLUE

    def show_tip(self, title, rows, accent, global_pos):
        """rows: str 旧格式兼容 / (color,label,value) 元组"""
        self.title_text = title
        self.accent = accent
        norm = []
        for r in rows:
            if isinstance(r, tuple):
                norm.append(r)
            else:
                norm.append((None, r, ""))
        self.rows = norm
        p = QPainter(self)
        f = QFont("Microsoft YaHei UI", 9)
        p.setFont(f)
        fm = p.fontMetrics()
        lab_w = max((fm.horizontalAdvance(lb) for _, lb, _ in norm), default=0)
        val_w = max((fm.horizontalAdvance(vl) for _, _, vl in norm), default=0)
        val_w = max(val_w, fm.horizontalAdvance(title))
        self._label_x = self.PAD + 12                       # 色点后标签起点
        self._value_right = self.PAD + 12 + lab_w + self.GAP + \
            max(val_w, self.VAL_MIN)
        w = self._value_right + self.PAD
        h = 34 + self.ROW_H * len(norm) + 6
        self.resize(w, h)
        x, y = global_pos.x() + 14, global_pos.y() + 16
        scr = QApplication.primaryScreen().availableGeometry()
        if x + w > scr.right():
            x = global_pos.x() - w - 10
        if y + h > scr.bottom():
            y = global_pos.y() - h - 10
        self.move(x, y)
        self.show()
        self.update()

    def hide_tip(self):
        self.hide()

    def paintEvent(self, ev):
        """配色完全复用面板全局色板 (CARD/BORDER/TEXT/TEXT2/TEXT3) → 风格统一"""
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        dark = theme_state["dark"]
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect().adjusted(0, 0, -1, -1)), 10, 10)
        # 底色=卡片色(不透明), 边框=面板边框; 暗色加一条顶部高光模拟玻璃受光
        p.setPen(QPen(BORDER, 1))
        p.setBrush(QColor(CARD.red(), CARD.green(), CARD.blue(), 252))
        p.drawPath(path)

        # 标题行: 左侧 accent 竖条 + 粗体标题 (与 CardHeader 同款语言)
        p.setPen(Qt.NoPen)
        p.setBrush(self.accent)
        p.drawRoundedRect(QRectF(6, 9, 3.5, 16), 1.75, 1.75)
        f = QFont("Microsoft YaHei UI", 9)
        f.setBold(True)
        p.setFont(f)
        p.setPen(TEXT)
        p.drawText(QRectF(self.PAD, 7, self.width() - self.PAD - 8, 18),
                   Qt.AlignLeft | Qt.AlignVCenter, self.title_text)

        f2 = QFont("Microsoft YaHei UI", 9)
        p.setFont(f2)
        y = 32
        for color, lb, vl in self.rows:
            cy = y + self.ROW_H / 2
            if color is not None:
                p.setPen(Qt.NoPen)
                p.setBrush(color)
                p.drawEllipse(QRectF(self.PAD + 1, cy - 3.5, 7, 7))
            p.setPen(TEXT2)                      # 标签: 次级文字色
            p.drawText(QRectF(self._label_x, y,
                              self._value_right - self.GAP - self._label_x,
                              self.ROW_H),
                       Qt.AlignLeft | Qt.AlignVCenter, lb)
            if vl:
                fv = QFont("Consolas", 9)
                fv.setBold(True)
                p.setFont(fv)
                p.setPen(TEXT if color is not None else TEXT2)  # 数值行用主文字
                p.drawText(QRectF(self._value_right - 400, y, 400, self.ROW_H),
                           Qt.AlignRight | Qt.AlignVCenter, vl)
                p.setFont(f2)
            y += self.ROW_H
        if dark:
            # 暗色下顶部 1px 高光线, 与卡片玻璃描边呼应
            hl = QColor(255, 255, 255, 28)
            p.setPen(QPen(hl, 1))
            p.drawLine(QPoint(10, 1), QPoint(self.width() - 11, 1))


# ============================================================ 汇总卡片
class StatCard(QFrame):
    def __init__(self, label, accent, parent=None):
        super().__init__(parent)
        self.label_text = label
        self.accent = accent
        self.value_text = "—"
        self.hint_text = ""
        self.setFixedHeight(78)

    def set_value(self, value, hint=""):
        self.value_text = value
        self.hint_text = hint
        self.update()

    def set_label(self, label):
        if self.label_text != label:
            self.label_text = label
            self.update()

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect().adjusted(0, 0, -1, -1)), 12, 12)
        p.setPen(QPen(BORDER, 1))
        p.setBrush(QBrush(CARD))
        p.drawPath(path)
        p.setPen(Qt.NoPen)
        p.setBrush(self.accent)
        p.drawRoundedRect(QRectF(14, 10, 22, 3.5), 1.75, 1.75)
        p.setPen(TEXT2)
        p.setFont(QFont("Microsoft YaHei UI", 9))
        p.drawText(QRectF(14, 17, w - 24, 16), Qt.AlignLeft | Qt.AlignVCenter,
                   self.label_text)
        p.setPen(TEXT)                       # 数值全不透明
        f = QFont("Microsoft YaHei UI", 14)
        f.setBold(True)
        p.setFont(f)
        fm = p.fontMetrics()
        vx, vy = 14, h - 16
        p.drawText(vx, vy, self.value_text)
        if self.hint_text:
            p.setPen(TEXT3)
            p.setFont(QFont("Consolas", 8.5))
            p.drawText(vx + fm.horizontalAdvance(self.value_text) + 7,
                       vy, self.hint_text)


# ============================================================ 模型明细表
ROW_H = 30
NAME_W = 138
TOTAL_W = 100
PCT_W = 46
HIT_W = 60
REQ_W = 62
PAD = 6


class TableHeader(QWidget):
    """表头行 (与数据行同宽, 放在同一滚动内容里保证对齐)"""
    def __init__(self, req_label="请求次数", parent=None):
        super().__init__(parent)
        self.req_label = req_label
        self.setFixedHeight(26)

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        p.setFont(QFont("Microsoft YaHei UI", 9))
        cols = [
            (PAD, NAME_W, "模型", Qt.AlignLeft | Qt.AlignVCenter),
            (w - PAD - REQ_W - HIT_W - PCT_W - TOTAL_W, TOTAL_W, "Tokens 总量",
             Qt.AlignRight | Qt.AlignVCenter),
            (w - PAD - REQ_W - HIT_W - PCT_W, PCT_W, "占比",
             Qt.AlignRight | Qt.AlignVCenter),
            (w - PAD - REQ_W - HIT_W, HIT_W, "缓存命中",
             Qt.AlignRight | Qt.AlignVCenter),
            (w - PAD - REQ_W, REQ_W, self.req_label,
             Qt.AlignRight | Qt.AlignVCenter),
        ]
        for x, cw, text, align in cols:
            p.setPen(TEXT3)
            p.drawText(QRectF(x, 0, cw, h), align, text)
        p.setPen(QPen(BORDER, 1))
        p.drawLine(0, h - 1, w, h - 1)


class ModelRow(QWidget):
    """模型明细行: 名称(超长省略) + 比例条 + 右侧数字; 整行悬浮显示完整信息"""
    def __init__(self, name, color, ratio, total, pct, hit_rate, requests,
                 input_tok=0, output_tok=0, cached_tok=0, zebra=False,
                 parent=None):
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
        self.setMouseTracking(True)          # 无按键也接收 hover
        if zebra:
            self.setStyleSheet(f"background:{qrgba(ZEBRA)};")
        self.setFixedHeight(ROW_H)

    def enterEvent(self, ev):
        self.setStyleSheet(f"background:{qrgba(HOVER)};")
        self._show_tip()

    def leaveEvent(self, ev):
        self.setStyleSheet(f"background:{qrgba(ZEBRA)};" if self._zebra else "")
        ChartTip.instance().hide_tip()

    def _show_tip(self):
        rows = [
            (None, "输入", fmt_full(self.input_tok)),
            (None, "输出", fmt_full(self.output_tok)),
            (None, "缓存命中", f"{fmt_full(self.cached_tok)}  ({self.hit_rate:.1f}%)"),
            (None, "请求次数", f"{self.requests:,}"),
            (self.color, "Tokens 总量", f"{fmt_full(self.total)}  ({self.pct:.1f}%)"),
        ]
        ChartTip.instance().show_tip(self.name, rows, self.color,
                                     self.mapToGlobal(QPoint(int(self.width() / 2), 4)))

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        cy = h / 2
        p.setPen(Qt.NoPen)
        p.setBrush(self.color)
        p.drawEllipse(QRectF(PAD, cy - 4, 8, 8))
        p.setPen(TEXT)
        p.setFont(QFont("Consolas", 9.5))
        name_rect = QRectF(PAD + 14, 0, NAME_W - 20, h)
        fm = p.fontMetrics()
        elided = fm.elidedText(self.name, Qt.ElideRight, int(name_rect.width()))
        p.drawText(name_rect, Qt.AlignVCenter | Qt.AlignLeft, elided)
        # 比例条
        bar_right = w - PAD - REQ_W - HIT_W - PCT_W - TOTAL_W - 12
        bar_left = PAD + NAME_W
        bw = bar_right - bar_left
        if bw > 20:
            track = QPainterPath()
            track.addRoundedRect(QRectF(bar_left, cy - 4.5, bw, 9), 4.5, 4.5)
            p.setPen(Qt.NoPen)
            p.setBrush(TRACK)
            p.drawPath(track)
            fill_w = max(9, bw * self.ratio)
            grad = QLinearGradient(bar_left, 0, bar_left + fill_w, 0)
            grad.setColorAt(0, self.color.lighter(112))
            grad.setColorAt(1, self.color)
            fillp = QPainterPath()
            fillp.addRoundedRect(QRectF(bar_left, cy - 4.5, fill_w, 9), 4.5, 4.5)
            p.setBrush(QBrush(grad))
            p.drawPath(fillp)

        def right_text(text, col_w, x_right, color, bold=False, size=9.5):
            p.setPen(color)
            f = QFont("Consolas", size)
            f.setBold(bold)
            p.setFont(f)
            p.drawText(QRectF(x_right - col_w, 0, col_w, h),
                       Qt.AlignVCenter | Qt.AlignRight, text)
        x1 = w - PAD - REQ_W - HIT_W - PCT_W
        right_text(fmt_full(self.total), TOTAL_W, x1, TEXT, bold=True)
        right_text(f"{self.pct:.1f}%", PCT_W, x1 + PCT_W, TEXT2)
        right_text(f"{self.hit_rate:.0f}%", HIT_W, x1 + PCT_W + HIT_W,
                   GREEN if self.hit_rate >= 80 else TEXT2)
        right_text(f"{self.requests:,}", REQ_W, x1 + PCT_W + HIT_W + REQ_W, TEXT2)

    def mouseMoveEvent(self, ev):
        # 悬浮中移动也保持 tip 跟手(位置不刷新, 仅确保不消失)
        pass


# ============================================================ 商汤额度明细行
# 列布局与 ModelRow 严格对齐 (NAME_W 同名; 右侧 用量/剩余/调用 三列), 风格统一。
SN_USED_W = 84
SN_REMAIN_W = 96
SN_CALL_W = 56


class SNHeader(QWidget):
    """商汤明细表头 (与 SNRow 同宽对齐)."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(26)

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        p.setFont(QFont("Microsoft YaHei UI", 9))
        x_used = w - PAD - SN_CALL_W - SN_REMAIN_W - SN_USED_W
        x_rem = w - PAD - SN_CALL_W - SN_REMAIN_W
        x_call = w - PAD - SN_CALL_W
        cols = [
            (PAD, NAME_W, "模型", Qt.AlignLeft | Qt.AlignVCenter),
            (x_used, SN_USED_W, "窗口用量", Qt.AlignRight | Qt.AlignVCenter),
            (x_rem, SN_REMAIN_W, "剩余额度", Qt.AlignRight | Qt.AlignVCenter),
            (x_call, SN_CALL_W, "调用", Qt.AlignRight | Qt.AlignVCenter),
        ]
        for x, cw, text, align in cols:
            p.setPen(TEXT3)
            p.drawText(QRectF(x, 0, cw, h), align, text)
        p.setPen(QPen(BORDER, 1))
        p.drawLine(0, h - 1, w, h - 1)


class SNRow(QWidget):
    """商汤模型额度行: 名称 + 用量进度条(绿→黄→红) + 剩余/调用; 悬浮显示详情."""
    def __init__(self, name, color, used, quota, remaining, calls, dsh_calls,
                 calibrated, zebra=False, parent=None):
        super().__init__(parent)
        self.name = name
        self.color = color
        self.used = used
        self.quota = quota
        self.remaining = remaining
        self.calls = calls
        self.dsh_calls = dsh_calls
        self.calibrated = calibrated
        self._zebra = zebra
        self.setMouseTracking(True)
        if zebra:
            self.setStyleSheet(f"background:{qrgba(ZEBRA)};")
        self.setFixedHeight(ROW_H)

    def enterEvent(self, ev):
        self.setStyleSheet(f"background:{qrgba(HOVER)};")
        self._show_tip()

    def leaveEvent(self, ev):
        self.setStyleSheet(f"background:{qrgba(ZEBRA)};" if self._zebra else "")
        ChartTip.instance().hide_tip()

    def _show_tip(self):
        rows = [
            (None, "本窗口已用", f"{self.used:,} 次"),
            (None, "套餐额度", f"{self.quota:,} 次 / {SN_WINDOW_HOURS}h"),
            (self.color, "剩余额度",
             f"{self.remaining:,} 次" + ("  (已校准)" if self.calibrated else "")),
            (None, "WB 窗口调用", f"{self.calls:,} 次"),
            (None, "DSH 今日调用", f"{self.dsh_calls:,} 次"),
        ]
        ChartTip.instance().show_tip(
            self.name, rows, self.color,
            self.mapToGlobal(QPoint(int(self.width() / 2), 4)))

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        cy = h / 2
        p.setPen(Qt.NoPen)
        p.setBrush(self.color)
        p.drawEllipse(QRectF(PAD, cy - 4, 8, 8))
        p.setPen(TEXT)
        p.setFont(QFont("Consolas", 9.5))
        name_rect = QRectF(PAD + 14, 0, NAME_W - 20, h)
        fm = p.fontMetrics()
        elided = fm.elidedText(self.name, Qt.ElideRight, int(name_rect.width()))
        p.drawText(name_rect, Qt.AlignVCenter | Qt.AlignLeft, elided)
        # 进度条
        bar_right = w - PAD - SN_CALL_W - SN_REMAIN_W - SN_USED_W - 12
        bar_left = PAD + NAME_W
        bw = bar_right - bar_left
        ratio = max(0.0, min(1.0, self.used / self.quota)) if self.quota else 0
        if bw > 20:
            track = QPainterPath()
            track.addRoundedRect(QRectF(bar_left, cy - 4.5, bw, 9), 4.5, 4.5)
            p.setPen(Qt.NoPen)
            p.setBrush(TRACK)
            p.drawPath(track)
            fill_w = max(9, bw * ratio)
            if ratio < 0.7:
                c = GREEN
            elif ratio < 0.9:
                c = YELLOW
            else:
                c = RED
            grad = QLinearGradient(bar_left, 0, bar_left + fill_w, 0)
            grad.setColorAt(0, c.lighter(112))
            grad.setColorAt(1, c)
            fillp = QPainterPath()
            fillp.addRoundedRect(QRectF(bar_left, cy - 4.5, fill_w, 9), 4.5, 4.5)
            p.setBrush(QBrush(grad))
            p.drawPath(fillp)

        def right_text(text, col_w, x_right, color, bold=False, size=9.5):
            p.setPen(color)
            f = QFont("Consolas", size)
            f.setBold(bold)
            p.setFont(f)
            p.drawText(QRectF(x_right - col_w, 0, col_w, h),
                       Qt.AlignVCenter | Qt.AlignRight, text)

        x_used = w - PAD - SN_CALL_W - SN_REMAIN_W - SN_USED_W
        x_rem = w - PAD - SN_CALL_W - SN_REMAIN_W
        x_call = w - PAD - SN_CALL_W
        right_text(f"{self.used:,}", SN_USED_W, x_used, TEXT, bold=True)
        right_text(f"{self.remaining:,}", SN_REMAIN_W, x_rem, TEXT2)
        right_text(f"{self.calls + self.dsh_calls:,}", SN_CALL_W, x_call, TEXT2)


# ============================================================ 商汤官网风格额度页
# 完全独立于 StatCard/ModelRow/SNRow; 复刻 platform.sensenova.cn 控制台
# 「当前窗口调用余量 · 按模型」样式: 圆角白卡、模型名、%剩余、紫进度条。
SN_PURPLE = QColor("#7c67ff")
SN_PURPLE_DARK = QColor("#9a8aff")
SN_ORANGE = QColor("#ff7043")
SN_ORANGE_DARK = QColor("#ff8a65")
SN_TRACK_LIGHT = QColor("#eef0f5")
SN_TRACK_DARK = QColor("#3a3d4a")


class SNProgressBar(QWidget):
    """圆角进度条 (剩余额度占比), 支持 purple/orange 两色主题."""

    def __init__(self, ratio=0.0, color="purple", parent=None):
        super().__init__(parent)
        self.ratio = ratio
        self.color = color
        self.setFixedHeight(10)

    def set_ratio(self, r):
        self.ratio = max(0.0, min(1.0, r))
        self.update()

    def set_color(self, color):
        self.color = color
        self.update()

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        r = h / 2
        track = SN_TRACK_DARK if theme_state["dark"] else SN_TRACK_LIGHT
        p.setPen(Qt.NoPen)
        p.setBrush(track)
        p.drawRoundedRect(0, 0, w, h, r, r)
        fill_w = max(h, w * self.ratio)
        if self.color == "orange":
            fill = SN_ORANGE_DARK if theme_state["dark"] else SN_ORANGE
        else:
            fill = SN_PURPLE_DARK if theme_state["dark"] else SN_PURPLE
        p.setBrush(fill)
        p.drawRoundedRect(0, 0, fill_w, h, r, r)


class SNPoolCard(QFrame):
    """积分池卡片 (单行大卡): 左栏本周余额大数字, 右栏 5h 窗口进度, 底部周额度/重置."""

    def __init__(self, pool, parent=None):
        super().__init__(parent)
        self.pool = pool
        self.setObjectName("sn_pool_card")
        self._build_ui()
        self.apply_theme()

    def _build_ui(self):
        v = QVBoxLayout(self)
        v.setContentsMargins(16, 13, 16, 13)
        v.setSpacing(7)

        # 标题行: 彩点 + 池名 (加粗清晰) | 适用范围/同步徽标 (单行卡宽度足够, 同行不挤)
        top = QHBoxLayout()
        top.setSpacing(7)
        self.dot_lbl = QLabel("●")
        self.dot_lbl.setFont(QFont("Microsoft YaHei UI", 9))
        top.addWidget(self.dot_lbl)
        self.name_lbl = QLabel(self.pool["name"])
        self.name_lbl.setFont(QFont("Microsoft YaHei UI", 12, QFont.Bold))
        top.addWidget(self.name_lbl)
        top.addSpacing(4)
        scope = self.pool.get("scope", "")
        if self.pool.get("synced") and self.pool.get("sync_time"):
            scope = f"✓ 已同步 {self.pool['sync_time']} · {scope}"
        self.scope_lbl = QLabel(scope)
        self.scope_lbl.setFont(QFont("Microsoft YaHei UI", 9))
        self.scope_lbl.setAlignment(Qt.AlignBottom)
        top.addWidget(self.scope_lbl, 0, Qt.AlignBottom)
        top.addStretch(1)
        v.addLayout(top)

        # 中部横排: 左栏 本周余额大数字 | 右栏 5h 窗口进度
        mid = QHBoxLayout()
        mid.setSpacing(20)
        left = QVBoxLayout()
        left.setSpacing(3)
        self.balance_tag_lbl = QLabel("周期刷新 · 本周余额")
        self.balance_tag_lbl.setFont(QFont("Microsoft YaHei UI", 9))
        left.addWidget(self.balance_tag_lbl)
        bal_row = QHBoxLayout()
        bal_row.setSpacing(7)
        self.balance_lbl = QLabel(f"{self.pool['weekly_remaining']:,.2f}")
        self.balance_lbl.setFont(QFont("Consolas", 21, QFont.Bold))
        bal_row.addWidget(self.balance_lbl)
        self.weekly_total_lbl = QLabel(f"/ {self.pool['weekly_total']:,}")
        self.weekly_total_lbl.setFont(QFont("Consolas", 10))
        bal_row.addWidget(self.weekly_total_lbl, 0, Qt.AlignBottom)
        bal_row.addStretch(1)
        left.addLayout(bal_row)
        mid.addLayout(left)

        right = QVBoxLayout()
        right.setSpacing(4)
        wr = QHBoxLayout()
        wr.setSpacing(6)
        self.window_label_lbl = QLabel("5h 窗口可用")
        self.window_label_lbl.setFont(QFont("Microsoft YaHei UI", 9))
        wr.addWidget(self.window_label_lbl)
        wr.addStretch(1)
        self.window_reset_lbl = QLabel(f"重置 {self.pool.get('window_reset', '—')}")
        self.window_reset_lbl.setFont(QFont("Microsoft YaHei UI", 9))
        wr.addWidget(self.window_reset_lbl)
        right.addLayout(wr)
        wt = self.pool.get("window_total", 0)
        ratio = self.pool["window_remaining"] / wt if wt else 0
        self.bar = SNProgressBar(ratio, color=self.pool.get("color", "purple"))
        right.addWidget(self.bar)
        bar_info = QHBoxLayout()
        bar_info.setSpacing(6)
        self.window_ratio_lbl = QLabel(
            f"{self.pool['window_remaining']:,.2f} / {wt:,}")
        self.window_ratio_lbl.setFont(QFont("Consolas", 10))
        bar_info.addWidget(self.window_ratio_lbl)
        bar_info.addStretch(1)
        self.window_pct_lbl = QLabel(f"{ratio * 100:.1f}%")
        self.window_pct_lbl.setFont(QFont("Consolas", 10, QFont.Bold))
        bar_info.addWidget(self.window_pct_lbl)
        right.addLayout(bar_info)
        mid.addLayout(right, 1)
        v.addLayout(mid)

        # 底部一行: 周额度 + 值 + 下次周重置, 全部靠左, 不用 stretch 把内容推到右侧
        bottom = QHBoxLayout()
        bottom.setSpacing(6)
        self.weekly_label_lbl = QLabel("周额度")
        self.weekly_label_lbl.setFont(QFont("Microsoft YaHei UI", 9))
        bottom.addWidget(self.weekly_label_lbl)
        nr = self.pool.get("next_weekly_reset", "—")
        self.next_reset_lbl = QLabel(
            f"{self.pool['weekly_total']:,} · 下次周重置 {nr}")
        self.next_reset_lbl.setFont(QFont("Consolas", 10, QFont.Bold))
        bottom.addWidget(self.next_reset_lbl)
        bottom.addStretch(1)
        v.addLayout(bottom)

    def apply_theme(self):
        dark = theme_state["dark"]
        accent = (SN_ORANGE_DARK if dark else SN_ORANGE) \
            if self.pool.get("color") == "orange" \
            else (SN_PURPLE_DARK if dark else SN_PURPLE)
        self.setStyleSheet(
            f"#sn_pool_card {{ background:{qrgba(CARD, 255)}; "
            f"border:1px solid {qrgba(BORDER)}; border-radius:12px; }}")
        self.dot_lbl.setStyleSheet(f"color:{qname(accent)}; font-size:9px;")
        self.name_lbl.setStyleSheet(f"color:{qname(TEXT)};")
        for lbl in (self.balance_lbl, self.next_reset_lbl):
            lbl.setStyleSheet(f"color:{qname(TEXT)};")
        for lbl in (self.scope_lbl, self.balance_tag_lbl, self.window_label_lbl,
                    self.window_reset_lbl, self.weekly_label_lbl,
                    self.weekly_total_lbl):
            lbl.setStyleSheet(f"color:{qname(TEXT3)};")
        for lbl in (self.window_ratio_lbl, self.window_pct_lbl):
            lbl.setStyleSheet(f"color:{qname(TEXT2)};")
        self.bar.update()


def _fmt_num(v, fmt=",.2f"):
    """把可能是字符串的数字格式化为千分位; 失败返回原字符串."""
    try:
        return format(float(v), fmt)
    except (ValueError, TypeError):
        return str(v) if v is not None else "—"


class SNPromoCard(QFrame):
    """活动固定积分卡片 (Flash-Lite 消费 1:1 返赠, 30 天有效; 改为竖向堆叠, 防右侧截断)."""

    def __init__(self, pool, parent=None):
        super().__init__(parent)
        self.pool = pool
        self.setObjectName("sn_promo_card")
        self._build_ui()
        self.apply_theme()

    def _build_ui(self):
        v = QVBoxLayout(self)
        v.setContentsMargins(16, 13, 16, 13)
        v.setSpacing(6)

        # 标题行: 彩点 + 池名 (12pt 粗体, 清晰)
        title = QHBoxLayout()
        title.setSpacing(7)
        self.dot_lbl = QLabel("●")
        self.dot_lbl.setFont(QFont("Microsoft YaHei UI", 9))
        title.addWidget(self.dot_lbl)
        self.name_lbl = QLabel(self.pool["name"])
        self.name_lbl.setFont(QFont("Microsoft YaHei UI", 12, QFont.Bold))
        title.addWidget(self.name_lbl)
        title.addStretch(1)
        v.addLayout(title)

        # scope / 已同步徽标 单独一行, 自动换行
        scope = "Flash-Lite 消费 1:1 返赠 · 30 天有效"
        if self.pool.get("synced") and self.pool.get("sync_time"):
            scope = f"✓ 已同步 {self.pool['sync_time']} · {scope}"
        self.scope_lbl = QLabel(scope)
        self.scope_lbl.setFont(QFont("Microsoft YaHei UI", 9))
        self.scope_lbl.setWordWrap(True)
        v.addWidget(self.scope_lbl)

        # 数据区: 总量余额 (独占一行大数字)
        self.total_tag_lbl = QLabel("总量余额")
        self.total_tag_lbl.setFont(QFont("Microsoft YaHei UI", 9))
        v.addWidget(self.total_tag_lbl)

        self.total_lbl = QLabel(_fmt_num(self.pool.get("total_balance", 0)))
        self.total_lbl.setFont(QFont("Consolas", 21, QFont.Bold))
        v.addWidget(self.total_lbl)

        # 最近到期: 标签 + 值 一行, 靠左, 避免被推到右边截断
        expire = QHBoxLayout()
        expire.setSpacing(7)
        self.expire_tag_lbl = QLabel("最近一次到期")
        self.expire_tag_lbl.setFont(QFont("Microsoft YaHei UI", 9))
        expire.addWidget(self.expire_tag_lbl)
        self.expire_lbl = QLabel(_fmt_num(self.pool.get("nearest_expire", 0)))
        self.expire_lbl.setFont(QFont("Consolas", 12, QFont.Bold))
        expire.addWidget(self.expire_lbl)
        expire.addStretch(1)
        v.addLayout(expire)

    def apply_theme(self):
        accent = SN_PURPLE_DARK if theme_state["dark"] else SN_PURPLE
        self.setStyleSheet(
            f"#sn_promo_card {{ background:{qrgba(CARD, 255)}; "
            f"border:1px solid {qrgba(BORDER)}; border-radius:12px; }}")
        self.dot_lbl.setStyleSheet(f"color:{qname(accent)}; font-size:9px;")
        self.name_lbl.setStyleSheet(f"color:{qname(TEXT)};")
        self.total_lbl.setStyleSheet(f"color:{qname(TEXT)};")
        self.expire_lbl.setStyleSheet(f"color:{qname(TEXT2)};")
        for lbl in (self.scope_lbl, self.total_tag_lbl, self.expire_tag_lbl):
            lbl.setStyleSheet(f"color:{qname(TEXT3)};")


class SNSyncPanel(QFrame):
    """同步设置面板: 内嵌商汤页底部 (取代旧二级对话框). 贴 cURL 一键配置自动同步."""

    saved = Signal()                 # 保存成功 → CardWindow 重新拉数据渲染
    cleared = Signal()               # 清除配置 → CardWindow 重算渲染
    save_finished = Signal(bool, str)   # 后台测试/抓取完成 (ok, msg) → 回主线程更新 UI

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("sn_sync_panel")
        self._status_color = None
        self._sync_test = False      # 测试模式: 同步执行网络调用 (offscreen 回归用)
        self._test_req = None
        self.save_finished.connect(self._on_save_finished)
        self._build_ui()
        self.apply_theme()

    def _build_ui(self):
        v = QVBoxLayout(self)
        v.setContentsMargins(16, 12, 16, 12)
        v.setSpacing(7)

        head = QHBoxLayout()
        head.setSpacing(8)
        self.title_lbl = QLabel("同步设置")
        self.title_lbl.setFont(QFont("Microsoft YaHei UI", 11, QFont.Bold))
        head.addWidget(self.title_lbl)
        self.status_lbl = QLabel("")
        self.status_lbl.setFont(QFont("Microsoft YaHei UI", 9.5))
        head.addWidget(self.status_lbl, 0, Qt.AlignBottom)
        head.addStretch(1)
        v.addLayout(head)

        self.desc_lbl = QLabel(
            "自动同步: 官网「积分额度」页 → F12 → Network(网络) → 找到响应含积分数字的请求 → "
            "右键 Copy → Copy as cURL → 粘贴到下面 → 保存。积分数字自动识别, 无需填写。")
        self.desc_lbl.setFont(QFont("Microsoft YaHei UI", 9))
        self.desc_lbl.setWordWrap(True)
        v.addWidget(self.desc_lbl)

        self.curl_edit = QPlainTextEdit()
        self.curl_edit.setPlaceholderText(
            "粘贴 Copy as cURL 内容 (curl \"https://platform.sensenova.cn/lite/console/...\")")
        self.curl_edit.setFixedHeight(64)
        v.addWidget(self.curl_edit)

        row = QHBoxLayout()
        row.setSpacing(8)
        self.err_lbl = QLabel("")
        self.err_lbl.setFont(QFont("Microsoft YaHei UI", 9))
        self.err_lbl.setWordWrap(True)
        row.addWidget(self.err_lbl, 1)
        self.btn_clear = QPushButton("清除配置")
        self.btn_clear.setCursor(Qt.PointingHandCursor)
        self.btn_clear.clicked.connect(self._on_clear)
        row.addWidget(self.btn_clear)
        self.btn_save = QPushButton("保存并测试")
        self.btn_save.setCursor(Qt.PointingHandCursor)
        self.btn_save.clicked.connect(self._on_save)
        row.addWidget(self.btn_save)
        v.addLayout(row)

    def set_status(self, s):
        """按 load_sn_stats() 结果刷新状态行 (render 时调用)."""
        if s.get("autosync_error"):
            self.status_lbl.setText(f"⚠ {s['autosync_error']}")
            self._status_color = "#e0a040"
        elif s.get("sync_src") == "auto":
            self.status_lbl.setText(
                f"✓ 自动同步 {s.get('sync_time')} · 每 5 分钟自动更新, 点⟳立即更新")
            self._status_color = "#3f9d63"
        elif s.get("synced"):
            self.status_lbl.setText(
                f"✓ 显示最后已知值 (同步于 {s.get('sync_time')}, 凭据已过期?)")
            self._status_color = "#e0a040"
        else:
            self.status_lbl.setText("未配置自动同步 — 余额为本地估算")
            self._status_color = None
        self.apply_theme()

    def _on_clear(self):
        clear_sn_autosync()
        clear_sn_sync()
        _autosync_mem.update(ts=0.0, values=None, error=None)
        self.curl_edit.clear()
        self.err_lbl.setText("已清除同步配置 (回到本地估算)。")
        self.cleared.emit()

    def _on_save(self):
        text = self.curl_edit.toPlainText().strip()
        if not text:
            self.err_lbl.setText("请先粘贴 cURL。")
            return
        req = parse_curl(text)
        if not req:
            self.err_lbl.setText("解析失败: 未找到 URL。请复制完整的 Copy as cURL 内容。")
            return
        if self._sync_test:
            # 回归测试模式: _http_json 已被 monkeypatch 成立即返回, 同步执行便于断言
            ok, msg = self._do_test_and_save(req)
            self.err_lbl.setText(msg)
            if ok:
                self.saved.emit()
            return
        # 真实网络请求可能长达 10~20s (代理超时/直连重试): 放后台线程,
        # 绝不在 UI 线程等网络 — 否则窗口"未响应"直至崩溃
        self.err_lbl.setText("正在测试接口…")
        self.btn_save.setEnabled(False)
        self.btn_clear.setEnabled(False)
        self._test_req = req
        threading.Thread(target=self._save_worker, daemon=True).start()

    def _save_worker(self):
        try:
            ok, msg = self._do_test_and_save(self._test_req)
        except Exception as e:   # 后台线程兜底: 任何异常都回主线程提示, 不崩程序
            ok, msg = False, f"测试过程异常: {str(e)[:60]}"
        self.save_finished.emit(ok, msg)

    def _on_save_finished(self, ok, msg):
        self.btn_save.setEnabled(True)
        self.btn_clear.setEnabled(True)
        self.err_lbl.setText(msg)
        if ok:
            self.saved.emit()

    def _do_test_and_save(self, req):
        """同步执行: 测试接口 → 零指纹探测 → 保存配置 → 立即抓取写手动回退.

        返回 (ok, msg); 在 worker 线程调用 (测试模式在主线程).
        """
        status, data, err = _http_json(req)
        if err:
            return False, f"接口调用失败: {err} — 请检查网络或重新抓包。"
        # 零指纹: 商汤接口自带 pool_type/name, 按结构直接认字段 (数字无需填写)
        paths = _detect_paths_by_structure(data)
        if not paths:
            return False, ("识别失败: 响应里没有找到商汤积分池结构 "
                           "(pools[].pool_type / 名称)。\n"
                           "请确认复制的请求是「积分额度」页的数据接口。")
        now = time.time()
        cfg = {"v": 1, "url": req["url"], "method": req["method"],
               "headers": req["headers"], "body": req["body"],
               "paths": paths, "fingerprint": None, "saved_ts": now}
        if not save_sn_autosync(cfg):
            return False, "保存失败 (文件写入权限问题)。"
        # 立即完整抓取一次 (含重置时间/活动积分), 抓到的值写入手动回退文件
        vals = sn_autosync_fetch(force=True)
        manual = load_sn_sync() or {}
        if vals:
            manual.update({"ts": _autosync_mem["ts"],
                           **{k: v for k, v in vals.items()
                              if isinstance(v, (int, float))}})
        else:
            manual.setdefault("ts", now)
        save_sn_sync(manual)
        if vals:
            return True, (f"✓ 已保存并同步 {time.strftime('%H:%M')} — "
                          f"通用池周余额 {vals.get('general_w', 0):,.0f}")
        return True, "✓ 配置已保存 (本次抓取失败, 将在下次刷新重试)。"

    def apply_theme(self):
        border = qrgba(BORDER)
        text, text2, text3 = qname(TEXT), qname(TEXT2), qname(TEXT3)
        self.setStyleSheet(
            f"#sn_sync_panel {{ background:{qrgba(CARD, 255)};"
            f" border:1px solid {border}; border-radius:12px; }}"
            f"QPlainTextEdit {{ background:{qrgba(TRACK)}; color:{text};"
            f" border:1px solid {border}; border-radius:8px; padding:5px 8px;"
            f" font-size:11px; selection-background-color:#3b6fe0; }}")
        self.title_lbl.setStyleSheet(f"color:{text};")
        self.desc_lbl.setStyleSheet(f"color:{text3};")
        c = self._status_color
        self.status_lbl.setStyleSheet(
            c if c else f"color:{text3};")
        self.err_lbl.setStyleSheet(
            f"color:{c};" if c and self.err_lbl.text().startswith("✓")
            else "color:#e05252;")
        self.btn_clear.setStyleSheet(
            f"QPushButton{{ background:{qrgba(TRACK)}; color:{text2};"
            f" border:1px solid {border}; border-radius:8px; padding:6px 14px;"
            f" font-size:12px; }}")
        self.btn_save.setStyleSheet(
            "QPushButton{ background:#3b6fe0; color:white; border:none;"
            " border-radius:8px; padding:6px 16px; font-size:12px; font-weight:600; }"
            "QPushButton:hover{ background:#2f5ec4; }")


class SNQuotaPage(QFrame):
    """商汤额度展示页: 官网「积分额度」风格 + 液态玻璃主题 (单列大卡 + 内嵌同步面板)."""

    saved = Signal()     # 同步面板保存成功 → CardWindow 重新拉数据
    cleared = Signal()   # 同步面板清除配置 → CardWindow 重算渲染

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("sn_quota_page")
        self._build_ui()

    def _build_ui(self):
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(12)

        # 标题区: 小标签「额度」+ 大标题「积分额度」+ 提示图标
        head = QHBoxLayout()
        head.setSpacing(8)
        self.tag_lbl = QLabel("额度")
        self.tag_lbl.setFont(QFont("Microsoft YaHei UI", 10, QFont.Bold))
        head.addWidget(self.tag_lbl)
        self.title_lbl = QLabel("积分额度")
        self.title_lbl.setFont(QFont("Microsoft YaHei UI", 18, QFont.Bold))
        head.addWidget(self.title_lbl)
        self.hint_lbl = QLabel("?")
        self.hint_lbl.setFont(QFont("Microsoft YaHei UI", 13, QFont.Bold))
        self.hint_lbl.setAlignment(Qt.AlignCenter)
        self.hint_lbl.setToolTip(
            "上限为官方公开的公测期固定额度（60,000/5h、600,000/周）；"
            "配置自动同步后显示官网控制台实时余额。实际以控制台为准。")
        head.addWidget(self.hint_lbl)
        head.addStretch(1)
        v.addLayout(head)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setStyleSheet("background:transparent; border:none;")
        host = QWidget()
        host.setStyleSheet("background:transparent;")
        self.cards_lay = QVBoxLayout(host)   # 单列: 每个积分卡片独占一行, 观感更舒展
        self.cards_lay.setContentsMargins(2, 2, 2, 2)
        self.cards_lay.setSpacing(10)
        self.scroll.setWidget(host)
        v.addWidget(self.scroll)

        # 同步设置面板 (内嵌, 取代旧二级对话框)
        self.sync_panel = SNSyncPanel()
        self.sync_panel.saved.connect(self.saved)
        self.sync_panel.cleared.connect(self.cleared)
        v.addWidget(self.sync_panel)

        self.foot_lbl = QLabel("最大额度为官方公开的公测期固定值；未配置同步时余额为本地调用记录估算，非官方实时积分，以控制台为准。")
        self.foot_lbl.setFont(QFont("Microsoft YaHei UI", 10))
        self.foot_lbl.setWordWrap(True)
        v.addWidget(self.foot_lbl)
        self._empty_tip = None

    def apply_theme(self):
        self.setStyleSheet("#sn_quota_page { background:transparent; border:none; }")
        text = qname(TEXT)
        text3 = qname(TEXT3)
        accent = SN_PURPLE_DARK if theme_state["dark"] else SN_PURPLE
        self.title_lbl.setStyleSheet(f"color:{text};")
        self.tag_lbl.setStyleSheet(
            f"color:{qname(accent)}; background:{qname(CARD)}; border-radius:6px; padding:2px 8px;")
        self.hint_lbl.setStyleSheet(
            f"color:{text3}; border:1px solid {qname(BORDER)}; border-radius:10px; "
            f"min-width:20px; max-width:20px; min-height:20px; max-height:20px;")
        self.foot_lbl.setStyleSheet(f"color:{text3};")
        for i in range(self.cards_lay.count()):
            it = self.cards_lay.itemAt(i)
            w = it.widget() if it else None
            if isinstance(w, (SNPoolCard, SNPromoCard)):
                w.apply_theme()
        self.sync_panel.apply_theme()
        if self._empty_tip is not None:
            self._empty_tip.setStyleSheet(
                f"color:{qname(TEXT3)}; font-size:11px; padding:20px 6px;")

    def render(self, s):
        """渲染传入的 load_sn_stats() 结果 (期望 pools 列表, 单列布局)."""
        lay = self.cards_lay
        while lay.count():
            it = lay.takeAt(0)
            w = it.widget()
            if w:
                w.deleteLater()
        self._empty_tip = None
        pools = s.get("pools", [])
        if not pools:
            self._empty_tip = QLabel("未检测到本地商汤/日日新模型调用记录。\n"
                                     "请先通过 WorkBuddy / DSH 调用 sensenova、deepseek 或 glm 系列模型。")
            self._empty_tip.setWordWrap(True)
            self._empty_tip.setAlignment(Qt.AlignCenter)
            lay.addWidget(self._empty_tip)
        else:
            for p in pools:
                card = SNPromoCard(p) if p.get("id") == "promo" else SNPoolCard(p)
                lay.addWidget(card)
        # 滚动区精确贴合内容高度 (单列: 各卡高之和 + 间距), 避免预留空白
        ch = 0
        n = lay.count()
        for i in range(n):
            w = lay.itemAt(i).widget() if lay.itemAt(i) else None
            if w is not None:
                ch += w.sizeHint().height()
        if n > 1:
            ch += lay.spacing() * (n - 1)
        mg = lay.contentsMargins()
        ch += mg.top() + mg.bottom()
        self.scroll.setFixedHeight(min(ch, 680))
        # 同步面板状态行 (自动同步/最后已知值/未配置/失败原因)
        self.sync_panel.set_status(s)
        self.apply_theme()


# ============================================================ 堆叠柱状图
class StackedBarChart(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.data = []
        self.setMouseTracking(True)
        self.setMinimumHeight(150)

    def set_data(self, daily, models_rank, days_limit=50):
        top = [m for m, _ in models_rank[:8]]
        self.colors = {m: MODEL_COLORS[i % len(MODEL_COLORS)] for i, m in enumerate(top)}
        days = sorted(d for d in daily if d != "unknown")[-days_limit:]
        self.data = []
        for d in days:
            parts = []
            for m in top:
                v = daily[d].get(m, {}).get("total", 0)
                if v:
                    parts.append((m, self.colors[m], v))
            self.data.append({"date": d, "parts": parts})
        self.update()

    def _geom(self):
        w, h = self.width(), self.height()
        return w, h, 42, 8, 6, 18

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h, padL, padR, padT, padB = self._geom()
        iw, ih = w - padL - padR, h - padT - padB
        if not self.data:
            p.setPen(TEXT3)
            p.drawText(self.rect(), Qt.AlignCenter, "暂无数据")
            return
        maxV = max((sum(v for _, _, v in d["parts"]) for d in self.data), default=1) or 1
        p.setFont(QFont("Consolas", 7.5))
        for k in range(4):
            y = padT + ih - ih * k / 3
            p.setPen(QPen(BORDER, 1))
            p.drawLine(int(padL), int(y), int(w - padR), int(y))
            p.setPen(TEXT3)
            v = maxV * k / 3
            label = f"{v/1e8:.1f}亿" if v >= 1e8 else (f"{v/1e4:.0f}万" if v >= 1e4 else f"{v:.0f}")
            p.drawText(QRectF(0, y - 8, padL - 6, 16), Qt.AlignRight | Qt.AlignVCenter, label)
        n = len(self.data)
        slot = iw / n
        bw = max(3.0, min(14.0, slot * 0.6))
        p.setFont(QFont("Consolas", 7))
        step = max(1, n // 12)
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
                p.drawText(QRectF(cx - 24, h - padB + 2, 48, 14),
                           Qt.AlignCenter, d["date"][5:].replace("-", "/"))

    def mouseMoveEvent(self, ev):
        if not self.data:
            return
        gp = ev.globalPosition().toPoint()
        x = ev.position().x()
        w, h, padL, padR, padT, padB = self._geom()
        iw = w - padL - padR
        slot = iw / len(self.data)
        idx = int((x - padL) / slot)
        if 0 <= idx < len(self.data):
            d = self.data[idx]
            total = sum(v for _, _, v in d["parts"])
            rows = []
            for m, color, v in sorted(d["parts"], key=lambda t: -t[2]):
                pct = v / total * 100 if total else 0
                rows.append((color, m, f"{fmt_full(v)}  ({pct:.1f}%)"))
            rows.append((None, "合计", fmt_full(total)))
            ChartTip.instance().show_tip(d["date"], rows, BLUE, gp)
        else:
            ChartTip.instance().hide_tip()

    def leaveEvent(self, ev):
        ChartTip.instance().hide_tip()


# ============================================================ 热力图
class HeatMap(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.daily = {}
        self.setMouseTracking(True)
        self.setMinimumHeight(120)
        self._cells = []

    def set_data(self, daily):
        self.daily = {d: a for d, a in daily.items() if d != "unknown"}
        self.update()

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        cell, gap = 12, 3
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
            if r <= 0:
                return 0
            if r < 0.25:
                return 1
            if r < 0.5:
                return 2
            if r < 0.75:
                return 3
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

        x = 8
        top = 24
        p.setFont(QFont("Microsoft YaHei UI", 8.5))
        for ym, dlist in sorted(months.items()):
            p.setPen(TEXT2)
            p.drawText(QRectF(x, 2, 7 * unit, 16), Qt.AlignLeft | Qt.AlignVCenter,
                       f"{int(ym[5:8])} 月")
            # 竖排月历: 列=周一~周日(自左而右), 行=第几周(自上而下)
            import datetime as _dt
            first = _dt.date(int(ym[:4]), int(ym[5:7]), 1)
            first_wd = first.weekday()          # 0=周一
            for d in dlist:
                try:
                    dd = _dt.date(int(d[:4]), int(d[5:7]), int(d[8:10]))
                except Exception:
                    continue
                day_index = dd.day - 1
                row = (first_wd + day_index) // 7      # 第几周
                col = dd.weekday()                      # 周一=0 ... 周日=6
                tot = sum(a.get("total", 0) for a in self.daily[d].values())
                cx, cy = x + col * unit, top + row * unit
                self._cells.append((cx, cy, cell, cell, d, tot))
                p.setPen(Qt.NoPen)
                p.setBrush(LV[level(tot)])
                p.drawRoundedRect(QRectF(cx, cy, cell, cell), 2.5, 2.5)
            x += 7 * unit + 14
        p.setPen(TEXT3)
        p.setFont(QFont("Microsoft YaHei UI", 8))
        p.drawText(QRectF(8, h - 15, w - 110, 13), Qt.AlignLeft | Qt.AlignVCenter,
                   "少 → 多")
        for i, c in enumerate(LV):
            p.setPen(Qt.NoPen)
            p.setBrush(c)
            p.drawRoundedRect(QRectF(w - 92 + i * (cell + 2), h - 15, cell - 2, cell - 2), 2, 2)

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


# ============================================================ 数据源: DSH desktop
def dsh_cache_path():
    """DSH desktop 的 token 用量缓存位置 (可用 DSH_HOME 环境变量覆盖)。"""
    base = os.environ.get("DSH_HOME") or os.path.expanduser("~/.dsh")
    return os.path.join(base, "storages", "usage-stats-cache.json")


def dsh_ledger_path():
    """DSH desktop 的计费账本位置 (含每轮 calls/请求次数 与 cost)。"""
    base = os.environ.get("DSH_HOME") or os.path.expanduser("~/.dsh")
    return os.path.join(base, "storages", "cost-meter", "ledger.json")


def _load_dsh_ledger():
    """读取 DSH 账本, 返回按日期归并的调用次数与花费。

    返回 {date: {"calls": int, "cost": float,
                 "models": {norm_model: calls, ...}}}。
    ledger 的 byProviderModel 键形如 'provider:model', 归一化为 'provider/model'
    以匹配 usage-stats-cache 的模型键。
    """
    p = dsh_ledger_path()
    if not os.path.exists(p):
        return {}
    try:
        with open(p, encoding="utf-8") as f:
            d = json.load(f)
    except Exception:
        return {}
    out = {}
    for date, day in d.get("days", {}).items():
        models = {}
        for mk, mb in day.get("byProviderModel", {}).items():
            models[mk.replace(":", "/")] = mb.get("calls", 0)
        out[date] = {
            "calls": day.get("calls", 0),
            "cost": day.get("cost", 0.0),
            "models": models,
        }
    return out


def load_dsh_stats():
    """聚合 DSH desktop 用量为与面板兼容的 stats 结构。

    数据源: cost-meter/ledger.json (权威, 按 日期×模型 已聚合, 无 session 重复)。
      days[date] = {input,output,cacheRead,cacheWrite,reasoning,calls,cost,
                    byProviderModel:{ 'provider:model': {input,output,cacheRead,
                    cacheWrite,reasoning,calls,cost} }, sessions:[{id,...}]}
    字段映射 (与 WB 对齐: input = 总输入 = 命中 + 未命中):
      input  <- input(cache-miss) + cacheRead(命中) + cacheWrite(新写)
      output <- output
      cached <- cacheRead          (缓存命中 token 量)
      total  <- input(总) + output
      requests <- calls            (请求/调用次数, 来自账本)
      cost     <- cost             (花费)
      cacheWrite/cached 仅保留, 命中率统一为 cached/input (与 WB 同口径)

    为什么不用 usage-stats-cache.json 做 token 源:
      该缓存按 session 存 days[date].models, 同一 (日期,模型) 会在多个 session
      中重复出现且数值不等(部分 session 是整日副本), 直接累加会把 token 与
      requests 错误放大数倍。ledger 已是干净的单次聚合, 内含同样的 token 明细,
      因此以 ledger 为唯一权威源, 同时天然补齐 requests 与 cost。
    """
    path = dsh_ledger_path()
    if not os.path.exists(path):
        return {"error": f"DSH 账本不存在: {path}", "source": "dsh"}
    try:
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
    except Exception as e:
        return {"error": f"读取 DSH 账本失败: {e}", "source": "dsh"}

    daily = {}            # date -> {model -> {requests,input,output,cached,cacheWrite,total}}
    daily_sessions = {}   # date -> 当日会话数 (去重)
    session_ids = set()   # 全局去重会话 id
    first = last = None
    total_cost = 0.0
    days = d.get("days", {})
    for date, day in days.items():
        if date == "unknown":
            continue
        if first is None or date < first:
            first = date
        if last is None or date > last:
            last = date
        dm = daily.setdefault(date, {})
        # 当日会话数 (去重, ledger sessions 为当日贡献会话列表)
        day_sids = {ss.get("id") for ss in (day.get("sessions") or [])
                    if isinstance(ss, dict) and ss.get("id")}
        session_ids |= day_sids
        daily_sessions[date] = len(day_sids)
        for model, b in day.get("byProviderModel", {}).items():
            mk = model.replace(":", "/")   # 'provider:model' -> 'provider/model'
            mi = b.get("input", 0)
            mo = b.get("output", 0)
            mcr = b.get("cacheRead", 0)
            mcw = b.get("cacheWrite", 0)
            mt = mi + mo + mcr + mcw
            if mt <= 0 and b.get("calls", 0) <= 0:
                continue
            # 统一口径: DSH 的 input 原仅指未命中缓存输入, 这里补上
            # cacheRead(命中) + cacheWrite(新写), 使其等于"总输入", 与 WB 一致。
            dm[mk] = {"requests": b.get("calls", 0),
                      "input": mi + mcr + mcw, "output": mo,
                      "cached": mcr, "cacheWrite": mcw, "total": mt}
        total_cost += day.get("cost", 0.0)

    # 今日
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
        "source": "dsh",
        "dsh": True,
        "daily": daily,
        "dailySessions": daily_sessions,
        "sessionsTotal": len(session_ids),
        "today": today_rec,
        "totalCost": round(total_cost, 2),
        "firstDay": first,
        "lastDay": last,
    }





# ============================================================ 数据源: 商汤日日新 (SenseNova)
# 实测结论: token.sensenova.cn 没有任何"查询余额/额度"的公开 API (已探测 20+
# 路径均 404, 且无 X-RateLimit-* 响应头, /v1/models 也无剩余额度字段). 余额仅在
# 网页控制台可见. 因此采用"混合: 自动统计 + 校准"方案:
#   1) 自动统计: 扫描本地 WB/DSH 调用记录, 统计近 5h 窗口内对各 SenseNova 模型的
#      调用次数 (WB 用原始 jsonl 的逐条时间戳做精确窗口; DSH 仅能拿到按日聚合,
#      用"今日"次数作近似并显式标注).
#   2) 校准: 用户在网页控制台复制真实剩余额度, 粘到面板的"额度校准"框, 保存后
#      以校准值作为权威剩余, 覆盖自动估算.
# 商汤渠道模型清单 (键用于从 WB/DSH 记录筛选候选; 2026-08-28 起计费改为积分,
# 旧的"次数/5h"套餐额度已废弃, 值仅作历史备注保留).
SN_WINDOW_HOURS = 5
SN_KNOWN_QUOTA = {
    "sensenova-6.8-flash-lite": 1500,
    "sensenova-6.7-flash-lite": 1500,
    "sensenova-u1-fast": 1500,
    "sensenova-u1.5-lite": 1500,
    "deepseek-v4-flash": 500,
    "glm-5.2": 500,
}

# 官方公测期积分池上限 (2026-08-28 新规, 双池各自独立):
# 滚动 5 小时 60,000 积分 / 滚动周 600,000 积分.
SN_POOL_WINDOW_QUOTA = 60000
SN_POOL_WEEKLY_QUOTA = 600000

# 积分手动同步文件: 用户从官网控制台「积分额度」页抄来的真实余额 (唯一可靠数据源).
# 结构: {"ts": 同步时刻epoch, "general_w": 通用池周余额, "general_5h": 通用池5h剩余,
#        "flash_w": Flash池周余额, "flash_5h": Flash池5h剩余, "promo": 活动积分总量|null}
SN_SYNC_FILE = os.path.join(scanner.PLUGIN_DATA_DIR, "sn_points_sync.json")


def load_sn_sync():
    try:
        with open(SN_SYNC_FILE, encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) and isinstance(d.get("ts"), (int, float)) else None
    except Exception:
        return None


def save_sn_sync(d):
    try:
        with open(SN_SYNC_FILE, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False)
        return True
    except Exception:
        return False


def clear_sn_sync():
    try:
        if os.path.exists(SN_SYNC_FILE):
            os.remove(SN_SYNC_FILE)
        return True
    except Exception:
        # 删除失败 (权限/沙箱回收站不可用): 覆写为空对象, load_sn_sync 视为未同步
        try:
            with open(SN_SYNC_FILE, "w", encoding="utf-8") as f:
                f.write("{}")
            return True
        except Exception:
            return False


# ---- 自动同步 (抓包控制台内部接口) ----
# 官方无积分 API, 但控制台 SPA 前端必调内部接口; 用户从浏览器 F12 复制该请求的
# cURL 粘贴进来, 工具解析后自动轮询。凭据仅存本机, 过期(401/403)后回退手动同步。
SN_AUTOSYNC_FILE = os.path.join(scanner.PLUGIN_DATA_DIR, "sn_autosync.json")
SN_AUTOSYNC_TTL = 300          # 抓取频控 (秒), 避免高频请求触发风控
_autosync_mem = {"ts": 0.0, "values": None, "error": None}   # 进程内频控缓存


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
    """把 cURL 文本拆成 token 列表.

    兼容: bash '\\' 与 cmd '^' 续行; bash 单/双引号; cmd 的 '^' 转义
    (Chrome 'Copy as cURL' 在 Windows 上把引号写成 ^", 需先剥掉 '^').
    """
    text = text.replace("\r\n", "\n")
    out, cur, quote = [], [], None
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        # 续行: bash '\\' / cmd '^' + 换行
        if c in ("\\", "^") and i + 1 < n and text[i + 1] == "\n":
            i += 2
            continue
        # cmd '^' 转义: 剥掉 '^' 本身, 让其后字符按常规处理 (含 ^" 引号)
        if c == "^":
            i += 1
            continue
        if quote is None and c in ("'", '"'):
            quote = c
            i += 1
            continue
        if quote is not None:
            # 双引号内的转义: bash \" 与 cmd "" 都表示字面引号
            if c == "\\" and quote == '"' and i + 1 < n and text[i + 1] == '"':
                cur.append('"')
                i += 2
                continue
            if c == quote:
                if quote == '"' and i + 1 < n and text[i + 1] == '"':
                    cur.append('"')
                    i += 2
                    continue
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
    """解析 cURL 命令 → {url, method, headers{}, body}; 不支持的字段忽略.

    兼容 Chrome/Edge 'Copy as cURL' (cmd 风格) 与 'Copy as cURL (bash)'。
    """
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
            # Chrome cmd 格式把 Cookie 放在 -b 参数里 → 转成 Cookie 请求头
            headers["Cookie"] = toks[i + 1]
            i += 2
            continue
        if tl in ("-d", "--data", "--data-raw", "--data-binary", "--data-ascii") \
                and i + 1 < len(toks):
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
    """按 _find_value_paths 生成的路径取值; 数字字符串转 float; 失败返回 None."""
    import re
    cur = node
    for part in re.findall(r"[^\.\[\]]+|\[\d+\]", path):
        if part.startswith("["):
            idx = int(part[1:-1])
            if not isinstance(cur, list) or idx >= len(cur):
                return None
            cur = cur[idx]
        else:
            if not isinstance(cur, dict) or part not in cur:
                return None
            cur = cur[part]
    if isinstance(cur, str):
        try:
            return float(cur)
        except ValueError:
            return cur
    return cur


def _enrich_paths(data, paths):
    """启发式补全 (商汤控制台接口): 指纹命中路径必落在 pools[i] 节点内, 节点上还有
    reset_at(官方重置时间)/grant_balance(活动返赠)/nearest_grant_* 等字段 —
    自动发现并一并记录; 无这些键的接口不受影响."""
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
        if not pfx:
            continue
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
                paths["promo_exp_bal"] = \
                    f"{node_path}.nearest_grant_expiring_balance"
    return paths


def _detect_paths_by_structure(data):
    """零指纹结构探测: 商汤接口自带 pools[].pool_type/name, 直接按结构认字段.

    返回 paths dict 或 None (不是商汤结构时)。让用户配置时无需填任何数字。
    """
    pools = data.get("pools") if isinstance(data, dict) else None
    if not isinstance(pools, list):
        return None
    paths = {}
    for i, nd in enumerate(pools):
        if not isinstance(nd, dict):
            continue
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
    """urllib 执行请求, 返回 (http_status, parsed_json_or_None, err_str_or_None).

    系统代理指向的本地端口无进程监听时报 WinError 10061 (连接被拒绝),
    此时自动绕过系统代理直连重试一次 — 商汤平台国内可直连.
    """
    import urllib.request, urllib.error

    def _do(opener):
        r = urllib.request.Request(req["url"], method=req["method"])
        for k, v in req.get("headers", {}).items():
            if k.lower() in ("content-length", "host", "accept-encoding"):
                continue
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
        if "10061" in reason:   # 本机代理端口拒绝连接 (代理软件没开)
            try:
                direct = urllib.request.build_opener(
                    urllib.request.ProxyHandler({}))
                status, raw = _do(direct)
            except urllib.error.HTTPError as e2:
                return e2.code, None, f"HTTP {e2.code}"
            except Exception as e2:
                return 0, None, f"{str(e2)[:60]} (绕过系统代理直连仍失败)"
        else:
            return 0, None, str(e)[:80]
    except Exception as e:
        return 0, None, str(e)[:80]
    try:
        return status, json.loads(raw), None
    except Exception:
        return status, None, "响应不是 JSON"


def sn_autosync_fetch(force=False):
    """调用抓包接口拿积分余额; 返回 {general_w, general_5h, flash_w, flash_5h, promo} 或 None.

    带进程内频控 (SN_AUTOSYNC_TTL); 失败把错误写入 _autosync_mem['error'] 供 UI 提示,
    并回退让调用方使用手动同步。
    """
    cfg = load_sn_autosync()
    if not cfg:
        return None
    now = time.time()
    if not force and now - _autosync_mem["ts"] < SN_AUTOSYNC_TTL \
            and _autosync_mem["values"] is not None:
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
        _autosync_mem.update(ts=now, values=None, error="接口响应结构变化, 请重新配置")
        return None
    promo_p = cfg.get("promo_path")
    if promo_p:
        pv = _get_path(data, promo_p)
        if isinstance(pv, (int, float)) and not isinstance(pv, bool):
            values["promo"] = float(pv)
    _autosync_mem.update(ts=now, values=values, error=None)
    cfg["last_ok_ts"] = now
    cfg["last_values"] = values
    save_sn_autosync(cfg)
    return values


# SN 事件缓存: 每个 WB jsonl 文件的 SN 相关调用事件 (epoch, model) 列表,
# 按文件 size+mtime 失效. 避免每次刷新全量解析所有 jsonl (商汤页加载慢的根因).
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
    """抽取全部 WB jsonl 中 SN 渠道模型的调用事件 (带磁盘缓存).

    返回 {path: [[epoch, model_lower], ...]}; 文件未变化时直接复用缓存,
    只有新增/变更的文件才重新解析 — 使商汤页刷新从"全量扫 jsonl"降为亚秒级.
    """
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
                        if not is_sn_model(m):
                            continue
                        t = _ts_to_epoch(e.get("ts"))
                        if t is not None:
                            events.append([t, m])
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

# (2026-08-28 起商汤改用「积分」计费, 模型友好名不再用于额度页, 故移除 SN_DISPLAY_NAME)


def is_sn_model(name):
    """判定是否为 token.sensenova.cn 渠道托管的模型.

    只统计文档列出的商汤自有/合作模型:
      - 名称中含 sensenova 的模型 (sensenova-*, sensenova/...)
      - 无服务商前缀的裸名 deepseek-v4-flash / glm-5.2 (即 token.sensenova.cn 上架版)
    不统计 aliyun/deepseek-*, deepseek-official/* 等其他服务商的同名路由
    (后者带有非 sensenova 的前缀, 必须排除).
    """
    s = (name or "").lower()
    if "sensenova" in s:
        return True
    # 仅允许"无服务商前缀"的裸名, 避免 deepseek-official/deepseek-v4-flash 误中
    return ("/" not in s) and s in ("deepseek-v4-flash", "glm-5.2")


def sn_canonical(name):
    """把 provider/model 形式的模型名归一到商汤渠道内部键 (与 SN_KNOWN_QUOTA 一致).

    归一规则:
      - 去掉服务商前缀 sensenova/ (DSH 账本以 sensenova/... 记录)
      - 特殊裸名 deepseek-v4-flash / glm-5.2 在商汤渠道以裸名登记, 不补前缀
      - 其余日日新模型统一补回 sensenova- 前缀, 使
          sensenova/u1-fast        -> sensenova-u1-fast
          sensenova/6.7-flash-lite -> sensenova-6.7-flash-lite
          sensenova/sensenova-6.7-flash-lite -> sensenova-6.7-flash-lite
          u1-fast                  -> sensenova-u1-fast
    目的: WB 裸名、DSH 带前缀名、以及 SN_KNOWN_QUOTA 声明名都归一到同一键,
          防止同一模型被拆成多行 / 额度被重复计数.
    """
    s = (name or "").lower()
    if s.startswith("sensenova/"):
        s = s[len("sensenova/"):]
    if s in ("deepseek-v4-flash", "glm-5.2"):
        return s
    if s.startswith("sensenova-"):
        return s
    # 形如 u1-fast / 6.7-flash-lite 的日日新模型, 归一为完整名
    return "sensenova-" + s


def sn_window_bounds(now=None):
    """5 小时额度窗口: 以本地时间 00:00/05:00/10:00/15:00/20:00 为边界对齐的整块窗口."""
    import datetime as _dt
    now = now if now is not None else time.time()
    dt = _dt.datetime.fromtimestamp(now)
    mins = dt.hour * 60 + dt.minute
    start_mins = (mins // (SN_WINDOW_HOURS * 60)) * SN_WINDOW_HOURS * 60
    start = _dt.datetime(dt.year, dt.month, dt.day) + _dt.timedelta(minutes=start_mins)
    end = start + _dt.timedelta(hours=SN_WINDOW_HOURS)
    return start.timestamp(), end.timestamp()


def _ts_to_epoch(ts):
    """把 WB jsonl 的 timestamp (ISO 字符串或 unix 秒/毫秒) 转成 epoch 秒; 失败返回 None."""
    import datetime as _dt
    if ts is None or ts == "":
        return None
    if isinstance(ts, (int, float)):
        v = float(ts)
        if v > 1e12:
            v /= 1000.0
        return v
    s = str(ts)
    iso = s.replace("Z", "+00:00")
    try:
        dt = _dt.datetime.fromisoformat(iso)
        if dt.tzinfo is not None:
            dt = dt.astimezone()
        return dt.timestamp()
    except Exception:
        pass
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return time.mktime(time.strptime(s[:19], fmt))
        except Exception:
            continue
    return None


# (校准方案已移除: 商汤无积分查询 API, 校准手动粘贴失去意义, 额度页改为本地估算演示)



def _load_wb_stats():
    try:
        with open(scanner.STATS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def scan_sn_window(candidates, ws, we):
    """统计候选 SN 模型在 [ws, we] 窗口内的调用次数与 token (基于事件缓存, 快).

    返回 (used, tok); used: model_lower -> 次数.
    """
    import collections
    cands = {m.lower() for m in candidates}
    used = collections.defaultdict(int)
    tin = collections.defaultdict(int)
    tou = collections.defaultdict(int)
    for events in _sn_events_all().values():
        for t, m in events:
            if m in cands and ws <= t <= we:
                used[m] += 1
    return used, {"in": tin, "out": tou}


def _fmt_reset(ts):
    """把 epoch 秒格式化为官网风格 '8月29日 05:00'."""
    import datetime as _dt
    dt = _dt.datetime.fromtimestamp(ts)
    return f"{dt.month}月{dt.day}日 {dt:%H:%M}"


def _next_weekly_reset_str():
    """滚动周额度下次重置 (演示估算: 以新规生效日 2026-08-28 00:00 为锚每 7 天滚动).

    官方为按账户滚动的周窗口, 各账户锚点不同且未公开, 此处仅作估算展示.
    """
    import datetime as _dt
    anchor = _dt.datetime(2026, 8, 28)
    now = _dt.datetime.now()
    week = _dt.timedelta(days=7)
    if now < anchor:
        nxt = anchor
    else:
        nxt = anchor + (int((now - anchor) // week) + 1) * week
    return f"{nxt.month}月{nxt.day}日 {nxt:%H:%M}"


def load_sn_stats(force=False):
    """聚合商汤积分池额度, 返回 source=='sn' 的 stats 结构 (含 pools 列表).

    官方规则 (2026-08-28 起公测期):
      - 双积分池: 通用积分(所有 Free 模型可用) + Flash-Lite 专属积分(仅 Flash-Lite 系列)
      - 每池独立上限: 滚动 5 小时 60,000 积分 / 滚动周 600,000 积分
      - Flash-Lite 消耗 1:1 返赠通用积分 → 计入「活动固定积分」, 30 天有效, 不占 5h/周额度
    无任何积分查询 API (GET /v1/models 仅返回 pricing=0), 控制台之外读不到实时余额;
    因此「已用」为本地 WB/DSH 调用次数的粗略估算 (1 次调用 ≈ 1 积分下界),
    「上限」为官方公开的固定值, 不随估算变化.
    """
    import collections
    # 1) 候选模型 (来自 WB 聚合 + DSH 账本, 并始终纳入渠道默认模型)
    wb = _load_wb_stats()
    candidates = {sn_canonical(n) for n in SN_KNOWN_QUOTA}
    if wb:
        for m in wb.get("models", {}):
            if is_sn_model(m):
                candidates.add(sn_canonical(m))
    dsh = None
    try:
        dsh = load_dsh_stats()
    except Exception:
        dsh = None
    if dsh and "error" not in dsh:
        for dm in dsh.get("daily", {}).values():
            for m in dm:
                if is_sn_model(m):
                    candidates.add(sn_canonical(m))

    # 2) 5h 窗口边界 + 事件缓存一次遍历: 窗口内计数 + 同步后计数; DSH 今日近似
    ws, we = sn_window_bounds()
    canon_used = collections.defaultdict(int)       # 当前 5h 窗口内
    canon_since = collections.defaultdict(int)      # 同步时刻之后 (任意时间)
    canon_win_since = collections.defaultdict(int)  # 同步时刻之后且仍在当前窗口内
    sync = None
    sync_src = None
    # 自动同步优先: 抓包接口实时值 (频控 5min); 失败/未配置回退手动同步文件
    auto_vals = sn_autosync_fetch(force=force)
    manual = load_sn_sync()
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
                "promo": auto_vals.get("promo") if "promo" in auto_vals
                else (manual or {}).get("promo"),
                "promo_exp_ts": auto_vals.get("promo_exp_ts"),
                "promo_exp_bal": auto_vals.get("promo_exp_bal")}
        sync_src = "auto"
    elif manual:
        sync = manual
        sync_src = "manual"
    sync_ts = sync["ts"] if sync else None
    cands_low = {c.lower() for c in candidates}
    if candidates:
        for events in _sn_events_all().values():
            for t, m in events:
                if m not in cands_low:
                    continue
                in_win = ws <= t <= we
                after = sync_ts is not None and t >= sync_ts
                if in_win:
                    canon_used[sn_canonical(m)] += 1
                    if after:
                        canon_win_since[sn_canonical(m)] += 1
                if after:
                    canon_since[sn_canonical(m)] += 1
    canon_dsh = collections.defaultdict(int)
    if dsh and "error" not in dsh:
        today = time.strftime("%Y-%m-%d")
        for m, b in dsh.get("daily", {}).get(today, {}).items():
            if is_sn_model(m):
                canon_dsh[sn_canonical(m)] += b.get("requests", 0)

    # 3) 按池聚合已用估算 (Flash-Lite 系列进专属池, 其余进通用池)
    flash_lite = {"sensenova-6.8-flash-lite", "sensenova-6.7-flash-lite"}

    def pool_of(c):
        return "flash_lite" if c in flash_lite else "general"

    acc = {"general": [0, 0], "flash_lite": [0, 0]}   # [5h已用, 周已用]
    acc_since = {"general": 0, "flash_lite": 0}       # 同步后各池调用数
    for c in candidates:
        pk = pool_of(c)
        acc[pk][0] += canon_used.get(c, 0)
        acc[pk][1] += canon_used.get(c, 0) + canon_dsh.get(c, 0)
        acc_since[pk] += canon_since.get(c, 0)

    # 3.5) 手动同步修正: 官网控制台余额为基准, 同步时刻之后用本地调用数往下扣
    # (官方无积分 API, 这是让"余额"贴近真实的唯一途径; 同步后调用 ≈1 积分/次, 下界估算)
    sync_time_str = None
    if sync:
        try:
            sync_time_str = time.strftime("%H:%M", time.localtime(sync["ts"]))
        except Exception:
            sync_time_str = None
        for pid, wkey, hkey in (("general", "general_w", "general_5h"),
                                ("flash_lite", "flash_w", "flash_5h")):
            wk = sync.get(wkey)
            if isinstance(wk, (int, float)) and wk >= 0:
                # 滚动周覆盖当前时刻 → 同步之后的调用必落在当前滚动周内
                acc[pid][1] = max(0, SN_POOL_WEEKLY_QUOTA - wk) + acc_since[pid]
            hk = sync.get(hkey)
            if isinstance(hk, (int, float)) and hk >= 0:
                if sync_ts is not None and sync_ts >= ws:
                    # 同一 5h 窗口: 同步时窗口已用 = 上限 - 官网剩余, 再加同步后窗口内调用
                    in_win_after = sum(canon_win_since.get(c, 0) for c in candidates
                                       if pool_of(c) == pid)
                    acc[pid][0] = max(0, SN_POOL_WINDOW_QUOTA - hk) + in_win_after
                # 同步发生在此前窗口 → 官网 5h 剩余已随窗口滚动失效, 保持本地估算

    # 3.6) 自动同步精确模式: 接口返回的就是官方实时值 — remaining 直接透传,
    # 不做"上限-已用"浮点往返, 也不掺本地估算 (那只是手动同步无法实时时的折中)
    exact = {}   # pid -> {"w5": 剩余, "w7": 剩余} (None 表示该字段未配置, 回退估算)
    if sync_src == "auto" and sync:
        for pid, pfx in (("general", "general"), ("flash_lite", "flash")):
            e = {}
            r5, rw = sync.get(f"{pfx}_5h"), sync.get(f"{pfx}_w")
            if isinstance(r5, (int, float)) and r5 >= 0:
                e["w5"] = r5
            if isinstance(rw, (int, float)) and rw >= 0:
                e["w7"] = rw
            if e:
                exact[pid] = e
    reset_5h_ts = None
    reset_w_ts = None
    if sync:
        for k in ("general_reset5", "flash_reset5"):
            v = sync.get(k)
            if isinstance(v, (int, float)) and v > 0:
                reset_5h_ts = v
                break
        for k in ("general_resetw", "flash_resetw"):
            v = sync.get(k)
            if isinstance(v, (int, float)) and v > 0:
                reset_w_ts = v
                break

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
            "window_reset": (_fmt_reset(reset_5h_ts)
                             if isinstance(reset_5h_ts, (int, float))
                             and reset_5h_ts > 0 else _fmt_reset(we)),
            "next_weekly_reset": (_fmt_reset(reset_w_ts)
                                  if isinstance(reset_w_ts, (int, float))
                                  and reset_w_ts > 0
                                  else _next_weekly_reset_str()),
            "synced": sync is not None,
            "sync_time": sync_time_str,
        }

    # 活动固定积分: 有同步值用官网真实值, 否则与官网一致显示 0;
    # 自动同步时附带官方到期时间与到期金额 (如 "10月4日 00:00 · 2538.7")
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
        build_pool("general", "通用积分池", "所有 Free 模型可用",
                   "purple", acc["general"]),
        build_pool("flash_lite", "Flash-Lite 专属积分池", "仅 Flash-Lite 系列模型可用",
                   "orange", acc["flash_lite"]),
        {"id": "promo", "name": "活动固定积分",
         "total_balance": promo_total, "nearest_expire": promo_expire,
         "synced": sync is not None, "sync_time": sync_time_str},
    ]
    return {
        "source": "sn",
        "window_start": ws, "window_end": we,
        "pools": pools,
        "synced": sync is not None,
        "sync_time": sync_time_str,
        "sync_src": sync_src,                      # 'auto' 抓包接口 / 'manual' 手动
        "autosync_error": _autosync_mem["error"],  # 自动同步失败原因 (供 UI 提示)
    }


# ============================================================ 刷新信号桥
class RefreshBridge(QObject):
    done = Signal(str, object)   # (发起扫描时的数据源, stats) — 防跨源渲染竞争


# ============================================================ 主窗口
class CardWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.resize(664, 880)
        # 锁死宽度: 比例条=140px(已含竖向滚动条占的14px); 固定宽使布局无法把窗口顶宽
        self.setFixedWidth(664)
        # 高度随可见内容自适应(商汤页收拢, 旧内容 880), 设上限避免极端情况溢出屏幕
        self.setMaximumHeight(1000)

        self._drag = None
        self._scanning = False
        self._pending_refresh = False   # 扫描期间切换了源 → 完成后补刷新源
        self._sn_cache = None       # 商汤 stats 内存缓存, 切页时直接渲染避免卡顿
        self.source = theme_state["source"]
        self.bridge = RefreshBridge()
        self.bridge.done.connect(self._on_scan_done)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 10, 10, 10)
        self.card = QFrame()
        self.card.setObjectName("card")
        outer.addWidget(self.card)
        lay = QVBoxLayout(self.card)
        lay.setContentsMargins(20, 12, 20, 14)
        lay.setSpacing(8)

        # ---- header
        head = QHBoxLayout()
        head.setSpacing(8)
        tbox = QVBoxLayout()
        tbox.setSpacing(1)
        self.title = QLabel("Token 审计")
        self.subtitle = QLabel("加载中…")
        tbox.addWidget(self.title)
        tbox.addWidget(self.subtitle)
        head.addLayout(tbox)
        head.addStretch(1)

        self.btn_today = self._tab_btn("今日")
        self.btn_7 = self._tab_btn("近7天")
        self.btn_30 = self._tab_btn("近30天")
        self.btn_all = self._tab_btn("全部")
        self.btn_all.setChecked(True)
        for b in (self.btn_today, self.btn_7, self.btn_30, self.btn_all):
            head.addWidget(b, 0, Qt.AlignTop)

        self.btn_refresh = QPushButton("⟳")
        self.btn_refresh.setFixedSize(32, 28)
        self.btn_refresh.setCursor(Qt.PointingHandCursor)
        self.btn_refresh.setToolTip("重新扫描会话数据")
        self.btn_refresh.clicked.connect(lambda: self.refresh(force=True))
        head.addWidget(self.btn_refresh, 0, Qt.AlignTop)

        self.btn_min = QPushButton("–")
        self.btn_min.setFixedSize(28, 28)
        self.btn_min.setCursor(Qt.PointingHandCursor)
        self.btn_min.clicked.connect(self.showMinimized)
        head.addWidget(self.btn_min, 0, Qt.AlignTop)
        self.btn_close = QPushButton("✕")
        self.btn_close.setFixedSize(28, 28)
        self.btn_close.setCursor(Qt.PointingHandCursor)
        self.btn_close.clicked.connect(self.hide)
        head.addWidget(self.btn_close, 0, Qt.AlignTop)
        lay.addLayout(head)

        # ---- 数据源切换 (顶部第二行)
        src_row = QHBoxLayout()
        src_row.setSpacing(6)
        src_lbl = QLabel("数据源")
        src_lbl.setStyleSheet(f"color:{qname(TEXT3)}; font-size:11px;")
        src_row.addWidget(src_lbl)
        self.src_wb = self._src_btn("WorkBuddy")
        self.src_dsh = self._src_btn("DSH")
        self.src_sn = self._src_btn("商汤")
        for b in (self.src_wb, self.src_dsh, self.src_sn):
            src_row.addWidget(b, 0, Qt.AlignTop)
        self.src_wb.setChecked(self.source == "wb")
        self.src_dsh.setChecked(self.source == "dsh")
        self.src_sn.setChecked(self.source == "sn")
        src_row.addStretch(1)
        lay.addLayout(src_row)

        # ---- 2x2 汇总
        grid = QGridLayout()
        grid.setSpacing(8)
        self.card_total = StatCard("合计 Token", BLUE)
        self.card_cache = StatCard("缓存命中", GREEN)
        self.card_io = StatCard("输入 / 输出", YELLOW)
        self.card_sess = StatCard("会话 / 请求", PURPLE)
        for i, c in enumerate((self.card_total, self.card_cache, self.card_io, self.card_sess)):
            grid.addWidget(c, i // 2, i % 2)

        # 今日条
        self.today_bar = QLabel("")
        self.today_bar.setWordWrap(True)
        self.today_bar.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)

        # ---- 明细表 (表头放滚动内容内, 与数据列严格同宽对齐)
        self.table_card = QFrame()
        tv = QVBoxLayout(self.table_card)
        tv.setContentsMargins(8, 4, 8, 6)
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
        self.model_area.setMinimumHeight(200)
        tv.addWidget(self.model_area)

        # ---- 图表
        self.chart_card = QFrame()
        cv = QVBoxLayout(self.chart_card)
        cv.setContentsMargins(14, 8, 8, 6)
        cv.setSpacing(2)
        cv.addWidget(CardHeader("每日用量", BLUE))
        self.chart = StackedBarChart()
        cv.addWidget(self.chart)

        self.heat_card = QFrame()
        hv = QVBoxLayout(self.heat_card)
        hv.setContentsMargins(14, 8, 12, 6)
        hv.setSpacing(2)
        hv.addWidget(CardHeader("活跃热力图", GREEN))
        self.heat = HeatMap()
        hv.addWidget(self.heat)

        # ---- 旧内容容器 (WB/DSH 源显示): 汇总卡 + 明细 + 图表 + 热力图
        self.content_old = QWidget()
        self.content_old.setObjectName("content_old")
        content_lay = QVBoxLayout(self.content_old)
        content_lay.setContentsMargins(0, 0, 0, 0)
        content_lay.setSpacing(8)
        content_lay.addLayout(grid)
        content_lay.addWidget(self.today_bar)
        content_lay.addWidget(self.table_card, 1)
        content_lay.addWidget(self.chart_card)
        content_lay.addWidget(self.heat_card)
        lay.addWidget(self.content_old)

        # ---- 商汤额度页 (SN 源显示): 完全独立, 不复用 StatCard/ModelRow/SNRow
        self.sn_page = SNQuotaPage()
        self.sn_page.saved.connect(self._on_sn_sync_saved)
        self.sn_page.cleared.connect(self._on_sn_sync_saved)
        lay.addWidget(self.sn_page)
        self.sn_page.setVisible(False)

        self.range = "all"
        self.stats = None
        self.apply_styles()

    # ---------------- 样式 (主题/玻璃切换后重刷) ----------------
    def apply_styles(self):
        # 玻璃模式: 边框用高光描边(上亮下暗)模拟玻璃面板受光; 普通模式用常规边框
        if theme_state["glass"]:
            hl = QColor(255, 255, 255, 90) if not theme_state["dark"] else QColor(255, 255, 255, 46)
            card_border = qrgba(hl)
            sub_border = qrgba(hl)
        else:
            card_border = qrgba(BORDER)
            sub_border = qrgba(BORDER)
        self.card.setStyleSheet(
            f"#card {{ background:{qrgba(BG)}; border:1px solid {card_border};"
            f" border-radius:16px; }}")
        self.title.setStyleSheet(f"color:{qname(TEXT)}; font-size:18px; font-weight:700;")
        self.subtitle.setStyleSheet(f"color:{qname(TEXT3)}; font-size:11px;")
        self.today_bar.setStyleSheet(
            f"background:{qrgba(CARD)}; border:1px solid {sub_border};"
            f" border-radius:9px; padding:6px 12px; color:{qname(TEXT2)}; font-size:11.5px;")
        for w in (self.table_card, self.chart_card, self.heat_card):
            w.setStyleSheet(
                f"background:{qrgba(CARD)}; border:1px solid {sub_border}; border-radius:12px;")
        self.btn_refresh.setStyleSheet(
            "QPushButton{ background:#3b6fe0; color:white; border:none;"
            " border-radius:8px; font-size:14px; }"
            "QPushButton:hover{ background:#2f5ec4; }"
            "QPushButton:disabled{ background:#aebfd8; }")
        ctrl = (f"QPushButton{{ background:{qrgba(TRACK)}; color:{qname(TEXT2)}; border:none;"
                f" border-radius:8px; font-size:13px; font-weight:700; }}")
        self.btn_min.setStyleSheet(ctrl +
            f"QPushButton:hover{{ background:{qrgba(HOVER)}; }}")
        if theme_state["dark"]:
            close_hover = "QPushButton:hover{ background:rgba(224,82,82,38); color:#ff7b7b; }"
        else:
            close_hover = "QPushButton:hover{ background:#fde3e3; color:#d33; }"
        self.btn_close.setStyleSheet(ctrl + close_hover)
        for b in (self.btn_today, self.btn_7, self.btn_30, self.btn_all):
            b.setStyleSheet(
                f"QPushButton{{ background:{qrgba(TRACK)}; color:{qname(TEXT2)}; border:none;"
                f" border-radius:8px; padding:6px 11px; font-size:11.5px; }}"
                f"QPushButton:checked{{ background:#3b6fe0; color:white; font-weight:600; }}"
                f"QPushButton:hover{{ color:{qname(TEXT)}; }}"
                "QPushButton:checked:hover{ color:white; }")
        for b in (self.src_wb, self.src_dsh, self.src_sn):
            b.setStyleSheet(
                f"QPushButton{{ background:{qrgba(TRACK)}; color:{qname(TEXT2)}; border:none;"
                f" border-radius:8px; padding:5px 13px; font-size:11.5px; }}"
                f"QPushButton:checked{{ background:#3b6fe0; color:white; font-weight:600; }}"
                f"QPushButton:hover{{ color:{qname(TEXT)}; }}"
                "QPushButton:checked:hover{ color:white; }")
        self.model_area.setStyleSheet("background:transparent; border:none;")
        self.model_host.setStyleSheet("background:transparent;")
        # 按钮悬浮提示
        self.btn_min.setToolTip("最小化 (悬浮球可再次唤起)")
        self.btn_close.setToolTip("隐藏窗口 (Esc) — 右键可退出")
        self.src_wb.setToolTip("WorkBuddy 会话数据 (~/.workbuddy)")
        self.src_dsh.setToolTip("DSH desktop 数据 (~/.dsh)")
        self.src_sn.setToolTip("商汤日日新积分额度 (5h/周双池 · 本地估算 + 官网同步)")
        self.sn_page.apply_theme()
        self.update()

    # ---------------- 位置 ----------------
    def place_right(self):
        """默认停靠屏幕右侧, 垂直位置以 WB/DSH 标准高度 (880) 居中为基准 —
        各页高度不同 (商汤页更矮) 时窗口顶部保持统一, 不会随高度变化上下漂移."""
        scr = (self.screen() or QApplication.primaryScreen()).availableGeometry()
        x = scr.right() - self.width() - 2
        y = scr.top() + max(8, (scr.height() - 880) // 2)   # 基准高度固定 880
        x = max(scr.left() + 2, min(x, scr.right() - self.width() - 2))
        y = max(scr.top() + 8, min(y, scr.bottom() - self.height() - 8))
        self.move(x, y)

    def showEvent(self, ev):
        super().showEvent(ev)
        self.place_right()   # 每次显示都回到右侧默认位并保证在屏幕内

    # ---------------- 主题 / 玻璃 ----------------
    def set_dark(self, dark):
        theme_state["dark"] = dark
        refresh_palette()
        self.apply_styles()
        apply_app_qss()          # 滚动条/tooltip 同步换主题
        self._update_all()
        save_settings()

    def set_glass(self, enabled):
        """液态玻璃: 纯 Qt 分层半透明实现(底板透/卡片微透/文字实)。
        不用任何系统级全窗口模糊(DWM backdrop/AccentPolicy)——它们都是矩形层,
        与自绘圆角窗口组合必然产生方框(已两次踩坑验证)。"""
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
            tip.update()      # 悬浮卡跟随主题换肤

    def _hwnd(self):
        try:
            return int(self.winId())
        except Exception:
            return 0

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

    def _src_btn(self, text):
        b = QPushButton(text)
        b.setCheckable(True)
        b.setCursor(Qt.PointingHandCursor)
        b.setFixedWidth(94)          # WorkBuddy / DSH / 商汤 等宽, 与最长标签对齐
        b.clicked.connect(lambda _=False, bb=b: self._switch_source(bb))
        return b

    def _switch_source(self, btn):
        for b in (self.src_wb, self.src_dsh, self.src_sn):
            b.setChecked(b is btn)
        if btn is self.src_dsh:
            self.source = "dsh"
        elif btn is self.src_sn:
            self.source = "sn"
        else:
            self.source = "wb"
        theme_state["source"] = self.source
        save_settings()
        self.load_initial()

    # ---------------- 刷新 (信号槽) ----------------
    def refresh(self, force=False):
        """force=True (手动点⟳): 绕过商汤接口 5min 频控, 立即拉最新积分."""
        if self._scanning:
            # 上一轮扫描未完成期间又请求刷新 (典型: 扫描中切换了数据源) —
            # 记下来, 等上一轮结束后自动补刷新, 避免新源永远拿不到数据
            self._pending_refresh = True
            return
        self._scanning = True
        self.btn_refresh.setEnabled(False)
        src = self.source   # 快照: 后台扫描期间用户可能切换源
        if src == "dsh":
            self.subtitle.setText("正在读取 DSH 用量缓存…")
        elif src == "sn":
            self.subtitle.setText("正在同步商汤积分…" if force
                                  else "正在统计商汤积分窗口…")
        else:
            self.subtitle.setText("正在扫描 WorkBuddy 会话数据…")

        def work():
            try:
                if src == "dsh":
                    s = load_dsh_stats()
                elif src == "sn":
                    s = load_sn_stats(force=force)
                else:
                    s = scanner.scan_full()
            except Exception as e:
                s = {"error": str(e)}
            self.bridge.done.emit(src, s)

        threading.Thread(target=work, daemon=True).start()

    def _on_scan_done(self, src, s):
        self._scanning = False
        self.btn_refresh.setEnabled(True)
        if isinstance(s, dict) and "error" in s:
            if src == self.source:
                self.subtitle.setText(f"加载失败: {s['error'][:60]}")
            self._kick_pending()
            return
        if src == self.source:
            self.stats = s
            self.render()
            if src == "dsh":
                self.subtitle.setText(
                    f"DSH · {s.get('firstDay','—')} ~ {s.get('lastDay','—')}"
                    f" · 累计花费 ¥{s.get('totalCost', 0):.2f}"
                    f" · 已更新 {time.strftime('%H:%M:%S')}")
            elif src == "sn":
                ws = time.strftime("%H:%M", time.localtime(s.get("window_start", 0)))
                we = time.strftime("%H:%M", time.localtime(s.get("window_end", 0)))
                if s.get("autosync_error"):
                    mode = f"自动同步失败({s['autosync_error']})"
                elif s.get("sync_src") == "auto":
                    mode = f"自动同步 {s['sync_time']}"
                elif s.get("synced"):
                    mode = f"已同步 {s['sync_time']}"
                else:
                    mode = "本地估算"
                self.subtitle.setText(
                    f"商汤 · 积分额度({mode}) · 窗口 {ws}–{we}"
                    f" · 已更新 {time.strftime('%H:%M:%S')}")
            else:
                self.subtitle.setText(
                    f"窗口 {s.get('firstDay','—')} ~ {s.get('lastDay','—')} · 真实 usage（非估算）"
                    f" · 已更新 {time.strftime('%H:%M:%S')}")
        elif src == "sn":
            # 扫描期间用户已切走: 商汤结果只入缓存不渲染, 防止跨源数据撞页
            self._sn_cache = s
        self._kick_pending()

    def _kick_pending(self):
        """扫描结束后若期间切换过源, 补一次新源刷新."""
        if self._pending_refresh and not self._scanning:
            self._pending_refresh = False
            QTimer.singleShot(0, self.refresh)

    def load_initial(self):
        if self.source == "sn":
            # 切到商汤页直接渲染缓存(或空态), 避免在主线程同步扫描 jsonl 导致卡顿;
            # 真正的刷新由下面的 QTimer 在后台线程执行。
            self.stats = self._sn_cache or {"source": "sn", "pools": []}
        elif self.source == "dsh":
            self.stats = load_dsh_stats()
        else:
            try:
                with open(scanner.STATS_FILE, "r", encoding="utf-8") as f:
                    self.stats = json.load(f)
            except Exception:
                # 保底空结构: 保证 render() 走完整分支 (恢复 880 高度/页面可见性),
                # 而不是卡在商汤页的收拢高度上
                self.stats = {"source": "wb", "daily": {}, "dailySessions": {},
                              "sessionsTotal": 0, "today": {}}
        self.render()
        QTimer.singleShot(200, self.refresh)

    # ---------------- 商汤积分同步 ----------------
    def _on_sn_sync_saved(self):
        """同步面板保存/清除后: 强制重算积分并刷新渲染.

        走 refresh(force=True) 的后台线程路径 — load_sn_stats(force) 会真实请求
        商汤接口 (可能 10~20s), 绝不能在 UI 线程同步执行, 否则窗口未响应直至崩溃.
        """
        self.refresh(force=True)

    def _filtered_daily(self):
        s = self.stats
        daily = s.get("daily", {})
        if self.range == "all":
            return daily
        if self.range == "today":
            today = time.strftime("%Y-%m-%d")
            return {d: a for d, a in daily.items() if d == today}
        import datetime
        cut = (datetime.date.today() - datetime.timedelta(days=int(self.range))).isoformat()
        return {d: a for d, a in daily.items() if d != "unknown" and d >= cut}

    def render(self):
        s = self.stats
        if not s:
            self.subtitle.setText("暂无数据，点击 ⟳ 扫描")
            return
        if self.source == "sn":
            self.render_sn(s)
            return
        # 非 SN 源: 显示旧内容容器, 隐藏商汤页, 复位汇总卡标签
        self.content_old.setVisible(True)
        self.sn_page.setVisible(False)
        self.resize(664, 880)   # 旧内容维持原定高度, 不受商汤页收拢影响
        self.card_total.set_label("合计 Token")
        self.card_cache.set_label("缓存命中")
        self.card_io.set_label("输入 / 输出")
        self.card_sess.set_label("会话 / 请求")
        daily = self._filtered_daily()
        agg = {}
        for a_map in daily.values():
            for m, a in a_map.items():
                b = agg.setdefault(m, {"requests": 0, "input": 0, "output": 0,
                                       "cached": 0, "cacheWrite": 0, "total": 0})
                for k in b:
                    b[k] += a.get(k, 0)
        tot = {"input": 0, "output": 0, "cached": 0, "cacheWrite": 0,
               "total": 0, "requests": 0}
        for a in agg.values():
            for k in tot:
                tot[k] += a.get(k, 0)

        self.card_total.set_value(fmt_full(tot["total"]))
        # 命中率统一口径: 命中 / 总输入 (DSH 的 input 已统一为"总输入", 与 WB 一致)
        rate = tot["cached"] / tot["input"] * 100 if tot["input"] else 0
        self.card_cache.set_value(fmt_full(tot["cached"]), f"命中率 {rate:.1f}%")
        self.card_io.set_value(fmt_full(tot["input"]), f"输出 {fmt(tot['output'])}")
        ds = s.get("dailySessions", {})
        n_sess = s.get("sessionsTotal", 0) if self.range == "all" \
            else sum(v for d, v in ds.items() if d in daily)
        self.card_sess.set_value(f"{n_sess:,}", f"请求 {tot['requests']:,} 次")

        td = s.get("today", {})
        trate = td.get("cached", 0) / td.get("input", 1) * 100 if td.get("input") else 0
        if s.get("dsh"):
            cost_txt = f"  ·  花费 ¥{td.get('cost', 0.0):.2f}"
        else:
            cost_txt = ""
        self.today_bar.setText(
            f"  今日 · 请求 {td.get('requests',0):,} 次  ·  输入 {fmt(td.get('input',0))}"
            f"  ·  输出 {fmt(td.get('output',0))}  ·  会话 {td.get('sessions',0)} 个"
            f"  ·  缓存命中率 {trate:.0f}%{cost_txt}")

        # 明细表: 表头在滚动内容内第一行 → 与数据列严格对齐
        while self.model_lay.count():
            item = self.model_lay.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        self.model_lay.addWidget(
            TableHeader("调用次数" if s.get("dsh") else "请求次数"))
        rows = sorted(agg.items(), key=lambda kv: -kv[1]["total"])
        max_total = rows[0][1]["total"] if rows else 1
        for i, (m, a) in enumerate(rows):
            hit = a["cached"] / a["input"] * 100 if a["input"] else 0
            row = ModelRow(m, MODEL_COLORS[i % len(MODEL_COLORS)],
                           a["total"] / max_total, a["total"],
                           a["total"] / tot["total"] * 100 if tot["total"] else 0,
                           hit, a["requests"],
                           input_tok=a.get("input", 0),
                           output_tok=a.get("output", 0),
                           cached_tok=a.get("cached", 0),
                           zebra=(i % 2 == 1))
            self.model_lay.addWidget(row)
        self.model_lay.addStretch(1)

        self.chart.set_data(daily, rows)
        self.heat.set_data(self.stats.get("daily", {}))

    # ---------------- 商汤额度页 ----------------
    def _fit_height(self):
        """按当前可见内容自适应窗口高度(只锁宽度, 不预留空白).

        先强制刷新布局, 让 sizeHint 反映最新卡片/滚动区高度, 再据此设定窗口高度,
        避免 adjustSize 在布局未结算时取到偏小的尺寸导致底部(校准卡片)被裁切.
        """
        if self.sn_page.isVisible() and self.sn_page.layout() is not None:
            self.sn_page.layout().activate()
        if self.layout() is not None:
            self.layout().activate()
        sh = self.sizeHint()
        self.resize(664, sh.height())

    def render_sn(self, s):
        # 商汤源: 完全切到专用额度页, 不复用旧 2x2 汇总卡/明细表/图表
        self.content_old.setVisible(False)
        self.sn_page.setVisible(True)

        # 专用页负责积分池卡片渲染 (数据基于本地调用记录估算)
        self.sn_page.render(s)
        # 窗口高度收拢到实际内容, 不预留空白
        self._fit_height()

    def _save_calib(self):
        # 校准方案已移除 (商汤无积分查询 API, 校准手动粘贴失去意义); 保留桩以防旧引用
        self.subtitle.setText("校准功能已移除")

    # ---------------- 拖动 / 菜单 ----------------
    def mousePressEvent(self, ev):
        if ev.button() == Qt.LeftButton and ev.position().y() < 56:
            self._drag = ev.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, ev):
        if self._drag is not None and ev.buttons() & Qt.LeftButton:
            self.move(ev.globalPosition().toPoint() - self._drag)

    def mouseReleaseEvent(self, ev):
        self._drag = None

    def keyPressEvent(self, ev):
        if ev.key() == Qt.Key_Escape:
            self.hide()

    def contextMenuEvent(self, ev):
        menu = make_menu(self)
        act_hide = menu.addAction("⌫  隐藏窗口 (Esc)")
        act_dark = menu.addAction(("◉ " if theme_state["dark"] else "○ ") + "深色模式")
        act_blur = menu.addAction(("◉ " if theme_state["glass"] else "○ ") +
                                  "液态玻璃 (半透明)")
        act_auto = menu.addAction(("◉ " if autostart_enabled() else "○ ") +
                                  "开机自启动")
        menu.addSeparator()
        act_quit = menu.addAction("✕  退出程序")
        chosen = menu.exec(ev.globalPos())
        if chosen == act_hide:
            self.hide()
        elif chosen == act_dark:
            self.set_dark(not theme_state["dark"])
        elif chosen == act_blur:
            self.set_glass(not theme_state["glass"])
        elif chosen == act_auto:
            new_state = not autostart_enabled()
            ok = set_autostart(new_state)
            self.subtitle.setText(
                ("已开启开机自启" if new_state else "已关闭开机自启")
                if ok else "自启设置失败 (权限或路径问题)")
        elif chosen == act_quit:
            os._exit(0)


# ============================================================ 开机自启
VBS_PATH = os.path.join(os.environ.get("APPDATA", ""),
                        "Microsoft", "Windows", "Start Menu", "Programs",
                        "Startup", "TokenAuditCard.vbs")
_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_RUN_NAME = "TokenAuditCard"


def _autostart_command():
    """pythonw + 脚本 的启动命令(无控制台窗口)"""
    pythonw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    if not os.path.exists(pythonw):
        pythonw = sys.executable
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
    """优先 VBS(启动文件夹, 直观可删), 写不进则回退注册表 Run 键(用户级)。"""
    if enable:
        cmd = _autostart_command()
        try:
            # VBScript 字符串内嵌引号需翻倍: "a""b" 表示 a"b
            def vbq(s):
                return '"' + s.replace('"', '""') + '"'
            content = (f'CreateObject("WScript.Shell").Run '
                       f'{vbq(cmd)}, 0, False\r\n')
            with open(VBS_PATH, "w", encoding="ascii") as f:
                f.write(content)
            return os.path.exists(VBS_PATH)
        except OSError:
            pass
        try:   # 回退: HKCU Run 键
            import winreg
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, _RUN_KEY) as k:
                winreg.SetValueEx(k, _RUN_NAME, 0, winreg.REG_SZ, cmd)
            return autostart_enabled()
        except OSError:
            return False
    else:
        removed = True
        try:
            if os.path.exists(VBS_PATH):
                os.remove(VBS_PATH)
        except OSError:
            removed = False
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY, 0,
                                winreg.KEY_SET_VALUE) as k:
                try:
                    winreg.DeleteValue(k, _RUN_NAME)
                except FileNotFoundError:
                    pass
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
    except Exception:
        pass


# ============================================================ 悬浮球
class BallWindow(QWidget):
    def __init__(self, card):
        super().__init__()
        self.card = card   # 可能为 None, 稍后由 main 注入
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.resize(54, 54)
        self.hover = False
        self._moved = False
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
            self.move(screen.right() - self.width() - 10,
                      screen.bottom() - self.height() - 10)
        self.setToolTip("Token 审计 — 单击打开面板 / 右键菜单")
        self.show()

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w = self.width()
        R = QRectF(3, 3, w - 6, w - 6)
        dark = theme_state["dark"]

        # ---- 外圈玻璃环 (半透明描边, 玻璃厚度感; 暗=浅环 / 亮=深环)
        if dark:
            ring = QColor(255, 255, 255, 55)
        else:
            ring = QColor(15, 17, 22, 55)
        p.setPen(QPen(ring, 1.4))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(R.adjusted(0.7, 0.7, -0.7, -0.7))

        # ---- 主体: 黑/白液态玻璃圆盘 (垂直渐变; 暗=黑玻璃 / 亮=白玻璃)
        grad = QLinearGradient(0, 3, 0, w - 3)
        if dark:
            c_top, c_mid, c_bot = (QColor(82, 86, 94, 232), QColor(48, 51, 58, 240),
                                   QColor(20, 22, 27, 248))
        else:
            c_top, c_mid, c_bot = (QColor(255, 255, 255, 242), QColor(238, 240, 245, 244),
                                   QColor(212, 216, 224, 248))
        if self.hover:   # 悬停微亮
            c_top = c_top.lighter(112)
            c_mid = c_mid.lighter(108)
        grad.setColorAt(0, c_top)
        grad.setColorAt(0.5, c_mid)
        grad.setColorAt(1, c_bot)
        path = QPainterPath()
        path.addEllipse(R)
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(grad))
        p.drawPath(path)

        # ---- 顶部高光弧 (液态玻璃的"光从上来"质感)
        hl = QPainterPath()
        hl.addEllipse(QRectF(R.left() + 5, R.top() + 2.5, R.width() - 10, R.height() * 0.46))
        hlgrad = QLinearGradient(0, R.top(), 0, R.top() + R.height() * 0.5)
        if dark:
            hlgrad.setColorAt(0, QColor(255, 255, 255, 120))
        else:
            hlgrad.setColorAt(0, QColor(255, 255, 255, 200))
        hlgrad.setColorAt(1, QColor(255, 255, 255, 0))
        p.setBrush(QBrush(hlgrad))
        p.drawPath(hl)

        # ---- 底部反光 (微弱的环境光回弹)
        rl = QPainterPath()
        rl.addEllipse(QRectF(R.left() + 10, R.bottom() - 13, R.width() - 20, 9))
        rlgrad = QLinearGradient(0, R.bottom() - 13, 0, R.bottom() - 4)
        rlgrad.setColorAt(0, QColor(255, 255, 255, 0))
        if dark:
            rlgrad.setColorAt(1, QColor(255, 255, 255, 40))
        else:
            rlgrad.setColorAt(1, QColor(0, 0, 0, 14))
        p.setBrush(QBrush(rlgrad))
        p.drawPath(rl)

        # ---- 中心闪电 (矢量绘制, 跟随暗/亮模式反色: 暗=白闪 / 亮=黑闪)
        cx, cy = w / 2.0, w / 2.0
        if dark:
            bolt_color = QColor(255, 255, 255, 242)
            shadow_color = QColor(0, 0, 0, 90)
        else:
            bolt_color = QColor(20, 22, 28, 240)
            shadow_color = QColor(0, 0, 0, 50)
        # 归一化闪电多边形 (0..1 方框, 中心 0.5,0.5)
        bolt = [(0.58, 0.0), (0.12, 0.55), (0.42, 0.55),
                (0.30, 1.0), (0.88, 0.40), (0.55, 0.40)]
        scale = 23.0

        def _bp():
            bp = QPainterPath()
            for i, (px, py) in enumerate(bolt):
                x = cx + (px - 0.5) * scale
                y = cy + (py - 0.5) * scale
                if i == 0:
                    bp.moveTo(x, y)
                else:
                    bp.lineTo(x, y)
            bp.closeSubpath()
            return bp

        p.setPen(Qt.NoPen)
        bp = _bp()
        # 投影
        p.setBrush(QBrush(shadow_color))
        p.save()
        p.translate(0, 1.6)
        p.drawPath(bp)
        p.restore()
        # 主体
        p.setBrush(QBrush(bolt_color))
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

    def mouseMoveEvent(self, ev):
        if ev.buttons() & Qt.LeftButton:
            self._moved = True
            self.move(ev.globalPosition().toPoint() - self._drag)

    def mouseReleaseEvent(self, ev):
        if ev.button() != Qt.LeftButton:
            return
        try:
            with open(os.path.join(scanner.PLUGIN_DATA_DIR, "ball_pos.json"), "w") as f:
                json.dump({"x": self.x(), "y": self.y()}, f)
        except Exception:
            pass
        if not self._moved:
            self._show_card()

    def _show_card(self):
        if self.card is None:
            return
        self.card.show()
        self.card.raise_()
        self.card.activateWindow()
        self.card.setWindowState((self.card.windowState() & ~Qt.WindowMinimized)
                                 | Qt.WindowActive)

    def contextMenuEvent(self, ev):
        menu = make_menu(self)
        a1 = menu.addAction("📊  打开统计面板")
        a2 = menu.addAction("⟳  立即刷新统计")
        menu.addSeparator()
        a3 = menu.addAction("✕  退出")
        chosen = menu.exec(ev.globalPos())
        if chosen == a1:
            self._show_card()
        elif chosen == a2:
            if self.card is not None:
                self.card.show()
                self.card.raise_()
                self.card.refresh()
        elif chosen == a3:
            os._exit(0)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Token 审计")
    app.setStyle("Fusion")
    load_settings()
    refresh_palette()
    apply_app_qss()
    ball = BallWindow(None)          # 悬浮球先出, 秒级可见
    card = CardWindow()              # 主窗口后台构建
    ball.card = card
    QTimer.singleShot(0, card.load_initial)   # 数据加载也延后一拍
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
