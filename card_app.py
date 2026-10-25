# -*- coding: utf-8 -*-
"""
Token 统计卡片 V9.4 - 三套右键菜单统一 + 毛玻璃/静态材质 + 精致双尺寸仪表盘

V9.4 highlights (Unified Menus & DSH Model Merge):
  - All three right-click menus (panel, floating ball / pet, tray) now share the same
    material controls: Frost, Static Background, pick / reset the frosted texture image.
  - Right-click menu emojis upgraded - the plain line-glyphs (hide-window, autostart,
    refresh, reset-texture, quit) were swapped for friendlier colour emoji.
  - DSH page merges the same model across provider prefixes (e.g. sensenova:deepseek-v4-flash
    and deepseek-official:deepseek-v4-flash now count as one "deepseek-v4-flash" row instead
    of two split rows), so a single model never shows duplicated usage split by source.

V9.3 highlights (Baked Frosted Glass):
  The frosted-glass mode uses a baked-in texture (assets/frost_bg.png - a wallpaper shipped
  with the repo, processed with a TRUE Gaussian via QGraphicsBlurEffect + mirrored padding,
  then desaturated). Users can pick their own image via the right-click menu.
  NOTE: never go back to "downscale-then-upscale" blur approximations. The bilinear upscale
  leaves periodic creases at the sample boundaries, which the eye reads as colour blocks -
  and it gets worse the higher the source resolution (adjacent samples differ more).
  Measured crease autocorrelation: 0.785 at 45px for the old 1/45 approximation, 0.085 for
  a true Gaussian. Glass and Frost stay mutually exclusive (adjacent sidebar buttons), and
  sidebar / title-bar controls re-skin themselves per material (solid chip / translucent
  highlight / hairline) so they never look like blocks pasted onto the glass.
  NOTE: Windows DWM System Backdrop (Acrylic/Mica) was thoroughly tested and REJECTED:
  on Qt self-drawn translucent windows it paints an opaque gray layer instead of blurring
  the desktop behind (works only on plain Win32 windows). Do not revisit without evidence.

V9.2 highlights (Multi-Machine Sync):
  Export this machine's full WorkBuddy + DSH usage snapshot to a JSON package, import
  it on another machine, and view every machine side by side. Imports are additive and
  never touch local data; re-importing an existing machine name overwrites that
  machine's snapshot instead of double-counting. Per-machine stats ship as two-column
  cards (rank bar on the left, share ring on the right) with a Today / All-time toggle.

核心规范:
  - 产品标识全面更名为「Token 统计」
  - 彻底去除色相色散畸变，回归纯净物理级菲涅尔镜面高光与透明晶体折射
  - 修复标准尺寸下 QSS 误用 pt 导致的「今日概况」超大字体与换行挤压缺陷
  - 顶部指标卡核心数字垂直重心上移，消除贴底压迫感，留出黄金透气间隙
  - 重构舒适大窗口 (1180×730) 字体层级体系，字重与行高开阔舒展，拒绝粗暴放大
  - 三档玻璃通透度无级调谐 + 右键多入口切换 + 每日柱状图鼠标锚点滚轮缩放与平移
  - 商汤额度页两张积分池卡**常驻**（未就绪用公测期满额占位）；按机统计双栏 + 环形占比圈
  - 「毛玻璃模式」(Frost)：静态内置磨砂底纹（assets/frost_bg.png = 内置壁纸经**真高斯**+去饱和），
    运行时零抓屏零延迟；支持自定义图片（自动做同样处理）；与液态玻璃互斥
    · ⚠️ 模糊必须用**真高斯**(_gaussian_blur)：旧的"缩到 1/45 再放大"会留下周期性折痕 = 色块
    · 纹理必须由窗口底板整块铺一次，卡片不画任何底色（否则每卡一张缩略图/出现底框）
    · 侧栏「液态玻璃 | 毛玻璃」并列等高按钮，三态切换（再点已选中的回默认）；明暗切换在最下方
    · 控件随材质换语言(material_btn_qss)：默认实底芯片 / 液态玻璃半透明高光 / 毛玻璃细线无底
    · 选中态在毛玻璃下**从底图取色**(FrostTexture.accent)：只取底图平均色的色相, 半透明填充+同色描边
    · 左栏「来源」NavButton 的选中态(填充/描边/竖条/文字)同样取底图色 → 全窗只有一个色源
    · 日期区间按钮用 range 角色(padding:3px 8px + 1px 描边), 与旧版 4px 9px 无描边的盒子逐像素等价
    · ⚠️ 回写按钮勾选态(apply_styles 同步材质按钮)必须 blockSignals, 否则会被当成"用户取消"
  - ⚠️ 属性名不要用 `metric`：QWidget 有虚函数 QPaintDevice::metric()，会与 PySide6 覆写冲突而崩
"""
import base64
import json
import os
import random
import shutil
import sys
import threading
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)
import scanner  # noqa: E402
try:
    import win_backdrop as _winbd        # 第76轮: DWM 实时毛玻璃(Acrylic)
except Exception:                        # 非 Windows / 导入失败 → 自动降级为静态底纹
    _winbd = None
import peer_store  # noqa: E402   # 2026-09-19 (第50轮): 多机数据源 导出/导入/合并


# ============================================================ 打包(exe)支持
# 2026-09-16: 本程序可打包成单文件 exe。资源解析规则：
#   · 未打包 → APP_DIR = 脚本目录（开发时与以前完全一致）
#   · 已打包 → APP_DIR = exe 所在目录；资源**优先取 exe 同级的 assets/**
#     （这样浅浅猫把 assets 放在 exe 旁边就能直接替换素材，无需重新打包），
#     找不到再回退到打包内置的那份（PyInstaller 解包目录 sys._MEIPASS）。
APP_ID = "qianqian.token-stats.1"        # Windows AppUserModelID：让任务栏图标正确归组
APP_NAME = "Token 统计"


def _app_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return BASE_DIR


APP_DIR = _app_dir()
_BUNDLE_DIR = getattr(sys, "_MEIPASS", APP_DIR)


def res(*parts):
    """资源路径：优先 exe/脚本 同级，否则回退到打包内置资源。"""
    local = os.path.join(APP_DIR, *parts)
    if os.path.exists(local):
        return local
    return os.path.join(_BUNDLE_DIR, *parts)


from PySide6.QtCore import (Qt, QRectF, QObject, Signal, QTimer, QPoint, QRect,
                            QPointF, QEvent, QSize)
from PySide6.QtGui import (QColor, QFont, QPainter, QPen, QBrush, QPainterPath,
                           QLinearGradient, QImage, QPixmap, QGuiApplication, QIcon,
                           QAction, QFontMetrics, QBitmap, QRegion)
from PySide6.QtWidgets import (QApplication, QWidget, QLabel, QVBoxLayout,
                               QHBoxLayout, QGridLayout, QFrame, QPushButton,
                               QScrollArea, QMenu, QSizePolicy, QPlainTextEdit,
                               QStackedWidget, QLineEdit, QSystemTrayIcon,
                               QFileDialog, QMessageBox, QInputDialog, QDialog,
                               QGraphicsScene, QGraphicsPixmapItem, QGraphicsBlurEffect,
                               QButtonGroup)


def app_icon():
    """exe / 任务栏 / 托盘 三处统一使用的图标（优先 .ico，回退 .png）。"""
    for name in ("app_icon.ico", "app_icon.png"):
        p = res("assets", name)
        if os.path.exists(p):
            ic = QIcon(p)
            if not ic.isNull():
                return ic
    return QIcon()

# ============================================================ 窗口尺寸与排版度量衡体系
SIZE_METRICS = {
    "default": {
        "name": "标准模式 (990×610)",
        "win_w": 990, "win_h": 610, "sidebar_w": 190,
        # 第73/74轮打磨: 字号/间距向示意图靠拢 (标签加字距、主数字更大、小指标数值加大)
        # 第75轮: 示意图是 CSS px, Qt 是 pt (1pt=1.333px) —— 之前直接把 34px 当 34pt 用, 大了 33%!
        #   正确换算: 主数字 34px→25.5pt / 标签 11px→8.3pt / 副文 11.5px→8.6pt / 小指标 15px→11.3pt
        "stat_h": 72, "stat_val_pt": 11.3, "stat_lbl_pt": 8.3, "stat_hint_pt": 8.6,
        "stat_val_y": 28,  # 重心明显上提，距底边界留出 15px+ 舒适余量
        # 第72轮: 指标区改为「方案 A 主次分层」(MetricsBand); 第74轮 128→132
        "metrics_h": 116, "metrics_val_pt": 25.5,
        "row_h": 28, "name_w": 94, "total_w": 76, "pct_w": 50, "hit_w": 40, "req_w": 48,
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
        "stat_h": 84, "stat_val_pt": 13.6, "stat_lbl_pt": 10.0, "stat_hint_pt": 10.2,
        "stat_val_y": 34,  # 大窗口下同样重心居中偏上，比例舒展
        "row_h": 34, "name_w": 118, "total_w": 88, "pct_w": 56, "hit_w": 46, "req_w": 54,
        "row_pt": 9.2, "row_head_pt": 8.8,  # 表格行高拉开，文字保持干练清秀
        # 第72轮: 指标区「方案 A 主次分层」; 反馈后 112→136; 第73轮 136→148; 第74轮 148→152
        "metrics_h": 134, "metrics_val_pt": 30,
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
    "pet_theme": "v3", "window_size": "default", "glass_transparency": "balanced",
    # 2026-09-23 (第60轮): 毛玻璃模式。★ 必须放进 theme_state —— save_settings() 落盘的就是它,
    # 放别处会一保存就丢(第58轮踩过的坑)。
    "frost": False,
    # 2026-09-25 (第63轮): 毛玻璃底纹是否用**用户自定义图**(True) 还是内置默认图(False)。
    # 同样必须进 theme_state 才能落盘。
    "frost_custom": False,
    # 2026-10-19 (第76轮): **静态背景** —— 毛玻璃模式下改用静态底纹(内置/自定义图)代替
    # DWM 实时 Acrylic。默认值 False = 默认走真·实时毛玻璃。
    "frost_static": False,
}

# 2026-10-19 (第76轮): 真毛玻璃(DWM Acrylic)是否已挂到窗口上。
#   True 时窗口背后的模糊由系统合成器完成, Qt 侧只铺极淡 tint —— 于是 _frost_fill 不再画纹理。
ACRYLIC = {"on": False}

# 第96轮: 设置页需要拿到桌宠实例(桌宠是独立顶层窗口, 主窗口没有直接引用),
# 由 main() 在创建后登记到这里。
PET_BALL = {"w": None}

# 第93轮: 主面板圆角半径 —— 与背板 Win11 系统圆角(实测约 10~11 逻辑px)对齐,
# 让"背板的圆"和"面板的圆"重合, 圆角缺口处就不再露出背板的方形材质角。
# 所有模式统一使用这个值(浅猫: 所有模式圆角一起同步)。
_PANEL_RADIUS = 10
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
    # 第94轮: 浅色毛玻璃下面板是**半透明**的(背板模糊 + 白 tint 48% + 罩层),
    # 浅灰小字(TEXT3=150,158,172, 为不透明白底 246,248,251 设计)会和背景融在一起
    # —— 浅猫截图: 顶部"WorkBuddy · …"和"合计 TOKEN"基本看不清。
    # ⇒ 浅色毛玻璃专用: 把灰字加深一档保证对比度(只影响毛玻璃, 液态玻璃/默认不动)。
    if theme_state.get("frost") and not theme_state["dark"]:
        globals().update(TEXT2=QColor(64, 72, 88), TEXT3=QColor(96, 104, 120))


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


def scrollbare_qss():
    """返回与全局一致的滚动条样式片段 (局部 setStyleSheet 会覆盖全局 QSS, 必须带上)。"""
    handle = "#d3d9e2" if not theme_state["dark"] else "#3d434c"
    handle_h = "#b8c2d0" if not theme_state["dark"] else "#4d545f"
    return (f"QScrollBar:vertical {{ background:transparent; width:6px; margin:2px 1px; }}"
            f"QScrollBar::handle:vertical {{ background:{handle}; border-radius:3px; min-height:24px; }}"
            f"QScrollBar::handle:vertical:hover {{ background:{handle_h}; }}"
            f"QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height:0; }}"
            f"QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background:transparent; }}"
            f"QScrollBar:horizontal {{ background:transparent; height:6px; margin:1px 2px; }}"
            f"QScrollBar::handle:horizontal {{ background:{handle}; border-radius:3px; min-width:24px; }}"
            f"QScrollBar::handle:horizontal:hover {{ background:{handle_h}; }}"
            f"QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width:0; }}"
            f"QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{ background:transparent; }}")


def style_scroll_area(area):
    """给 QScrollArea 套「透明底 + 主题化滚动条」。"""
    area.setStyleSheet(
        "QScrollArea{ background:transparent; border:none; }"
        "QScrollArea > QWidget > QWidget{ background:transparent; }" + scrollbare_qss())


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


def fmt_compact(n):
    """紧凑计数 (2026-10-17 第72轮): 486.2M / 1.29B / 456.9K —— 浅猫: "token 用 M 来计数, 解决了数字过长问题"。

    与 `fmt` 的区别: `fmt` 走中文单位(亿/万), 适合概览;`fmt_compact` 走 K/M/B, 位数短且**列宽稳定**,
    适合明细表这种需要右对齐成列的场景。
    """
    n = int(n)
    if n >= 1e9: return f"{n/1e9:.2f}B"
    if n >= 1e6: return f"{n/1e6:.1f}M"
    if n >= 1e3: return f"{n/1e3:.1f}K"
    return f"{n:,}"


# ============================================================ 纯净 iOS 27 液态玻璃光学底板
# ============================================================ 毛玻璃材质 (Frost, 2026-09-23 第60轮)
# 浅猫: "再增加一个毛玻璃的主题模式, 主要认真还原图片里毛玻璃效果的质感"
#        要点是"淡化卡片存在感, 改成用细线分割"。
def frost_rule_color(dark):
    """毛玻璃下「细线分割」用的线色 —— 极淡, 只是若有若无的分区暗示(不是卡片描边)。"""
    return QColor(255, 255, 255, 16) if dark else QColor(28, 38, 58, 20)


def paint_frost_card(p, rect, radius, dark):
    """毛玻璃下的「卡片框」(2026-10-19 第73轮)。

    浅猫: "毛玻璃模式我之前把底下几个卡片的框给去除了, 现在我想要加回来"。
    只补 **1px 圆角细描边** —— 卡片底(淡罩层)由 `paint_frost_flat()` 负责, 这里不重复铺底,
    这样"有框"但依然通透, 不会退化成普通模式的实体卡片。
    """
    path = QPainterPath()
    path.addRoundedRect(rect, radius, radius)
    # 淡底 (第74轮反馈: 之前只有框, 底"基本等同于无") —— 让卡片从底板上浮出来一点,
    # 但仍是"通透的一层", 不是普通模式那种实底卡片。
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(255, 255, 255, 24) if dark else QColor(255, 255, 255, 105))
    p.drawPath(path)
    p.setBrush(Qt.NoBrush)
    edge = QColor(255, 255, 255, 40) if dark else QColor(28, 38, 58, 48)
    p.setPen(QPen(edge, 1.0))
    p.drawPath(path)



# ============================================================ 毛玻璃材质 (Frost, 2026-09-25 第63轮重做)
# 浅猫: "不要实时抓屏了, 直接在当前对话页面抓一张内置进去, 效果挺好; 再支持自定义图片"
#
# 方案: **静态内置纹理**(首次启动时抓一次当前屏幕 → 强高斯模糊 → 压暗 → 存 PNG)。
#   · 彻底摆脱抓屏: 零延迟、拖拽完全跟手、不吃 CPU;
#   · 观感仍是"真模糊"—— 因为纹理本身就是真高斯模糊出来的;
#   · 用户可自选任意图片作底(自动做同样的模糊+压暗, 保证文字可读)。
#
# ⚠️ 为什么不走系统级 DWM Acrylic: 实测在 Qt 自绘透明窗口上, DWMWA_SYSTEMBACKDROP_TYPE
#    (Acrylic/Mica/MicaAlt) 只会画一层**不透明灰**把背景盖死(红蓝对照实验红蓝差 +196 → +6),
#    纯 Win32 窗口则正常 —— 属 Qt 窗口合成路径与 DWM 材质不兼容, 无参数可解。详见 协作进度.md 第63轮。
FROST_TEX_DIR = os.path.join(APP_DIR, "assets")
FROST_TEX_DEFAULT = os.path.join(FROST_TEX_DIR, "frost_bg.png")
FROST_TEX_USER = os.path.join(FROST_TEX_DIR, "frost_bg_user.png")

# 合成参数 (2026-09-25 定稿): 纹理存的是**中性模糊图**, 明暗合成在绘制时完成。
#   · 深色 = 纹理 + 压暗罩(alpha 越大越暗);
#   · 浅色 = **白底 + 纹理低透明度叠加** —— 直接在白底上盖白罩会把纹理透成"灰斑"显脏(实测), 
#            改用降低纹理不透明度才是干净的奶白磨砂。
FROST_TINT_DARK = 168        # 深色: 压暗罩 alpha
FROST_TEX_LIGHT_OP = 0.30    # 浅色: 纹理叠加不透明度 (越小白越干净)
FROST_BASE_LIGHT = (252, 253, 255)   # 浅色底
CARD_TINT_ALPHA = 0.85       # 卡片相对底板的"更实"系数 (文字多, 需要更干净的底)

# 2026-09-25 (第64轮): 模糊改为**真高斯**(QGraphicsBlurEffect), 见 _gaussian_blur。
#   浅猫实测反馈: "用高分辨率做底图, 色块感就会比较强" —— 根因是旧的"缩到 1/45 再放大 45 倍"
#   近似: 双线性放大会在采样边界留下**周期性折痕**(实测自相关在 45px 处 0.80, 而真高斯无长周期峰),
#   源图分辨率越高、各采样点颜色差越大, 折痕越明显 → 看上去就是一块一块的色块。
FROST_WORK_SIDE = 1400       # 纹理工作分辨率(长边): 与窗口显示尺寸同量级即可
FROST_BLUR_RATIO = 0.021     # 高斯半径 = 工作长边 × 该比例 (1400 → ≈29px)


def _gaussian_blur(src, radius):
    """真高斯模糊 (QGraphicsBlurEffect), 返回同尺寸 QImage。

    ⭐ 2026-09-25 (第64轮) 为什么换掉旧的"级联降采样→放大"近似:
      旧做法把图缩到 **1/45**(1400px → 31px) 再放大 45 倍。缩小时的确是面积平均(模糊),
      但**放大是双线性插值**: 每个采样点变成一块 ~45px 的线性平面, 采样边界上是折痕
      (一阶导连续、二阶导跳变) —— 实测 |g''| 自相关在 **45px 处 0.80**, 肉眼看就是
      "一块一块"的色块。源图分辨率越高、相邻采样点色差越大, 折痕越显眼 → 浅猫说的
      "高分辨率底图色块感更强"正是这个。
      真高斯在同一尺度上做卷积, 没有任何重采样折痕(自相关无长周期峰), 且半径可直接按
      工作分辨率给定 —— 想糊多狠就糊多狠, 不再受"放大倍数"限制。

    边缘: 先在四周用**镜像**铺出 2r+10 的 padding 再模糊, 最后裁回中心 —— 否则模糊会
    把画面边缘"吃"进去, 表现为一圈暗边。
    """
    r = float(radius)
    if r <= 0:
        return src
    w, h = src.width(), src.height()
    if w <= 1 or h <= 1:
        return src
    # padding 取 3r: Qt 的模糊核支撑比标称半径更宽(实测 2r 时最外圈仍偏暗 ~3%),
    # 裁回中心后必须完全落在"被镜像铺满"的区域里。
    pad = int(r * 3 + 12)
    canvas = QImage(w + 2 * pad, h + 2 * pad, QImage.Format_ARGB32)
    canvas.fill(QColor(0, 0, 0, 0))     # 防御: QImage 不清零, 先铺透明再画
    p = QPainter(canvas)
    p.setRenderHint(QPainter.SmoothPixmapTransform)

    def _mirror(x, y, fx, fy):
        """把原图(可按需镜像)画到 (x,y) 起、尺寸仍为 w×h 的矩形里。"""
        p.save()
        p.translate(x + (w if fx else 0), y + (h if fy else 0))
        p.scale(-1 if fx else 1, -1 if fy else 1)
        p.drawImage(0, 0, src)
        p.restore()

    # ⚠️ 8 张镜像图必须**逐张给出偏移**: 边条只翻一个轴, 角块翻两个轴。
    #    (第64轮实测踩坑: 用 "pad-w/pad+w 与 pad-h/pad+h" 配对循环时, 左右边条的 y
    #     被错写成 pad±h → 画到了画面外, 四角与上下边留下透明洞, 模糊后就是一圈暗边。)
    _l, _m, _r = pad - w, pad, pad + w
    _t, _c, _b = pad - h, pad, pad + h
    for (x, y, fx, fy) in ((_l, _c, True, False), (_r, _c, True, False),
                           (_m, _t, False, True), (_m, _b, False, True),
                           (_l, _t, True, True), (_r, _t, True, True),
                           (_l, _b, True, True), (_r, _b, True, True)):
        _mirror(x, y, fx, fy)
    p.drawImage(pad, pad, src)          # 中心原图最后画, 保证不被镜像覆盖
    p.end()

    scene = QGraphicsScene()
    item = QGraphicsPixmapItem(QPixmap.fromImage(canvas))
    eff = QGraphicsBlurEffect()
    eff.setBlurRadius(r)
    eff.setBlurHints(QGraphicsBlurEffect.QualityHint)
    item.setGraphicsEffect(eff)
    scene.addItem(item)

    out = QImage(w, h, QImage.Format_ARGB32)
    out.fill(QColor(0, 0, 0))
    pp = QPainter(out)
    scene.render(pp, QRectF(0, 0, w, h), QRectF(pad, pad, w, h))
    pp.end()
    return out


class FrostTexture:
    """毛玻璃底纹 —— 单例, 负责加载/生成/缓存那张模糊背景图。

    线程安全: 只在 UI 线程用(生成是一次性动作, 首次启动约 0.5~1s, 已用后台线程规避卡顿)。
    """
    _inst = None

    @classmethod
    def instance(cls):
        if cls._inst is None:
            cls._inst = FrostTexture()
        return cls._inst

    def __init__(self):
        self._img = None          # QImage (原尺寸纹理)
        self._scaled = {}         # {(w,h): QPixmap} 缩放缓存
        self._path = None         # 当前纹理文件路径
        self._is_tall = False     # 是否竖图(决定填充策略)
        self._failed = False
        self._accent = {}         # {(路径, 明暗): QColor} 选中态取色缓存 (第65轮)

    # ---------------------------------------------------------- 加载
    def current_path(self):
        """用户自定义图优先, 否则内置默认图。"""
        try:
            if theme_state.get("frost_custom") and os.path.exists(FROST_TEX_USER):
                return FROST_TEX_USER
        except Exception:
            pass
        return FROST_TEX_DEFAULT

    def load(self, force=False):
        """加载当前纹理(带缓存)。返回 QImage 或 None。"""
        path = self.current_path()
        if (not force) and self._img is not None and self._path == path:
            return self._img
        try:
            img = QImage(path)
            if img.isNull():
                self._img = None
                self._path = path
                return None
            self._img = img
            self._path = path
            self._scaled.clear()
            self._accent.clear()      # 换图 → 选中态取色也要跟着重算
            self._failed = False
            return img
        except Exception:
            self._failed = True
            return None

    def set_custom(self, src_path):
        """把用户选的图片处理成纹理(真高斯模糊 + 去饱和)并保存; 成功返回 True。

        处理链: 读入 → 等比缩放到工作分辨率(长边 FROST_WORK_SIDE) → 真高斯模糊 → 去饱和 → 存 PNG
        """
        try:
            img = QImage(src_path)
        except Exception:
            return False
        if img.isNull():
            return False
        try:
            processed = self._process(img)
            os.makedirs(FROST_TEX_DIR, exist_ok=True)
            if not processed.save(FROST_TEX_USER, "PNG"):
                return False
            theme_state["frost_custom"] = True
            self.load(force=True)
            return True
        except Exception:
            return False

    def clear_custom(self):
        """恢复内置默认纹理。"""
        theme_state["frost_custom"] = False
        try:
            if os.path.exists(FROST_TEX_USER):
                os.remove(FROST_TEX_USER)
        except Exception:
            pass
        self.load(force=True)

    # ---------------------------------------------------------- 选中态取色 (第65轮)
    def accent(self, dark):
        """从**当前底图**取一个"选中态"用色 —— 色相取自底图, 饱和度/明度归一化到可读区间。

        浅猫的诉求: 毛玻璃下按钮的选中态不要永远是那个品牌蓝, 而是**跟着底图的颜色走**,
        再稍微通透一点。这里取底图 8×8 缩略图的平均色, 只保留它的**色相**,
        饱和度和明度拉到一个"看得清但不刺眼"的区间(灰度底图退回品牌蓝色相)。
        换内置底图或自选图后自动跟着变(缓存按路径失效)。
        """
        key = (self.current_path(), bool(dark))
        hit = self._accent.get(key)
        if hit is not None:
            return hit
        col = QColor(59, 111, 224)          # 兜底: 品牌蓝
        try:
            img = self.load()
            if img is not None:
                sm = img.scaled(8, 8, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
                r = g = b = 0
                for y in range(sm.height()):
                    for x in range(sm.width()):
                        px = sm.pixelColor(x, y)
                        r += px.red(); g += px.green(); b += px.blue()
                n = max(1, sm.width() * sm.height())
                h, s, _v, _a = QColor(r // n, g // n, b // n).getHsv()
                if h < 0:                   # 纯灰底图没有色相 → 用品牌蓝
                    h = 210
                col = QColor.fromHsv(h, max(s, 110), 215 if dark else 158)
        except Exception:
            col = QColor(59, 111, 224)
        self._accent[key] = col
        return col

    # ---------------------------------------------------------- 图像处理
    @staticmethod
    def _process(img):
        """等比缩放 + 真高斯模糊 + 去饱和 → 返回**中性**纹理。

        ⚠️ 这里**不做明暗处理**: 压暗/提亮由绘制时的罩层完成(见 paint_frost_*),
           这样同一张纹理在深色/浅色下都合适, 也省掉逐像素循环(全走 Qt 的 C++ 路径)。
        """
        w, h = img.width(), img.height()
        if w <= 0 or h <= 0:
            return img
        # 1) 等比缩到长边 1400 (模糊图不需要原分辨率)
        long_side = max(w, h)
        if long_side > 1400:
            k = 1400.0 / long_side
            img = img.scaled(max(1, int(w * k)), max(1, int(h * k)),
                             Qt.KeepAspectRatio, Qt.SmoothTransformation)
        w, h = img.width(), img.height()
        # 2) 真高斯模糊 (第64轮替换旧的"降采样→放大"近似, 详见 _gaussian_blur)
        radius = max(10.0, max(w, h) * FROST_BLUR_RATIO)
        out = _gaussian_blur(img, radius)
        w, h = out.width(), out.height()
        # 3) 去饱和 35% (叠一层灰度自画像) —— 用 QPainter 做, 比逐像素快两个数量级
        try:
            if out.format() != QImage.Format_ARGB32:
                out = out.convertToFormat(QImage.Format_ARGB32)
            gray = out.convertToFormat(QImage.Format_Grayscale8) \
                      .convertToFormat(QImage.Format_ARGB32)
            p = QPainter(out)
            p.setOpacity(0.35)
            p.drawImage(0, 0, gray)
            p.end()
        except Exception:
            pass
        return out

    # ---------------------------------------------------------- 取用
    def pixmap_for(self, w, h, dpr=1.0):
        """返回铺满 (w,h) 的纹理 QPixmap —— 等比裁剪填充(cover), 不变形。"""
        img = self.load()
        if img is None or w <= 0 or h <= 0:
            return None
        pw, ph = max(1, int(w * dpr)), max(1, int(h * dpr))
        key = (pw, ph)
        pm = self._scaled.get(key)
        if pm is not None:
            return pm
        # cover: 按较大比例缩放, 居中裁剪
        iw, ih = img.width(), img.height()
        k = max(pw / float(iw), ph / float(ih))
        sw, sh = max(1, int(iw * k)), max(1, int(ih * k))
        scaled = img.scaled(sw, sh, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
        x = max(0, (sw - pw) // 2)
        y = max(0, (sh - ph) // 2)
        pm = QPixmap.fromImage(scaled.copy(x, y, pw, ph))
        if len(self._scaled) > 6:       # 缓存上限(尺寸切换时会有多档)
            self._scaled.clear()
        self._scaled[key] = pm
        return pm


def ensure_frost_texture():
    """首次运行时生成内置纹理: 抓一次当前屏幕 → 真高斯模糊 → 存 assets/frost_bg.png。

    仅在没有纹理文件时执行一次; 之后永远复用(这就是"不实时抓屏"的关键)。
    ⚠️ 自第64轮起仓库内置了一张无风险壁纸底纹, 本函数只在底纹文件缺失时才走(兜底)。
    """
    if os.path.exists(FROST_TEX_DEFAULT):
        return True
    try:
        scr = QGuiApplication.primaryScreen()
        if scr is None:
            return False
        pm = scr.grabWindow(0)
        if pm.isNull():
            return False
        img = pm.toImage()
        if img.isNull() or img.width() < 100:
            return False
        processed = FrostTexture._process(img)
        os.makedirs(FROST_TEX_DIR, exist_ok=True)
        return bool(processed.save(FROST_TEX_DEFAULT, "PNG"))
    except Exception:
        return False


def _frost_fill(p, widget, rect, dark, alpha):
    """把毛玻璃底铺进 rect (调用方负责 setClipPath)。

    alpha 语义: ≥1 更实(文字多的地方), <1 更透。两种明暗各自合成:
      · 深色 = 画纹理 → 压暗罩;
      · 浅色 = 铺白底 → 纹理以低不透明度叠上(避免深纹理透成灰斑)。

    第76轮: ACRYLIC["on"] 为真时**不再画纹理** —— 模糊由 DWM 在窗口背后实时合成,
    这里只铺一层极淡 tint 保证文字可读即可(画纹理反而会把实时模糊盖死)。
    """
    alpha = max(0.0, min(1.6, float(alpha)))
    if ACRYLIC["on"]:
        # 真模糊与上色由 DWM 的 Acrylic tint 负责; Qt 侧只补一层极薄雾保证文字清晰。
        p.fillRect(rect, QColor(255, 255, 255, 10 if dark else 42))
        return
    pm = None
    if widget is not None:
        try:
            pm = FrostTexture.instance().pixmap_for(
                int(rect.width()), int(rect.height()),
                widget.devicePixelRatioF() if hasattr(widget, "devicePixelRatioF") else 1.0)
        except Exception:
            pm = None
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    tr = rect.toRect()
    if pm is None:
        # 兜底: 纹理不可用(生成失败/文件损坏) → 纯色, 绝不渐变
        p.fillRect(rect, QColor(22, 25, 32) if dark else QColor(*FROST_BASE_LIGHT))
        return
    if dark:
        p.drawPixmap(tr, pm)
        tint = int(FROST_TINT_DARK * alpha)
        if tint > 0:
            p.fillRect(rect, QColor(12, 15, 20, min(255, tint)))
    else:
        p.fillRect(rect, QColor(*FROST_BASE_LIGHT))
        op = FROST_TEX_LIGHT_OP / max(0.35, alpha)   # alpha 越大 → 纹理越淡(越干净)
        p.save()
        p.setOpacity(max(0.05, min(1.0, op)))
        p.drawPixmap(tr, pm)
        p.restore()


def paint_frost_blur(p, widget, rect, radius, dark, alpha=1.0):
    """毛玻璃主材质 = 内置/自定义模糊纹理 + 细腻描边。无渐变。

    alpha: 1.0 = 主底板; 卡片传 <1 会更透一些。
    """
    path = QPainterPath()
    path.addRoundedRect(rect, radius, radius)
    p.save()
    p.setClipPath(path)
    _frost_fill(p, widget, rect, dark, alpha)
    p.restore()
    edge = int((40 if dark else 130) * alpha)
    if edge > 0:
        p.setPen(QPen(QColor(255, 255, 255, edge), 1.0))
        p.setBrush(Qt.NoBrush)
        p.drawPath(path)


def paint_frost_flat(p, rect, dark, alpha=1.0, radius=0.0, widget=None):
    """毛玻璃下的分区: **完全不画**(浅猫定稿: 连底框都不要)。

    纹理由窗口底板整块铺一次(连续、细腻); 卡片区不再叠任何色 —— 分区感只由
    极淡的 1px 细线和内容本身的排布承担, 才是参考图那种"整块玻璃"的纯平观感。
    保留函数本体是为了不破坏 paint_pod 的调用结构(以后如需恢复层次色也有挂载点)。
    """
    return


def paint_section_rule(p, w):
    """毛玻璃模式的「细线分割」: 在当前控件顶部画 1px 通栏细线。"""
    p.setPen(QPen(frost_rule_color(theme_state["dark"]), 1.0))
    p.drawLine(QPointF(0.0, 0.5), QPointF(float(w), 0.5))


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
        path.addRoundedRect(rect, _PANEL_RADIUS, _PANEL_RADIUS)   # 第93轮: 10(对齐系统圆角)

        dark = theme_state["dark"]
        glass = theme_state["glass"]

        # 毛玻璃模式: 静态底纹(内置/自定义) 或 区域实时模糊(+Qt 侧罩层, 见 _frost_fill)。
        if theme_state.get("frost"):
            paint_frost_blur(p, self, rect, _PANEL_RADIUS, dark)
            # 侧边栏分隔线: 细线 (与分区线同一套语言)
            p.setPen(QPen(frost_rule_color(dark), 1.0))
            p.drawLine(QPointF(self.sep_x, 1.0), QPointF(self.sep_x, h - 1.0))
            return

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
    """iOS 27 纯净悬浮透镜子卡片 (Frosted Glass Pod)

    update 2026-09-23 (第60轮): 新增 `rule` 开关 —— 毛玻璃模式下"卡片"不再画底板,
    只在顶部画 1px 细线做分区; 而**横向并排的一组**(四张指标卡 / 商汤两张积分池卡)
    不该各画一条线, 这些位置传 `rule=False`。
    """
    def __init__(self, radius=10, parent=None, rule=True, frame=False):
        super().__init__(parent)
        self.radius = radius
        self.rule = rule
        # 第73轮: 毛玻璃下是否画回"卡片框"(1px 细描边 + 极淡填充), 只用于底部内容卡片
        self.frame = frame

    def paintEvent(self, ev):
        paint_pod(self, self.radius, role="section", rule=self.rule, frame=self.frame)


def paint_pod(widget, radius, inset=0.5, role="section", rule=True, frame=False):
    """把「菲涅尔切角玻璃底层」画在任意 widget 上。

    2026-09-19 第52轮抽成独立函数: 原来只有 GlassPodFrame 会画这层底,
    而 GlassDialog 需要继承 QDialog (拿真模态), 无法再继承 QFrame,
    因此把绘制逻辑抽出来供两者共用 —— 保证弹窗与子卡片视觉完全同源。

    update 2026-09-23 (第60轮) 新增 `role` / `rule`:
      · `role="section"` 页面里的分区(卡片): 毛玻璃模式下**不画底**, 只在顶部画 1px 细线;
      · `role="panel"`   浮层(自绘弹窗): 浮层必须保持实体, 毛玻璃下换成同一套磨砂玻璃材质,
                         否则弹窗会"隐形"在玻璃上。
    update 2026-10-19 (第73轮) 新增 `frame`: 毛玻璃下给**底部内容卡片**画回 1px 卡片框
      (浅猫: "把底下几个卡片的框加回来"), 与"纯细线分区"区分开。
    """
    p = QPainter(widget)
    p.setRenderHint(QPainter.Antialiasing)
    w, h = widget.width(), widget.height()
    r = radius
    rect = QRectF(inset, inset, w - 2 * inset, h - 2 * inset)
    path = QPainterPath()
    path.addRoundedRect(rect, r, r)

    dark = theme_state["dark"]
    glass = theme_state["glass"]

    # 毛玻璃模式 (第63轮: 对齐参考图 —— **纯平**、无边框、无描边、无圆角卡片感)
    #   参考图特征: 深色半透明 + 系统实时模糊透出 + 区块之间只用 1px 细线分隔。
    #   所以卡片这里只铺一层**极淡的平色**(让文字有底), 不画任何边框/圆角描边。
    if theme_state.get("frost"):
        if role == "panel":
            # 浮层(弹窗)必须更实, 否则会"隐形"在玻璃上
            paint_frost_blur(p, widget, rect, min(r + 4.0, 16.0), dark)
        elif frame:
            # 第73轮: 底部内容卡片 —— 淡罩层 + **1px 卡片框**(浅猫要求加回), 不画顶部细线
            paint_frost_flat(p, rect, dark, alpha=CARD_TINT_ALPHA, widget=widget)
            paint_frost_card(p, rect, r, dark)
        elif rule:
            # 分区卡片: 纹理 + 稍厚罩层(保证文字清晰) + 一条细线
            paint_frost_flat(p, rect, dark, alpha=CARD_TINT_ALPHA, widget=widget)
            paint_section_rule(p, w)
        else:
            # 横向并排/首段: 同样铺纹理, 只是更透、不画细线
            paint_frost_flat(p, rect, dark, alpha=CARD_TINT_ALPHA * 0.7, widget=widget)
        p.end()
        return

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
    p.end()



# ============================================================ 通用按钮工厂 (2026-09-19 第51轮)
# 统一「主态 / 幽灵态 / 图标态」三档按钮样式, 让全程序按钮语言收敛为同一套:
#   · primary  — 实心蓝底, 用于每个面板的主操作 (导出 / 保存)
#   · ghost    — 透明底 + 描边, 用于次要操作 (改名 / 覆盖更新)
#   · danger   — 幽灵态, hover 转红, 用于破坏性操作 (删除)
#   · icon     — 极简无边框, 用于标题栏右上的轻量开关
BTN_GEOM = {"h": 26, "radius": 7, "pad_x": 12, "icon_pad": 10}


def make_btn(kind="ghost", text="", parent=None, compact=False):
    """按统一视觉语言创建按钮。kind ∈ {primary, ghost, danger, icon}"""
    b = QPushButton(text, parent)
    b.setCursor(Qt.PointingHandCursor)
    b.setProperty("btn_kind", kind)
    b.setFixedHeight(BTN_GEOM["icon_pad"] + 2 if compact else BTN_GEOM["h"])
    if compact:
        b.setFixedWidth(BTN_GEOM["icon_pad"] + 14)
    style_btn(b)
    return b


def style_btn(b, kind=None, pt=None, height=None):
    """(重新)套用按钮样式。切换主题/字号后需重调。pt 单位为 pt, 默认跟随度量。"""
    kind = kind or b.property("btn_kind") or "ghost"
    m = curr_metric()
    pt = pt or (m["sn_sub_pt"] + 0.4)
    r = 7 if not height else max(6, int(height / 3.6))
    pad = "3px 14px" if height is None else "2px 12px"

    if kind == "primary":
        qss = (f"QPushButton{{ background:#3b6fe0; color:#ffffff; border:none;"
               f" border-radius:{r}px; padding:{pad}; font-size:{pt}pt; font-weight:600; }}"
               f"QPushButton:hover{{ background:#2f5ec4; }}"
               f"QPushButton:pressed{{ background:#28529f; }}"
               f"QPushButton:disabled{{ background:{qrgba(TRACK)}; color:{qname(TEXT3)}; }}")
    elif kind == "danger":
        qss = (f"QPushButton{{ background:transparent; color:{qname(TEXT3)};"
               f" border:1px solid {qrgba(BORDER)}; border-radius:{r}px; padding:{pad};"
               f" font-size:{pt}pt; }}"
               f"QPushButton:hover{{ background:rgba(224,82,82,0.10); color:#e05252;"
               f" border-color:rgba(224,82,82,0.42); }}"
               f"QPushButton:pressed{{ background:rgba(224,82,82,0.18); }}")
    elif kind == "icon":
        qss = (f"QPushButton{{ background:transparent; color:{qname(TEXT3)}; border:none;"
               f" border-radius:6px; padding:0 7px; font-size:{pt}pt; }}"
               f"QPushButton:hover{{ background:{qrgba(HOVER)}; color:{qname(TEXT)}; }}")
    else:  # ghost
        qss = (f"QPushButton{{ background:transparent; color:{qname(TEXT2)};"
               f" border:1px solid {qrgba(BORDER)}; border-radius:{r}px; padding:{pad};"
               f" font-size:{pt}pt; }}"
               f"QPushButton:hover{{ background:{qrgba(HOVER)}; color:{qname(BLUE)};"
               f" border-color:rgba(59,111,224,0.38); }}"
               f"QPushButton:pressed{{ background:rgba(59,111,224,0.14); }}"
               f"QPushButton:disabled{{ color:{qname(TEXT3)}; }}")
    b.setStyleSheet(qss)
    return b


# ============================================================ 材质自适应控件样式 (2026-09-25 第64轮)
# 浅猫反馈: 侧栏几个设置按钮 + 右上角按钮在**毛玻璃 / 液态玻璃**下"很突兀"。
# 根因: 它们一直用的是"默认模式"的实底芯片(不透明 TRACK 填充、无描边), 而两种材质下
#   主板与侧栏都变成透明 —— 毛玻璃更是只剩细线分区 —— 实底芯片就成了"贴上去的色块"。
# 现按材质分三套语言(选中态永远是唯一强元素, 保证一眼看出当前状态):
#   · 默认     : 实底 TRACK 芯片(保持原观感, 不动)
#   · 液态玻璃 : 半透明高光片 + 亮描边(与主板的菲涅尔高光同源)
#   · 毛玻璃   : 近乎无底 + 极淡细线(与"细线分区"同源), 悬停只给一层薄雾
def material_btn_qss(role, dark, glass, frost, px=12):
    """按当前材质生成按钮 QSS。

    role: primary(主操作·刷新) / opt(选项·明暗) / range(时间区间) / mat(材质按钮) / icon(标题栏 – ✕)

    第65轮(浅猫): 选中态在**毛玻璃下改为"从底图取色 + 稍微通透"** —— 不再是那个恒定的品牌蓝,
    而是取底图平均色的**色相**(见 FrostTexture.accent), 以半透明填充 + 同色描边呈现,
    观感上像左栏「来源」按钮的选中态, 但更实一点(左栏是 alpha 72/30, 这里 120/155)。
    液态玻璃同理: 仍用品牌蓝, 但透明度从 0.92 降到 0.62/0.72。
    """
    if frost:
        # 第96轮(浅猫: 亮色下未选中按钮几乎看不见): 原先浅色用"白色34%"做按钮底,
        # 在同样很浅的毛玻璃面板上等于隐身。改为**深色薄雾**(比面板略暗一点点的中性色),
        # 描边同步加深; 选中态的不透明度也提高(155->190), 避免底图取色偏浅时选中态发白。
        chip_bg = "rgba(255,255,255,0.055)" if dark else "rgba(30,40,60,0.10)"
        chip_bd = "rgba(255,255,255,0.13)" if dark else "rgba(28,38,58,0.40)"
        chip_hov = "rgba(255,255,255,0.11)" if dark else "rgba(30,40,60,0.16)"
        _fa = FrostTexture.instance().accent(dark)      # ← 底图取色
        acc = qrgba(_fa, 120 if dark else 190)
        acc_hov = qrgba(_fa, 155 if dark else 210)
        acc_bd = qrgba(_fa, 175 if dark else 225)       # 描边同色, 比填充更实
        acc_strong = qrgba(_fa, 205 if dark else 230)   # 主操作(刷新): 同色相但保持分量
        acc_strong_hov = qrgba(_fa, 235 if dark else 245)
        # 第97轮: pick(网格候选) 用的"淡底 + 同色文字"两档
        acc_soft = qrgba(_fa, 72 if dark else 92)
        acc_txt = qname(_fa.lighter(128) if dark else _fa.darker(118))
    elif glass:
        chip_bg = "rgba(255,255,255,0.10)" if dark else "rgba(255,255,255,0.55)"
        chip_bd = "rgba(255,255,255,0.20)" if dark else "rgba(255,255,255,0.85)"
        chip_hov = "rgba(255,255,255,0.19)" if dark else "rgba(255,255,255,0.80)"
        acc = "rgba(59,111,224,0.62)" if dark else "rgba(59,111,224,0.72)"
        acc_hov = "rgba(47,94,196,0.74)" if dark else "rgba(47,94,196,0.84)"
        acc_bd = "rgba(255,255,255,0.34)" if dark else "rgba(255,255,255,0.95)"
        acc_strong = "rgba(59,111,224,0.84)" if dark else "rgba(59,111,224,0.88)"
        acc_strong_hov = "rgba(47,94,196,0.92)" if dark else "rgba(47,94,196,0.94)"
        acc_soft = "rgba(59,111,224,0.22)" if dark else "rgba(59,111,224,0.13)"
        acc_txt = "#9dbcff" if dark else "#2f5ec4"
    else:
        chip_bg = qrgba(TRACK)
        chip_bd = "transparent"
        chip_hov = qrgba(HOVER)
        acc = "#3b6fe0"
        acc_hov = "#2f5ec4"
        acc_bd = "transparent"
        acc_strong = "#3b6fe0"
        acc_strong_hov = "#2f5ec4"
        acc_soft = "rgba(59,111,224,0.18)" if dark else "rgba(59,111,224,0.10)"
        acc_txt = "#8fb0ff" if dark else "#2f5ec4"

    fg = qname(TEXT2)
    fg_hov = qname(TEXT)
    size = f" font-size:{px}px;" if px else ""

    if role == "primary":          # 刷新数据: 主操作保持分量(毛玻璃下同色相但更实的一档)
        return (f"QPushButton{{ background:{acc_strong}; color:#ffffff; border:1px solid {acc_bd};"
                f" border-radius:8px; font-weight:600; }}"
                f"QPushButton:hover{{ background:{acc_strong_hov}; }}"
                f"QPushButton:disabled{{ background:{chip_bg}; color:{qname(TEXT3)};"
                f" border-color:{chip_bd}; }}")

    if role == "icon":             # 标题栏 – : 只有悬停薄雾
        return (f"QPushButton{{ background:{chip_bg}; color:{fg};"
                f" border:1px solid {chip_bd}; border-radius:6px;{size} font-weight:700; }}"
                f"QPushButton:hover{{ background:{chip_hov}; color:{fg_hov}; }}")

    if role == "icon_close":       # 标题栏 ✕ : 悬停转红
        close_hov = "rgba(224,82,82,0.22)" if (glass or frost) else "#e05252"
        close_fg = "#ffffff" if not (glass or frost) else "#e05252"
        return (f"QPushButton{{ background:{chip_bg}; color:{fg};"
                f" border:1px solid {chip_bd}; border-radius:6px;{size} font-weight:700; }}"
                f"QPushButton:hover{{ background:{close_hov}; color:{close_fg}; }}")

    if role == "mat":              # 材质按钮: 选中=实心蓝(唯一强元素), 未选中=按材质分档
        return (f"QPushButton{{ background:{chip_bg}; color:{fg};"
                f" border:1px solid {chip_bd}; border-radius:8px;{size} }}"
                f"QPushButton:hover{{ background:{chip_hov}; color:{fg_hov}; }}"
                f"QPushButton:checked{{ background:{acc}; color:white; border-color:{acc_bd};"
                f" font-weight:600; }}"
                f"QPushButton:checked:hover{{ background:{acc_hov}; color:white; }}")

    if role == "seg":              # 分段控件里的按钮(第74轮): 外层一个大框, 内部无隔断
        # 未选中=完全透明(融进外框), 选中=实色药丸 —— 与示意图的 DAY/MONTH/TOTAL 一致
        return (f"QPushButton{{ background:transparent; color:{fg}; border:none;"
                f" border-radius:6px; padding:3px 10px;{size} }}"
                f"QPushButton:hover{{ background:{chip_hov}; color:{fg_hov}; }}"
                f"QPushButton:checked{{ background:{acc}; color:white; font-weight:600; }}"
                f"QPushButton:checked:hover{{ background:{acc_hov}; color:white; }}")

    if role == "pick":             # 第97轮: 网格候选按钮(桌宠主题 2x2) —— 选中=强调色描边+淡底+同色文字
        # 与示意图 .pick/.pick.on 一致: 未选中是普通描边胶囊, 选中不变成实心块,
        # 只把"描边 + 淡底 + 文字"一起换成强调色 —— 网格里多个实心块会很吵。
        return (f"QPushButton{{ background:{chip_bg}; color:{fg};"
                f" border:1px solid {chip_bd}; border-radius:8px; padding:6px 10px;{size} }}"
                f"QPushButton:hover{{ background:{chip_hov}; color:{fg_hov}; }}"
                f"QPushButton:checked{{ background:{acc_soft}; color:{acc_txt};"
                f" border-color:{acc_bd}; font-weight:600; }}"
                f"QPushButton:checked:hover{{ background:{acc_soft}; color:{acc_txt};"
                f" border-color:{acc_bd}; }}")

    if role == "range":            # 时间区间按钮: **尺寸必须与旧版一致**
        # 旧版是 padding:4px 9px + 无描边; 这里用 padding:3px 8px + 1px 描边 ——
        # 盒子尺寸完全相同(宽 文本+18 / 高 文本+8), 默认档描边透明 → 观感也一致。
        return (f"QPushButton{{ background:{chip_bg}; color:{fg};"
                f" border:1px solid {chip_bd}; border-radius:6px; padding:3px 8px;{size} }}"
                f"QPushButton:hover{{ background:{chip_hov}; color:{fg_hov}; }}"
                f"QPushButton:checked{{ background:{acc}; color:white; font-weight:600;"
                f" border-color:{acc_bd}; }}"
                f"QPushButton:checked:hover{{ background:{acc_hov}; color:white; }}")

    # role == "opt": 明暗切换(占满侧栏宽度, 不加内边距)
    return (f"QPushButton{{ background:{chip_bg}; color:{fg};"
            f" border:1px solid {chip_bd}; border-radius:6px;{size} }}"
            f"QPushButton:hover{{ background:{chip_hov}; color:{fg_hov}; }}"
            f"QPushButton:checked{{ background:{acc}; color:white; font-weight:600;"
            f" border-color:{acc_bd}; }}"
            f"QPushButton:checked:hover{{ background:{acc_hov}; color:white; }}")


def seg_box_qss(dark, glass, frost):
    """分段控件的**外框**样式 —— 第97轮从 apply_styles 里抽出来共用。

    顶栏的时间区间条和设置页里所有二选一/多选一小组都用这一套:
    圆角 9 + 1px 细描边 + 内部由 role="seg" 的按钮填充(未选中透明、选中实色药丸)。
    """
    if frost:
        bg = "rgba(255,255,255,0.045)" if dark else "rgba(255,255,255,0.34)"
        bd = "rgba(255,255,255,0.13)" if dark else "rgba(28,38,58,0.13)"
    elif glass:
        bg = "rgba(255,255,255,0.09)" if dark else "rgba(255,255,255,0.50)"
        bd = "rgba(255,255,255,0.20)" if dark else "rgba(255,255,255,0.85)"
    else:
        bg = qrgba(TRACK)
        bd = "transparent"
    return f"background:{bg}; border:1px solid {bd}; border-radius:9px;"


# ============================================================ 自绘弹窗 (2026-09-19 第51轮)
# 系统 QMessageBox / QInputDialog 的字体、圆角、阴影与卡片语言完全不搭。
# 这里统一改为自绘玻璃卡片弹窗: 与主卡片同款圆角 + 描边 + 彩点标题 + 拖拽移动。
class DlgIcon(QWidget):
    """弹窗标题前的语义徽章: 圆形淡底 + 居中符号 (替代过粗的 BarIndicator)"""

    GLYPH = {"warn": "!", "error": "!", "ok": "✓", "ask": "?", "info": "i"}

    def __init__(self, kind="info", parent=None):
        super().__init__(parent)
        self.kind = kind
        self.setFixedSize(20, 20)

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        col = {"warn": QColor("#e0813f"), "error": RED,
               "ok": GREEN, "ask": PURPLE}.get(self.kind, BLUE)
        bg = QColor(col)
        bg.setAlpha(48 if theme_state["dark"] else 34)
        p.setPen(Qt.NoPen)
        p.setBrush(bg)
        p.drawEllipse(QRectF(0.5, 0.5, 19, 19))
        p.setBrush(col)
        p.drawEllipse(QRectF(4.5, 4.5, 11, 11))
        p.setPen(QColor("#ffffff"))
        f = QFont("Microsoft YaHei UI", 7.5, QFont.Bold)
        p.setFont(f)
        p.drawText(QRectF(0, 0, 20, 20), Qt.AlignCenter, self.GLYPH.get(self.kind, "i"))


class GlassDialog(QDialog):
    """程序内统一弹窗: 模态等待 + 玻璃卡片 + 底部按钮区。

    用法:
        dlg = GlassDialog(window, "标题", "正文", icon="warn")
        dlg.add_field("机器名", text="台式机")          # 可选输入框
        if dlg.exec_ok(): ...

    ⚠ 2026-09-19 第52轮修复: 原来基类是 GlassPodFrame(QFrame) + 手写 QEventLoop
    来"假装"模态 —— 实际 IS_MODAL=False、adjustSize() 算不出尺寸(恒为 640x480
    默认值), Windows 下既不抢焦点也压不住主窗, 表现为**弹窗根本看不见**。
    现改为真正的 QDialog 基类: 玻璃底改由 paint_pod() 共用函数绘制,
    模态交给 Qt 原生 exec(), 尺寸交给布局 sizeHint —— 三处问题一并解决。
    """

    def __init__(self, parent, title, message="", icon="info", accent=None,
                 ok_text="确定", cancel_text="取消", width=380):
        super().__init__(parent, Qt.Dialog | Qt.FramelessWindowHint)
        self.setObjectName("glass_dialog")
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setModal(True)
        self.radius = 14
        self._icon_kind = icon
        self._accent = accent or {"warn": QColor("#e0813f"), "error": RED,
                                  "ok": GREEN, "ask": PURPLE}.get(icon, BLUE)
        self._parent_win = parent
        self._drag = None
        self._ok = False
        self._field = None
        self._tag = None
        self._width = width
        self._build(title, message, ok_text, cancel_text, icon)
        self.apply_theme()
        self._fit()

    # ---------- 玻璃底面 (与 GlassPodFrame 同源) ----------
    def paintEvent(self, ev):
        paint_pod(self, self.radius, inset=0.5, role="panel")

    # ---------- 构建 ----------
    def _build(self, title, message, ok_text, cancel_text, icon="info"):
        v = QVBoxLayout(self)
        v.setContentsMargins(20, 16, 20, 16)
        v.setSpacing(4)

        head = QHBoxLayout()
        head.setSpacing(8)
        self.bar_ind = DlgIcon(icon)
        head.addWidget(self.bar_ind, 0, Qt.AlignVCenter)
        self.title_lbl = QLabel(title)
        head.addWidget(self.title_lbl, 0, Qt.AlignVCenter)
        head.addStretch(1)
        self.btn_x = QPushButton("✕")
        self.btn_x.setCursor(Qt.PointingHandCursor)
        self.btn_x.setFixedSize(22, 22)
        self.btn_x.clicked.connect(lambda: self.reject())
        head.addWidget(self.btn_x, 0, Qt.AlignTop)
        v.addLayout(head)

        self.wrap = QWidget()
        self.wrap.setFixedWidth(self._width - 40)
        wv = QVBoxLayout(self.wrap)
        wv.setContentsMargins(0, 0, 0, 0)
        wv.setSpacing(11)
        self.msg_lbl = QLabel(message)
        self.msg_lbl.setWordWrap(True)
        self.msg_lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
        wv.addWidget(self.msg_lbl)
        self._wrap_lay = wv
        v.addSpacing(2)
        v.addWidget(self.wrap)
        v.addSpacing(7)

        brow = QHBoxLayout()
        brow.setSpacing(8)
        brow.addStretch(1)
        self.btn_cancel = None
        if cancel_text:
            self.btn_cancel = make_btn("ghost", cancel_text)
            self.btn_cancel.clicked.connect(lambda: self.reject())
            brow.addWidget(self.btn_cancel)
        self.btn_ok = make_btn("primary", ok_text)
        self.btn_ok.clicked.connect(lambda: self.accept())
        self.btn_ok.setDefault(True)
        brow.addWidget(self.btn_ok)
        v.addLayout(brow)
        self._brow = brow

    def add_field(self, label, text="", placeholder="", password=False):
        """在正文下方追加一个带标签的输入框 (用于「改名」等场景)。

        @⚠ 2026-09-19 第53轮修复: 本方法是在 __init__ 之后才被调用的, 而
        __init__ 里的 apply_theme() 执行时 self._field 还是 None —— 于是
        「给输入框套主题样式」那段分支**从未执行过**。实测证据: 输入框
        styleSheet 长度为 0、暗色模式下中心像素仍渲染成纯白 rgb(255,255,255),
        表现为"弹窗输入框没适配暗色"。
        现在本方法末尾补一次 apply_theme(), 保证控件建好即拿到当前主题样式。
        """
        row = QHBoxLayout()
        row.setSpacing(8)
        row.setContentsMargins(0, 0, 0, 0)
        tag = QLabel(label)
        tag.setFixedWidth(52)
        tag.setObjectName("dlg_tag")
        tag.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        row.addWidget(tag, 0, Qt.AlignVCenter)
        edit = QLineEdit()
        edit.setText(text)
        edit.setPlaceholderText(placeholder)
        edit.setFixedHeight(curr_metric()["nav_btn_h"] - 2)
        if password:
            edit.setEchoMode(QLineEdit.Password)
        edit.selectAll()
        row.addWidget(edit, 1)
        self._wrap_lay.addLayout(row)
        self._field = edit
        self._tag = tag
        self.apply_theme()      # ← 建好即套主题 (修复: 原缺失)
        self._fit()             # ← 加高后重算尺寸, 否则输入框会被裁掉
        return edit

    def field_value(self):
        return self._field.text().strip() if self._field is not None else ""

    # ---------- 交互 ----------
    def _fit(self):
        """按布局 sizeHint 定尺寸并居中到父窗。

        QDialog + FramelessWindowHint 下 adjustSize() 会走布局的 sizeHint,
        这是它相对旧 QFrame 实现的关键区别 (旧实现恒得 640x480 默认值)。

        @⚠ 2026-09-19 第53轮修正: 构造期的 sizeHint 只反映**当时已有**的内容,
        且会把 minimumHeight 锁死在该值上 —— 之后 add_field() 追加输入框时,
        若直接 adjustSize(), 高度**不会增长**(实测 113 → 113, 输入框被裁)。
        根因: 布局需要一次 show/activate 周期才会重新协商尺寸约束。
        解法: 先 `setMinimumHeight(0)` 解开旧约束, 再 activate → adjustSize。
        """
        self.setFixedWidth(self._width)
        lay = self.layout()
        # 逐层 invalidate + activate: 只顶层的 invalidate 不够 —— add_field 把输入框
        # 加在 **wrap 的内层 QHBoxLayout** 上, 必须让内层先算出自己的 sizeHint,
        # 外层才拿得到正确总高。否则实测高度会停在旧值(113/145), 输入框被裁。
        for sub in (self._wrap_lay, lay):
            try:
                sub.invalidate()
                sub.activate()
            except Exception:
                pass
        self.setMinimumHeight(0)              # 解开上一次锁定的最小高度
        self.setMinimumHeight(lay.sizeHint().height())
        self.adjustSize()
        self._center_on(self._parent_win)

    def _center_on(self, parent):
        if parent is None:
            return
        try:
            pg = parent.window().frameGeometry()
        except Exception:
            return
        g = self.frameGeometry()
        g.moveCenter(pg.center())
        self.move(g.topLeft())

    def mousePressEvent(self, ev):
        if ev.button() == Qt.LeftButton and ev.position().y() < 46:
            self._drag = ev.globalPosition().toPoint() - self.frameGeometry().topLeft()
            ev.accept()
        else:
            super().mousePressEvent(ev)

    def mouseMoveEvent(self, ev):
        if self._drag is not None and ev.buttons() & Qt.LeftButton:
            self.move(ev.globalPosition().toPoint() - self._drag)
            ev.accept()

    def mouseReleaseEvent(self, ev):
        self._drag = None

    def keyPressEvent(self, ev):
        if ev.key() == Qt.Key_Escape:
            self.reject()
        elif ev.key() in (Qt.Key_Return, Qt.Key_Enter):
            self.accept()
        else:
            super().keyPressEvent(ev)

    def exec_ok(self):
        """模态显示并等待用户响应, 返回是否确认。

        用 Qt 原生 exec(): 真正阻塞式模态栈 —— 主窗不可点、焦点必在弹窗上,
        这正是"弹窗看不见"问题的根治手段。
        """
        if self._field is not None:
            self._field.setFocus()
        return self.exec() == QDialog.Accepted

    # ---------- 外观 ----------
    def apply_theme(self):
        m = curr_metric()
        self.title_lbl.setStyleSheet(f"color:{qname(TEXT)}; font-weight:700;"
                                     f" font-size:{m['sn_title_pt'] + 0.3}pt;")
        self.msg_lbl.setStyleSheet(f"color:{qname(TEXT2)}; font-size:{m['sn_sub_pt'] + 0.3}pt;")
        self.btn_x.setStyleSheet(
            "QPushButton{ background:transparent; color:%s; border:none;"
            " border-radius:6px; font-size:11px; }"
            "QPushButton:hover{ background:rgba(224,82,82,0.14); color:#e05252; }" % qname(TEXT3))
        if self._field is not None:
            tag = getattr(self, "_tag", None) or self.findChild(QLabel, "dlg_tag")
            if tag is not None:
                tag.setStyleSheet(f"color:{qname(TEXT3)}; font-size:{m['sn_sub_pt'] + 0.3}pt;"
                                  " background:transparent;")
            # 输入框必须走全局调色板: 暗色下若是浅底, 浅色文字会完全不可读
            self._field.setStyleSheet(
                f"QLineEdit{{ background:{qrgba(TRACK)}; color:{qname(TEXT)};"
                f" border:1px solid {qrgba(BORDER)}; border-radius:7px; padding:5px 9px;"
                f" font-size:{m['opt_btn_px']}px; selection-background-color:#3b6fe0;"
                f" selection-color:#ffffff; }}"
                f"QLineEdit:hover{{ border:1px solid #6b8fe8; }}"
                f"QLineEdit:focus{{ border:1px solid #3b6fe0; background:{qrgba(HOVER)}; }}")
        style_btn(self.btn_ok, "primary")
        if self.btn_cancel is not None:
            style_btn(self.btn_cancel, "ghost")
        self.bar_ind.update()
        self.update()


def dlg_confirm(parent, title, message, ok_text="确定", icon="ask"):
    """自绘确认框 → bool"""
    return GlassDialog(parent, title, message, icon=icon, ok_text=ok_text).exec_ok()


def dlg_notify(parent, title, message, error=False):
    """自绘通知框 (单按钮, 无取消) → bool"""
    return GlassDialog(parent, title, message, icon="error" if error else "ok",
                       ok_text="知道了", cancel_text=None).exec_ok()


def dlg_prompt(parent, title, message, default="", label="", placeholder=""):
    """自绘输入框 → (text, ok)"""
    d = GlassDialog(parent, title, message, icon="ask", ok_text="保存")
    d.add_field(label or "内容", default, placeholder)
    ok = d.exec_ok()
    return (d.field_value(), ok)


# ============================================================ 头部组件
class CardHeader(QWidget):
    def __init__(self, text, accent=BLUE, parent=None, bold=True):
        super().__init__(parent)
        self.text = text
        self.accent = accent
        self.bold = bold
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
        f.setBold(bool(self.bold))     # 第97轮后半: 浅猫要求图表类卡片标题不用粗体
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


class MetricsBand(QWidget):
    """顶部指标区 —— 方案 A「主次分层」(2026-10-17 第72轮)

    浅猫: "顶部四个小卡片的设计我觉得有点普通的, 层级和呈现可以做到更优秀" →
      · 左: 合计 Token 作为**主指标** —— 超大数字 + 环比 chip + 近 30 天迷你趋势线;
      · 右: 缓存命中 / 输入·输出 / 会话·请求 三行**紧凑小指标**, 行间细线分隔;
      · 中间一条竖细线分栏。

    ⚠️ 三种材质模式(普通 / 液态玻璃 / 毛玻璃)**都不铺底**: 指标区直接落在主板上, 与示意图一致;
       配色一律走调色板(TEXT / TEXT2 / TEXT3 / BORDER / TRACK), 深浅色自动跟随,
       分栏线在毛玻璃下用 `frost_rule_color()` 与全窗细线语言统一。
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.total = 0
        self.cached = 0
        self.rate = 0.0
        self.input = 0
        self.output = 0
        self.sessions = 0
        self.requests = 0
        self.today_total = 0
        self.delta = None       # 近 7 天 vs 前 7 天 环比 (None = 数据不足)
        self.wow = 0            # 近 7 天合计
        self.spark = []         # 趋势线数据 (随所选时间区段变化)
        self.spark_days = ("", "")
        self.apply_size()

    def apply_size(self):
        m = curr_metric()
        self.setFixedHeight(m["metrics_h"])
        self.update()

    @staticmethod
    def _day_total(daily, d):
        try:
            return sum(int(x.get("total", 0) or 0) for x in daily[d].values())
        except Exception:
            return 0

    def set_stats(self, s, tot, n_sess, daily_filtered=None):
        """由 render() 喂数据 —— 环比与趋势线在这里算好, 绘制只负责画。

        第72轮反馈(浅猫): 趋势线要**跟随所选时间区段**变化 →
          · 7天 / 30天 / 全部: 直接取该区间每日总量;
          · 今日: 单日画不出趋势, 回退为最近 7 天(仅作形态参考, 不冒充"今日趋势")。
        环比仍固定取「近 7 天 vs 前 7 天」—— 与区段无关的稳定参照, 不被单日波动带跑。
        """
        self.total = int(tot.get("total", 0) or 0)
        self.cached = int(tot.get("cached", 0) or 0)
        self.input = int(tot.get("input", 0) or 0)
        self.output = int(tot.get("output", 0) or 0)
        self.requests = int(tot.get("requests", 0) or 0)
        self.sessions = int(n_sess or 0)
        self.rate = (self.cached / self.input * 100) if self.input else 0.0
        self.today_total = int((s.get("today") or {}).get("total", 0) or 0)

        full = {d: a for d, a in (s.get("daily") or {}).items() if d and d != "unknown"}
        days_all = sorted(full)

        if daily_filtered is None:
            # 没传区段 → 维持原行为: 近 30 天
            days_sp = days_all[-30:]
            src = full
        else:
            fd = {d: a for d, a in daily_filtered.items() if d and d != "unknown"}
            if len(fd) >= 2:
                days_sp = sorted(fd)
                src = fd
            else:
                # 今日(单日)画不出趋势 → 回退近 7 天作形态参考
                days_sp = days_all[-7:]
                src = full
        self.spark = [self._day_total(src, d) for d in days_sp]
        self.spark_days = (days_sp[0], days_sp[-1]) if days_sp else ("", "")

        # 环比取"近 7 天 vs 前 7 天": 比日环比稳, 不会被单日波动带跑
        recent7 = sum(self._day_total(full, d) for d in days_all[-7:])
        prev7 = sum(self._day_total(full, d) for d in days_all[-14:-7])
        self.wow = recent7
        self.delta = ((recent7 - prev7) / prev7 * 100.0) if prev7 > 0 else None
        self.update()

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        m = curr_metric()
        dark = theme_state["dark"]
        # 第74轮反馈: 左右两区之间要**留空** —— 主指标占 58%(右区相应收窄),
        # 分栏线两侧各留一段呼吸区, 不再让两区紧贴分栏线。
        hero_w = int(w * 0.58)          # 主指标栏宽
        col_x = hero_w
        HERO_PAD = 16.0                 # 主指标内容 → 分栏线 的留白
        COL_PAD = 22.0                  # 分栏线 → 右区内容 的留白

        # ---------- ① 主指标: 标签 / 超大数字 / 量级 / 环比 / 趋势线
        p.setPen(TEXT3)
        # 第73轮打磨: 标签加字距(示意图的小字标签是"疏排"的), 更像"区块名"而不是一句正文
        _lf = QFont("Microsoft YaHei UI", m["stat_lbl_pt"])
        _lf.setLetterSpacing(QFont.PercentageSpacing, 112.0)
        p.setFont(_lf)
        p.drawText(QRectF(0, 0, hero_w - HERO_PAD, 17), Qt.AlignLeft | Qt.AlignVCenter, "合计 TOKEN")

        val_y0 = 15.0
        val_h = m["metrics_val_pt"] + 16
        p.setPen(TEXT)
        p.setFont(QFont("Consolas", m["metrics_val_pt"], QFont.Bold))
        val_txt = f"{self.total:,}"
        p.drawText(QRectF(0, val_y0, hero_w - HERO_PAD, val_h),
                   Qt.AlignLeft | Qt.AlignVCenter, val_txt)
        # 量级标注: "≈ 1.42 亿" 紧跟数字之后 (示意图同款: 数字 + 量级)
        vw = p.fontMetrics().horizontalAdvance(val_txt)
        p.setPen(TEXT2)
        p.setFont(QFont("Microsoft YaHei UI", m["stat_hint_pt"] + 2.7))
        p.drawText(QRectF(vw + 10, val_y0 + val_h * 0.22, 88, val_h * 0.7),
                   Qt.AlignLeft | Qt.AlignVCenter, f"≈ {fmt(self.total)}")

        y2 = val_y0 + val_h
        tx = 0.0
        if self.delta is not None:
            up = self.delta >= 0
            chip_txt = f"{'▲' if up else '▼'} {abs(self.delta):.1f}%"
            chip_col = QColor(GREEN if up else "#e05252")
            p.setFont(QFont("Microsoft YaHei UI", m["stat_hint_pt"]))
            cw = p.fontMetrics().horizontalAdvance(chip_txt) + 12
            p.setPen(Qt.NoPen)
            cc = QColor(chip_col); cc.setAlpha(46 if dark else 40)
            p.setBrush(cc)
            p.drawRoundedRect(QRectF(0, y2 - 1, cw, 16), 4, 4)
            p.setPen(chip_col)
            p.drawText(QRectF(0, y2 - 1, cw, 16), Qt.AlignCenter, chip_txt)
            tx = cw + 8
        p.setPen(TEXT3)
        p.setFont(QFont("Microsoft YaHei UI", m["stat_hint_pt"]))
        p.drawText(QRectF(tx, y2 - 1, hero_w - HERO_PAD - tx, 16), Qt.AlignLeft | Qt.AlignVCenter,
                   f"近 7 天 {fmt_compact(self.wow)} · 今日 {fmt_compact(self.today_total)}")

        # 趋势线: 随所选时间区段变化; 加**渐变面积填充**让它"落在地上", 不再是一根孤线
        if len(self.spark) >= 2:
            mx = max(self.spark) or 1
            y0 = y2 + 21.0
            sh = max(26.0, h - y0 - 10.0)
            n = len(self.spark)
            # 第75轮: 折线右端也**往里收**(示意图同款 —— 不顶到分栏线, 右侧留白)
            spark_w = (hero_w - HERO_PAD) * 0.80
            pts = [(spark_w * i / (n - 1),
                    y0 + sh - 3.0 - (self.spark[i] / mx) * (sh - 8.0))
                   for i in range(n)]
            if n >= 3:
                area = QPainterPath()
                area.moveTo(pts[0][0], y0 + sh)
                for x, yy in pts:
                    area.lineTo(x, yy)
                area.lineTo(pts[-1][0], y0 + sh)
                area.closeSubpath()
                fade = QLinearGradient(0, y0, 0, y0 + sh)
                fade.setColorAt(0.0, QColor(BLUE.red(), BLUE.green(), BLUE.blue(), 82))
                fade.setColorAt(1.0, QColor(BLUE.red(), BLUE.green(), BLUE.blue(), 0))
                p.setPen(Qt.NoPen)
                p.setBrush(QBrush(fade))
                p.drawPath(area)
            p.setBrush(Qt.NoBrush)
            p.setPen(QPen(BLUE, 2.0, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            for i in range(len(pts) - 1):
                p.drawLine(QPointF(pts[i][0], pts[i][1]), QPointF(pts[i + 1][0], pts[i + 1][1]))

        # ---------- ② 分栏细线 (毛玻璃下与全窗细线同一套色)
        rule = frost_rule_color(dark) if theme_state.get("frost") else QColor(BORDER)
        p.setPen(QPen(rule, 1.0))
        p.drawLine(QPointF(col_x + 0.5, 4), QPointF(col_x + 0.5, h - 4))

        # ---------- ③ 右侧三行紧凑小指标
        rows = [
            (GREEN, "缓存命中", fmt_compact(self.cached), f"{self.rate:.1f}%"),
            (YELLOW, "输入 / 输出",
             f"{fmt_compact(self.input)} / {fmt_compact(self.output)}", ""),
            (PURPLE, "会话 / 请求", f"{self.sessions:,}", f"{self.requests:,} 次"),
        ]
        gap = (h - 10.0) / len(rows)
        RPAD = 8.0        # 右侧留白 (第72轮反馈: 别顶着面板边)
        for i, (acc, label, value, hint) in enumerate(rows):
            ty = 5.0 + i * gap
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(acc))
            p.drawRoundedRect(QRectF(col_x + COL_PAD, ty + gap / 2 - 1.5, 16, 3), 1.5, 1.5)
            p.setPen(TEXT2)
            p.setFont(QFont("Microsoft YaHei UI", m["stat_lbl_pt"] + 0.5))
            p.drawText(QRectF(col_x + COL_PAD + 22, ty, 120, gap),
                       Qt.AlignLeft | Qt.AlignVCenter, label)
            # 数值 + 次要提示, 一律右对齐成列
            p.setFont(QFont("Consolas", m["stat_val_pt"] + 0.4, QFont.Bold))
            vw = p.fontMetrics().horizontalAdvance(value) + 2
            hw = 0.0
            if hint:
                p.setFont(QFont("Consolas", m["stat_hint_pt"]))
                hw = p.fontMetrics().horizontalAdvance(hint) + 10
                p.setPen(TEXT3)
                p.drawText(QRectF(w - RPAD - hw, ty, hw, gap),
                           Qt.AlignRight | Qt.AlignVCenter, hint)
            p.setPen(TEXT)
            p.setFont(QFont("Consolas", m["stat_val_pt"] + 0.4, QFont.Bold))
            p.drawText(QRectF(w - RPAD - hw - vw, ty, vw, gap),
                       Qt.AlignRight | Qt.AlignVCenter, value)
            if i < len(rows) - 1:
                p.setPen(QPen(rule, 1.0))
                p.drawLine(QPointF(col_x + COL_PAD, ty + gap), QPointF(w - RPAD, ty + gap))
        p.end()


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
        # 毛玻璃模式: 明细行不铺斑马纹 (第60轮) —— 否则细线分区上会再"长出"色块
        if zebra and not theme_state.get("frost"):
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
        self.setStyleSheet(f"background:{qrgba(ZEBRA)};"
                           if (self._zebra and not theme_state.get("frost")) else "")
        ChartTip.instance().hide_tip()

    def mouseMoveEvent(self, ev):
        # 跟随鼠标持续更新悬浮框 + 50ms 节流(每像素触发会重建 tip, 鼠标扫过 CPU 飙高)
        now = time.time()
        if now - getattr(self, "_last_tip_t", 0.0) < 0.05:
            return
        self._last_tip_t = now
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
            # 第74轮: 示意图那种"从本色渐变到浅色"的胶囊 (原来方向是反的)
            grad.setColorAt(0, self.color)
            grad.setColorAt(1, self.color.lighter(135))
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
        # 第72轮反馈: Tokens 用 K/M/B 计数 —— 位数短、列宽稳定 (67,440,666 → 67.4M)
        right_text(fmt_compact(self.total), total_w, x1, TEXT, bold=True)
        right_text(f"{self.pct:.1f}%", pct_w, x1 + pct_w, TEXT2)
        right_text(f"{self.hit_rate:.0f}%", hit_w, x1 + pct_w + hit_w,
                   GREEN if self.hit_rate >= 80 else TEXT2)
        right_text(f"{self.requests:,}", req_w, x1 + pct_w + hit_w + req_w, TEXT2)


# ============================================================ 每日用量分布 (支持滚轮缩放 & 拖动平移)
# 第97轮后半6: 浅猫要"三套方案都实际做出来, 用同源卡片可切换对比"。
# 三套绘制**共用同一份数据、同一套配色、同一组几何与交互**(滚轮缩放/拖动/悬浮提示),
# 只有 paintEvent 的画法不同 —— 这样对比才是有意义的(demo 与实际完全同源)。
#   · "stack_area" 堆叠平滑面积 + 逐层渐变   (ECharts area-stack-gradient 风格)
#   · "glass_bar"  渐变立体柱 + 光影         (垂直渐变模拟顶光 + 柱顶小圆角 + 左侧高光)
#   · "dual"       双视图(上趋势面积 + 下构成带)
CHART_MODES = ("stack_area", "glass_bar", "dual")
CHART_MODE_DEFAULT = "glass_bar"      # 定案前保持接近现状的柱状, 不擅自改默认外观

# ---------------------------------------------------------------- 平滑曲线
def _smooth_path(pts):
    """把点列变成平滑的 QPainterPath —— 与 ECharts 的 smooth:true 观感一致。"""
    path = QPainterPath()
    if not pts:
        return path
    path.moveTo(pts[0][0], pts[0][1])
    n = len(pts)
    if n == 1:
        return path
    for i in range(n - 1):
        p0 = pts[i - 1] if i > 0 else pts[i]
        p1, p2 = pts[i], pts[i + 1]
        p3 = pts[i + 2] if i + 2 < n else p2
        c1 = (p1[0] + (p2[0] - p0[0]) / 6.0, p1[1] + (p2[1] - p0[1]) / 6.0)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6.0, p2[1] - (p3[1] - p1[1]) / 6.0)
        path.cubicTo(c1[0], c1[1], c2[0], c2[1], p2[0], p2[1])
    return path


def _monotone_path(pts):
    """单调三次插值(PCHIP / Fritsch-Carlson) —— **曲线永不过冲出数据范围**。

    ⚠️ 第97轮后半6实测教训: Catmull-Rom 在"骤升骤降"的数据上会**过冲**(冲出相邻数据点
    的范围), 而堆叠面积的上下边界一过冲就会**互相穿越**, 带状路径自交后 OddEven 填充
    直接乱掉(浅色下表现为"一大片斜坡")。ECharts/D3 的 smooth 曲线用的正是单调插值
    (curveMonotoneX / PCHIP 同源), 保证:
      · 极值处切线为 0(不过冲);
      · 每段曲线的值都介于两端点之间 —— 于是堆叠带的**上边界恒在下边界之上**(屏幕),
        路径永不自交。观感与 Catmull-Rom 接近, 但"稳"。
    """
    path = QPainterPath()
    n = len(pts)
    if n == 0:
        return path
    path.moveTo(pts[0][0], pts[0][1])
    if n < 3:
        for pt in pts[1:]:
            path.lineTo(pt[0], pt[1])
        return path
    xs = [pt[0] for pt in pts]
    ys = [pt[1] for pt in pts]
    dx = [xs[i + 1] - xs[i] for i in range(n - 1)]
    dy = [ys[i + 1] - ys[i] for i in range(n - 1)]
    slope = [(dy[i] / dx[i]) if dx[i] else 0.0 for i in range(n - 1)]
    # 节点切线(Fritsch-Carlson): 变号处置 0, 其余取加权调和平均
    m = [0.0] * n
    m[0] = slope[0]
    m[-1] = slope[-1]
    for i in range(1, n - 1):
        if slope[i - 1] * slope[i] <= 0:
            m[i] = 0.0
        else:
            w1 = 2.0 * dx[i] + dx[i - 1]
            w2 = dx[i] + 2.0 * dx[i - 1]
            den = w1 / slope[i - 1] + w2 / slope[i]
            m[i] = (w1 + w2) / den if den else 0.0
    # Hermite → 三次贝塞尔
    for i in range(n - 1):
        h = dx[i]
        if h == 0:
            path.lineTo(xs[i + 1], ys[i + 1])
            continue
        c1x = xs[i] + h / 3.0
        c1y = ys[i] + m[i] * h / 3.0
        c2x = xs[i + 1] - h / 3.0
        c2y = ys[i + 1] - m[i + 1] * h / 3.0
        path.cubicTo(c1x, c1y, c2x, c2y, xs[i + 1], ys[i + 1])
    return path


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
        # 第97轮后半6: 画法可切换(见 CHART_MODES), 默认保持现状
        self.mode = CHART_MODE_DEFAULT
        self.setMouseTracking(True)
        self.apply_size()

    def set_mode(self, mode):
        """切换画法(仅影响绘制, 数据与交互完全共用)。"""
        if mode in CHART_MODES and mode != self.mode:
            self.mode = mode
            self.update()

    def apply_size(self):
        m = curr_metric()
        self.setMinimumHeight(m["chart_min_h"])
        self.update()

    def set_data(self, daily, models_rank):
        top = [m for m, _ in models_rank[:8]]
        self.colors = {m: MODEL_COLORS[i % len(MODEL_COLORS)] for i, m in enumerate(top)}
        days = sorted(d for d in daily if d != "unknown")

        # 2026-09-25 (第64轮): **移除"记住缩放/平移"** —— 浅猫要求撤掉这个记忆功能。
        #   原行为(第46轮加的): 数据末日期未延展时保留用户上次的滚轮缩放/平移视图。
        #   现改为每次 set_data 都回到默认视图(最近 35 天 / 全量)。缩放与平移操作本身
        #   仍然可用, 只是活到下一次数据重绘为止(不再跨刷新/跨切页"记着")。
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
        self._sync_slice()   # 内部已有 clamp, 不会越界

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

    # ---------------- 第97轮后半6: 三套画法(共用数据与交互) ----------------
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

        try:
            if self.mode == "stack_area":
                self._paint_stack_area(p, w, h, padL, padR, padT, padB, iw, ih)
            elif self.mode == "dual":
                self._paint_dual(p, w, h, padL, padR, padT, padB, iw, ih)
            else:
                self._paint_glass_bar(p, w, h, padL, padR, padT, padB, iw, ih)
        except Exception:
            # 任何画法出错都退回朴素柱状, 保证界面永远有图可看
            try:
                self._paint_glass_bar(p, w, h, padL, padR, padT, padB, iw, ih)
            except Exception:
                pass

    # ---- 公共小件 ----
    def _axis_labels(self, p, padT, padB, ih, maxV):
        """极简 Y 轴: 只标顶值与 0(三套共用)。"""
        is_lg = theme_state.get("window_size") == "large"
        p.setFont(QFont("Consolas", 8.0 if is_lg else 7.5))
        p.setPen(TEXT3)
        p.drawText(QRectF(0, padT - 6, self._geom()[2] - 4, 16),
                   Qt.AlignRight | Qt.AlignVCenter, fmt_compact(maxV))
        p.drawText(QRectF(0, padT + ih - 6, self._geom()[2] - 4, 16),
                   Qt.AlignRight | Qt.AlignVCenter, "0")

    def _grid(self, p, w, padL, padR, padT, ih, k=3, alpha=0.5):
        """极淡水平网格(三套共用)。"""
        is_lg = theme_state.get("window_size") == "large"
        col = QColor(BORDER)
        col.setAlphaF(col.alphaF() * alpha)
        pen = QPen(col, 1)
        p.setPen(pen)
        for j in range(k):
            y = padT + ih - ih * j / (k - 1) if k > 1 else padT + ih
            p.drawLine(int(padL), int(y), int(w - padR), int(y))

    def _dates(self, p, padL, iw, h, padB, items, ys=None):
        """底部日期: 首 / 中 / 尾(三套共用)。"""
        is_lg = theme_state.get("window_size") == "large"
        p.setFont(QFont("Consolas", 7.8 if is_lg else 7.0))
        p.setPen(TEXT3)
        n = len(items)
        ys = ys or [h - padB + 1] * n
        for i in (0, n // 2, n - 1):
            if i >= n:
                continue
            cx = padL + iw * i / max(1, n - 1)
            p.drawText(QRectF(cx - 24, ys[i], 48, 14), Qt.AlignCenter,
                       items[i]["date"][5:].replace("-", "/"))

    def _peak_index(self):
        return max(range(len(self.data)),
                   key=lambda i: sum(v for _, _, v in self.data[i]["parts"]))

    # ---- 方案 D: 堆叠平滑面积 + 逐层渐变 ----
    def _paint_stack_area(self, p, w, h, padL, padR, padT, padB, iw, ih):
        n = len(self.data)
        if n < 2:
            self._paint_glass_bar(p, w, h, padL, padR, padT, padB, iw, ih)
            return
        # 累计层(从下往上), 与 ECharts stack 同义
        order = list(self.colors)          # set_data 里按 models_rank 顺序写入
        cum = [0.0] * n
        layers = []
        for m in order:
            for i, d in enumerate(self.data):
                cum[i] += sum(v for mm, _, v in d["parts"] if mm == m)
            layers.append((m, list(cum)))
        maxV = max(cum) or 1

        xs = [padL + iw * i / (n - 1) for i in range(n)]
        base = [(x, padT + ih) for x in xs]

        self._grid(p, w, padL, padR, padT, ih, k=3, alpha=0.45)
        self._axis_labels(p, padT, padB, ih, maxV)

        # ⚠️⚠️ 覆盖法(从最上层往最下层画完整区域, 后画覆盖先画):
        # PySide6 的 QPainterPath.subtracted() **是坏的**(实测: 矩形差集的 bbox
        # 仍等于原区域, 布尔运算没有生效) —— 差集法会让最后画的层盖掉前面所有层,
        # 整张图变成最后那个模型的颜色(实测整片橙)。
        # 覆盖法是 ECharts/D3 内部的标准做法: 每层画"自己的累计曲线到底部"的完整
        # 区域, 从上往下依次覆盖; 每层可见的部分正好是它与上一层之间的带。
        # 渐变用**不透明**的双色(顶亮→底本色) —— 半透明会在覆盖中互相叠脏。
        dark = bool(theme_state.get("dark"))
        for m, vals in reversed(layers):
            col = self.colors.get(m, BLUE)
            cur = [(xs[j], padT + ih - v / maxV * ih) for j, v in enumerate(vals)]
            reg = _monotone_path(cur)
            reg.lineTo(xs[-1], padT + ih)
            reg.lineTo(xs[0], padT + ih)
            reg.closeSubpath()
            band_top = min(y for _, y in cur)
            g = QLinearGradient(0, band_top, 0, padT + ih)
            g.setColorAt(0, col.lighter(126))
            g.setColorAt(0.55, col)
            g.setColorAt(1, col.darker(112))
            p.setPen(Qt.NoPen)
            p.setBrush(g)
            p.drawPath(reg)
            # 层与层之间的极细高光线(贴着本层曲线)
            pen = QPen(QColor(col.lighter(150)), 0.9)
            pen.setCosmetic(True)
            p.setPen(pen)
            p.drawPath(_monotone_path(cur))

        # 峰值: 垂直虚线 + 顶点圆(ECharts axisPointer cross 风格)
        pi = self._peak_index()
        px_ = xs[pi]
        dash = QPen(TEXT2, 1)
        dash.setStyle(Qt.DashLine)
        p.setPen(dash)
        p.drawLine(int(px_), int(padT), int(px_), int(padT + ih))
        p.setPen(Qt.NoPen)
        p.setBrush(CARD)
        p.drawEllipse(QPointF(px_, padT + ih - cum[pi] / maxV * ih), 2.6, 2.6)
        self._dates(p, padL, iw, h, padB, self.data)

    # ---- 方案 E: 清爽渐变柱(第97轮后半7 重做) ----
    def _paint_glass_bar(self, p, w, h, padL, padR, padT, padB, iw, ih):
        """浅猫定调: 不要立体感、要清爽。

        每根柱一个**整根柱范围**的渐变, 顶实底虚、无高光条; 柱顶小圆角保留。
          · 暗色: 本色 → 本色混白 40%(往下变淡、向白色渐变 —— 第97轮后半10 浅猫要求);
          · 浅色: 本色 → 同色淡出(245→110, 保持不变)。
        """
        n = len(self.data)
        maxV = max((sum(v for _, _, v in d["parts"]) for d in self.data), default=1) or 1
        slot = iw / n
        bw = max(3.0, min(16.0, slot * 0.66))
        dark = bool(theme_state.get("dark"))
        # 第97轮后半10(浅猫: "暗色版本改成往下慢慢变淡但是取白色渐变"):
        #  暗色卡片上"同色变淡"= 往深底融, 反差小看不出来 → 改成**向白色渐变**
        #  (本色 → 本色混白 40%), 柱子像被顶部光源照亮、向下渐渐化开;
        #  浅色版**保持不变**: 同色淡出(245→110), 浅底上已经很清晰。
        #  渐变范围仍是**整根柱**(柱顶→柱底), 保证整根柱方向统一、段间无透明度断层。
        WHITE_K = 0.40

        self._grid(p, w, padL, padR, padT, ih, k=3, alpha=0.5)
        self._axis_labels(p, padT, padB, ih, maxV)

        for i, d in enumerate(self.data):
            cx = padL + slot * i + slot / 2
            y_cur = padT + ih
            total = sum(v for _, _, v in d["parts"])
            col_top = padT + ih - total / maxV * ih      # 整根柱的柱顶
            for j, (_m, color, v) in enumerate(d["parts"]):
                hh = v / maxV * ih
                top = y_cur - hh
                x0 = cx - bw / 2
                # 渐变范围 = 整根柱(各段在自己高度区间内取渐变的一部分)
                g = QLinearGradient(0, col_top, 0, padT + ih)
                if dark:
                    # 暗色: 本色 → 本色混白(往下变淡、向白色渐变)
                    g.setColorAt(0.0, QColor(color.red(), color.green(), color.blue(), 255))
                    g.setColorAt(1.0, QColor(
                        int(color.red() + (255 - color.red()) * WHITE_K),
                        int(color.green() + (255 - color.green()) * WHITE_K),
                        int(color.blue() + (255 - color.blue()) * WHITE_K), 255))
                else:
                    # 浅色: 同色淡出(保持原样)
                    g.setColorAt(0.0, QColor(color.red(), color.green(), color.blue(), 245))
                    g.setColorAt(1.0, QColor(color.red(), color.green(), color.blue(), 110))
                p.setPen(Qt.NoPen)
                p.setBrush(g)
                if j == 0 and hh > 2:
                    # 顶部小圆角(与卡片语言一致, 不是卡通胶囊)
                    r = min(2.0, bw / 2)
                    path = QPainterPath()
                    path.moveTo(x0, y_cur)
                    path.lineTo(x0, top + r)
                    path.quadTo(x0, top, x0 + r, top)
                    path.lineTo(x0 + bw - r, top)
                    path.quadTo(x0 + bw, top, x0 + bw, top + r)
                    path.lineTo(x0 + bw, y_cur)
                    path.closeSubpath()
                    p.drawPath(path)
                else:
                    p.drawRect(QRectF(x0, top, bw, hh))
                y_cur = top
        self._dates(p, padL, iw, h, padB, self.data)

    # ---- 方案 F: 双视图(上趋势面积 + 下构成带) ----
    def _paint_dual(self, p, w, h, padL, padR, padT, padB, iw, ih):
        n = len(self.data)
        if n < 2:
            self._paint_glass_bar(p, w, h, padL, padR, padT, padB, iw, ih)
            return
        band_h = min(26.0, ih * 0.34)
        gap = 6.0
        area_ih = ih - band_h - gap
        totals = [sum(v for _, _, v in d["parts"]) for d in self.data]
        maxV = max(totals) or 1
        xs = [padL + iw * i / (n - 1) for i in range(n)]

        self._grid(p, w, padL, padR, padT, area_ih, k=3, alpha=0.4)
        self._axis_labels(p, padT, padB, area_ih, maxV)

        # 上: 总量平滑面积 —— 第97轮后半8(浅猫: "渐变遮罩加回来, 遮罩范围扩大一点")
        # ⭐ 直接沿用**顶部指标区那条迷你趋势线**的做法(第72轮, 她认可的效果):
        #   · 渐变用 QColor(r,g,b,alpha) 显式构造, 顶端 alpha 82 → 底端 0;
        #   · **遮罩范围是整个绘图区 ih**(不只是上区 area_ih) —— 范围一大,
        #     深浅过渡就被"拉平"了, 斜向分界的对比度大幅降低(这正是她要的观感)。
        pts = [(xs[i], padT + area_ih - totals[i] / maxV * area_ih) for i in range(n)]
        line = _monotone_path(pts)
        area = QPainterPath(line)
        area.lineTo(xs[-1], padT + area_ih)
        area.lineTo(xs[0], padT + area_ih)
        area.closeSubpath()
        fade = QLinearGradient(0, padT, 0, padT + ih)
        fade.setColorAt(0.0, QColor(BLUE.red(), BLUE.green(), BLUE.blue(), 82))
        fade.setColorAt(1.0, QColor(BLUE.red(), BLUE.green(), BLUE.blue(), 0))
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(fade))
        p.drawPath(area)
        pen = QPen(BLUE, 1.5)
        pen.setCosmetic(True)
        p.setPen(pen)
        p.drawPath(line)

        # 峰值点
        pi = self._peak_index()
        p.setPen(Qt.NoPen)
        p.setBrush(BLUE)
        p.drawEllipse(QPointF(xs[pi], pts[pi][1]), 2.4, 2.4)

        # 中间细分隔
        sep_y = padT + area_ih + gap / 2
        sc = QColor(BORDER)
        sc.setAlphaF(sc.alphaF() * 0.7)
        p.setPen(QPen(sc, 1))
        p.drawLine(int(padL), int(sep_y), int(w - padR), int(sep_y))

        # 下: 迷你构成带(无间隙堆叠柱)
        by = padT + area_ih + gap
        slot = iw / n
        bw = max(2.0, min(10.0, slot * 0.72))
        for i, d in enumerate(self.data):
            cx = padL + slot * i + slot / 2
            yc = by + band_h
            for _m, color, v in d["parts"]:
                hh = v / maxV * band_h
                if hh <= 0:
                    continue
                c = QColor(color); c.setAlphaF(c.alphaF() * 0.82)
                p.setBrush(c)
                p.drawRect(QRectF(cx - bw / 2, yc - hh, bw, hh))
                yc -= hh
        self._dates(p, padL, iw, h, padB, self.data,
                    ys=[by + band_h] * n)

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
        # @2026-10-17 第72轮: **拖动平移** ——
        #   `_pan` = 相对"最新"往回翻的月数 (0 = 最新; 越大越早);
        #   `_max_pan` 在每次绘制时按"总月数 - 可见月数"算出来(窗口宽度变化也自适应)。
        self._pan = 0
        self._drag_x = None
        self._drag_pan = 0
        self._month_w = 0.0     # 单个月份占的像素宽 (拖动换算用, 绘制时落地)
        self._max_pan = 0
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
        # @2026-10-17 第72轮: 可见窗口由 _pan 决定 (拖动平移), 不再死盯最近几个月
        all_m = sorted(months.keys())
        self._max_pan = max(0, len(all_m) - fit_m)
        self._pan = max(0, min(self._pan, self._max_pan))
        end = len(all_m) - self._pan
        start_i = max(0, end - fit_m)
        recent_m = all_m[start_i:end]
        self._month_w = 7 * unit + 12

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

        # @2026-10-17 第72轮: 能平移时, 底部右侧标出"当前显示的月份区间" + 拖动提示
        if self._max_pan > 0 and recent_m:
            p.setPen(TEXT3)
            p.setFont(QFont("Microsoft YaHei UI", 8.2 if is_lg else 7.5))
            _hint = f"{recent_m[0]} ~ {recent_m[-1]}"
            if self._pan < self._max_pan:
                _hint += "   ⟵ 拖动看更早"
            p.drawText(QRectF(120, h - 15, w - 128, 14),
                       Qt.AlignRight | Qt.AlignVCenter, _hint)

    # ---------------- 拖动平移 (@2026-10-17 第72轮) ----------------
    def _can_pan(self):
        return self._max_pan > 0

    def mousePressEvent(self, ev):
        # 第74轮反馈: 光标保持常规形态(不要手掌) —— 拖动能力靠"可拖"本身被发现即可
        if ev.button() == Qt.LeftButton and self._can_pan():
            self._drag_x = ev.position().x()
            self._drag_pan = self._pan
            ChartTip.instance().hide_tip()      # 拖动时别让悬浮框挡着

    def mouseReleaseEvent(self, ev):
        if self._drag_x is not None:
            self._drag_x = None

    def wheelEvent(self, ev):
        # 第74轮: 滚轮也能翻月份 —— 向下滚 = 看更早, 与"向右拖"同向
        if not self._can_pan():
            return
        step = 1 if ev.angleDelta().y() < 0 else -1
        new_pan = max(0, min(self._max_pan, self._pan + step))
        if new_pan != self._pan:
            self._pan = new_pan
            self.update()
        ev.accept()

    def mouseMoveEvent(self, ev):
        # 拖动中: 按"单月像素宽"换算月数 —— 向右拖 = 往回看更早的月份
        if self._drag_x is not None and self._month_w > 0:
            delta = int(round((ev.position().x() - self._drag_x) / self._month_w))
            new_pan = max(0, min(self._max_pan, self._drag_pan + delta))
            if new_pan != self._pan:
                self._pan = new_pan
                self.update()
            return
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
        self._drag_x = None
        self.unsetCursor()


# ============================================================ DSH 数据层
def dsh_ledger_path():
    base = os.environ.get("DSH_HOME") or os.path.expanduser("~/.dsh")
    return os.path.join(base, "storages", "cost-meter", "ledger.json")


DSH_PROVIDER_ALIASES = {
    # ⭐ 第87轮(浅猫): 别机快照/历史数据里 provider 名可能拼写不一致
    # (实测办公室快照是 "sencenova:..." 而本机是 "sensenova:..."), 导致同一个
    # 来源同一个模型被拆成两行。这里把已知别名归一成规范名。
    # 注意: **不要剥掉 provider** —— 不同 provider 的同名模型(sensenova vs
    # deepseek-official 的 deepseek-v4-flash)是不同来源, 应保持分开。
    "sencenova": "sensenova",
    "sensenova": "sensenova",
    "workbuddy": "workbuddy",
    "aliyun": "aliyun",
    "deepseek-official": "deepseek-official",
    "deepseek": "deepseek-official",
    "openrouter": "openrouter",
    "opencode1": "opencode1",
    "opencode2dsh": "opencode2dsh",
    "dots": "dots",
    "dots-vision": "dots-vision",
    "xiaomi": "xiaomi",
    "mollycloud": "mollycloud",
    "bai": "bai",
}


def _dsh_provider(model):
    """取键的 provider 段(冒号前 / 首段斜杠前), 未识别前缀返回 None。"""
    m = str(model or "")
    if ":" in m:
        return m.split(":", 1)[0].strip().lower() or None
    if "/" in m:
        return m.split("/", 1)[0].strip().lower() or None
    return None


def _dsh_model_key(model):
    """把账本里的模型键归一成规范键 "provider/model"。

    ⚠️ 第87轮修正(浅猫纠正): 之前误把 provider 剥掉、把不同来源的同名模型合并成一行
    (sensenova:deepseek-v4-flash + deepseek-official:deepseek-v4-flash → 一行),
    这会丢掉「走的是哪个通道」的信息。正确做法是 **保留 provider**:
      · 统一大小写/分隔符("provider:model" 与 "provider/model" 都归一为 provider/model)
      · 修正已知 provider 拼写别名(sencenova → sensenova)
      · 这样「同一来源同一模型」合并,「不同来源同名模型」仍分开。
    """
    m = (model or "").strip()
    prov = _dsh_provider(m)
    mdl = m
    if ":" in m:
        mdl = m.split(":", 1)[1].strip()
    elif "/" in m:
        mdl = m.split("/", 1)[1].strip()
    mdl = mdl.strip()
    if prov:
        prov = DSH_PROVIDER_ALIASES.get(prov, prov)
        return "%s/%s" % (prov, mdl)
    return mdl


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
            # 第87轮: 同源同模型(拼写/分隔符变体)归一到同一键后**必须累加**,
            # 否则后一条会覆盖前一条(实测 input 1000+2000 → 2000 而非 3000)。
            # 注意保留 provider: 不同 provider 的同名模型(sensenova vs deepseek-official)是
            # 不同来源, 保持分开。
            mk = _dsh_model_key(model)
            mi = b.get("input", 0)
            mo = b.get("output", 0)
            mcr = b.get("cacheRead", 0)
            mcw = b.get("cacheWrite", 0)
            mt = mi + mo + mcr + mcw
            if mt <= 0 and b.get("calls", 0) <= 0:
                continue
            agg = dm.get(mk)
            if agg is None:
                agg = {"requests": 0, "input": 0, "output": 0,
                       "cached": 0, "cacheWrite": 0, "total": 0}
                dm[mk] = agg
            agg["requests"] += b.get("calls", 0)
            agg["input"] += mi + mcr + mcw
            agg["output"] += mo
            agg["cached"] += mcr
            agg["cacheWrite"] += mcw
            agg["total"] += mt
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
_sn_cred_mem = {"last_ok_ts": 0.0, "last_ok_values": None}


def _sn_curl_host_ok(url):
    """cURL 凭据是否指向商汤域名 (非商汤一律视为无效配置)"""
    try:
        from urllib.parse import urlparse
        h = (urlparse(str(url)).hostname or "").lower()
        return bool(h) and (h == SN_CRED_HOST_OK or h.endswith("." + SN_CRED_HOST_OK))
    except Exception:
        return False


def _sn_quarantine_curl(url):
    """把无效 cURL 配置挪到 sn_autosync.invalid.json。

    历史遗留: 回归测试曾把 mock 配置(api.example.com)写进真实数据目录且没还原,
    之后每次 Playwright 失败都会回退到这台不存在的域名 → 报一个与真实原因无关的
    DNS 错误, 让人误以为"同步坏了"。这里做一次性自愈。
    """
    dst = SN_AUTOSYNC_FILE.replace(".json", ".invalid.json")
    try:
        shutil.move(SN_AUTOSYNC_FILE, dst)
        _sn_cred_log("curl-invalid", "凭据域名非商汤(%s) → 已归档 %s" % (str(url)[:48], os.path.basename(dst)))
    except Exception:
        try:
            with open(SN_AUTOSYNC_FILE, "w", encoding="utf-8") as f:
                f.write("{}")
        except Exception:
            pass


def load_sn_autosync():
    try:
        with open(SN_AUTOSYNC_FILE, encoding="utf-8") as f:
            d = json.load(f)
        if not (isinstance(d, dict) and d.get("url")):
            return None
        if not _sn_curl_host_ok(d["url"]):
            _sn_quarantine_curl(d.get("url"))
            return None
        return d
    except Exception:
        return None


def save_sn_autosync(d):
    try:
        if not _sn_curl_host_ok((d or {}).get("url")):
            return False
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
# 2026-09-16 第45轮: 凭据链路优化 —— ①Edge 多候选自动发现 ②本地 JWT 过期预判(免注定 401 的往返)
#   ③事件驱动等待额度响应(替代固定 sleep 5s) ④统一超时/重试收敛最坏耗时 ⑤凭据域名校验(清除测试残留投毒)
SN_EDGE_CANDIDATES = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]
SN_EDGE_PATH = SN_EDGE_CANDIDATES[0]   # 兼容旧引用; 实际一律走 _sn_edge_path() 动态探测
SN_LOGIN_STATE = os.path.join(scanner.PLUGIN_DATA_DIR, "sn_login_state.json")
SN_ACCOUNT_FILE = os.path.join(scanner.PLUGIN_DATA_DIR, "sn_account.json")
SN_TOKEN_FILE = os.path.join(scanner.PLUGIN_DATA_DIR, "sn_token.json")
SN_CRED_LOG = os.path.join(scanner.PLUGIN_DATA_DIR, "sn_cred.log")
SN_POOL_API = "/lite/console/v1/tokenplan/pool-usage"
SN_POOL_URL = "https://platform.sensenova.cn" + SN_POOL_API
SN_CONSOLE_URL = "https://platform.sensenova.cn/console"
SN_USE_PLAYWRIGHT = True   # 真自动抓取开关 (测试环境置 False 走 cURL mock)

SN_CRED_HOST_OK = "sensenova.cn"     # cURL 凭据必须指向商汤域名, 否则视为无效并归档
SN_HTTP_TIMEOUT = 8                  # 快路径单次 HTTP 超时 (原 15s × 最坏 3 次 → 40s+, 严重拖慢刷新)
SN_HTTP_TRIES = 2                    # 瞬时网络错误重试次数
SN_401_TRIES = 2                     # 瞬时 401 重试次数 (实测存在"同一 token 一会儿 401 一会儿 200")
SN_TOKEN_MIN_TTL = 120               # token 剩余寿命低于此值 → 直接续期, 省掉一次注定 401 的往返
SN_TOKEN_REFRESH_MARGIN = 900        # 剩余寿命低于此值 → 周期刷新时提前续期
SN_CRED_RESP_WAIT = 25               # 控制台页面等待额度响应总上限 (秒, 事件驱动: 一到就走)
SN_CRED_RESP_FAST = 8                # 先快等这么久; 还没到就用页面里的 token 自己直连(见下)
_sn_edge_mem = {"path": None, "ts": 0.0}
_sn_tok_mem = {"tok": None, "exp": None}


def _sn_cred_log(tag, msg, sec=None):
    """凭据链路轻量日志 (16/32/64... 超 64KB 自动保留最后 200 行)。

    "时不时失败"这类问题没有日志就只能靠猜 —— 记下每次走的哪条路径、耗时、结果,
    事后一眼能看出是凭据过期、网络抖动还是页面改版。
    """
    try:
        line = "%s  %-13s %s%s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), tag,
                                    ("%5.2fs  " % sec) if sec is not None else "", msg)
        try:
            if os.path.getsize(SN_CRED_LOG) > 65536:
                with open(SN_CRED_LOG, encoding="utf-8", errors="replace") as f:
                    keep = f.readlines()[-200:]
                with open(SN_CRED_LOG, "w", encoding="utf-8") as f:
                    f.writelines(keep)
        except OSError:
            pass
        with open(SN_CRED_LOG, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        pass


def _sn_edge_path():
    """动态定位系统 Edge (固定候选 → 注册表 App Paths → PATH 兜底), 结果缓存。

    旧实现把路径写死成 x86 Edge: 一旦 Edge 装到 x64 目录/换盘/卸载重装,
    _sn_playwright_ready() 直接 False → 整条真自动链路**静默失效**并退化到 cURL,
    表面症状就是"时不时获取失败"。
    """
    now = time.time()
    p = _sn_edge_mem["path"]
    if p and os.path.exists(p):
        return p
    if p is None and now - _sn_edge_mem["ts"] < 60:
        return None                       # 刚探测过且没找到 → 60s 内不重复扫盘
    cands = list(SN_EDGE_CANDIDATES)
    la = os.environ.get("LOCALAPPDATA")
    if la:
        cands.append(os.path.join(la, r"Microsoft\Edge\Application\msedge.exe"))
    try:
        import winreg
        for root in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
            try:
                with winreg.OpenKey(root, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\msedge.exe") as k:
                    v = winreg.QueryValue(k, None)
                    if v:
                        cands.append(v.strip('"'))
            except OSError:
                pass
    except Exception:
        pass
    for name in ("msedge", "msedge.exe"):
        try:
            w = shutil.which(name)
            if w:
                cands.append(w)
        except Exception:
            pass
    found = None
    for c in cands:
        try:
            if c and os.path.exists(c):
                found = c
                break
        except Exception:
            continue
    if found:
        _sn_edge_mem.update(path=found, ts=now)
        if found != SN_EDGE_CANDIDATES[0]:
            _sn_cred_log("edge", "使用非默认路径 Edge: %s" % found)
        return found
    _sn_edge_mem.update(path=None, ts=now)
    _sn_cred_log("edge", "未找到系统 Edge (候选 %d 个)" % len(cands))
    return None


def _sn_account_credentials():
    """读取账号密码 (兼容 password_b64 base64 + 旧明文 password)"""
    try:
        with open(SN_ACCOUNT_FILE, "r", encoding="utf-8-sig") as f:
            d = json.load(f)
    except Exception:
        return "", ""
    username = d.get("username", "")
    pwd = d.get("password_b64", "")
    if pwd:
        try:
            pwd = base64.b64decode(pwd).decode("utf-8")
        except Exception:
            pwd = ""
    else:
        pwd = d.get("password", "")   # 兼容旧明文
    return username, pwd


def _sn_account_ready():
    """是否已配置账号密码 (可支撑浏览器自动登录)"""
    username, password = _sn_account_credentials()
    return bool(username and password)


def _sn_token_exp(tok):
    """本地解析 JWT 的 exp (秒级时间戳), 解析不了返回 None。

    商汤 access_token 是标准 JWT(RS256), 载荷自带 iat/exp → 完全可以在本地判断
    凭据是否还有效, 不必先打一次注定 401 的网络请求才发现过期。
    """
    if not tok:
        return None
    if _sn_tok_mem["tok"] == tok:
        return _sn_tok_mem["exp"]
    exp = None
    try:
        part = tok.split(".")[1]
        part += "=" * (-len(part) % 4)
        v = json.loads(base64.urlsafe_b64decode(part)).get("exp")
        exp = float(v) if v else None
    except Exception:
        exp = None
    _sn_tok_mem.update(tok=tok, exp=exp)
    return exp


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
    """Playwright 是否可用(已安装 + 能找到系统 Edge)"""
    try:
        import playwright  # noqa: F401
    except Exception:
        return False
    return _sn_edge_path() is not None


def _sn_direct_fetch(token):
    """用 access_token urllib 直连 pool-usage, 返回 (data_dict, error)。401 返回 (None, '401')

    健壮性/速度: ①单次超时收敛到 SN_HTTP_TIMEOUT(8s) ②瞬时网络错误最多重试 SN_HTTP_TRIES
    次(短退避) ③系统代理拒绝连接(10061)自动绕过代理直连重试 ④401/403 立即返回, 不做无意义重试
    ⑤SSL 校验失败(企业代理/MITM)自动放宽一次。最坏耗时由 45s+ 收敛到 ~18s。
    """
    import urllib.request, urllib.error, time as _time

    def _mk_ctx(insecure):
        try:
            import ssl
            c = ssl.create_default_context()
            if insecure:
                c.check_hostname = False
                c.verify_mode = ssl.CERT_NONE
            return c
        except Exception:
            return None

    def _do(direct=False, insecure=False):
        req = urllib.request.Request(SN_POOL_URL, headers={
            "Authorization": "Bearer " + token,
            "accept": "application/json",
            "User-Agent": "Mozilla/5.0",
        })
        kwargs = {"timeout": SN_HTTP_TIMEOUT}
        ctx = _mk_ctx(insecure)
        if ctx is not None:
            kwargs["context"] = ctx
        if direct:
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            resp = opener.open(req, **kwargs)
        else:
            resp = urllib.request.urlopen(req, **kwargs)
        body = resp.read(2_000_000).decode("utf-8", "replace")
        return json.loads(body)

    def _ok(data):
        return isinstance(data, dict) and bool(data.get("pools"))

    last_err = ""
    for attempt in range(SN_HTTP_TRIES):
        try:
            data = _do()
            if _ok(data):
                return data, None
            return None, "积分接口无 pools 数据"
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                return None, "401"
            return None, f"HTTP {e.code}"
        except urllib.error.URLError as e:
            reason = str(getattr(e, "reason", "")) + str(e)
            # SSL 证书校验失败(企业代理/MITM) → 仅此情况放宽校验重试一次
            ru = reason.upper()
            if any(k in ru for k in ("SSL", "CERTIFICATE", "CERTIFICATION")):
                try:
                    data = _do(direct=False, insecure=True)
                    if _ok(data):
                        _sn_cred_log("token-direct", "证书校验失败 → 已放宽一次成功")
                        return data, None
                    return None, "积分接口无 pools 数据"
                except urllib.error.HTTPError as e2:
                    if e2.code in (401, 403):
                        return None, "401"
                    return None, f"HTTP {e2.code}"
                except Exception as e2:
                    return None, str(e2)[:120]
            # 系统代理拒绝连接 → 绕过代理直连重试
            if "10061" in reason or "ProxyError" in reason or "proxy" in reason.lower():
                try:
                    data = _do(direct=True)
                    if _ok(data):
                        _sn_cred_log("token-direct", "系统代理不可用 → 已直连成功")
                        return data, None
                    return None, "积分接口无 pools 数据"
                except urllib.error.HTTPError as e2:
                    if e2.code in (401, 403):
                        return None, "401"
                    return None, f"HTTP {e2.code}"
                except Exception as e2:
                    return None, str(e2)[:120]
            last_err = reason[:120]
            if attempt < SN_HTTP_TRIES - 1:
                _time.sleep(0.4 * (attempt + 1))   # 短退避重试
        except Exception as e:
            last_err = str(e)[:120]
            if attempt < SN_HTTP_TRIES - 1:
                _time.sleep(0.4 * (attempt + 1))
    return None, last_err or "网络请求失败"


def sn_token_ttl():
    """当前 access_token 剩余有效秒数 (判断不了返回 None)"""
    tok = _sn_load_token()
    if not tok:
        return None
    exp = _sn_token_exp(tok)
    if exp is None:
        return None
    return exp - time.time()


def sn_token_near_expiry():
    """token 是否已进入提前续期窗口。

    商汤 access_token 寿命 3h(实测 iat→exp = 10800s), 周期刷新每 5min 一次 ——
    进入窗口就顺手换一张新证, 用户几乎永远不会正好撞上"过期才续期"的慢路径。
    """
    ttl = sn_token_ttl()
    return ttl is not None and ttl < SN_TOKEN_REFRESH_MARGIN


def _sn_playwright_login_and_fetch():
    """Edge 持久登录态抓额度 (事件驱动等待)。返回 (data, token, error)

    2026-09-16 提速/稳健:
      · 不再固定 sleep 5s —— 改为轮询等待额度响应, 一拿到就返回, 未拿到最多等 SN_CRED_RESP_WAIT
      · goto 用 wait_until="commit" (SPA 的 load 很慢, 而额度请求在 JS 起来后就会发出)
      · 登录态文件缺失时用干净上下文直接尝试账号密码登录 (首次运行也能全自动, 原实现直接判"未登录")
      · 非登录页但没抓到 → reload 一次给二次机会 (页面改版/首次加载慢)
      · 全程 try/finally 保证关浏览器 (原实现多处提前 return 不 close, 会残留无头 msedge,
        累积后拖慢甚至卡死后续抓取)
    """
    edge = _sn_edge_path()
    if not edge:
        return None, None, "未找到系统 Edge (请确认 Edge 已安装)"
    try:
        from playwright.sync_api import sync_playwright
    except Exception as e:
        return None, None, f"playwright 导入失败: {str(e)[:80]}"

    username, password = _sn_account_credentials()

    captured = {}
    token = None
    t0 = time.perf_counter()
    browser = None
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                executable_path=edge, headless=True, timeout=20000,
                args=["--no-first-run", "--no-default-browser-check",
                      "--disable-sync", "--disable-background-networking"])
            _st = SN_LOGIN_STATE if os.path.exists(SN_LOGIN_STATE) else None
            ctx = browser.new_context(storage_state=_st)
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

            def _grab_token():
                try:
                    return page.evaluate("() => localStorage.getItem('access_token')")
                except Exception:
                    return None

            def _wait_leave_login(limit):
                """等待页面离开 /login (登录提交后跳转需要时间)。

                ★ 这是 45 轮引入的回归修复: 原实现登录提交后调 _wait_data(), 而 _wait_data
                一看到 URL 还含 /login 就立刻返回 False —— 可提交后那一两秒必然还在登录页,
                于是续签永远失败("未捕获到积分数据", 而且每次都几秒内失败)。
                """
                end = time.time() + limit
                while time.time() < end:
                    try:
                        if "/login" not in (page.url or ""):
                            return True
                    except Exception:
                        pass
                    try:
                        page.wait_for_timeout(200)
                    except Exception:
                        return False
                return False

            def _wait_data(limit):
                """事件驱动等待: 额度响应一到立刻返回, 而不是死等固定秒数"""
                end = time.time() + limit
                while time.time() < end:
                    if captured.get("data"):
                        return True
                    try:
                        if "/login" in (page.url or ""):
                            return False
                    except Exception:
                        pass
                    try:
                        page.wait_for_timeout(150)
                    except Exception:
                        return bool(captured.get("data"))
                return bool(captured.get("data"))

            try:
                # commit 级导航: SPA 的 load/domcontentloaded 可能很慢, 而额度请求在 JS 起来后
                # 就会发出 → 用 commit + 轮询可以比原来省 3~7s
                page.goto(SN_CONSOLE_URL, wait_until="commit", timeout=20000)
            except Exception:
                pass

            # ① 先快等页面自己发的额度响应 (常见 2~4s)
            _wait_data(SN_CRED_RESP_FAST)

            # ② 页面额度请求迟迟没发(SPA 慢/改版) → 用页面里的 token 自己直连一次。
            #    实测控制台 SPA 冷启动慢时, 页面自己的请求可能 25s 都不出现, 而 localStorage
            #    里的 token 早就可用了 —— 这一步能把那种情况从 25s+ 压到 ~8s。
            if not captured.get("data") and "/login" not in (page.url or ""):
                _tk = _grab_token()
                if _tk:
                    _d, _e = _sn_direct_fetch(_tk)
                    if _d is not None and _d.get("pools"):
                        captured["data"] = _d
                        token = _tk
                        _sn_cred_log("browser", "页面额度请求未到, 改用页面 token 直连成功")

            # ③ 还没拿到 → 继续等满, 然后按"是否在登录页"分流
            if not captured.get("data"):
                _wait_data(max(0, SN_CRED_RESP_WAIT - SN_CRED_RESP_FAST))
                on_login = "/login" in (page.url or "")
                if on_login:
                    if not username or not password:
                        return None, None, "登录态已过期且未配置账号密码"
                    try:
                        page.get_by_text("账号密码登录", exact=True).click(timeout=8000)
                        page.wait_for_timeout(1200)
                        page.get_by_placeholder("请设置用户名").fill(username)
                        page.get_by_placeholder("请输入密码").fill(password)
                        page.wait_for_timeout(300)
                        page.get_by_role("button", name="登录", exact=True).click(timeout=8000)
                    except Exception as e:
                        return None, None, f"自动重登失败: {str(e)[:100]}"
                    _sn_cred_log("relogin", "已提交账号密码, 等待跳转…")
                    # 先等页面真正离开 /login, 再等额度响应 (顺序不能反, 见 _wait_leave_login 注释)
                    if not _wait_leave_login(30):
                        return None, None, ("自动登录未成功 (30s 后仍停留在登录页: "
                                            "密码可能有误或出现了验证码)")
                    _sn_cred_log("relogin", "已离开登录页, 等待额度响应")
                    _wait_data(SN_CRED_RESP_WAIT)
                else:
                    try:
                        page.reload(wait_until="commit", timeout=15000)
                    except Exception:
                        pass
                    _wait_data(min(12, SN_CRED_RESP_WAIT))
                if not captured.get("data"):
                    return None, None, "未捕获到积分数据 (控制台响应超时或页面改版)"

            if not token:
                token = _grab_token()

            try:
                ctx.storage_state(path=SN_LOGIN_STATE)
            except Exception:
                pass
            if token:
                _sn_save_token(token)
    except Exception as e:
        _sn_cred_log("browser", "异常: %s" % str(e)[:90], time.perf_counter() - t0)
        return None, None, f"playwright 抓取异常: {str(e)[:120]}"
    finally:
        try:
            if browser is not None:
                browser.close()
        except Exception:
            pass

    data = captured.get("data")
    if data is not None:
        _sn_cred_log("browser", "抓取成功 (token=%s)" % ("有" if token else "无"),
                     time.perf_counter() - t0)
    return data, token, None


def sn_playwright_fetch(force_login=False, proactive=False):
    """商汤积分真自动抓取: token 直连优先(0.2~0.8s) → 需要时浏览器续期(秒级)。返回 (values, error)

    2026-09-16: 加入本地 JWT 过期预判 —— token 已过期/即将过期时不再浪费一次注定 401 的
    网络往返(可能还要等 8s 超时), 直接走浏览器续期; proactive=True 时进入续期窗口
    (SN_TOKEN_REFRESH_MARGIN) 就主动换证, 让用户几乎不会撞上慢路径。
    """
    tok = _sn_load_token()
    exp = _sn_token_exp(tok) if tok else None
    ttl = (exp - time.time()) if exp is not None else None
    need_browser = bool(force_login) or (
        proactive and ttl is not None and ttl < SN_TOKEN_REFRESH_MARGIN)
    if tok and not need_browser:
        if ttl is None or ttl > SN_TOKEN_MIN_TTL:
            t0 = time.perf_counter()
            data, err = None, None
            for attempt in range(SN_401_TRIES + 1):
                data, err = _sn_direct_fetch(tok)
                if data is not None or err != "401":
                    break
                # 实测存在"同一 token 一会儿 401 一会儿 200"(服务端瞬时抖动/多节点不一致)。
                # 直接升级到浏览器要 5~30s, 而在这里多试一次只要 <1s —— 非常划算。
                if attempt < SN_401_TRIES:
                    _sn_cred_log("token-401", "瞬时 401, %.1fs 后重试 (%d/%d)"
                                 % (0.6 * (attempt + 1), attempt + 1, SN_401_TRIES))
                    time.sleep(0.6 * (attempt + 1))
            if data is not None:
                values = _sn_parse_pool_data(data)
                if values:
                    _sn_save_token(tok)   # 缓存 token, 避免每次从 login_state 解析
                    _sn_cred_log("token-direct", "直连成功", time.perf_counter() - t0)
                    return values, None
            _sn_cred_log("token-direct",
                         "凭据已失效(401) → 浏览器续期" if err == "401" else f"失败: {err}",
                         time.perf_counter() - t0)
        else:
            _sn_cred_log("token-stale", "剩余 %.0fs → 跳过直连, 直接浏览器续期" % ttl)
    elif tok and need_browser and proactive and not force_login:
        _sn_cred_log("token-renew", "剩余 %.0fs 进入续期窗口 → 主动换证" % ttl)
    elif not tok and not os.path.exists(SN_LOGIN_STATE) and not _sn_account_ready():
        return None, "未登录 (请在商汤页填写账号密码完成首次登录)"

    # 慢路径: 浏览器续期 + 抓取
    data, new_token, err = _sn_playwright_login_and_fetch()
    if data is None:
        return None, err or "抓取失败"
    values = _sn_parse_pool_data(data)
    if not values:
        return None, "积分接口响应结构无法识别"
    return values, None



def sn_autosync_fetch(force=False, proactive=False):
    """商汤额度自动获取总入口。

    顺序: ①活跃内存值(5min 频控, 省重复请求) ②真自动(token 直连 → 浏览器续期)
    ③磁盘 cURL 凭据回退。失败原因写入 _autosync_mem["error"] 供 UI 明确展示。

    2026-09-16: 不再要求"登录态文件必须存在"才走真自动 —— 缺文件时浏览器会用账号密码
    直接登录一次(首次运行也能全自动), 原实现这种情况直接判死并悄悄退化成 cURL。
    """
    now = time.time()
    if not force and _autosync_mem["values"] is not None and now - _autosync_mem["ts"] < SN_AUTOSYNC_TTL:
        return _autosync_mem["values"]

    # ① 真自动: token 直连优先, 需要时浏览器续期
    if SN_USE_PLAYWRIGHT and _sn_playwright_ready():
        vals, err = sn_playwright_fetch(proactive=proactive)
        if vals:
            _autosync_mem.update(ts=time.time(), values=vals, error=None)
            _sn_cred_mem.update(last_ok_ts=time.time(), last_ok_values=vals)
            return vals
        _autosync_mem.update(ts=now, values=None, error=err)
        if err != "401":
            _sn_cred_log("autosync", "真自动失败: %s" % err)

    # ② cURL 凭据回退 (半自动兜底)
    cfg = load_sn_autosync()
    if not cfg:
        if not _autosync_mem["error"]:
            _autosync_mem.update(ts=now, values=None, error="未配置有效凭据 (可粘贴控制台 cURL)")
        return None
    paths = cfg.get("paths") or {}
    if not paths:
        _autosync_mem.update(ts=now, values=None, error="未配置字段路径")
        return None
    t0 = time.perf_counter()
    status, data, err = _http_json(cfg)
    if err:
        _sn_cred_log("curl", "调用失败: %s" % err, time.perf_counter() - t0)
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
    _sn_cred_log("curl", "调用成功", time.perf_counter() - t0)
    _autosync_mem.update(ts=now, values=values, error=None)
    _sn_cred_mem.update(last_ok_ts=now, last_ok_values=values)
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
    # 副本去重: workdaddy 复制产生的同 sessionId 副本不重复计数(与 scanner 同一判据)
    _all = list(scanner._iter_jsonl_files())
    _keep, _dropped, _ = scanner._dedupe_files(_all)
    for path in _keep:
        try:
            st = os.stat(path)
            size, mtime = st.st_size, st.st_mtime_ns // 1_000_000   # 毫秒精度(秒级会漏检同秒两次写入)
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


def _default_sn_pools():
    """凭证 / 数据未就绪时的占位积分池: 两张卡以「官方公测期满额」渲染。

    update 2026-09-20 (第57轮): 浅猫要求「不管怎样积分卡都固定在那里, 只是没加载
    凭证的时候数据是默认满额数据」。原实现在 pools 为空时把整个卡片区换成一段文字,
    首次打开要等凭证加载完卡片才"长出来"(先文字后卡片的跳变)。
    这里返回的字段与 load_sn_stats().build_pool 完全一致 —— 即占位卡与真实卡**同形**,
    唯一区别是还没有消耗(remaining == total); 重置时间也取真实的下一次 5h 窗口边界与
    滚动周锚点, 避免出现 "—" 的空洞感。
    """
    try:
        _ws, we = sn_window_bounds()
        win_reset = _fmt_reset(we)
    except Exception:
        win_reset = "—"
    try:
        week_reset = _next_weekly_reset_str()
    except Exception:
        week_reset = "—"

    def mk(pid, name, scope, color):
        return {
            "id": pid, "name": name, "scope": scope, "color": color,
            "window_total": SN_POOL_WINDOW_QUOTA,
            "window_remaining": float(SN_POOL_WINDOW_QUOTA),
            "weekly_total": SN_POOL_WEEKLY_QUOTA,
            "weekly_remaining": float(SN_POOL_WEEKLY_QUOTA),
            "window_reset": win_reset, "next_weekly_reset": week_reset,
            "synced": False, "sync_time": None, "placeholder": True,
        }

    return [mk("general", "通用积分池", "所有 Free 模型可用", "purple"),
            mk("flash_lite", "Flash-Lite 专属积分池", "仅 Flash-Lite 系列模型", "orange")]


def load_sn_stats(force=False, proactive=False):
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
    auto_vals = sn_autosync_fetch(force=force, proactive=proactive)
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
    last_ok_time = None
    if _sn_cred_mem.get("last_ok_ts"):
        try:
            last_ok_time = time.strftime("%H:%M", time.localtime(_sn_cred_mem["last_ok_ts"]))
        except Exception:
            last_ok_time = None
    elif _autosync_mem.get("values") is not None:
        try:
            last_ok_time = time.strftime("%H:%M", time.localtime(_autosync_mem["ts"]))
        except Exception:
            last_ok_time = None

    return {
        "source": "sn", "window_start": ws, "window_end": we,
        "pools": pools, "synced": sync is not None, "sync_time": sync_time_str,
        "sync_src": sync_src, "autosync_error": _autosync_mem["error"],
        "last_ok_time": last_ok_time,
    }


# ============================================================ 商汤积分池卡片 (双进度对称仪表)
# ============================================================ 商汤积分池卡片 (双进度对称仪表)
class BarIndicator(QWidget):
    """小细条指示器: 自绘圆角胶囊 (16×4 圆角2px, 与 WB/DSH StatCard 同款渲染)"""
    def __init__(self, color, parent=None):
        super().__init__(parent)
        self._color = color
        self.setFixedSize(16, 4)
        self.setAttribute(Qt.WA_TranslucentBackground)   # 角部透明, 圆角才能透出父背景可见

    def set_color(self, c):
        self._color = c
        self.update()

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(self._color)
        p.drawRoundedRect(QRectF(0.5, 0.5, 15, 3), 2.0, 2.0)


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
        self.setFixedHeight(m.get("sn_prog_h", 10))
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
    """商汤积分池卡片: 采用小细条标题语言，额度数值字号加大醒目"""
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

        # 1. 顶栏: 小细条标识 + 池名称 (左) | 适用模型说明 (右)
        top = QHBoxLayout()
        top.setSpacing(8)

        self.bar_indicator = BarIndicator(SN_PURPLE)
        top.addWidget(self.bar_indicator, 0, Qt.AlignVCenter)

        self.name_lbl = QLabel(self.pool["name"])
        top.addWidget(self.name_lbl, 0, Qt.AlignVCenter)
        top.addStretch(1)

        self.scope_lbl = QLabel(self.pool.get("scope", ""))
        top.addWidget(self.scope_lbl, 0, Qt.AlignVCenter)
        v.addLayout(top)

        # 2. 周周期额度展示块
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

        # 3. 5h 滑动窗口额度展示块
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
        is_lg = theme_state.get("window_size") == "large"

        # 额度标题与数值字号适当调大，视觉对比更突出
        title_pt = m["sn_title_pt"] + 0.5
        lbl_pt = 9.6 if not is_lg else 10.6
        val_pt = 10.6 if not is_lg else 11.8
        date_pt = 8.6 if not is_lg else 9.3

        self.name_lbl.setFont(QFont("Microsoft YaHei UI", title_pt, QFont.Bold))
        self.scope_lbl.setFont(QFont("Microsoft YaHei UI", m["sn_sub_pt"]))

        self.week_title.setFont(QFont("Microsoft YaHei UI", lbl_pt))
        self.window_title.setFont(QFont("Microsoft YaHei UI", lbl_pt))
        self.week_val_lbl.setFont(QFont("Consolas", val_pt, QFont.Bold))
        self.window_val_lbl.setFont(QFont("Consolas", val_pt, QFont.Bold))

        self.week_reset_lbl.setFont(QFont("Microsoft YaHei UI", date_pt))
        self.window_reset_lbl.setFont(QFont("Microsoft YaHei UI", date_pt))

        self.bar_week.apply_size()
        self.bar_win.apply_size()
        self.update()

    def apply_theme(self):
        dark = theme_state["dark"]
        is_orange = self.pool.get("color") == "orange"
        accent = (SN_ORANGE_DARK if dark else SN_ORANGE) if is_orange \
            else (SN_PURPLE_DARK if dark else SN_PURPLE)

        self.setStyleSheet("#sn_pool_card { background:transparent; border:none; }")
        self.bar_indicator.set_color(accent)

        self.name_lbl.setStyleSheet(f"color:{qname(TEXT)};")
        self.week_val_lbl.setStyleSheet(f"color:{qname(accent)};")
        self.window_val_lbl.setStyleSheet(f"color:{qname(accent)};")

        for lbl in (self.scope_lbl, self.week_reset_lbl, self.window_reset_lbl):
            lbl.setStyleSheet(f"color:{qname(TEXT3)};")

        for lbl in (self.week_title, self.window_title):
            lbl.setStyleSheet(f"color:{qname(TEXT2)}; font-weight: 500;")

        self.apply_size()
        self.bar_week.update()
        self.bar_win.update()
        self.update()


class SNPromoCard(GlassPodFrame):
    """活动固定积分卡片: 双列居中平衡布局 + 到期黄色胶囊标签"""
    def __init__(self, parent=None):
        super().__init__(radius=12, parent=parent)
        self.setObjectName("sn_promo_card")
        self._build_ui()
        self.apply_theme()

    def _build_ui(self):
        v = QVBoxLayout(self)
        v.setContentsMargins(16, 8, 16, 8)
        v.setSpacing(6)

        top = QHBoxLayout()
        top.setSpacing(8)

        self.promo_icon = QLabel("🎁")
        self.promo_icon.setFont(QFont("Microsoft YaHei UI", 13))
        top.addWidget(self.promo_icon, 0, Qt.AlignVCenter)

        self.title_lbl = QLabel("活动固定积分")
        top.addWidget(self.title_lbl, 0, Qt.AlignVCenter)
        top.addStretch(1)

        self.rule_lbl = QLabel("Flash-Lite 1:1 消费返赠 · 30天有效")
        top.addWidget(self.rule_lbl, 0, Qt.AlignVCenter)
        v.addLayout(top)

        content_row = QHBoxLayout()
        content_row.setSpacing(12)
        content_row.setContentsMargins(4, 0, 4, 2)

        left_col = QVBoxLayout()
        left_col.setSpacing(1)
        self.total_tag = QLabel("总量余额")
        left_col.addWidget(self.total_tag)

        self.total_val = QLabel("0.00")
        left_col.addWidget(self.total_val)
        content_row.addLayout(left_col, 1)

        self.v_line = QFrame()
        self.v_line.setFrameShape(QFrame.VLine)
        self.v_line.setFixedWidth(1)
        content_row.addWidget(self.v_line)

        right_col = QVBoxLayout()
        right_col.setSpacing(1)

        expire_head = QHBoxLayout()
        expire_head.setSpacing(6)
        self.expire_tag = QLabel("最近一次到期")
        expire_head.addWidget(self.expire_tag)

        self.expire_date_badge = QLabel("—")
        expire_head.addWidget(self.expire_date_badge)
        expire_head.addStretch(1)
        right_col.addLayout(expire_head)

        self.expire_val = QLabel("0.00")
        right_col.addWidget(self.expire_val)
        content_row.addLayout(right_col, 1)

        v.addLayout(content_row)

    def set_data(self, total_val, expire_info):
        """设置数据并智能拆分到期日期与到期额度"""
        try:
            fv = float(total_val)
            self.total_val.setText(f"{fv:,.3f}".rstrip("0").rstrip(".") if "." in f"{fv:,.3f}" else f"{fv:,.0f}")
        except Exception:
            self.total_val.setText(str(total_val) if total_val else "0.00")

        exp_s = str(expire_info) if expire_info else "—"
        if " · " in exp_s:
            d_part, _, b_part = exp_s.partition(" · ")
            self.expire_date_badge.setText(d_part.strip())
            try:
                fb = float(b_part)
                self.expire_val.setText(f"{fb:,.4f}".rstrip("0").rstrip(".") if "." in f"{fb:,.4f}" else f"{fb:,.0f}")
            except Exception:
                self.expire_val.setText(b_part.strip())
        else:
            self.expire_date_badge.setText(exp_s)
            self.expire_val.setText("0.00")

    def apply_size(self):
        m = curr_metric()
        is_lg = theme_state.get("window_size") == "large"

        self.title_lbl.setFont(QFont("Microsoft YaHei UI", m["sn_title_pt"], QFont.Bold))
        self.rule_lbl.setFont(QFont("Microsoft YaHei UI", m["sn_sub_pt"]))

        lbl_pt = 8.5 if not is_lg else 9.0
        val_pt = 13.0 if not is_lg else 15.0
        badge_pt = 8.0 if not is_lg else 8.5

        self.total_tag.setFont(QFont("Microsoft YaHei UI", lbl_pt))
        self.expire_tag.setFont(QFont("Microsoft YaHei UI", lbl_pt))
        self.expire_date_badge.setFont(QFont("Consolas", badge_pt, QFont.Bold))

        self.total_val.setFont(QFont("Consolas", val_pt, QFont.Bold))
        self.expire_val.setFont(QFont("Consolas", val_pt, QFont.Bold))
        self.update()

    def apply_theme(self):
        dark = theme_state["dark"]
        accent = SN_PURPLE_DARK if dark else SN_PURPLE
        border = qrgba(BORDER)

        self.setStyleSheet("#sn_promo_card { background:transparent; border:none; }")

        self.title_lbl.setStyleSheet(f"color:{qname(TEXT)};")
        self.rule_lbl.setStyleSheet(f"color:{qname(TEXT3)};")

        self.total_tag.setStyleSheet(f"color:{qname(TEXT3)}; font-weight:500;")
        self.expire_tag.setStyleSheet(f"color:{qname(TEXT3)}; font-weight:500;")

        self.total_val.setStyleSheet(f"color:{qname(TEXT)};")
        self.expire_val.setStyleSheet(f"color:{qname(accent)};")

        badge_bg = "rgba(245, 158, 11, 0.22)" if dark else "rgba(245, 158, 11, 0.16)"
        badge_text = "#fbbf24" if dark else "#b45309"
        self.expire_date_badge.setStyleSheet(
            f"background:{badge_bg}; color:{badge_text}; border-radius:4px; padding:1px 6px;")

        self.v_line.setStyleSheet(f"background:{border};")
        self.apply_size()
        self.update()


class SNSyncPanel(GlassPodFrame):
    """商汤同步面板: 分段切换「账号密码(自动登录) / 手动 cURL(兜底)」"""
    saved = Signal()
    cleared = Signal()
    save_finished = Signal(bool, str)
    account_saved = Signal()

    def __init__(self, parent=None):
        super().__init__(radius=12, parent=parent)
        self.setObjectName("sn_sync_panel")
        self._status_mode = "none"
        self._status_msg = "未配置自动同步"
        self._sync_test = False
        self._seg = "account"
        self.save_finished.connect(self._on_save_finished)
        self._build_ui()
        self._load_account()
        self.apply_theme()

    def _seg_btn(self, text):
        b = QPushButton(text)
        b.setCheckable(True)
        b.setCursor(Qt.PointingHandCursor)
        return b

    def _build_ui(self):
        v = QVBoxLayout(self)
        v.setContentsMargins(16, 8, 16, 8)
        v.setSpacing(7)

        # 顶栏: 小细条 + 标题 + 状态徽标
        head = QHBoxLayout()
        head.setSpacing(8)
        self.bar_indicator = BarIndicator(QColor("#3b6fe0"))
        head.addWidget(self.bar_indicator, 0, Qt.AlignVCenter)
        self.title_lbl = QLabel("商汤同步")
        head.addWidget(self.title_lbl, 0, Qt.AlignVCenter)
        self.status_lbl = QLabel("")
        head.addWidget(self.status_lbl, 0, Qt.AlignVCenter)
        head.addStretch(1)
        v.addLayout(head)

        # 分段切换按钮
        seg = QHBoxLayout()
        seg.setSpacing(4)
        self.btn_seg_account = self._seg_btn("🔐 账号密码")
        self.btn_seg_curl = self._seg_btn("📋 手动 cURL")
        self.btn_seg_account.clicked.connect(lambda: self._switch_seg("account"))
        self.btn_seg_curl.clicked.connect(lambda: self._switch_seg("curl"))
        seg.addWidget(self.btn_seg_account)
        seg.addWidget(self.btn_seg_curl)
        v.addLayout(seg)

        # 内容栈
        self.content_stack = QStackedWidget()

        # 页0: 账号密码 (自动登录主路径)
        acc_page = QWidget()
        acc_lay = QVBoxLayout(acc_page)
        acc_lay.setContentsMargins(0, 2, 0, 0)
        acc_lay.setSpacing(6)
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
        acc_lay.addLayout(form)
        brow = QHBoxLayout()
        brow.setSpacing(8)
        self.account_guide = QLabel("仅存本机, 用于凭证过期自动重登")
        brow.addWidget(self.account_guide, 1)
        self.btn_save_account = QPushButton("保存账号")
        self.btn_save_account.setCursor(Qt.PointingHandCursor)
        self.btn_save_account.clicked.connect(self._on_account_save)
        brow.addWidget(self.btn_save_account)
        acc_lay.addLayout(brow)
        self.content_stack.addWidget(acc_page)

        # 页1: 手动 cURL (兜底)
        curl_page = QWidget()
        curl_lay = QVBoxLayout(curl_page)
        curl_lay.setContentsMargins(0, 2, 0, 0)
        curl_lay.setSpacing(6)
        self.curl_edit = QPlainTextEdit()
        self.curl_edit.setPlaceholderText('粘贴 cURL 命令 (curl "https://platform.sensenova.cn/lite/console/...")')
        self.curl_edit.setFixedHeight(52)
        curl_lay.addWidget(self.curl_edit)
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
        curl_lay.addLayout(row)
        self.content_stack.addWidget(curl_page)

        v.addWidget(self.content_stack)

        self._switch_seg("account")

    def apply_size(self):
        m = curr_metric()
        self.title_lbl.setFont(QFont("Microsoft YaHei UI", m["sn_title_pt"], QFont.Bold))
        self.status_lbl.setFont(QFont("Microsoft YaHei UI", m["sn_sub_pt"], QFont.Bold))
        self.account_guide.setFont(QFont("Microsoft YaHei UI", m["sn_sub_pt"]))
        self.err_lbl.setFont(QFont("Microsoft YaHei UI", m["sn_sub_pt"]))
        self.user_tag.setFont(QFont("Microsoft YaHei UI", m["sn_sub_pt"]))
        self.pwd_tag.setFont(QFont("Microsoft YaHei UI", m["sn_sub_pt"]))
        self.user_edit.setFixedHeight(32)
        self.pwd_edit.setFixedHeight(32)
        self.btn_show.setFixedHeight(32)
        self.btn_show.setFixedWidth(44)
        self.curl_edit.setFixedHeight(52)
        self.btn_clear.setFixedHeight(m["opt_btn_h"])
        self.btn_save.setFixedHeight(m["opt_btn_h"])
        self.btn_save_account.setFixedHeight(m["opt_btn_h"])
        for b in (self.btn_seg_account, self.btn_seg_curl):
            b.setFixedHeight(m["opt_btn_h"])
        self.update()

    def set_status(self, s):
        if s.get("autosync_error"):
            self._status_mode = "error"
            self._status_msg = f"⚠ {s['autosync_error'][:26]}"
            # 同步失败时补上"上次成功时间", 让人一眼分清"数据是新的但拉取失败"与"从没成功过"
            if s.get("last_ok_time"):
                self._status_msg += f" · 上次成功 {s['last_ok_time']}"
        elif s.get("sync_src") == "auto":
            self._status_mode = "success"
            t = s.get("sync_time", time.strftime("%H:%M"))
            self._status_msg = f"✓ 自动同步 {t}"
        else:
            self._status_mode = "none"
            self._status_msg = "未配置自动同步"
        self.status_lbl.setToolTip(str(s.get("autosync_error") or ""))
        self.apply_theme()

    def set_syncing(self, msg="正在同步积分…"):
        self._status_mode = "syncing"
        self._status_msg = f"⟳ {msg}"
        self.status_lbl.setToolTip("")
        self.apply_theme()

    def set_failed(self, msg):
        """扫描失败/超时时强制把面板从 syncing 态拉回来。

        原实现失败路径只改副标题, 面板会永久停在「⟳ 正在自动获取凭证并同步…」——
        看起来就是"点了没反应/一直转圈"。
        """
        self._status_mode = "error"
        self._status_msg = f"⚠ {str(msg)[:26]}"
        self.status_lbl.setToolTip(str(msg))
        self.apply_theme()

    def _switch_seg(self, which):
        self._seg = which
        self.btn_seg_account.setChecked(which == "account")
        self.btn_seg_curl.setChecked(which == "curl")
        self.content_stack.setCurrentIndex(0 if which == "account" else 1)
        self._apply_seg_style()

    def _apply_seg_style(self):
        m = curr_metric()
        checked = ("QPushButton{ background:#3b6fe0; color:white; border:none; border-radius:6px;"
                   f" padding:4px 12px; font-size:{m['opt_btn_px']}px; font-weight:600; }}")
        normal = (f"QPushButton{{ background:{qrgba(TRACK)}; color:{qname(TEXT2)};"
                  f" border:1px solid {qrgba(BORDER)}; border-radius:6px;"
                  f" padding:4px 12px; font-size:{m['opt_btn_px']}px; }}"
                  f"QPushButton:hover{{ background:{qrgba(HOVER)}; color:{qname(TEXT)}; }}")
        for b in (self.btn_seg_account, self.btn_seg_curl):
            b.setStyleSheet(checked if b.isChecked() else normal)

    def _toggle_pwd(self):
        if self.btn_show.isChecked():
            self.pwd_edit.setEchoMode(QLineEdit.Normal)
            self.btn_show.setText("隐藏")
        else:
            self.pwd_edit.setEchoMode(QLineEdit.Password)
            self.btn_show.setText("显示")

    def _load_account(self):
        username, password = _sn_account_credentials()
        self.user_edit.setText(username)
        self.pwd_edit.setText(password)

    def _on_account_save(self):
        username = self.user_edit.text().strip()
        password = self.pwd_edit.text()
        if not username or not password:
            self.account_guide.setText("请填写账号和密码")
            self.account_guide.setStyleSheet("color:#e05252;")
            return
        try:
            b64 = base64.b64encode(password.encode("utf-8")).decode("ascii")
            with open(SN_ACCOUNT_FILE, "w", encoding="utf-8") as f:
                json.dump({"username": username, "password_b64": b64}, f, ensure_ascii=False)
        except Exception as e:
            self.account_guide.setText(f"保存失败: {str(e)[:30]}")
            self.account_guide.setStyleSheet("color:#e05252;")
            return
        self.account_guide.setText("✓ 已保存")
        self.account_guide.setStyleSheet("color:#34d399;")
        self.account_saved.emit()

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
        self._set_busy(True, "同步中…")

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

    def _set_busy(self, busy, label="保存并同步"):
        """忙碌态: 按钮禁用 + 文案变化 (原实现只是静默 disable, 视觉上看不出被点过)"""
        self.btn_save.setEnabled(not busy)
        self.btn_clear.setEnabled(not busy)
        self.btn_save.setText(label if busy else "保存并同步")

    def _on_save_finished(self, ok, msg):
        self._set_busy(False)
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
            f"QLineEdit {{ background:{qrgba(TRACK)}; color:{text}; border:1px solid {border};"
            f" border-radius:6px; padding:5px 8px; font-size:{m['opt_btn_px']}px; }}"
            f"QLineEdit:focus {{ border:1px solid #3b6fe0; }}"
        )
        self.title_lbl.setStyleSheet(f"color:{text};")
        self.account_guide.setStyleSheet(f"color:{text3};")
        self.user_tag.setStyleSheet(f"color:{text2};")
        self.pwd_tag.setStyleSheet(f"color:{text2};")
        self._apply_seg_style()

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
            f"QPushButton:hover{{ background:{qrgba(HOVER)}; color:{text}; }}"
            f"QPushButton:disabled{{ color:{text3}; border-color:{border}; }}")
        self.btn_save.setStyleSheet(
            "QPushButton{ background:#3b6fe0; color:white; border:none; border-radius:6px;"
            f" padding:4px 16px; font-size:{m['opt_btn_px']}px; font-weight:600; }}"
            "QPushButton:hover{ background:#2f5ec4; }"
            "QPushButton:disabled{ background:#7c8aa5; color:#e6e9f0; }")
        self.btn_show.setStyleSheet(
            f"QPushButton{{ background:transparent; color:{text3}; border:none;"
            f" border-radius:6px; font-size:{m['sn_sub_pt']}px; padding:0 6px; }}"
            f"QPushButton:hover{{ color:#3b6fe0; }}"
            "QPushButton:checked{ color:#3b6fe0; font-weight:600; }")
        self.btn_save_account.setStyleSheet(
            "QPushButton{ background:#3b6fe0; color:white; border:none; border-radius:6px;"
            f" padding:4px 16px; font-size:{m['opt_btn_px']}px; font-weight:600; }}"
            "QPushButton:hover{ background:#2f5ec4; }")
        self.apply_size()
        self.update()


class SNQuotaPage(QWidget):
    """商汤日日新展示页: 视觉风格高度收敛统驭，精致美观不花哨"""
    saved = Signal()
    cleared = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(10)

        # 1. 左右对称双积分池 (额度文字加大醒目)
        # update 2026-09-20 (第57轮): 两张卡改为**常驻** —— 数据/凭证未就绪时用
        # 「默认满额占位」(见 _default_sn_pools), 不再退化成一段文字等待加载。
        self.pools_layout = QHBoxLayout()
        self.pools_layout.setSpacing(10)
        v.addLayout(self.pools_layout)
        self._pools_placeholder = True

        # 2. 活动固定积分卡片 (双列平衡排版)
        self.promo_card = SNPromoCard()
        self.promo_bar = self.promo_card
        v.addWidget(self.promo_card)

        # 3. 商汤同步面板 (账号密码 + 手动 cURL 分段)
        self.sync_panel = SNSyncPanel()
        self.sync_panel.saved.connect(self.saved)
        self.sync_panel.cleared.connect(self.cleared)
        self.sync_panel.account_saved.connect(self._on_account_saved)
        v.addWidget(self.sync_panel)

        # 4. 状态提示行 (原先占据积分卡的位置, 第57轮按浅猫要求挪到页面底部)
        self.hint_lbl = QLabel(
            "尚未获取商汤额度数据，上方两张卡片显示的是官方公测期默认满额额度；"
            "在「商汤同步」面板粘贴官网 cURL 即可开启实时自动同步。")
        self.hint_lbl.setWordWrap(True)
        self.hint_lbl.hide()
        v.addWidget(self.hint_lbl)

        # 5. 底部微型注释
        self.foot_lbl = QLabel("注: 上限为官方公开的公测期固定额度 (60,000/5h · 600,000/周)；数据均以控制台实际调用与配额为准。")
        self.foot_lbl.setStyleSheet(f"color:{qname(TEXT3)};")
        v.addWidget(self.foot_lbl)

        v.addStretch(1)

    def apply_size(self):
        m = curr_metric()
        self.foot_lbl.setFont(QFont("Microsoft YaHei UI", m["sn_date_pt"]))
        self.hint_lbl.setFont(QFont("Microsoft YaHei UI", m["sn_date_pt"]))

        for i in range(self.pools_layout.count()):
            w = self.pools_layout.itemAt(i).widget()
            if isinstance(w, SNPoolCard):
                w.apply_size()
        self.promo_card.apply_size()
        self.sync_panel.apply_size()
        self.update()

    def _on_account_saved(self):
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

        pools = s.get("pools") or []
        by_id = {p.get("id"): p for p in pools if isinstance(p, dict)}

        # update 2026-09-20 (第57轮): 两张积分卡**常驻渲染** —— 缺哪一张就用
        # 「默认满额占位」补齐(_default_sn_pools), 并亮起底部提示行说明是占位数据;
        # 数据到齐后提示行自动隐藏。这样首次打开(凭证还在加载)时卡片就已就位,
        # 不会出现"先一段文字、稍后卡片才长出来"的跳变。
        missing = [pid for pid in ("general", "flash_lite") if not by_id.get(pid)]
        if missing:
            for p in _default_sn_pools():
                if p["id"] in missing:
                    by_id[p["id"]] = p

        for pid in ("general", "flash_lite"):
            _card = SNPoolCard(by_id[pid])
            _card.rule = False      # 两张池卡并排 = 一组, 不各画分区线 (第60轮)
            self.pools_layout.addWidget(_card, 1)

        promo = by_id.get("promo")
        if promo:
            self.promo_card.set_data(promo.get("total_balance", 0),
                                     promo.get("nearest_expire", "—"))
        else:
            self.promo_card.set_data(0, "—")

        self._pools_placeholder = bool(missing)
        self.hint_lbl.setVisible(self._pools_placeholder)

        self.sync_panel.set_status(s)
        self.apply_theme()

    def apply_theme(self):
        self.foot_lbl.setStyleSheet(f"color:{qname(TEXT3)};")
        # update 2026-09-20 (第57轮): 底部状态提示行 —— 与脚注同色系, 占位时显示。
        self.hint_lbl.setStyleSheet(f"color:{qname(TEXT3)};")

        for i in range(self.pools_layout.count()):
            w = self.pools_layout.itemAt(i).widget()
            if isinstance(w, SNPoolCard):
                w.apply_theme()

        self.promo_card.apply_theme()
        self.sync_panel.apply_theme()
        self.apply_size()

# ============================================================ 多机数据源页 (2026-09-19 第50轮)
# 第51轮视觉重做: 机器行改双列信息卡 + 来源胶囊徽标 + 图标态操作按钮;
#               按机统计改自绘排行条; 页面整体走「面板头 / 内容」统一栅格。
SRC_META = {
    "wb": ("WorkBuddy", QColor("#3b6fe0")),
    "dsh": ("DSH", QColor("#7c67ff")),
}

# 按机统计列的几何常量 (绘制与列头共用, 保证像素级对齐)
# update 2026-09-20 (第59轮): 新增右栏「环形占比圈」——
#   ring_w = 右栏总宽; 左栏内容一律按 (w - ring_w) 布局, 两栏之间在 ring_w 处画细竖线分隔。
RANK_COL = dict(rank_x=6.0, rank_d=18.0, name_x=32.0, name_w=132.0, bar_gap=10.0,
                right_pad=6.0, tot_w=110.0, req_w=74.0, day_w=158.0,
                ring_w=104.0)


class SrcBadge(QWidget):
    """来源胶囊徽标: 圆点 + 文字, 自绘圆角底 (替代原来的纯文本 ' · ' 拼接)"""

    def __init__(self, srcs, parent=None):
        super().__init__(parent)
        self.srcs = list(srcs or [])
        m = curr_metric()
        self.setFixedHeight(m["sn_date_pt"] + 12)
        self._font = QFont("Microsoft YaHei UI", m["sn_date_pt"] + 0.2)
        p = QPainter(self)
        p.setFont(self._font)
        fm = p.fontMetrics()
        w = 0
        for s in self.srcs:
            label = SRC_META.get(s, (s.upper(), GRAY))[0]
            w += 9 + fm.horizontalAdvance(label) + 12
        self.setFixedWidth(max(24, w))
        p.end()

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setFont(self._font)
        fm = p.fontMetrics()
        h = self.height()
        x = 0.0
        dark = theme_state["dark"]
        for s in self.srcs:
            label, col = SRC_META.get(s, (s.upper(), GRAY))
            tw = fm.horizontalAdvance(label)
            cw = 9 + tw + 12
            bg = QColor(col)
            bg.setAlpha(64 if dark else 28)
            p.setPen(Qt.NoPen)
            p.setBrush(bg)
            p.drawRoundedRect(QRectF(x, 0.5, cw, h - 1.0), (h - 1.0) / 2.0, (h - 1.0) / 2.0)
            p.setBrush(col)
            p.drawEllipse(QRectF(x + 5.5, h / 2.0 - 2.0, 4.0, 4.0))
            p.setPen(col.lighter(125) if dark else col)
            p.drawText(QRectF(x + 13.5, 0, tw + 2, h), Qt.AlignLeft | Qt.AlignVCenter, label)
            x += cw + 5


class MachineRow(QWidget):
    """别机列表中的一行: 机器名 / 来源徽标 / token 总量 / 请求 / 日期跨度 + 操作。

    2026-09-19 第52轮修复: 原来继承 GlassPodFrame —— 但父级 peer_card 本身就是
    GlassPodFrame, **两层玻璃底叠加**后内层明显比外层深/亮, 暗色模式下尤其突兀
    (外壳浅灰、内层近黑), 这正是浅猫反馈的"统计里面的框框没适配暗色模式"。
    现改为普通 QWidget, 自己只画一层**中性浅底 + 细描边**, 与外壳形成清晰层级,
    明暗两套主题都只看全局调色板, 不再叠加玻璃透明度。
    """

    remove = Signal(str)
    replace = Signal(str)

    def __init__(self, item, parent=None):
        super().__init__(parent)
        self.item = item
        self.machine = item.get("machine", "")
        self._hover = False
        self.setMouseTracking(True)
        self._build_ui()
        self.apply_theme()

    def enterEvent(self, ev):
        self._hover = True
        self.update()

    def leaveEvent(self, ev):
        self._hover = False
        self.update()

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        dark = theme_state["dark"]
        # 毛玻璃模式 (第60轮): 列表行不再画成"卡片块", 只在 hover 时给一层极淡高亮
        if theme_state.get("frost"):
            if self._hover:
                hv = QColor(HOVER)
                hv.setAlpha(150 if dark else 190)
                p.setPen(Qt.NoPen)
                p.setBrush(hv)
                p.drawRoundedRect(QRectF(0.5, 0.5, w - 1.0, h - 1.0), 10, 10)
            return
        base = QColor(HOVER) if self._hover else QColor(ZEBRA)
        base.setAlpha(235 if dark else 255)
        p.setPen(Qt.NoPen)
        p.setBrush(base)
        p.drawRoundedRect(QRectF(0.5, 0.5, w - 1.0, h - 1.0), 10, 10)
        bd = QColor(BORDER)
        bd.setAlpha(190 if dark else 255)
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(bd, 1.0))
        p.drawRoundedRect(QRectF(0.5, 0.5, w - 1.0, h - 1.0), 10, 10)

    def _build_ui(self):
        v = QVBoxLayout(self)
        v.setContentsMargins(13, 9, 13, 9)
        v.setSpacing(7)

        # ---- 顶行: 指示条 + 机器名 ............... 总量 + tokens
        top = QHBoxLayout()
        top.setSpacing(8)
        self.bar = BarIndicator(PURPLE)
        top.addWidget(self.bar, 0, Qt.AlignVCenter)

        self.name_lbl = QLabel(self.machine)
        self.name_lbl.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.name_lbl.setMinimumWidth(40)
        top.addWidget(self.name_lbl, 1)

        # 来源徽标 (单列通栏后可与名字同行, 不再单独占一行)
        self.badge = SrcBadge(self.item.get("sources") or [])
        top.addWidget(self.badge, 0, Qt.AlignVCenter)

        dig = self.item.get("digest") or {}
        self.total_lbl = QLabel(fmt_full(dig.get("total_tokens", 0)))
        top.addWidget(self.total_lbl, 0, Qt.AlignVCenter)
        self.unit_lbl = QLabel("tokens")
        self.unit_lbl.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
        top.addWidget(self.unit_lbl, 0, Qt.AlignVCenter)
        v.addLayout(top)

        # ---- 底行: 元信息 ...... 操作按钮组 (单列后同一行放得下)
        bot = QHBoxLayout()
        bot.setSpacing(6)
        self.meta_lbl = QLabel(self._meta_text(dig))
        self.meta_lbl.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.meta_lbl.setMinimumWidth(60)
        self.meta_lbl.setToolTip(self._meta_text(dig))
        bot.addWidget(self.meta_lbl, 1)

        self.btn_replace = make_btn("ghost", "覆盖更新")
        self.btn_replace.setToolTip("用新数据包覆盖这台机器的旧快照")
        self.btn_replace.clicked.connect(lambda: self.replace.emit(self.machine))
        bot.addWidget(self.btn_replace, 0, Qt.AlignVCenter)

        self.btn_remove = make_btn("danger", "删除")
        self.btn_remove.setToolTip("删除本机保存的这台机器的快照")
        self.btn_remove.clicked.connect(lambda: self.remove.emit(self.machine))
        bot.addWidget(self.btn_remove, 0, Qt.AlignVCenter)
        v.addLayout(bot)

    def _meta_text(self, dig):
        return (f"{dig.get('requests', 0):,} 请求  ·  "
                f"{dig.get('first_day', '—') or '—'} ~ {dig.get('last_day', '—') or '—'}")

    @staticmethod
    def _short_time(s):
        s = str(s or "")
        return s.replace("T", " ")[5:16] if len(s) >= 16 else (s or "—")

    def apply_size(self):
        m = curr_metric()
        self.name_lbl.setFont(QFont("Microsoft YaHei UI", m["row_pt"] + 0.8, QFont.Bold))
        self.total_lbl.setFont(QFont("Consolas", m["row_pt"] + 1.4, QFont.Bold))
        for w, pt in ((self.meta_lbl, m["row_head_pt"] - 0.6), (self.unit_lbl, m["sn_date_pt"])):
            w.setFont(QFont("Microsoft YaHei UI", pt))
        bh = m["row_h"] - 6
        for b in (self.btn_replace, self.btn_remove):
            b.setFixedHeight(bh)
            style_btn(b, None, pt=m["sn_sub_pt"] - 0.6, height=bh)
        self.badge.update()
        self.update()

    def apply_theme(self):
        self.name_lbl.setStyleSheet(f"color:{qname(TEXT)};")
        self.total_lbl.setStyleSheet(f"color:{qname(BLUE)};")
        self.meta_lbl.setStyleSheet(f"color:{qname(TEXT3)};")
        self.unit_lbl.setStyleSheet(f"color:{qname(TEXT3)}; margin-right:2px;")
        style_btn(self.btn_replace, "ghost")
        style_btn(self.btn_remove, "danger")
        self.update()


class StatRankRow(QWidget):
    """按机统计的一行 (第51轮视觉重做 / 第59轮改为双栏)

    布局为**双栏** (浅猫第59轮: "改成双栏的, 中间用细线隔开, 左边还是之前的呈现方式,
    右边是环形占比圈"):

      ┌───────────────────────────────┬──────────┐
      │ ① 机器名 (+本机圆点)   Token 总量 │          │
      │ ── 用量占比条 (相对最大机器) ──── │  ◯ 占比%  │  ← 环形占比圈 (对总量真实占比)
      │ 请求数 · 数据区间               │          │
      └───────────────────────────────┴──────────┘
                    左栏(原有)          细竖线      右栏(环形)

    · 左栏: 与第51轮完全一致 —— 名次徽标 / 机器名 / Token 总量 / 占比条 / 请求·区间;
      只是可用宽度收窄为 `w - RANK_COL["ring_w"]`。
    · 右栏: **环形占比圈** —— 弧长 = 本机占全部机器总量的比例, 圆心写百分比。
      注意两条"占比"口径不同且互补: 左栏的条是**相对最大机器**归一(排行用),
      右栏的环是**占总量**的真实百分比(份额用)。
    · `metric` 决定取哪一口径: "total"(总量) 或 "today"(今日)。

    @2026-09-19 第53轮: 新增 `placeholder` 骨架态 —— 首次进入多机页时完整合并
    数据要等后台 scan 回来(约 100ms), 旧实现这段时间是「空态文案」, 数据到位后
    整列统计条突然长出来, 观感就是浅猫说的「刷的一下出来」。骨架态用同样行高
    画一条暗淡占位条, 让首帧就有稳定骨架, 数据到位后原地替换不再跳变。
    """

    def __init__(self, rank, machine, d, mx, is_local, parent=None, placeholder=False,
                 grand_total=None, metric="total"):
        super().__init__(parent)
        self.rank = rank
        self.machine = machine
        # ⚠️ 属性名**不能**叫 `metric` —— QWidget 有虚函数 QPaintDevice::metric(),
        #    PySide6 会去取 self.metric 当覆写调用, 赋成字符串会在构造 QPainter 时
        #    抛 "Error calling Python override of QWidget::metric(): 'str' object is
        #    not callable" → 进程直接 abort (2026-09-20 踩到, 排查了一整轮)。
        self.stat_metric = metric or "total"
        # update 2026-09-20 (第59轮): 双口径 —— value 按 stat_metric 取, share 对 grand_total 求。
        self.total = int(d.get(self.stat_metric, 0) or 0)
        self.mx = mx or 1
        self.grand_total = int(grand_total or 0)
        self.share = (self.total / self.grand_total) if self.grand_total else 0.0
        self.is_local = is_local
        self.placeholder = placeholder
        self.requests = d.get("requests", 0)
        self.first_day = d.get("firstDay", "") or "—"
        self.last_day = d.get("lastDay", "") or "—"
        self.by_source = d.get("bySource") or {}
        self._hover = False
        self.setMouseTracking(True)
        m = curr_metric()
        self.ROW_TOP_H = 20.0
        self.BAR_Y = 35.0
        self.BAR_H = 7.0
        self.FOOT_Y = 48.0
        self.setFixedHeight(int(self.FOOT_Y + m["sn_date_pt"] + 14))

    def enterEvent(self, ev):
        # 骨架态不响应 hover (还没有真实内容可强调)
        if self.placeholder:
            return
        self._hover = True
        self.update()

    def leaveEvent(self, ev):
        if self.placeholder:
            return
        self._hover = False
        self.update()

    def paintEvent(self, ev):
        if self.placeholder:
            self._paint_placeholder(ev)
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        m = curr_metric()
        dark = theme_state["dark"]
        C = RANK_COL
        # 左栏可用宽度: 右栏固定让给环形占比圈
        lw = max(120.0, w - C["ring_w"])

        if self._hover:
            hv = QColor(HOVER)
            hv.setAlpha(190)
            p.setPen(Qt.NoPen)
            p.setBrush(hv)
            p.drawRoundedRect(QRectF(0.5, 0.5, w - 1.0, h - 1.0), 9, 9)
        else:
            # 轻斑马纹底: 让每一行读起来像独立的「框」, 暗色下也保持层级可辨。
            # 毛玻璃模式下不画 (第60轮): 否则又在"细线分区"上长出一张张小卡片。
            if not theme_state.get("frost"):
                zb = QColor(ZEBRA if self.rank % 2 == 0 else CARD)
                zb.setAlpha(150 if dark else (255 if self.rank % 2 == 0 else 0))
                if zb.alpha() > 0:
                    p.setPen(Qt.NoPen)
                    p.setBrush(zb)
                    p.drawRoundedRect(QRectF(0.5, 0.5, w - 1.0, h - 1.0), 9, 9)

        # ================= 双栏之间的细竖线 (第59轮)
        sep = QColor(BORDER)
        sep.setAlpha(170 if dark else 200)
        p.setPen(QPen(sep, 1.0))
        p.drawLine(QPointF(lw + 0.5, 7.0), QPointF(lw + 0.5, h - 7.0))

        # ================= 左栏 · 上行: 名次 + 机器名 ......... Token 总量
        top_y = 8.0
        top_h = self.ROW_TOP_H
        cy = top_y + top_h / 2.0

        rank_col = QColor("#d6a72c") if self.rank == 1 else (
            QColor("#9aa3b2") if self.rank == 2 else (
                QColor("#c08a5e") if self.rank == 3 else QColor(TEXT3)))
        p.setPen(Qt.NoPen)
        p.setBrush(rank_col)
        p.drawEllipse(QRectF(C["rank_x"], cy - C["rank_d"] / 2.0, C["rank_d"], C["rank_d"]))
        p.setPen(QColor("#ffffff"))
        p.setFont(QFont("Consolas", m["sn_date_pt"] + 0.2, QFont.Bold))
        p.drawText(QRectF(C["rank_x"], cy - C["rank_d"] / 2.0, C["rank_d"], C["rank_d"]),
                   Qt.AlignCenter, str(self.rank))

        # 机器名 (超长省略, 不侵入右侧总量)
        p.setFont(QFont("Microsoft YaHei UI", m["row_pt"], QFont.Bold if self.is_local else QFont.Normal))
        p.setPen(QColor(BLUE) if self.is_local else QColor(TEXT))
        name_res = lw - C["name_x"] - C["tot_w"] - 30
        nm = p.fontMetrics().elidedText(self.machine, Qt.ElideRight, int(max(40, name_res)))
        p.drawText(QRectF(C["name_x"], top_y, name_res, top_h),
                   Qt.AlignLeft | Qt.AlignVCenter, nm)
        if self.is_local:
            tw = p.fontMetrics().horizontalAdvance(nm)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(BLUE))
            p.drawEllipse(QRectF(C["name_x"] + tw + 6, cy - 2.5, 5, 5))

        # 数值 (右, 等宽加粗) —— 今日模式下即"今日用量"
        p.setFont(QFont("Consolas", m["row_pt"] + 1.6, QFont.Bold))
        p.setPen(QColor(TEXT))
        p.drawText(QRectF(lw - C["tot_w"] - C["right_pad"], top_y, C["tot_w"], top_h),
                   Qt.AlignRight | Qt.AlignVCenter, fmt_full(self.total))

        # ================= 左栏 · 中行: 用量占比条 (相对最大机器)
        bar_x = C["name_x"]
        bar_w = max(60.0, lw - bar_x - C["right_pad"])
        bh = self.BAR_H
        by = self.BAR_Y
        tr = QColor(TRACK)
        tr.setAlpha(235)
        p.setPen(Qt.NoPen)
        p.setBrush(tr)
        p.drawRoundedRect(QRectF(bar_x, by, bar_w, bh), bh / 2, bh / 2)

        ratio = max(0.0, min(1.0, self.total / self.mx)) if self.mx else 0.0
        fw = bar_w * ratio
        if fw > 1.5:
            grad = QLinearGradient(bar_x, 0, bar_x + fw, 0)
            c0 = QColor(BLUE) if self.is_local else QColor(PURPLE)
            c1 = QColor(c0)
            c1.setAlpha(150 if dark else 190)
            grad.setColorAt(0.0, c0)
            grad.setColorAt(1.0, c1)
            p.setBrush(QBrush(grad))
            p.drawRoundedRect(QRectF(bar_x, by, fw, bh), bh / 2, bh / 2)

        # ================= 左栏 · 底行: 请求 / 区间
        foot_y = self.FOOT_Y
        foot_h = h - foot_y - 3.0
        p.setFont(QFont("Microsoft YaHei UI", m["sn_date_pt"] - 0.2))
        p.setPen(QColor(TEXT3))
        p.drawText(QRectF(bar_x, foot_y, lw - bar_x - C["right_pad"], foot_h),
                   Qt.AlignLeft | Qt.AlignTop,
                   f"{self.requests:,} 请求   ·   {self.first_day} ~ {self.last_day}")

        # ================= 右栏: 环形占比圈
        self._paint_ring(p, lw, w, h, m)

    def _paint_ring(self, p, lw, w, h, m):
        """环形占比圈 (第59轮新增): 弧长 = 本机占**全部机器总量**的比例, 圆心写百分比。

        用两段同心圆弧实现: 底环(TRACK) 铺满整圈 + 前景弧(本机蓝 / 别机紫)按占比画。
        Qt 的 drawArc 角度以 3 点方向为 0°、**逆时针为正**, 所以起点取 90°(12 点方向),
        跨度取负值(顺时针增长)才符合"从顶部顺时针填充"的直觉。
        """
        C = RANK_COL
        cx = lw + C["ring_w"] / 2.0
        cy = h / 2.0 - 1.0
        th = 6.0                                    # 圈线粗细
        ro = min(21.0, (C["ring_w"] - 18.0) / 2.0)  # 外半径
        rr = ro - th / 2.0                          # 描边中心线半径
        rect = QRectF(cx - rr, cy - rr, rr * 2.0, rr * 2.0)

        p.setBrush(Qt.NoBrush)
        tr = QColor(TRACK)
        tr.setAlpha(235)
        p.setPen(QPen(tr, th, Qt.SolidLine, Qt.FlatCap))
        p.drawArc(rect, 0, 360 * 16)

        accent = QColor(BLUE) if self.is_local else QColor(PURPLE)
        if self.share > 0.001:
            # 满圈(360°)会被 Qt 当成"不画", 故夹到 359.9° (=5759/16)
            span = -int(360 * 16 * min(1.0, self.share))
            span = max(span, -5759)
            p.setPen(QPen(accent, th, Qt.SolidLine, Qt.FlatCap))
            p.drawArc(rect, 90 * 16, span)

        p.setFont(QFont("Consolas", m["sn_date_pt"] + 0.6, QFont.Bold))
        p.setPen(accent)
        pct = self.share * 100.0
        txt = f"{pct:.0f}%" if pct >= 10.0 else f"{pct:.1f}%"
        p.drawText(rect, Qt.AlignCenter, txt)

    def _paint_placeholder(self, ev):
        """骨架占位: 与真实行**同高同结构**, 只把内容换成暗淡色块。

        @2026-09-19 第53轮新增。目的不是"转圈提示", 而是让首帧与数据到位后的
        帧在**几何上完全一致** —— 用户看不到"从无到有"的突增, 只看到占位块被
        真实内容原地替换。色块用 TEXT3 低透明度, 深浅色都自然。
        """
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        C = RANK_COL

        base = QColor(ZEBRA if self.rank % 2 == 0 else CARD)
        base.setAlpha(150 if theme_state["dark"] else (255 if self.rank % 2 == 0 else 0))
        # 毛玻璃模式: 骨架行同样不画底 (第60轮)
        if base.alpha() > 0 and not theme_state.get("frost"):
            p.setPen(Qt.NoPen)
            p.setBrush(base)
            p.drawRoundedRect(QRectF(0.5, 0.5, w - 1.0, h - 1.0), 9, 9)

        lw = max(120.0, w - C["ring_w"])

        # 双栏之间的细竖线 (与真实行同位置, 保证骨架→数据不跳变)
        sep = QColor(BORDER)
        sep.setAlpha(170 if theme_state["dark"] else 200)
        p.setPen(QPen(sep, 1.0))
        p.drawLine(QPointF(lw + 0.5, 7.0), QPointF(lw + 0.5, h - 7.0))

        sk = QColor(TEXT3)
        sk.setAlpha(46 if theme_state["dark"] else 40)
        p.setPen(Qt.NoPen)
        p.setBrush(sk)

        # 上行: 名次圆 + 机器名占位块 (+ 右侧总量占位块)
        cy = 8.0 + self.ROW_TOP_H / 2.0
        p.drawEllipse(QRectF(C["rank_x"], cy - C["rank_d"] / 2.0, C["rank_d"], C["rank_d"]))
        p.drawRoundedRect(QRectF(C["name_x"], cy - 5.0, 84.0, 10.0), 5, 5)
        tw = 68.0
        p.drawRoundedRect(QRectF(lw - C["right_pad"] - tw, cy - 6.0, tw, 12.0), 6, 6)

        # 中行: 占比条占位 (细条, 只用 30% 宽度以示"未填满")
        by, bh = self.BAR_Y, self.BAR_H
        bar_x = C["name_x"]
        avail = max(40.0, lw - bar_x - C["right_pad"])
        p.drawRoundedRect(QRectF(bar_x, by, avail * 0.30, bh), bh / 2, bh / 2)

        # 底行: 请求/区间占位
        fy = self.FOOT_Y
        p.drawRoundedRect(QRectF(bar_x, fy + 2.0, 148.0, 8.0), 4, 4)

        # 右栏: 环形圈占位 (同几何、暗色描边, 让首帧就有"这里是个圈"的骨架)
        cx = lw + C["ring_w"] / 2.0
        rcy = h / 2.0 - 1.0
        ro = min(21.0, (C["ring_w"] - 18.0) / 2.0)
        rr = ro - 3.0
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(sk, 6.0))
        p.drawArc(QRectF(cx - rr, rcy - rr, rr * 2.0, rr * 2.0), 0, 360 * 16)
        p.end()


class MachineBox(QWidget):
    """本机机器框 —— 内联编辑式改名 (2026-09-19 第53轮重做)

    浅猫："改名不需要弹窗，直接在原有名字框就能输入修改然后保存会不会更好？"
    → 把原来「点改名 → 弹模态框 → 输入 → 保存」的三步流程, 改成**框内就地编辑**:
      点「改名」→ 名字原地变输入框 + 出现 保存/取消 → Enter 提交 / Esc 取消。

    实现要点 (踩坑记录):
      - 输入框是**常驻子控件**、平时 hide(), 进入编辑态才 show() 并 setFocus()。
        不要每次新建 QLineEdit, 否则焦点/事件循环时序难控。
      - `_overlay` 为真时 paintEvent **提前 return**: 让子控件完整露出,
        否则自绘的名字文字会跟输入框叠在一起。
      - 保存走 `name_edited` 信号把新名字交给页面, 由页面落盘并刷新。
    """

    rename_requested = Signal()
    name_edited = Signal(str)

    def __init__(self, name="—", parent=None):
        super().__init__(parent)
        self._name = name or "—"
        self._hover = False
        self._rename_rect = QRectF()
        self._saved_rect = QRectF()
        self._cancel_rect = QRectF()
        self._edit_mode = False
        self._edit_hover = ""          # "" / "save" / "cancel"
        self._font = QFont("Microsoft YaHei UI", 9.0, QFont.Bold)
        self._sub_font = QFont("Microsoft YaHei UI", 8.0)
        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        # 常驻输入框 (平时隐藏)
        self._edit = QLineEdit(self)
        self._edit.setObjectName("machine_edit")
        self._edit.hide()
        self._edit.returnPressed.connect(self.commit_edit)
        self._edit.installEventFilter(self)

        self.apply_size()

    # ---------- 名字 ----------
    def set_name(self, name):
        self._name = name or "—"
        self.update()

    def machine_name(self):
        return self._name

    # ---------- 尺寸 / 主题 ----------
    def apply_size(self):
        m = curr_metric()
        self._font = QFont("Microsoft YaHei UI", m["sn_sub_pt"] + 0.2, QFont.Bold)
        self._sub_font = QFont("Microsoft YaHei UI", m["sn_date_pt"] - 0.2)
        h = m["nav_btn_h"] - 2
        self.setFixedHeight(h)
        self._edit.setFixedHeight(h - 8)
        self._edit.setStyleSheet(
            f"QLineEdit#machine_edit{{ background:{qrgba(TRACK)}; color:{qname(TEXT)};"
            f" border:1px solid {qrgba(BORDER)}; border-radius:6px; padding:2px 8px;"
            f" font-size:{m['opt_btn_px']}px; selection-background-color:#3b6fe0;"
            f" selection-color:#ffffff; }}"
            # update 2026-09-20 (第57轮): 边框由「常亮蓝」改为与商汤输入框同源的
            # BORDER 细线 + focus 变蓝 —— 与 _paint_shell 的新配方成一套语言。
            f"QLineEdit#machine_edit:focus{{ border:1px solid #3b6fe0; }}")
        self.update()

    def apply_theme(self):
        self.apply_size()

    # ---------- 编辑态 ----------
    def start_edit(self):
        """进入就地编辑: 输入框覆盖名字区, 右侧「改名」换成 保存/取消。"""
        if self._edit_mode:
            return
        self._edit_mode = True
        # 先算好按钮与输入框几何 —— 命中判定不能等 paintEvent 才建立,
        # 否则"刚进入编辑态就点保存"会因矩形为空而落空。
        self._recalc_edit_btns()
        self._layout_edit()
        self._edit.setText(self._name if self._name != "—" else "")
        self._edit.selectAll()
        self.update()
        self._edit.show()
        self._edit.raise_()
        self._edit.setFocus()

    def cancel_edit(self):
        if not self._edit_mode:
            return
        self._edit_mode = False
        self._edit_hover = ""
        self._edit.hide()
        self.update()

    def commit_edit(self):
        """提交新名字: 去空白后经信号交给页面落盘。名字未变则等同取消。"""
        if not self._edit_mode:
            return
        text = self._edit.text().strip()
        self.cancel_edit()
        if not text or text == self._name:
            return
        self._name = text          # 先本地生效, 页面落盘后再 set_name 覆盖一次即可
        self.update()
        self.name_edited.emit(text)

    # ---------- 交互 ----------
    def eventFilter(self, obj, ev):
        """输入框失焦时自动提交 (点空白处也不会丢改动)。"""
        if obj is self._edit and ev.type() == QEvent.FocusOut:
            if self._edit_mode:
                self.commit_edit()
        return super().eventFilter(obj, ev)

    def enterEvent(self, ev):
        self._hover = True
        self.update()

    def leaveEvent(self, ev):
        self._hover = False
        self._edit_hover = ""
        self.update()

    def keyPressEvent(self, ev):
        if self._edit_mode and ev.key() == Qt.Key_Escape:
            self.cancel_edit()
            ev.accept()
            return
        super().keyPressEvent(ev)

    def resizeEvent(self, ev):
        self._layout_edit()
        super().resizeEvent(ev)

    def mouseMoveEvent(self, ev):
        pos = ev.position()
        was = self._edit_hover
        if self._edit_mode:
            if self._saved_rect.contains(pos):
                self._edit_hover = "save"
            elif self._cancel_rect.contains(pos):
                self._edit_hover = "cancel"
            else:
                self._edit_hover = ""
        else:
            self._edit_hover = ""
        self.setCursor(Qt.PointingHandCursor if (
            self._rename_rect.contains(pos) or self._edit_hover) else Qt.ArrowCursor)
        if was != self._edit_hover:
            self.update()
        super().mouseMoveEvent(ev)

    def mouseReleaseEvent(self, ev):
        if ev.button() != Qt.LeftButton:
            super().mouseReleaseEvent(ev)
            return
        pos = ev.position()
        if self._edit_mode:
            if self._saved_rect.contains(pos):
                self.commit_edit()
                ev.accept()
                return
            if self._cancel_rect.contains(pos):
                self.cancel_edit()
                ev.accept()
                return
        elif self._rename_rect.contains(pos):
            self.rename_requested.emit()
            self.start_edit()
            ev.accept()
            return
        super().mouseReleaseEvent(ev)

    # ---------- 几何 ----------
    def _recalc_rename(self, p):
        """「改名」热区几何: 靠右对齐, 命中判定与绘制共用同一矩形。"""
        p.setFont(self._sub_font)
        tw = p.fontMetrics().horizontalAdvance("改名")
        rw = tw + 16
        self._rename_rect = QRectF(self.width() - rw - 10, 1.0, rw, self.height() - 2.0)

    def _recalc_edit_btns(self):
        """编辑态两个按钮的几何 (保存 / 取消), 靠右排布。"""
        fm = QFontMetrics(self._sub_font)
        w1 = fm.horizontalAdvance("保存") + 18
        w2 = fm.horizontalAdvance("取消") + 18
        h = self.height() - 8.0
        y = 4.0
        x2 = self.width() - w2 - 8.0
        x1 = x2 - w1 - 6.0
        self._saved_rect = QRectF(x1, y, w1, h)
        self._cancel_rect = QRectF(x2, y, w2, h)
        self._name_end_x = x1 - 8.0

    def _layout_edit(self):
        """把输入框摆到「名字」原本占的位置上。"""
        if not hasattr(self, "_edit"):
            return
        self._recalc_edit_btns()
        tx = 32.0
        fm = QFontMetrics(self._sub_font)
        tag_w = fm.horizontalAdvance("本机")
        name_x = tx + tag_w + 7
        w = max(60.0, self._name_end_x - name_x)
        self._edit.setGeometry(int(name_x), 4, int(w), self.height() - 8)

    # ---------- 绘制 ----------
    def paintEvent(self, ev):
        # 编辑态: 让出画面给子控件, 不画自绘文字 (否则与输入框叠字)
        if self._edit_mode:
            p = QPainter(self)
            p.setRenderHint(QPainter.Antialiasing)
            self._paint_shell(p)
            p.end()
            return

        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        self._paint_shell(p)

        # 左: 主机图标 (自绘方屏 + 底座, 避免依赖 emoji 字体)
        cy = h / 2.0
        ic = QColor(BLUE)
        p.setPen(QPen(ic, 1.4))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(QRectF(11.5, cy - 6.0, 13.0, 9.5), 2.0, 2.0)
        p.setPen(Qt.NoPen)
        p.setBrush(ic)
        p.drawRoundedRect(QRectF(16.0, cy + 4.0, 4.0, 1.6), 0.8, 0.8)
        p.drawRoundedRect(QRectF(13.5, cy + 6.0, 9.0, 1.4), 0.7, 0.7)

        # 中: 「本机」小字 + 机器名
        p.setFont(self._sub_font)
        p.setPen(QColor(TEXT3))
        tag = "本机"
        tag_w = p.fontMetrics().horizontalAdvance(tag)
        tx = 32.0
        p.drawText(QRectF(tx, 0, tag_w + 2, h), Qt.AlignLeft | Qt.AlignVCenter, tag)

        self._recalc_rename(p)
        p.setFont(self._font)
        p.setPen(QColor(TEXT))
        name_x = tx + tag_w + 7
        name_w = self._rename_rect.left() - name_x - 8
        nm = p.fontMetrics().elidedText(self._name, Qt.ElideRight, int(max(30, name_w)))
        p.drawText(QRectF(name_x, 0, max(30.0, name_w), h),
                   Qt.AlignLeft | Qt.AlignVCenter, nm)

        # 右: 改名 (hover 高亮, 可点击)
        p.setFont(self._sub_font)
        if self._hover:
            hv = QColor(BLUE)
            hv.setAlpha(30 if theme_state["dark"] else 22)
            p.setPen(Qt.NoPen)
            p.setBrush(hv)
            p.drawRoundedRect(self._rename_rect, 6, 6)
        p.setPen(QColor(BLUE))
        p.drawText(self._rename_rect, Qt.AlignCenter, "改名")
        p.end()

    def _paint_shell(self, p):
        """外壳: 与商汤页输入框同源配方 —— TRACK 填充 + BORDER 细描边。

        update 2026-09-20 (第57轮): 浅猫反馈「多机名字的框框和输入时候的框框边缘
        都有点不清晰, 没有商汤页输密码那个框框清晰」。定位原因:
          原实现用 CARD(近白/近黑) alpha 150~190 填充 + BLUE alpha 90~120 描边 ——
          填充与所在玻璃卡片**几乎同色**(毫无对比), 描边又是低透明度淡蓝,
          于是整体只剩一条若隐若现的线, 自然"边缘不清晰"。
        而商汤页 QLineEdit 清晰的真因是 **TRACK 填充与卡片底形成明度差** +
        BORDER 细描边(不是靠粗/艳的描边)。此处改为同一配方, 两处输入框视觉同源。
        """
        w, h = self.width(), self.height()
        rect = QRectF(0.5, 0.5, w - 1.0, h - 1.0)

        # 毛玻璃模式 (第60轮): 不铺填充, 只留 1px 细描边 —— 像玻璃上画出的一个框
        if theme_state.get("frost"):
            p.setBrush(Qt.NoBrush)
            col = QColor(255, 255, 255, 44) if theme_state["dark"] else QColor(28, 38, 58, 46)
            p.setPen(QPen(col, 1.0))
            p.drawRoundedRect(rect, 9, 9)
            return

        # 填充: TRACK (与卡片底拉开明度差, 这是"看得见是输入框"的主因)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(TRACK))
        p.drawRoundedRect(rect, 9, 9)

        # 描边: BORDER 全不透明 1px 细线 (与商汤输入框同款)
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QColor(BORDER), 1.0))
        p.drawRoundedRect(rect, 9, 9)

        # 编辑态下: 右侧两个按钮 (保存 / 取消) 由自绘负责
        if not self._edit_mode:
            return
        self._recalc_edit_btns()
        for rect, label, key in ((self._saved_rect, "保存", "save"),
                                 (self._cancel_rect, "取消", "cancel")):
            on = self._edit_hover == key
            if key == "save":
                c = QColor(BLUE) if on else QColor(HOVER)
                if on:
                    c = QColor(BLUE).darker(110)
                p.setPen(Qt.NoPen)
                p.setBrush(c)
                p.drawRoundedRect(rect, 6, 6)
                p.setPen(QColor("#ffffff") if on else QColor(BLUE))
            else:
                if on:
                    c = QColor(RED); c.setAlpha(28)
                    p.setPen(Qt.NoPen)
                    p.setBrush(c)
                    p.drawRoundedRect(rect, 6, 6)
                p.setPen(QColor(RED) if on else QColor(TEXT3))
            p.setFont(self._sub_font)
            p.drawText(rect, Qt.AlignCenter, label)

        # 编辑态左侧: 主机图标 + 「本机」小字 (与静态态一致, 保持视觉连续)
        h2 = self.height()
        cy = h2 / 2.0
        ic = QColor(BLUE)
        p.setPen(QPen(ic, 1.4))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(QRectF(11.5, cy - 6.0, 13.0, 9.5), 2.0, 2.0)
        p.setPen(Qt.NoPen)
        p.setBrush(ic)
        p.drawRoundedRect(QRectF(16.0, cy + 4.0, 4.0, 1.6), 0.8, 0.8)
        p.drawRoundedRect(QRectF(13.5, cy + 6.0, 9.0, 1.4), 0.7, 0.7)
        p.setFont(self._sub_font)
        p.setPen(QColor(TEXT3))
        tag = "本机"
        tag_w = p.fontMetrics().horizontalAdvance(tag)
        p.drawText(QRectF(32.0, 0, tag_w + 2, h2), Qt.AlignLeft | Qt.AlignVCenter, tag)


class StatHeaderRow(QWidget):
    """按机统计的列头: 与 StatRankRow 两行式布局对齐 (机器 / Token 总量 + 分隔线)。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(18)

    def apply_size(self):
        m = curr_metric()
        self.setFixedHeight(m["sn_date_pt"] + 10)
        self.update()

    def apply_theme(self):
        self.update()

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        m = curr_metric()
        C = RANK_COL
        lw = max(120.0, w - C["ring_w"])
        p.setFont(QFont("Microsoft YaHei UI", m["sn_date_pt"] - 0.2))
        p.setPen(QColor(TEXT3))
        p.drawText(QRectF(C["name_x"], 0, lw - C["name_x"] - C["tot_w"], h),
                   Qt.AlignLeft | Qt.AlignVCenter, "机器 / 用量占比")
        p.drawText(QRectF(lw - C["tot_w"] - C["right_pad"], 0, C["tot_w"], h),
                   Qt.AlignRight | Qt.AlignVCenter, "Token 总量")
        # update 2026-09-20 (第59轮): 右栏表头 —— 环形圈是"占全部机器总量"的百分比
        p.drawText(QRectF(lw, 0, C["ring_w"], h), Qt.AlignCenter, "占比")

        ln = QColor(BORDER)
        ln.setAlpha(150)
        p.setPen(QPen(ln, 1.0))
        p.drawLine(QPointF(C["rank_x"], h - 0.5), QPointF(w - C["right_pad"], h - 0.5))


class MultiMachinePage(QWidget):
    """多机数据源页: 本机身份 / 导出导入 / 别机列表 / 按机统计对比。"""

    export_requested = Signal()
    import_requested = Signal()
    machine_remove = Signal(str)
    machine_replace = Signal(str)
    machine_rename = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._peers = []
        self._summary = {}
        self._skeleton_n = 0      # 骨架行数: 记住上次真实台数, 让骨架与内容同高
        self._pending = False     # 数据在途标记 (render 时记录, 供切换口径时复用)
        # update 2026-09-20 (第59轮): 按机统计口径 —— "total"(总量) / "today"(今日)
        self._stat_metric = "total"
        self._build_ui()

    def _stat_seg_btn(self, text):
        """按机统计口径的分段按钮 (样式复用商汤同步面板那套)。"""
        b = QPushButton(text)
        b.setCheckable(True)
        b.setCursor(Qt.PointingHandCursor)
        return b

    def _apply_stat_seg_style(self):
        """「今日 / 总量」分段样式 —— 选中实心蓝, 未选中 TRACK 底 + BORDER 细描边。"""
        m = curr_metric()
        checked = ("QPushButton{ background:#3b6fe0; color:white; border:none; border-radius:6px;"
                   f" padding:3px 11px; font-size:{m['opt_btn_px']}px; font-weight:600; }}")
        normal = (f"QPushButton{{ background:{qrgba(TRACK)}; color:{qname(TEXT2)};"
                  f" border:1px solid {qrgba(BORDER)}; border-radius:6px;"
                  f" padding:3px 11px; font-size:{m['opt_btn_px']}px; }}"
                  f"QPushButton:hover{{ background:{qrgba(HOVER)}; color:{qname(TEXT)}; }}")
        for b in (self.btn_stat_today, self.btn_stat_total):
            b.setStyleSheet(checked if b.isChecked() else normal)

    def _switch_stat_metric(self, which):
        """切换 按机统计 口径 (今日 / 总量) —— 只重画统计列表, 不重跑整页。"""
        if which == self._stat_metric:
            return
        self._stat_metric = which
        for b, k in ((self.btn_stat_today, "today"), (self.btn_stat_total, "total")):
            b.setChecked(k == which)
        self._apply_stat_seg_style()
        self._render_stat_rows()
        self.apply_size()

    # ---------- 面板头工厂 (统一「小细条 + 标题 + 右侧说明」语言) ----------
    def _panel_head(self, parent_layout, title, accent, right_text="", extra=None):
        """面板头工厂: [小细条] 标题 …(右侧对齐) [extra...] [说明胶囊]

        update 2026-09-20 (第59轮): 新增 `extra` —— 需要在右侧说明**之前**插入控件
        (按机统计的「今日 / 总量」分段切换) 时用它, 避免各页面各自拼 layout。
        """
        h = QHBoxLayout()
        h.setSpacing(8)
        bar = BarIndicator(accent)
        h.addWidget(bar, 0, Qt.AlignVCenter)
        lbl = QLabel(title)
        h.addWidget(lbl, 0, Qt.AlignVCenter)
        h.addStretch(1)
        for w in (extra or []):
            h.addWidget(w, 0, Qt.AlignVCenter)
        right = None
        if right_text is not None:
            right = QLabel(right_text)
            h.addWidget(right, 0, Qt.AlignVCenter)
        parent_layout.addLayout(h)
        return bar, lbl, right

    def _build_ui(self):
        """多机页布局 (2026-09-19 第52轮重做)

        从「顶部操作卡 + 13:9 双栏」改为**单列纵向三段**, 原因是双栏下:
          · 左栏排行条被拉得极长, 右侧却空出一大块, 横向空间浪费;
          · 右栏过窄, 机器名 + 总量 + 按钮互相挤压, 观感局促;
          · 两块卡片底部各留一大片空白, 高度不齐。
        单列后每段横向铺满, 排行条长度即真实占比, 信息密度更均匀。

        第③段「已导入的机器」按浅猫要求**并入第①段「数据源管理」**:
        机器框在左、导出/导入按钮在右, 导入按钮统一为「导入/更新别机数据」
        (新机器 = 导入, 同名机器 = 覆盖更新, 由 peer_store 的快照语义自动决定)。
        """
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(10)

        # ================= 1. 数据源管理: 左侧机器框 / 右侧导出导入
        self.action_card = GlassPodFrame(radius=12, rule=False)   # 首段: 毛玻璃下不画分区线
        self.action_card.setObjectName("multi_action_card")
        av = QVBoxLayout(self.action_card)
        av.setContentsMargins(16, 13, 16, 13)
        av.setSpacing(10)

        r1 = QHBoxLayout()
        r1.setSpacing(8)
        self.bar_action = BarIndicator(BLUE)
        r1.addWidget(self.bar_action, 0, Qt.AlignVCenter)
        self.title_lbl = QLabel("数据源管理")
        r1.addWidget(self.title_lbl, 0, Qt.AlignVCenter)
        r1.addStretch(1)
        self.peer_count_lbl = QLabel("0 台")
        r1.addWidget(self.peer_count_lbl, 0, Qt.AlignVCenter)
        av.addLayout(r1)

        # ---- 主体行: [本机机器框] ....... [导出] [导入/更新]
        row = QHBoxLayout()
        row.setSpacing(9)

        self.machine_box = MachineBox("—")
        # 就地编辑: 保存时直接抛新名字给页面落盘 (不再走弹窗)
        self.machine_box.name_edited.connect(self.machine_rename.emit)
        row.addWidget(self.machine_box, 1)

        self.btn_export = make_btn("primary", "⬆  导出本机数据")
        self.btn_export.clicked.connect(self.export_requested)
        row.addWidget(self.btn_export, 0, Qt.AlignVCenter)

        self.btn_import = make_btn("primary", "⬇  导入/更新别机数据")
        self.btn_import.setToolTip("选择别机导出的数据包：新机器直接导入，"
                                   "已存在的机器名则覆盖更新其旧数据")
        self.btn_import.clicked.connect(self.import_requested)
        row.addWidget(self.btn_import, 0, Qt.AlignVCenter)
        av.addLayout(row)

        self.hint_lbl = QLabel("导出本机数据（含 WorkBuddy + DSH 两个来源的全部记录）为文件，"
                               "可拷到其他电脑导入；导入不会影响本机数据，按机器名分别存放 —— "
                               "同名机器视为同一台的更新，直接覆盖其旧快照。")
        self.hint_lbl.setWordWrap(True)
        self.hint_lbl.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        av.addWidget(self.hint_lbl)
        v.addWidget(self.action_card)

        # ================= 2. 按机统计 (单列通栏)
        self.stat_card = GlassPodFrame(radius=12)
        self.stat_card.setObjectName("multi_stat_card")
        sv = QVBoxLayout(self.stat_card)
        sv.setContentsMargins(16, 12, 16, 12)
        sv.setSpacing(8)
        # update 2026-09-20 (第59轮): 「今日 / 总量」分段切换 (浅猫: "按机统计也可以切换今日、总量")
        self.btn_stat_today = self._stat_seg_btn("今日")
        self.btn_stat_total = self._stat_seg_btn("总量")
        self.btn_stat_total.setChecked(True)
        self.btn_stat_today.clicked.connect(lambda: self._switch_stat_metric("today"))
        self.btn_stat_total.clicked.connect(lambda: self._switch_stat_metric("total"))
        self.bar_stat, self.stat_title, self.stat_scope_lbl = self._panel_head(
            sv, "按机统计", GREEN, "", extra=[self.btn_stat_today, self.btn_stat_total])

        # 列头 (与 StatRankRow 的列宽严格对齐)
        self.stat_header = StatHeaderRow()
        sv.addWidget(self.stat_header)

        self.stat_area = QScrollArea()
        self.stat_area.setWidgetResizable(True)
        self.stat_area.setFrameShape(QFrame.NoFrame)
        self.stat_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        style_scroll_area(self.stat_area)
        self.stat_host = QWidget()
        self.stat_host.setStyleSheet("background:transparent;")
        self.stat_lay = QVBoxLayout(self.stat_host)
        self.stat_lay.setContentsMargins(0, 0, 0, 0)
        self.stat_lay.setSpacing(2)
        self.stat_area.setWidget(self.stat_host)
        sv.addWidget(self.stat_area, 1)
        v.addWidget(self.stat_card, 3)

        # ================= 3. 已导入的机器 (单列通栏)
        self.peer_card = GlassPodFrame(radius=12)
        self.peer_card.setObjectName("multi_peer_card")
        pv = QVBoxLayout(self.peer_card)
        pv.setContentsMargins(16, 12, 16, 12)
        pv.setSpacing(8)
        self.bar_peer, self.peer_title, self.peer_scope_lbl = self._panel_head(
            pv, "已导入的机器", PURPLE, "")

        self.peer_area = QScrollArea()
        self.peer_area.setWidgetResizable(True)
        self.peer_area.setFrameShape(QFrame.NoFrame)
        self.peer_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        style_scroll_area(self.peer_area)
        self.peer_host = QWidget()
        self.peer_host.setStyleSheet("background:transparent;")
        self.peer_lay = QVBoxLayout(self.peer_host)
        self.peer_lay.setContentsMargins(0, 0, 0, 0)
        self.peer_lay.setSpacing(6)
        self.peer_area.setWidget(self.peer_host)
        pv.addWidget(self.peer_area, 1)
        v.addWidget(self.peer_card, 2)

    # ---------------- 尺寸 ----------------
    def apply_size(self):
        m = curr_metric()
        for w, pt in ((self.title_lbl, m["sn_title_pt"]), (self.stat_title, m["sn_title_pt"]),
                      (self.peer_title, m["sn_title_pt"]), (self.hint_lbl, m["sn_sub_pt"] - 0.2),
                      (self.peer_count_lbl, m["sn_date_pt"]), (self.stat_scope_lbl, m["sn_date_pt"]),
                      (self.peer_scope_lbl, m["sn_date_pt"])):
            w.setFont(QFont("Microsoft YaHei UI", pt))
        self.machine_box.apply_size()
        bh = m["nav_btn_h"] - 2
        for b in (self.btn_export, self.btn_import):
            b.setFixedHeight(bh)
            style_btn(b, None, pt=m["sn_sub_pt"] + 0.2, height=bh)
        self.stat_header.apply_size()
        # update 2026-09-20 (第59轮): 口径分段按钮尺寸 + 样式随度量刷一遍
        th = m["nav_btn_h"] - 10
        for b in (self.btn_stat_today, self.btn_stat_total):
            b.setFixedHeight(th)
        self._apply_stat_seg_style()
        for row in self.findChildren(MachineRow):
            row.apply_size()
        self.update()

    # ---------------- 主题 ----------------
    def apply_theme(self):
        m = curr_metric()
        self.title_lbl.setStyleSheet(f"color:{qname(TEXT)}; font-weight:700;")
        self.stat_title.setStyleSheet(f"color:{qname(TEXT)}; font-weight:700;")
        self.peer_title.setStyleSheet(f"color:{qname(TEXT)}; font-weight:700;")
        self.hint_lbl.setStyleSheet(f"color:{qname(TEXT3)};")
        self.peer_count_lbl.setStyleSheet(
            f"color:{qname(TEXT3)}; background:{qrgba(TRACK)}; border-radius:5px; padding:2px 8px;")
        self.stat_scope_lbl.setStyleSheet(
            f"color:{qname(TEXT2)}; background:{qrgba(TRACK)}; border-radius:5px; padding:2px 8px;")
        self.peer_scope_lbl.setStyleSheet(
            f"color:{qname(TEXT2)}; background:{qrgba(TRACK)}; border-radius:5px; padding:2px 8px;")
        # 空态占位文案
        for t in self.findChildren(QLabel, "multi_empty_title"):
            t.setStyleSheet(f"color:{qname(TEXT2)}; font-size:{m['sn_sub_pt'] + 0.6}pt;"
                            f" font-weight:600;")
        for s in self.findChildren(QLabel, "multi_empty_sub"):
            s.setStyleSheet(f"color:{qname(TEXT3)}; font-size:{m['sn_date_pt']}pt;")
        style_btn(self.btn_export, "primary")
        style_btn(self.btn_import, "primary")
        self._apply_stat_seg_style()
        self.machine_box.apply_theme()
        self.stat_header.apply_theme()
        for row in self.findChildren(MachineRow):
            row.apply_theme()
        # 局部 QSS 必须重套, 否则切换主题后滚动条仍是上一个主题的颜色
        style_scroll_area(self.stat_area)
        style_scroll_area(self.peer_area)
        self.update()

    # ---------------- 渲染 ----------------
    def _clear_layout(self, lay):
        """清空一个 QVBoxLayout 里**全部**条目 (含 addStretch 的 spacer)。

        @2026-09-19 第53轮: 原来只 takeAt(0).widget(), 有两个后果 ——
          ① addStretch 产生的 spacer item 取不到 widget, 会永远排在最前,
             新内容全被挤到它后面 (隐性布局错位);
          ② deleteLater() 只是"稍后删除", 同一轮里反复 clear/重建时旧控件
             仍挂在 parent 上 → findChildren 越数越多, 内存与绘制都白耗。
        现在: 逐项 takeAt(0) 并**按类型收尾** (widget→setParent(None)+deleteLater,
        spacer→交给 PySide 回收), 同时先把旧行 setParent(None) 立刻脱离可见树,
        避免新内容已加、旧内容还没删的"叠影"帧。
        """
        while lay.count():
            it = lay.takeAt(0)
            w = it.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()
            # 其余是 spacer / layout item: takeAt 已将其从布局移除, 无需额外处理

    def render(self, peers, summary, machine_name="", pending=False):
        """渲染多机页。

        @2026-09-19 第53轮: 新增 pending 参数。首次进入多机页时完整合并数据要等
        后台 scan 返回(约 100ms), 这段时间**不能**显示「暂无统计数据」空态 ——
        否则数据到位后整列统计条突然长出来, 就是浅猫说的「刷的一下出来」。
        pending=True 时按上一帧的机器台数画**同高骨架行**, 数据到位后原地替换。
        """
        self._peers = list(peers or [])
        self._summary = dict(summary or {})
        self._pending = bool(pending)      # 记下来, 切换统计口径时复用
        self.machine_box.set_name(machine_name or "—")

        # 别机列表
        self._clear_layout(self.peer_lay)
        if not self._peers:
            self.peer_lay.addWidget(self._empty_hint(
                "尚未导入其他机器的数据",
                "在另一台电脑上点「导出本机数据」，把文件拷过来后点「导入/更新别机数据」即可。"))
        else:
            for it in self._peers:
                row = MachineRow(it)
                row.remove.connect(self.machine_remove)
                row.replace.connect(self.machine_replace)
                self.peer_lay.addWidget(row)
        self.peer_lay.addStretch(1)
        self.peer_count_lbl.setText(f"{len(self._peers)} 台")
        self.peer_scope_lbl.setText(f"{len(self._peers)} 台别机")
        self.peer_scope_lbl.setVisible(bool(self._peers))

        # 按机统计对比 (口径由 self._stat_metric 决定: total / today)
        self._render_stat_rows()
        self.apply_theme()
        self.apply_size()

    def _render_stat_rows(self):
        """按机统计列表 —— 支持「今日 / 总量」两种口径。

        update 2026-09-20 (第59轮): 浅猫要求"按机统计也可以切换今日、总量"。
        两条"占比"口径**刻意不同且互补**:
          · 左栏排行条按**当期最大值**归一 → 看相对排行;
          · 右栏环形圈按**当期合计**求占比 → 看真实份额。
        今日模式下若各机器今天都没有用量, 给空态文案而不是画一排 0。
        """
        key = self._stat_metric
        self._clear_layout(self.stat_lay)
        rows = [(m, d) for m, d in self._summary.items() if d]
        rows.sort(key=lambda kv: -int(kv[1].get(key, 0) or 0))
        vals = [int(d.get(key, 0) or 0) for _m, d in rows]
        grand = sum(vals)

        if self._pending and not rows:
            # 数据在途: 画骨架而非空态文案, 避免"从无到有"的突增观感
            for i in range(max(self._skeleton_n, 1)):
                self.stat_lay.addWidget(StatRankRow(
                    i + 1, "", {"total": 0}, 1, False, placeholder=True))
        elif not rows:
            self.stat_lay.addWidget(self._empty_hint(
                "暂无统计数据", "导入/更新别机数据后这里会显示各机器的用量对比。"))
        elif key == "today" and grand <= 0:
            self.stat_lay.addWidget(self._empty_hint(
                "今日暂无用量", "今天各机器都还没有产生用量；可切回「总量」看累计对比。"))
        else:
            mx = max(vals) or 1
            for i, (m, d) in enumerate(rows, 1):
                self.stat_lay.addWidget(StatRankRow(
                    i, m, d, mx, bool(d.get("local")),
                    grand_total=grand, metric=key))
            self._skeleton_n = len(rows)
        self.stat_lay.addStretch(1)

        # 第97轮后半16: 与 WorkBuddy 页同款的 QScrollArea 压扁防护 ——
        # stat_area 同样是 setWidgetResizable(True), 重建行的瞬间 stat_host 的
        # sizeHint 没重算会被压到 viewport 内(行距先小再正常)。把已渲染控件的
        # 真实高度累加写进 minimumHeight, 并 activate 布局让 sizeHint 当帧正确。
        _h = 0
        for _i in range(self.stat_lay.count()):
            _it = self.stat_lay.itemAt(_i)
            _w = _it.widget() if _it is not None else None
            if _w is not None:
                _h += _w.height()
        self.stat_host.setMinimumHeight(_h + 4)
        try:
            self.stat_lay.activate()
            self.stat_host.updateGeometry()
        except Exception:
            pass

        if self._pending and not rows:
            self.stat_scope_lbl.setText("正在汇总…")
        else:
            label = "今日合计" if key == "today" else "合计"
            self.stat_scope_lbl.setText(f"{label} {fmt_full(grand)} · {len(rows)} 台机器")

    def _empty_hint(self, title, sub):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 26, 0, 26)
        lay.setSpacing(5)
        t = QLabel(title)
        t.setAlignment(Qt.AlignCenter)
        t.setObjectName("multi_empty_title")
        lay.addWidget(t)
        s = QLabel(sub)
        s.setAlignment(Qt.AlignCenter)
        s.setWordWrap(True)
        s.setObjectName("multi_empty_sub")
        lay.addWidget(s)
        return w


class NavButton(QPushButton):
    """侧边栏数据源导航按钮 (2026-09-19 第51轮 自绘重做)

    原来只是一个 QPushButton + QSS, 选中态仅换背景色 —— 视觉上扁平、和卡片的
    玻璃语言脱节, 且 4 个按钮不等宽时文字起始位置飘。现改为纯自绘:
      · 左侧 3px 竖条选中指示器 (选中时淡入 + 上移)
      · 图标与文字分列排版, 图标居中于固定 26px 图标槽, 文字左对齐 → 四个按钮完全对齐
      · 选中态: 蓝色柔和填充 + 左侧指示条 + 文字加粗变色
      · hover 态: 中性浅填充, 与选中态明显区分
    """
    ICON_W = 22
    PAD_L = 13
    GAP = 3

    def __init__(self, text, icon_str="", parent=None):
        super().__init__("", parent)
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.text = text
        self.icon_str = icon_str
        self._hover = False
        self.setMouseTracking(True)
        self.apply_size()

    def sizeHint(self):
        from PySide6.QtCore import QSize
        return QSize(150, curr_metric()["nav_btn_h"])

    def apply_size(self):
        m = curr_metric()
        self.setFixedHeight(m["nav_btn_h"])
        self.update()

    def enterEvent(self, ev):
        self._hover = True
        self.update()
        super().enterEvent(ev)

    def leaveEvent(self, ev):
        self._hover = False
        self.update()
        super().leaveEvent(ev)

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        m = curr_metric()
        checked = self.isChecked()
        dark = theme_state["dark"]
        glass = theme_state["glass"]
        frost = bool(theme_state.get("frost"))     # 第64轮: 毛玻璃也要参与适配
        r = 9.0
        # 第66轮(浅猫): 毛玻璃下选中态高亮**也从底图取色** —— 与侧栏/标题栏按钮同一套取色,
        #   于是整窗在毛玻璃模式下只有一个色源(底图), 不会"左边蓝、右边蓝绿"打架。
        #   液态玻璃/默认仍用品牌蓝(那两套材质的底色是蓝调玻璃, 取色反而会脏)。
        hi = FrostTexture.instance().accent(dark) if frost else QColor(BLUE)

        # 1. 背景 (选中 > hover > 常态)
        if checked:
            bg = QColor(hi)
            bg.setAlpha(72 if dark else 30)
            p.setPen(Qt.NoPen)
            p.setBrush(bg)
            p.drawRoundedRect(QRectF(0.5, 0.5, w - 1.0, h - 1.0), r, r)
            # 材质态下叠一层极淡描边, 让选中块在透光背景上仍有边界感
            # 第64轮: 毛玻璃一并适配 —— 它的描边比液态玻璃更"细气"(与细线分区同源)
            if glass or frost:
                rim = QColor(hi)
                if glass:
                    rim.setAlpha(80 if dark else 62)
                else:
                    rim.setAlpha(52 if dark else 44)
                p.setBrush(Qt.NoBrush)
                p.setPen(QPen(rim, 1.0))
                p.drawRoundedRect(QRectF(0.5, 0.5, w - 1.0, h - 1.0), r, r)
        elif self._hover:
            hv = QColor(HOVER)
            # 第64轮: 材质态下 hover 不能是一块实底(会像"贴上去的色块") ——
            #   液态玻璃给半透明高光, 毛玻璃只给一层薄雾
            hv.setAlpha(210 if not (glass or frost) else (120 if glass else 58))
            p.setPen(Qt.NoPen)
            p.setBrush(hv)
            p.drawRoundedRect(QRectF(0.5, 0.5, w - 1.0, h - 1.0), r, r)

        # 2. 左侧竖条指示器 (选中态)
        if checked:
            bar_h = min(h - 18.0, 20.0)
            y = (h - bar_h) / 2.0
            p.setPen(Qt.NoPen)
            p.setBrush(hi)
            p.drawRoundedRect(QRectF(3.5, y, 3.0, bar_h), 1.5, 1.5)

        # 3. 图标 (居中于固定图标槽, 保证四个按钮文字左边界完全一致)
        f = QFont("Microsoft YaHei UI", m["nav_btn_pt"] - 0.4)
        p.setFont(f)
        p.setPen(QColor(TEXT2) if not checked else QColor(hi))
        p.drawText(QRectF(self.PAD_L, 0, self.ICON_W, h),
                   Qt.AlignCenter, self.icon_str)

        # 4. 文字
        tf = QFont("Microsoft YaHei UI", m["nav_btn_pt"])
        tf.setBold(bool(checked))
        p.setFont(tf)
        p.setPen(QColor(hi) if checked else (QColor(TEXT) if self._hover else QColor(TEXT2)))
        tx = self.PAD_L + self.ICON_W + self.GAP
        p.drawText(QRectF(tx, 0, w - tx - 8, h),
                   Qt.AlignLeft | Qt.AlignVCenter, self.text)


# ============================================================ 刷新信号桥
class RefreshBridge(QObject):
    # 第三个参数是扫描代次: 看门狗超时后线程若才回, 结果已作废 (不覆盖新状态)
    done = Signal(str, object, int)


# ============================================================ 主窗口 (双尺寸自适应架构)
class CardWindow(QWidget):
    # 2026-09-16: 面板"最小化"不再缩到任务栏, 而是收进系统托盘(托盘常驻, 随时可叫回)
    minimize_to_tray = Signal()
    tray_ok = False        # 由 main() 依据系统托盘是否可用来设置

    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window | Qt.WindowStaysOnTopHint)
        # 自绘圆角窗口: 整个窗口透明, 由自绘底板提供视觉(三种材质通用, 不可按模式切换)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self._translucent = True

        self._drag = None
        self._scanning = False
        self._pending_refresh = False
        self._pending_force = False
        self._scan_gen = 0
        self._sn_cache = None
        self.source = theme_state["source"]
        self.range = "today"
        self.stats = None
        # 第97轮: 置顶态从 settings 恢复(默认 True, 与"窗口创建时就带 StaysOnTopHint"一致)
        self._always_top = bool(theme_state.get("always_top", True))

        self.bridge = RefreshBridge()
        self.bridge.done.connect(self._on_scan_done)

        self._build_ui()
        self.apply_size_mode(theme_state.get("window_size", "default"), save=False)
        self.apply_styles()

        # 周期自动刷新: 每 5 分钟一次 (商汤源保持凭证/积分新鲜, 失败后自动重试)
        self._auto_refresh_timer = QTimer(self)
        self._auto_refresh_timer.timeout.connect(self._auto_refresh_tick)
        self._auto_refresh_timer.start(300_000)   # 5 分钟

        # 刷新看门狗: work 线程卡死超时后强制恢复 UI, 避免刷新按钮永久卡在"刷新中"
        self._scan_started = 0.0
        self._scan_watchdog = QTimer(self)
        self._scan_watchdog.timeout.connect(self._scan_watchdog_check)

    def _auto_refresh_tick(self):
        """周期刷新: 商汤源自动同步(失败也持续重试), WB/DSH 源保持数据新鲜。

        商汤凭据进入续期窗口(剩余 < SN_TOKEN_REFRESH_MARGIN)时主动换证 + 强制取数,
        这样用户手动点刷新时基本永远是 0.2s 的快路径。
        """
        if self._scanning:
            return
        pro = False
        if self.source == "sn":
            try:
                pro = sn_token_near_expiry()
            except Exception:
                pro = False
        self.refresh(force=pro, proactive=pro)

    def _scan_watchdog_check(self):
        """看门狗: work 线程超时未回时强制恢复刷新按钮, 杜绝卡死"""
        if not self._scanning:
            self._scan_watchdog.stop()
            return
        if time.time() - self._scan_started > 60:
            self._scanning = False
            self._pending_refresh = False
            self._pending_force = False
            self._scan_gen += 1          # 作废在途结果, 避免迟到的返回值覆盖新状态
            self._scan_watchdog.stop()
            self._btn_busy(False)
            self.subtitle.setText("刷新超时 (数据源响应过慢)，请重试")
            if self.source == "sn":
                self.sn_page.sync_panel.set_failed("同步超时，请重试")

    def _build_ui(self):
        outer = QHBoxLayout(self)
        outer.setContentsMargins(10, 10, 10, 10)
        self.outer_lay = outer      # 保留引用(供潜在的布局微调用)

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
        # 2026-09-19 (第50轮): 多机数据源 —— 导出本机 / 导入别机 / 按机统计
        self.btn_nav_multi = NavButton("多机合并", "🔀")

        # 第96轮: 「设置」与数据源**并列**—— 它们都是"导航目的地", 属于同一组单选关系:
        #   点设置 → 数据源全部熄灭; 点任一数据源 → 设置熄灭并回到统计页。
        self.btn_nav_set = NavButton("设置", "⚙️")
        self.btn_nav_set.setCheckable(True)

        for b in (self.btn_nav_wb, self.btn_nav_dsh, self.btn_nav_sn, self.btn_nav_multi,
                  self.btn_nav_set):
            side_lay.addWidget(b)
            if b is self.btn_nav_set:
                b.clicked.connect(lambda _=False: self._show_settings(True))
            else:
                b.clicked.connect(lambda _=False, bb=b: self._switch_nav(bb))

        self.btn_nav_wb.setChecked(self.source == "wb")
        self.btn_nav_dsh.setChecked(self.source == "dsh")
        self.btn_nav_sn.setChecked(self.source == "sn")
        self.btn_nav_multi.setChecked(self.source == "multi")

        side_lay.addStretch(1)

        # ---- 第95轮(浅猫定稿): 侧栏底部统一为四层, 按钮高度统一 ----
        #   ① 明暗切换 + 刷新   (同一行, 位于主题按钮**之上**)
        #   ② 主题行: 毛玻璃 | 液态 | 静态  —— **没有"默认"按钮, 都不选即默认**
        #   ③ ⚙️ 设置
        #   ④ 版本号(左对齐)

        top_row = QHBoxLayout()
        top_row.setSpacing(6)
        self.btn_theme_toggle = QPushButton("🌙 暗色" if not theme_state["dark"] else "☀️ 亮色")
        self.btn_theme_toggle.setCursor(Qt.PointingHandCursor)
        self.btn_theme_toggle.clicked.connect(lambda: self.set_dark(not theme_state["dark"]))
        top_row.addWidget(self.btn_theme_toggle, 1)

        self.btn_refresh = QPushButton("刷新")
        self.btn_refresh.setCursor(Qt.PointingHandCursor)
        self.btn_refresh.clicked.connect(lambda: self.refresh(force=True))
        top_row.addWidget(self.btn_refresh, 1)
        side_lay.addLayout(top_row)

        # 主题行(三态): 点已选中的 → 取消 → 回到默认(无玻璃)。用 toggled 语义。
        mat_row = QHBoxLayout()
        mat_row.setSpacing(6)

        self.btn_frost = QPushButton("毛玻璃")
        self.btn_frost.setCheckable(True)
        self.btn_frost.setChecked(bool(theme_state.get("frost")) and not theme_state.get("frost_static"))
        self.btn_frost.setCursor(Qt.PointingHandCursor)
        self.btn_frost.toggled.connect(self._on_frost_btn)
        mat_row.addWidget(self.btn_frost, 1)

        self.btn_glass_toggle = QPushButton("液态")
        self.btn_glass_toggle.setCheckable(True)
        self.btn_glass_toggle.setChecked(bool(theme_state["glass"]))
        self.btn_glass_toggle.setCursor(Qt.PointingHandCursor)
        self.btn_glass_toggle.toggled.connect(self._on_glass_btn)
        mat_row.addWidget(self.btn_glass_toggle, 1)

        self.btn_static_bg = QPushButton("静态")
        self.btn_static_bg.setCheckable(True)
        self.btn_static_bg.setChecked(bool(theme_state.get("frost_static")))
        self.btn_static_bg.setCursor(Qt.PointingHandCursor)
        self.btn_static_bg.toggled.connect(self._on_static_btn)
        mat_row.addWidget(self.btn_static_bg, 1)
        side_lay.addLayout(mat_row)

        self.lbl_ver = QLabel(APP_BUILD)
        self.lbl_ver.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        side_lay.addWidget(self.lbl_ver)

        main_layout.addWidget(self.sidebar)

        # ---- 2. 右侧工作区
        self.workspace = QWidget()
        self.workspace.setObjectName("workspace")
        work_lay = QVBoxLayout(self.workspace)
        self.work_lay = work_lay       # 第95轮: 设置页要在这一层做"显示/隐藏"切换
        work_lay.setContentsMargins(18, 14, 18, 14)
        work_lay.setSpacing(10)

        top_bar = QHBoxLayout()
        self.subtitle = QLabel("加载中…")
        self.subtitle.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.subtitle.setMinimumWidth(0)
        top_bar.addWidget(self.subtitle, 1)

        # 第97轮: 设置页的顶栏标题 —— 与 subtitle 同一槽位(stretch 1), 两者互斥显隐,
        # 这样「设置」两个字的位置、基线、最小/关闭按钮的排布与主界面完全一致。
        self.lbl_set_title = QLabel("设置")
        self.lbl_set_title.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.lbl_set_title.setMinimumWidth(0)
        self.lbl_set_title.setVisible(False)
        top_bar.addWidget(self.lbl_set_title, 1)

        self.range_box = QWidget()
        self.range_box.setObjectName("range_box")
        # 第74轮: 时间区间改"分段控件" —— 外面一个大框, 内部**无隔断**(spacing 0), 只靠选中态区分
        rb_lay = QHBoxLayout(self.range_box)
        rb_lay.setContentsMargins(3, 2, 3, 2)
        rb_lay.setSpacing(0)
        self.btn_today = self._tab_btn("今日")
        self.btn_7 = self._tab_btn("7天")
        self.btn_30 = self._tab_btn("30天")
        self.btn_all = self._tab_btn("全部")
        self.btn_today.setChecked(True)
        for b in (self.btn_today, self.btn_7, self.btn_30, self.btn_all):
            rb_lay.addWidget(b)
        top_bar.addWidget(self.range_box)

        top_bar.addSpacing(6)
        self.btn_min = QPushButton("–")
        self.btn_min.setFixedSize(26, 26)
        self.btn_min.setCursor(Qt.PointingHandCursor)
        self.btn_min.setToolTip("最小化到任务栏")
        self.btn_min.clicked.connect(self._minimize_to_taskbar)
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

        # 2026-10-17 第72轮: 四张并排小卡片 → 方案 A「主次分层」指标区
        self.metrics = MetricsBand()
        dash_lay.addWidget(self.metrics)

        self.today_bar = QLabel("")
        dash_lay.addWidget(self.today_bar)

        body_split = QHBoxLayout()
        body_split.setSpacing(10)

        self.table_card = GlassPodFrame(radius=10, frame=True)
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

        self.chart_card = GlassPodFrame(radius=10, frame=True)
        self.chart_card.setObjectName("chart_card")
        cv = QVBoxLayout(self.chart_card)
        cv.setContentsMargins(10, 6, 8, 6)
        cv.setSpacing(0)
        # 第97轮后半(浅猫): 去掉标题里的"(滚轮缩放/拖动平移)"提示, 标题改常规字重
        cv.addWidget(CardHeader("每日用量分布", BLUE, bold=False))
        self.chart = StackedBarChart()
        cv.addWidget(self.chart)
        charts_col.addWidget(self.chart_card, 56)

        self.heat_card = GlassPodFrame(radius=10, frame=True)
        self.heat_card.setObjectName("heat_card")
        hv = QVBoxLayout(self.heat_card)
        hv.setContentsMargins(10, 6, 8, 6)
        hv.setSpacing(0)
        hv.addWidget(CardHeader("近期活跃热力", GREEN, bold=False))
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

        # Page 2: 多机数据源页 (2026-09-19 第50轮)
        self.multi_page = MultiMachinePage()
        self.multi_page.export_requested.connect(self._on_export_clicked)
        self.multi_page.import_requested.connect(self._on_import_clicked)
        self.multi_page.machine_remove.connect(self._on_peer_remove)
        self.multi_page.machine_replace.connect(self._on_peer_replace)
        self.multi_page.machine_rename.connect(self._on_rename_machine)
        self.stack.addWidget(self.multi_page)

        work_lay.addWidget(self.stack, 1)
        main_layout.addWidget(self.workspace, 1)

    def _minimize_to_taskbar(self):
        """第97轮(浅猫): 右上角最小化 = **缩到任务栏**, 不是收进托盘。

        这是第76轮加"托盘最小化"时没同步改的遗留问题: 按钮还接着 `_minimize_to_tray`
        (hide() 收进托盘), 于是任务栏最小化形同虚设。
        · 主窗口是无边框窗口但**不是** Qt.Tool, 任务栏本来就有图标 → showMinimized() 即可;
        · 背板由 changeEvent(WindowStateChange → isMinimized) 统一收起, 不用在这里处理;
        · 托盘图标的"单击显示/收起"保持原样, 不受影响。
        """
        if self.isMinimized():
            self.showNormal()
            self.raise_()
            return
        self.showMinimized()

    def _minimize_to_tray(self):
        """最小化 = 收进托盘: 隐藏面板, 由系统托盘图标常驻; 托盘菜单/双击可重新打开。
        兜底: 若本机系统托盘不可用, 退回原来的"缩到任务栏", 避免收起来后叫不回来。"""
        if not getattr(self, "tray_ok", False):
            self.showMinimized()
            return
        self.hide()
        self.minimize_to_tray.emit()

    def show_from_tray(self):
        """从托盘/悬浮球把面板叫回来(置顶 + 激活)。"""
        self.show()
        self.raise_()
        self.activateWindow()

    # ---------------- 几何变化 → 模糊底失效 (第62轮) ----------------
    def moveEvent(self, ev):
        """窗口移动后背景区域变了, 模糊底必须重抓(否则显示的是旧位置的桌面)。"""
        super().moveEvent(ev)
        # 第86轮: 双层窗口 —— 背板要跟着主窗口走(否则材质和面板错位)
        if getattr(self, "_frost_win", None) is not None and self._frost_win.isVisible():
            self._position_frost_window()

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        # 第86轮: 双层窗口 —— 尺寸变化时同步背板矩形
        if getattr(self, "_frost_win", None) is not None and self._frost_win.isVisible():
            self._position_frost_window()
        # 第79轮: 模糊区域是"按像素写死"的 → 改尺寸后必须按新尺寸重设
        if ACRYLIC["on"] or theme_state.get("frost"):
            self._sync_acrylic(force=True)

    # 注: showEvent 统一实现在下方(第76/77轮, 需要同时刷新纹理缓存 + 挂 DWM 材质)

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
        # 第84轮: 亚克力下窗口要比基准小 20px(让可见面板尺寸与其它模式一致) → 交给统一口径处理
        try:
            self._sync_frost_margins()
        except Exception:
            pass

        self.sidebar.setFixedWidth(m["sidebar_w"])
        self.card.sep_x = float(m["sidebar_w"])

        self.app_title.setFont(QFont("Microsoft YaHei UI", m["title_pt"], QFont.Bold))
        self.subtitle.setFont(QFont("Microsoft YaHei UI", m["subtitle_pt"]))
        # 第97轮: 设置页顶栏标题 —— 比副标题大一档、加粗、主文字色(与示意图 .ttl 一致)
        _tf = QFont("Microsoft YaHei UI", m["subtitle_pt"] + 3)
        _tf.setBold(True)
        self.lbl_set_title.setFont(_tf)
        self.src_head.setFont(QFont("Microsoft YaHei UI", m["sn_date_pt"]))

        for b in (self.btn_nav_wb, self.btn_nav_dsh, self.btn_nav_sn, self.btn_nav_multi, self.btn_nav_set):
            b.apply_size()

        self.btn_refresh.setFixedHeight(m["refresh_h"])
        self.btn_refresh.setFont(QFont("Microsoft YaHei UI", m["nav_btn_pt"], QFont.Bold))

        # 第62轮: 按钮统一与「刷新数据」同高(原 opt_btn_h=28/30 偏扁, 视觉不协调)
        # 第77轮: 静态背景与明暗切换同一行 → 一起纳入同高同字号, 否则两者盒高不一致
        _opt_h = m["refresh_h"]
        _opt_ft = QFont("Microsoft YaHei UI", m["nav_btn_pt"])
        # 第95轮: 侧栏底部**全部**按钮同高同字号(含新增的「设置」)
        for _b in (self.btn_theme_toggle, self.btn_glass_toggle, self.btn_frost,
                   getattr(self, "btn_static_bg", None), getattr(self, "btn_settings", None)):
            if _b is None:
                continue
            _b.setFixedHeight(_opt_h)
            _b.setFont(_opt_ft)

        self.metrics.apply_size()

        self.today_bar.setFixedHeight(m["today_h"])
        self.chart.apply_size()
        self.heat.apply_size()
        self.sn_page.apply_size()
        self.multi_page.apply_size()

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
        # 2026-09-23 (第60轮): 毛玻璃下侧栏也走透明, 分栏交给主板那条细线
        frost = bool(theme_state.get("frost"))
        side_transparent = glass or frost
        self.sidebar.setStyleSheet(
            f"#sidebar {{ background:{'transparent' if side_transparent else qrgba(SIDEBAR)};"
            f" border-top-left-radius:14px; border-bottom-left-radius:14px;"
            f" border-right:{'none' if side_transparent else f'1px solid {qrgba(BORDER)}'}; }}")

        self.app_title.setStyleSheet(f"color:{qname(TEXT)};")
        self.subtitle.setStyleSheet(f"color:{qname(TEXT3)};")
        self.lbl_set_title.setStyleSheet(f"color:{qname(TEXT)};")
        self.src_head.setStyleSheet(f"color:{qname(TEXT3)}; padding-left:4px;")

        if frost:
            # 第74轮反馈: 今日概况也要底框 —— 与底部卡片同语言(淡底 + 1px 细描边)
            tb_bg = "rgba(255, 255, 255, 0.052)" if dark else "rgba(255, 255, 255, 0.52)"
            tb_border = "rgba(255, 255, 255, 0.14)" if dark else "rgba(28, 38, 58, 0.14)"
        elif glass:
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

        # ===== 2026-09-25 (第64轮): 侧栏与标题栏按钮**按材质分档** =====
        # 浅猫反馈: 这几个按钮在毛玻璃/液态玻璃下"很突兀"。根因见 material_btn_qss 的注释:
        # 它们一直是默认模式的实底芯片, 而两种材质下主板/侧栏都是透明的。
        # 现在四种角色(主操作/选项/材质/标题栏)都走材质感知样式; **默认模式观感与以前完全一致**。
        self.btn_refresh.setStyleSheet(material_btn_qss("primary", dark, glass, frost))
        self.btn_min.setStyleSheet(material_btn_qss("icon", dark, glass, frost))
        self.btn_close.setStyleSheet(material_btn_qss("icon_close", dark, glass, frost))

        # 时间区间 + 明暗切换: 同一套"选项"语言
        opt_qss = material_btn_qss("opt", dark, glass, frost, px=m["opt_btn_px"])
        range_qss = material_btn_qss("seg", dark, glass, frost, px=m["opt_btn_px"])
        for b in (self.btn_today, self.btn_7, self.btn_30, self.btn_all):
            b.setStyleSheet(range_qss)
        # 外层大框 (分段控件的"容器"): 圆角 + 1px 细描边, 与卡片/按钮同语言
        # 第97轮: 配色抽到 seg_box_qss(), 设置页的小组与这里同源
        self.range_box.setStyleSheet(
            "#range_box { %s }" % seg_box_qss(dark, glass, frost))
        # 明暗切换: 独立按钮(非互斥组), 放最下面
        self.btn_theme_toggle.setStyleSheet(opt_qss)
        self.btn_theme_toggle.setText("🌙 暗色" if not dark else "☀️ 亮色")

        # 材质二选一按钮组 —— 互斥点亮; 选中态是这一组里唯一的强元素
        mat_style = material_btn_qss("mat", dark, glass, frost, px=m["opt_btn_px"])
        _gl = bool(theme_state.get("glass"))
        # 第79轮: 三材质互斥 —— 毛玻璃按钮只在"实时模糊档"亮, 静态背景档由它自己的按钮亮
        _fr = bool(theme_state.get("frost")) and not bool(theme_state.get("frost_static"))
        # ⚠️ 第65轮修 bug: 这里的 setChecked 是"把按钮同步到当前状态", **不是用户意图**,
        #    必须屏蔽信号。否则互斥切换时另一方被 setChecked(False) 会触发 toggled(False)
        #    → _on_*_btn(False) → _set_material(None), 把用户刚做的切换又撤销掉。
        #    实测症状: 毛玻璃模式下点「液态玻璃」→ 两个材质全灭, 掉回默认模式(要点两次才行)。
        self.btn_glass_toggle.setStyleSheet(mat_style)
        self.btn_frost.setStyleSheet(mat_style)
        for _b, _on in ((self.btn_glass_toggle, _gl), (self.btn_frost, _fr)):
            _b.blockSignals(True)
            _b.setChecked(_on)
            _b.blockSignals(False)
        # 第76轮: 静态背景按钮 —— 与明暗切换同一行, 毛玻璃模式下才真正起作用
        if getattr(self, "btn_static_bg", None) is not None:
            self.btn_static_bg.setStyleSheet(
                material_btn_qss("mat", dark, glass, frost, px=m["opt_btn_px"]))
            _sb = bool(theme_state.get("frost_static"))
            self.btn_static_bg.blockSignals(True)
            self.btn_static_bg.setChecked(_sb)
            self.btn_static_bg.blockSignals(False)

        # 第96轮: 侧栏「设置」按钮 —— 用主操作样式(primary)与上面一排区分开,
        # 处于设置页时用"已选中"配色, 让用户一眼知道当前在哪一页。
        if getattr(self, "btn_settings", None) is not None:
            _on_page = bool(self.btn_settings.isChecked())
            self.btn_settings.setStyleSheet(
                material_btn_qss("primary" if _on_page else "opt",
                                 dark, glass, frost, px=m["opt_btn_px"]))
            self.btn_settings.setText("⚙️  设置" if _on_page else "⚙️  设置")
        # 版本号: 小号灰字、左对齐, 与侧栏其它文字同一层级
        if getattr(self, "lbl_ver", None) is not None:
            self.lbl_ver.setStyleSheet(
                "color:%s; font-size:10.5px; background:transparent;" % qname(TEXT3))

        # NavButton 为纯自绘 (见类内 paintEvent), 不再套 QSS, 避免与自绘叠加产生双重背景
        for b in (self.btn_nav_wb, self.btn_nav_dsh, self.btn_nav_sn, self.btn_nav_multi, self.btn_nav_set):
            b.setStyleSheet("background:transparent; border:none;")
            b.update()

        self.model_area.setStyleSheet("background:transparent; border:none;")
        self.model_host.setStyleSheet("background:transparent;")
        self.sn_page.apply_theme()
        self.update()

    def set_dark(self, dark):
        theme_state["dark"] = dark
        # 第92轮(浅猫: 文字/组件与 DWM 背景切换不同步):
        #   · DWM 的 tint 是**异步合成**的, 而 Qt 的样式重刷如果用 update() 只是"排队",
        #     两边就会各走各的节奏 → 观感不同步;
        #   · 现在的做法: ① **先**下发 tint(尽早进入 DWM 队列); ② 用 **repaint() 同步**
        #     把文字/组件立刻画出来 —— 两边都在**同一帧**被提交, 差距只剩 DWM 自身的 1 帧延迟。
        # 第93轮回退: 第92轮"tint 先发 + repaint"实测**更不同步**(tint 一发 DWM 立即变色,
        # 而样式重刷要几十 ms, 拉长了不同步窗口) → 回到"样式全部刷完 → 最后发 tint"的次序。
        refresh_palette()
        self._apply_window_backdrop()     # 第63轮: 暗色影响 DWM 材质观感, 需重应用
        self.apply_styles()
        apply_app_qss()
        self._refresh_subpages_theme()
        self._update_all()
        try:
            self._sync_acrylic(force=True)
        except Exception:
            pass
        # 第96轮: 主题变了 → 设置页的按钮配色/文字必须重建(否则残留上一主题的浅色文字)
        if getattr(self, "page_settings", None) is not None and self.page_settings.isVisible():
            self.page_settings.refresh()
        save_settings()

    def _on_glass_btn(self, checked):
        """液态玻璃按钮 (三维语义见 _set_material)。"""
        self._set_material("glass" if checked else None)

    def _on_static_btn(self, checked):
        """静态背景按钮(第76轮)。"""
        self.set_static_bg(checked)

    def set_static_bg(self, on):
        """静态背景开关(第79轮): 与 液态玻璃 / 毛玻璃 **三选一互斥**。

        开 → 进入静态背景材质(内置/自定义底纹), 同时关掉另外两个;
        关 → 回到毛玻璃(DWM 实时模糊), 而不是掉回默认 —— 与另两个按钮"点第二次取消"不同,
        因为它自带一个"取消后去哪"的明确去处。
        """
        self._set_material("static" if on else None)

    def _apply_acrylic_mask(self):
        """第78轮重做: 用 **QRegion** 把窗口裁成圆角, 消灭 DWM 亚克力铺出的矩形框。

        ⚠️ 第77轮踩的坑: 用 `QImage(Format_Mono)` + `QBitmap.fromImage()` 做 mask 时,
        Mono 的色彩表索引 0 默认就是**白色 = 不透明**, 我 `fill(0)` 以为是"全透明底",
        实际把整个窗口设成了不透明遮罩 → 浅猫看到"遮罩全覆盖, 什么都看不到也点不了"。
        → 改用 `QRegion`(由圆角路径的填充多边形生成): 没有位图色彩表语义, 不会反转。

        注意: setMask 会同时影响 DWM 材质与命中测试, 所以任何异常都必须**回退到不裁**。
        """
        try:
            if not ACRYLIC["on"]:
                if self.mask() is not None:
                    self.clearMask()
                return
            w, h = self.width(), self.height()
            if w <= 22 or h <= 22:
                return
            # 裁到**面板区域**(外圈 10px 边距之外), 半径与面板 14px 对齐:
            # 这样窗外那圈是纯壁纸 → 没有 DWM 材质、没有矩形框, 而我们的圆角外框原样保留。
            path = QPainterPath()
            path.addRoundedRect(QRectF(0.0, 0.0, float(w), float(h)), 14.0, 14.0)   # 窗口＝面板(第84轮)
            region = QRegion(path.toFillPolygon().toPolygon())
            if region.isEmpty():
                self.clearMask()
                return
            self.setMask(region)
        except Exception:
            try:
                self.clearMask()
            except Exception:
                pass


    def _sync_acrylic(self, force=False):
        """第86轮: 双层窗口 —— 材质挂在底层背板上, 主窗口只画内容。

        实测(第84/85轮三方案对照): AccentPolicy 材质必然铺满**整个窗口矩形**,
        SetWindowRgn / setMask / 模糊区域全都拦不住 → 只要材质挂在主窗口上,
        面板外那 10px 就一定是材质。⇒ 解法: 让材质挂在一个**恰好等于面板矩形的
        底层小窗口**上, 主窗口浮在它上面只画罩层 —— 面板外那圈就露出真实桌面,
        与其它三种模式完全一致。
        """
        want = bool(theme_state.get("frost")) and not bool(theme_state.get("frost_static"))
        if _winbd is None or not _winbd.supported():
            want = False
        if want == ACRYLIC["on"] and not force:
            return
        if not want:
            try:
                _winbd.clear_blur_region(int(self.winId()))
                _winbd.remove_acrylic(int(self.winId()))
                _winbd.reset_frame(int(self.winId()))
                _winbd.reset_corner(int(self.winId()))
            except Exception:
                pass
            if getattr(self, "_frost_win", None) is not None:
                try:
                    self._frost_win.hide()
                    _winbd.remove_acrylic(int(self._frost_win.winId()))
                    _winbd.reset_frame(int(self._frost_win.winId()))
                    _winbd.reset_corner(int(self._frost_win.winId()))
                except Exception:
                    pass
            ACRYLIC["on"] = False
            self._sync_frost_margins()
            return
        # ---- 挂材质: 挂在底层背板窗口(尺寸=面板矩形) ----
        ok = False
        try:
            fw = self._ensure_frost_window()
            self._position_frost_window()
            # corner=True: 背板走 Win11 原生圆角(浅猫 demo v2 投票选定的方案) ——
            # 背板自己是圆的 → 圆角缺口不再溢出方形材质角, 直边也无需内缩(没有未模糊带)。
            # 第91轮: 背板**内缩0 + 系统圆角**(浅猫 demo 选定, 探针实测: 无未模糊带 15.1、
            # 外环干净 4.3; 相比内缩6 的"未模糊带 39.5"明显更好)。
            # 第91轮定案: corner=False + 内缩6。理由见数据:
            #   corner=True(系统圆角) 会带出外扩边框/辉光, 必然污染外圈(= 外框问题复现),
            #   关投影(Qt.NoDropShadowWindowHint 在 Windows 无效 / DWM NCRP_DISABLED) 也救不回来;
            #   内缩0 则四角尖材质 86~96, 不可接受。
            # ⇒ 保留当前这组(四角 1.4 干净 / 外环 0.2 干净), 代价是直边 6px 未模糊带。
            ok = _winbd.apply_acrylic(int(fw.winId()), bool(theme_state.get("dark")),
                                      corner=True)      # 方案B: 背板走 Win11 原生圆角
            fw.show()
            fw.lower()          # 背板必须待在主窗口下面
            self.raise_()
            # 第97轮后半: 背板刚显示, 置顶态要跟主窗口对齐 ——
            # 背板创建时带 WindowStaysOnTopHint, 若用户已关"始终置顶", 这里按 Win32 撤掉,
            # 否则会留下"玻璃板悬在其它窗口前面"的怪象。
            try:
                _winbd.set_topmost(int(fw.winId()), bool(getattr(self, "_always_top", True)))
                _winbd.set_topmost(int(self.winId()), bool(getattr(self, "_always_top", True)))
            except Exception:
                pass
        except Exception:
            ok = False
        ACRYLIC["on"] = bool(ok)
        self._sync_frost_margins()

    def _ensure_frost_window(self):
        """创建/复用垫在面板正下方的"亚克力背板窗口"(尺寸=面板矩形)。

        ⚠️ 第91轮关键: 必须带 **Qt.NoDropShadowWindowHint** ——
        背板是个顶层窗口, Windows 会给它画投影; 投影会落到主窗口的外圈 10px 上,
        这正是核验器一直报"外环残留"的真因(数据特征也吻合: 下环 87.6 > 左右 33 >
        上环 16.9, 就是典型投影的方向性)。去掉投影后, 背板才能内缩 0(模糊铺满到边缘)
        而不污染外圈。
        """
        fw = getattr(self, "_frost_win", None)
        if fw is None:
            fw = QWidget(None, Qt.FramelessWindowHint | Qt.Window |
                         Qt.WindowStaysOnTopHint | Qt.NoDropShadowWindowHint)
            fw.setAttribute(Qt.WA_TranslucentBackground)
            fw.setObjectName("frost_backdrop")
            self._frost_win = fw
        return fw

    def _position_frost_window(self):
        """把背板窗口对齐到主窗口的**面板矩形**。

        第87轮: 背板比面板**再内缩 6px** —— 面板是 14px 圆角, 背板若是同尺寸的直角矩形,
        四个圆角缺口处就会露出背板的方形材质角(浅猫截图里"圆角处仍有一点点材质")。
        内缩 6px 后背板的直角完全藏进面板的圆角曲线之内(14px 圆角的缺口对角线边界
        在距角 4.1px 处, 6px > 4.1px), 缺口处露出的是**真实桌面**; 代价只是面板直边
        处有 6px 宽的"未模糊带"(背板没盖到), 视觉上几乎不可察觉。
        """
        fw = getattr(self, "_frost_win", None)
        if fw is None:
            return
        try:
            # 第91轮关键修正: 必须用 **geometry()**, 不能用 frameGeometry() ——
            # 后者在无边框窗口上会**含 DWM 阴影边距(约10px)**, 等于把背板整体往外挪 10px,
            # 于是背板盖住整个窗口(连外圈 10px 环带一起) —— 这正是核验器一直报"外环残留"的
            # 真正原因; 也解释了为什么之前"内缩6"看起来干净(16 > 阴影偏移10, 恰好落进面板内)。
            g = self.geometry()
            INSET = 10               # 方案B: 背板与面板矩形完全重合 → 模糊铺到边缘, 无未模糊带
            fw.setGeometry(g.x() + INSET, g.y() + INSET,
                           max(1, g.width() - INSET * 2), max(1, g.height() - INSET * 2))
        except Exception:
            pass

    def _sync_frost_margins(self):
        """第86轮: 外边距**恒为 10px** —— 与其它三种模式完全统一, 不再有任何特殊口径。

        材质挂在底层背板窗口上, 主窗口自身不带任何 DWM 材质,
        因此不再需要第84轮"窗口=面板/缩20px"的妥协, 布局口径与其它模式完全一致。
        """
        try:
            self.outer_lay.setContentsMargins(10, 10, 10, 10)
        except Exception:
            pass
            pass

    def showEvent(self, ev):
        super().showEvent(ev)
        # 第97轮后半: 置顶态每次显示都同步一次 ——
        # ① 从设置恢复(窗口创建时带 StaysOnTopHint, 上次存的是"关"就要撤掉);
        # ② 最小化恢复 / 从托盘叫回后, Qt 可能按 flag 重新置顶, 这里按 _always_top 纠回来。
        # 只用 Win32 改 Z 序(见 _set_always_top), 不重设 flags → 不闪。
        try:
            import win_backdrop as _wb
            fw = getattr(self, "_frost_win", None)
            if fw is not None and fw.winId():
                _wb.set_topmost(int(fw.winId()), bool(getattr(self, "_always_top", True)))
            _wb.set_topmost(int(self.winId()), bool(getattr(self, "_always_top", True)))
        except Exception:
            pass
        self._top_applied = True
        # 第76/77轮: 同样要在 show 之后(winId 才稳定) → 刷新纹理缓存 + 挂 DWM 材质 + 圆角裁剪
        # (本方法是唯一的 showEvent 实现, 覆盖了上面早期的同名定义)
        # 第84轮: 先只挂材质(0.15ms 级), 让窗口**立刻**出现; 纹理解码这种重活推迟 30ms,
        # 否则"一键重启"后会有一段时间看不到窗口, 观感像卡住。
        QTimer.singleShot(0, lambda: self._sync_acrylic(force=True))
        QTimer.singleShot(30, self._apply_window_backdrop)

    def changeEvent(self, ev):
        super().changeEvent(ev)
        # 最小化恢复 / 跨屏 DPI 变化后 DWM 会掉材质 → 重新挂上
        if ev.type() == QEvent.WindowStateChange:
            fw = getattr(self, "_frost_win", None)
            if self.isMinimized():
                if fw is not None and fw.isVisible():
                    fw.hide()                       # 第86轮: 主窗最小化 → 背板一起藏
            elif fw is not None:
                QTimer.singleShot(60, lambda: self._sync_acrylic(force=True))

    def _on_frost_btn(self, checked):
        """毛玻璃按钮 (三维语义见 _set_material)。"""
        self._set_material("frost" if checked else None)

    def _set_material(self, kind):
        """统一材质切换入口。kind: 'glass' | 'frost' | 'static' | None(默认)。

        第79轮(浅猫): 「静态背景」= 第三种材质, 与 液态玻璃 / 毛玻璃 **三选一互斥**,
        且都能再点一次取消回默认 —— 和原来的三态语义完全一致:
          · glass   → 液态玻璃
          · frost   → 毛玻璃 (DWM 实时模糊)
          · static  → 静态背景 (内置/自定义静态底纹, 与第63轮那套观感一致)
          · None    → 默认无玻璃
        """
        kind = kind if kind in ("glass", "frost", "static") else None
        new_glass = (kind == "glass")
        new_frost = kind in ("frost", "static")      # static 也是"毛玻璃系"(都走 frost 绘制)
        new_static = (kind == "static")
        if (new_glass == bool(theme_state.get("glass")) and
                new_frost == bool(theme_state.get("frost")) and
                new_static == bool(theme_state.get("frost_static"))):
            return                                    # 状态未变: 不重复刷新
        was_frost = bool(theme_state.get("frost"))    # 判"是否进出毛玻璃模式"用
        theme_state["glass"] = new_glass
        theme_state["frost"] = new_frost
        theme_state["frost_static"] = new_static
        refresh_palette()
        self._apply_window_backdrop()                 # 刷新静态模糊纹理缓存
        self.apply_styles()                           # 内部会同步两个按钮的勾选态
        self._refresh_subpages_theme()
        # 第63轮提速: render() 会重建整页控件(实测 ~100ms), 只在"行级底色"受影响时做 ——
        #   毛玻璃模式下明细行不铺斑马纹(靠细线分区), 进出该模式必须重渲染;
        #   仅在液态玻璃 <-> 默认之间切换时, 行背景走 QSS 且 apply_styles 已刷新 → 免重建。
        if new_frost or was_frost:
            try:
                self.render()
            except Exception:
                pass
        self._update_all()
        # 第82轮(浅猫: 切回其它模式会**先完全变透一下**): DWM 材质必须**最后**撤。
        # 之前 _apply_window_backdrop() 在样式重刷之前就调 _sync_acrylic() → AccentPolicy 先消失,
        # 窗口变纯透明, 屏幕上就闪一下"全透", 之后才画上液态玻璃/静态背景。改到此处: 先刷完样式
        # 与内容, 最后一步才撤 DWM, 中间帧永远有东西。
        # 第87轮: 光"最后"还不够 —— update() 只是**排队**重绘, 真正画完在下一轮事件循环;
        # 立刻撤 DWM 仍会闪一帧全透。改为**延迟 110ms** 再撤: 旧材质多留一瞬, 新样式先画好,
        # 切换变成"材质→材质"的直接过渡, 不再经过透明态。
        # 第88轮: 只对"**离开**毛玻璃"延迟 ——
        #   · 进入毛玻璃若也延迟 110ms, 这 110ms 里 ACRYLIC["on"] 还是 False,
        #     _frost_fill 会先画一帧**静态纹理**(浅猫看到的"闪一下静态图片模式") → 进入必须立即挂;
        #   · 延迟撤完后必须补一次重绘: 否则最后一帧停留在"只有罩层"的画(毛玻璃→静态背景
        #     会"丢失底图全透", 因为撤材质后没人触发重绘)。
        # 第92轮(浅猫逐项观察后的定案):
        #   判据不能看 frost, 要看**材质是否还要用** —— 静态背景虽然 frost=True, 但它**不用
        #   亚克力**, 所以"毛玻璃→静态背景"同样属于"撤材质":
        #     · 毛玻璃→静态背景: 旧代码立即撤 → 背板没了、新静态底图还没画 → 闪一下全透
        #     · 毛玻璃→液态玻璃: 延迟130ms → 新样式已经画在材质之上 → 先"发闷不透", 再才正常
        #   ⇒ 正解: 先用 **repaint() 同步**把新样式画到屏幕上(update() 只是排队, 不够),
        #     然后**立即**撤材质 —— 既不会经过透明态, 也不会出现"新样式盖在材质上"的那一帧。
        _will_want = new_frost and not new_static
        if ACRYLIC["on"] and not _will_want:
            # 第93轮(浅猫: 上轮顺序仍闪): 正确次序是 ——
            #   ① 先把 ACRYLIC["on"] 置 False(这样紧接着的重绘画的是**新样式的实底**,
            #      而不是亚克力模式下那层近乎透明的罩层 —— 上轮就是败在这里);
            #   ② repaint() 同步绘制(新样式已盖住背板材质);
            #   ③ 最后才撤材质(此时它被挡住, 撤不撤都看不见)。
            ACRYLIC["on"] = False
            try:
                self.repaint()
                self.card.repaint()
            except Exception:
                pass
            try:
                self._sync_acrylic(force=True)
            except Exception:
                pass
            self._update_all()
        else:
            try:
                self._sync_acrylic(force=True)   # 进入毛玻璃/静态互切: 立即同步
            except Exception:
                pass
        # 第96轮: 材质变化影响按钮 QSS → 设置页同步重建
        if getattr(self, "page_settings", None) is not None and self.page_settings.isVisible():
            self.page_settings.refresh()
        save_settings()

    def set_glass(self, enabled):
        """液态玻璃开关(供右键菜单等调用)。开它即自动关毛玻璃。"""
        self._set_material("glass" if enabled else None)

    def set_frost(self, on):
        """毛玻璃开关(供右键菜单等调用)。开它即自动关液态玻璃。"""
        self._set_material("frost" if on else None)

    def choose_frost_image(self):
        """让用户选一张图片作毛玻璃底纹(自动做模糊+压暗处理)。"""
        try:
            from PySide6.QtWidgets import QFileDialog
            path, _ = QFileDialog.getOpenFileName(
                self, "选择毛玻璃底纹图片", "",
                "图片 (*.png *.jpg *.jpeg *.bmp *.webp);;所有文件 (*)")
            if not path:
                return
            ok = FrostTexture.instance().set_custom(path)
            if not ok:
                try:
                    from PySide6.QtWidgets import QMessageBox
                    QMessageBox.warning(self, "无法使用该图片",
                                        "图片读取失败, 请换一张试试。")
                except Exception:
                    pass
                return
            # 处理成功 → 开毛玻璃并刷新
            if not theme_state.get("frost"):
                self._set_material("frost")
            else:
                self._apply_window_backdrop()
                # 第65轮: 选中态颜色是"从底图取色"的 → 换图后必须重刷样式, 否则还是旧图取到的色
                self.apply_styles()
                self._update_all()
            save_settings()
        except Exception:
            pass

    def reset_frost_image(self):
        """恢复内置默认底纹(丢弃自定义图)。"""
        try:
            FrostTexture.instance().clear_custom()
            self._apply_window_backdrop()
            self.apply_styles()      # 第65轮: 底图变了 → 选中态取色跟着重算
            self._update_all()
            save_settings()
        except Exception:
            pass

    def _apply_window_backdrop(self):
        """按当前明暗/自定义图刷新毛玻璃纹理(浅色与深色用不同的压暗处理)。

        第63轮重做: 纹理是**静态**的(内置或用户自选), 所以这里只是切一下缓存,
        没有任何抓屏/系统调用 —— 零延迟, 拖拽完全跟手。
        """
        tex = FrostTexture.instance()
        tex._scaled.clear()          # 明暗切换后纹理处理不同 → 清缩放缓存
        # 第82轮: 亚克力模式下纹理**不会被绘制**(模糊来自 DWM) → 跳过这块耗时的图片解码,
        # 让明暗切换少干一件重活, 进一步压掉"半拍"。
        if theme_state.get("frost") and not ACRYLIC["on"]:
            tex.load(force=True)
        # 第82轮: 这里**只**刷新静态底纹缓存, 不碰 DWM ——
        # 挂/撤材质统一由调用方按正确次序负责(见 _set_material / set_dark), 太早撤会闪全透。

    def _refresh_subpages_theme(self):
        """2026-09-19 第51轮: 子页面用 QLabel + QSS 上色, 主题切换必须显式重刷,
        否则多机页/商汤页会在切换暗色后保留旧主题的文字颜色 (update() 不重算 QSS)。"""
        try:
            self.sn_page.apply_theme()
        except Exception:
            pass
        try:
            self.multi_page.apply_theme()
        except Exception:
            pass

    def _update_all(self):
        """重绘整个窗口树。

        第63轮提速: 原实现遍历 QApplication.allWidgets()(含**其它应用/隐藏窗口**的控件),
        切换材质时要刷几十上百个不可见控件 → 明显卡顿。改为:
          ① 只遍历本窗口(self)的子树; ② 跳过不可见控件(反正看不见)。
        """
        self.update()
        for w in self.findChildren(QWidget):
            if w.isVisible():
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
        for b in (self.btn_nav_wb, self.btn_nav_dsh, self.btn_nav_sn, self.btn_nav_multi, self.btn_nav_set):
            b.setChecked(b is btn)
        # 第96轮: 选了数据源 → 「设置」熄灭并退出设置页
        if getattr(self, "btn_nav_set", None) is not None:
            self.btn_nav_set.blockSignals(True)
            self.btn_nav_set.setChecked(False)
            self.btn_nav_set.blockSignals(False)
        self._show_settings(False)
        if btn is self.btn_nav_dsh:
            self.source = "dsh"
        elif btn is self.btn_nav_sn:
            self.source = "sn"
        elif btn is self.btn_nav_multi:
            self.source = "multi"
        else:
            self.source = "wb"
        theme_state["source"] = self.source
        save_settings()
        self.load_initial()

    # ---------------- 异步刷新链路 ----------------
    def _btn_busy(self, busy):
        """刷新按钮忙碌态: 文案 + 禁用 + 视觉一致 (原来只是 disable, 点下去像没反应)"""
        self.btn_refresh.setEnabled(not busy)
        # 第96轮: 刷新完成后要还原成「刷新」两字 —— 原来这里写死 "刷新数据",
        # 于是只要刷新过一次, 按钮就再也不会变回「刷新」(浅猫实测到的 bug)。
        self.btn_refresh.setText("⟳  同步中…" if busy else "刷新")

    def refresh(self, force=False, proactive=False):
        if self._scanning:
            # 合并重复请求: force 必须一起记下来, 否则用户在自动刷新期间点按钮,
            # 后续补刷新会退化成 force=False 而命中 TTL 缓存 → 数据看着"没更新"
            self._pending_refresh = True
            self._pending_force = self._pending_force or force
            return
        self._scanning = True
        self._scan_gen += 1
        gen = self._scan_gen
        self._scan_started = time.time()
        self._scan_watchdog.start(2000)   # 看门狗: 每 2s 检查一次, 超 60s 强制恢复
        self._btn_busy(True)
        src = self.source
        if src == "dsh": self.subtitle.setText("正在读取 DSH 账本…")
        elif src == "multi":
            self.subtitle.setText("正在汇总多机数据…")
        elif src == "sn":
            # 进度反馈: 同步面板显示进度态, 避免更新按钮灰色像卡住
            self.sn_page.sync_panel.set_syncing("正在自动获取凭证并同步…" if force else "正在同步积分数据…")
            self.subtitle.setText("正在自动同步商汤积分 (获取凭证)…" if force else "正在同步商汤积分…")
        else: self.subtitle.setText("正在扫描 WorkBuddy 会话数据…")

        def work():
            try:
                if src == "dsh": s = self._build_source_stats("dsh")
                elif src == "sn": s = load_sn_stats(force=force, proactive=proactive)
                elif src == "multi": s = self._build_multi_stats()
                else: s = self._build_source_stats("wb")
            except Exception as e:
                s = {"error": str(e)}
            self.bridge.done.emit(src, s, gen)

        threading.Thread(target=work, daemon=True).start()

    # ---------------- 多机数据源 (2026-09-19 第50轮) ----------------
    def _build_source_stats(self, src_key):
        """单来源视图 = 本机实时数据 + 已导入的别机快照（2026-09-19 第55轮新增）。

        浅猫实机反馈：导入别机数据后**只有「多机合并」页能看到**，WB / DSH 页仍是纯本机
        数据，与最初"按数据源自动识别并在程序侧补充上去"的诉求不符。这里把同一来源
        （wb 或 dsh）的各机数据合并后直接交给页面渲染。

        ⚠️ **没有任何别机数据时走原路径**（直接返回扫描结果的原始结构）——
        这样零别机时的行为与加这个功能之前完全一致，不给既有回归留隐患。
        """
        peers = peer_store.load_all_peers()
        if not peers:
            return scanner.scan_full() if src_key == "wb" else load_dsh_stats()
        local = {}
        try:
            local[src_key] = scanner.scan_full() if src_key == "wb" else load_dsh_stats()
        except Exception as e:
            local[src_key] = {"error": str(e)}
        entries = [{"machine": peer_store.load_machine_name(), "local": True, "stats": local}]
        for name, pk in peers.items():
            entries.append({"machine": name, "local": False,
                            "stats": (pk or {}).get("sources") or {}})
        return peer_store.source_view(entries, src_key, include_local=True)

    def _build_multi_stats(self):
        """汇总多机数据: 本机实时（WB+DSH）+ 各别机快照 → 合并视图。

        返回结构与统计页同构（daily/models/dailySessions/firstDay/lastDay），
        额外带 machines（按机摘要）与 peers（别机列表）供页面渲染。
        """
        local = {}
        try:
            local["wb"] = scanner.scan_full()
        except Exception as e:
            local["wb"] = {"error": str(e)}
        try:
            local["dsh"] = load_dsh_stats()
        except Exception as e:
            local["dsh"] = {"error": str(e)}
        peer_pkgs = peer_store.load_all_peers()
        entries = [{"machine": peer_store.load_machine_name(), "local": True, "stats": local}]
        for name, pk in peer_pkgs.items():
            entries.append({"machine": name, "local": False, "stats": pk.get("sources") or {}})
        merged = peer_store.merge_machines(entries, include_local=True)
        # 标记本机，供页面用 🖥 区分
        local_name = peer_store.load_machine_name()
        for name, d in merged["machines"].items():
            d["local"] = (name == local_name)
        merged["peers"] = peer_store.list_peers()
        merged["machineName"] = local_name
        merged["source"] = "multi"
        return merged

    def _on_export_clicked(self):
        """导出本机数据（WB + DSH 全量快照）到用户选择的文件。"""
        name = peer_store.load_machine_name()
        default = f"token-stats-{name}-{time.strftime('%Y%m%d')}.json"
        path, _ = QFileDialog.getSaveFileName(
            self, "导出本机数据", os.path.join(os.path.expanduser("~"), "Desktop", default),
            "Token 统计数据包 (*.json)")
        if not path:
            return
        local = {}
        try:
            local["wb"] = scanner.scan_full()
        except Exception as e:
            local["wb"] = {"error": str(e)}
        try:
            local["dsh"] = load_dsh_stats()
        except Exception as e:
            local["dsh"] = {"error": str(e)}
        pkg = peer_store.build_export_package(name, local)
        ok, err = peer_store.write_export(pkg, path)
        if ok:
            srcs = "+".join(sorted(pkg["sources"])) or "无"
            self.subtitle.setText(f"已导出「{name}」数据（{srcs}）→ {os.path.basename(path)}")
            self._show_toast(f"导出成功\n\n机器「{name}」\n来源: {srcs}\n文件: {path}")
        else:
            self.subtitle.setText(f"导出失败: {err}")
            self._show_toast(f"导出失败\n\n{err}", error=True)

    def _on_import_clicked(self):
        """导入/更新别机数据包（不影响本机数据，按机器名分别存放）。

        @2026-09-19 第52轮: 按钮文案统一为「导入/更新别机数据」, 对应下面两条语义 ——
          包内机器名是新的 → 新增一台机器；
          包内机器名已存在 → 视为同一台机器的新快照, 直接覆盖其旧数据。
        """
        path, _ = QFileDialog.getOpenFileName(
            self, "导入/更新别机数据", os.path.expanduser("~"),
            "Token 统计数据包 (*.json);;所有文件 (*)")
        if not path:
            return
        self._import_path(path, replace=False)

    def _on_peer_replace(self, machine):
        """覆盖更新某台机器：重新选择该机器的数据包并替换其存档。"""
        path, _ = QFileDialog.getOpenFileName(
            self, f"选择「{machine}」的新数据包（覆盖更新）", os.path.expanduser("~"),
            "Token 统计数据包 (*.json);;所有文件 (*)")
        if not path:
            return
        pkg, err = peer_store.parse_package(path)
        if pkg and pkg.get("machine") != machine:
            self._show_toast(
                f"机器名不匹配\n\n该包属于「{pkg.get('machine')}」，"
                f"与要覆盖的「{machine}」不同。\n请改用「导入/更新别机数据」。", error=True)
            return
        self._import_path(path, replace=True)

    def _import_path(self, path, replace=False):
        """写入一份别机快照, 并按「新增 / 覆盖更新」给出明确反馈。

        @2026-09-19 第52轮: 区分两种结果的措辞 —— 首次导入说「新机器已导入」,
        同名机器说「已覆盖更新」, 避免用户误以为旧数据被叠加累计。
        """
        pkg, err = peer_store.parse_package(path)
        if not pkg:
            self.subtitle.setText(f"导入失败: {err}")
            self._show_toast(f"导入失败\n\n{err}", error=True)
            return
        ok, msg, info = peer_store.import_peer(pkg, replace=replace)
        if ok:
            dig = (info or {}).get("digest", {})
            fresh = not bool((info or {}).get("replaced", False))
            head = "新机器已导入" if fresh else "已覆盖更新同名机器"
            self.subtitle.setText(f"已导入「{pkg['machine']}」· {head}")
            detail = ("该机器名此前未出现过，已作为一台新机器加入统计。"
                      if fresh else
                      "该机器名已存在，本次按最新快照覆盖其旧数据（不是累加）。")
            self._show_toast(
                f"{head}\n\n机器: {pkg['machine']}\n{detail}\n\n"
                f"来源: {'+'.join(sorted(pkg['sources']))}\n"
                f"Token: {dig.get('total_tokens', 0):,}\n"
                f"请求: {dig.get('requests', 0):,}\n"
                f"区间: {dig.get('first_day', '—')} ~ {dig.get('last_day', '—')}")
            self.refresh(force=True)
        else:
            self.subtitle.setText(f"导入失败: {msg}")
            self._show_toast(f"导入失败\n\n{msg}", error=True)

    def _on_peer_remove(self, machine):
        ok_yes = dlg_confirm(
            self, "删除机器数据",
            f"确定删除机器「{machine}」的已导入数据？\n\n"
            f"只删除本机保存的这台机器的快照，不影响对方电脑上的原始数据。",
            ok_text="删除", icon="error")
        if not ok_yes:
            return
        ok, msg = peer_store.remove_peer(machine)
        self.subtitle.setText(msg if ok else f"删除失败: {msg}")
        if ok:
            self.refresh(force=True)

    def _on_rename_machine(self, name=""):
        """保存机器名 —— 就地编辑版 (2026-09-19 第53轮)。

        浅猫："改名不需要弹窗，直接在原有名字框就能输入修改然后保存"
        → 名字由 MachineBox 内联输入框直接给出, 这里不再弹 dlg_prompt。
        兼容旧调用 (传空串时回退到读当前存档值, 不会覆盖为空)。
        """
        text = (name or "").strip()
        if not text:
            # 无新名字传入: 说明是旧式触发, 回退读当前值, 不做任何写入
            return
        peer_store.save_machine_name(text)
        self.subtitle.setText(f"本机机器名已设为「{text}」")
        self.refresh(force=True)

    def _show_toast(self, text, error=False):
        """轻量结果提示: 统一走自绘玻璃弹窗，与卡片语言一致。"""
        lines = [ln for ln in str(text).split("\n")]
        title = lines[0] if lines else "提示"
        body = "\n".join(lines[1:]).strip()
        if error and not body:
            body = title
            title = "操作失败"
        dlg_notify(self, title, body or title, error=error)

    def _on_scan_done(self, src, s, gen=None):
        # 代次校验: 看门狗超时后线程若才回来, 其结果已作废, 不能覆盖新状态
        if gen is not None and gen != self._scan_gen:
            return
        self._scan_watchdog.stop()
        self._scanning = False
        self._btn_busy(False)
        if isinstance(s, dict) and "error" in s:
            if src == self.source:
                self.subtitle.setText(f"加载失败: {s['error'][:50]}")
                if src == "sn":
                    self.sn_page.sync_panel.set_failed(f"加载失败: {s['error'][:40]}")
            self._kick_pending()
            return
        if src == self.source:
            self.stats = s
            if src == "sn": self._sn_cache = s
            self.render()
            if src == "dsh":
                # @2026-09-19 第55轮: 别机 DSH 数据已并入本页, 副标题标出构成, 数字才不"来路不明"
                # @2026-10-17 第72轮: **删除「累计花费 ¥」** —— 浅猫反馈计费口径不准确, 暂不展示计费。
                _np = int(s.get("mergedPeers", 0) or 0)
                _src_txt = f" · 含 {_np} 台别机" if _np else ""
                self.subtitle.setText(
                    f"DSH · {s.get('firstDay','—')} ~ {s.get('lastDay','—')}{_src_txt}"
                    f" · 已更新 {time.strftime('%H:%M:%S')}")
            elif src == "multi":
                n_peer = len(s.get("peers") or [])
                self.subtitle.setText(
                    f"多机合并 · 本机 + {n_peer} 台别机 · "
                    f"{s.get('firstDay','—')} ~ {s.get('lastDay','—')} · 已更新 {time.strftime('%H:%M:%S')}")
            elif src == "sn":
                ws = time.strftime("%H:%M", time.localtime(s.get("window_start", 0)))
                we = time.strftime("%H:%M", time.localtime(s.get("window_end", 0)))
                self.subtitle.setText(f"商汤 · 积分额度 · 窗口 {ws}–{we} · 已更新 {time.strftime('%H:%M:%S')}")
            else:
                _np = int(s.get("mergedPeers", 0) or 0)
                _src_txt = f" · 含 {_np} 台别机" if _np else ""
                self.subtitle.setText(f"WorkBuddy · {s.get('firstDay','—')} ~ {s.get('lastDay','—')} · 真实 usage{_src_txt} · 已更新 {time.strftime('%H:%M:%S')}")
        elif src == "sn":
            self._sn_cache = s
        self._kick_pending()

    def _kick_pending(self):
        if self._pending_refresh and not self._scanning:
            self._pending_refresh = False
            f, self._pending_force = self._pending_force, False
            QTimer.singleShot(0, lambda: self.refresh(force=f))

    def _apply_page(self):
        """按当前 source 同步切换 stack 页与控件可见性 —— 必须与数据渲染解耦。

        2026-09-19 第52轮修复: 原来只有 render() 里才 setCurrentIndex, 而 render()
        只在数据到位后由后台回调触发。若用户在同步中途切页, refresh() 因 _scanning
        为 True 直接 return(合并重复请求), 回调被推迟 → **stack 一直停在旧页,
        表现为"同步过程中无法切换到多机合并页面"**。现把切页独立出来, 切页即时生效,
        数据渲染等 refresh 回来再补。
        """
        if self.source == "sn":
            self.stack.setCurrentIndex(1)
        elif self.source == "multi":
            self.stack.setCurrentIndex(2)
        else:
            self.stack.setCurrentIndex(0)
        # 第97轮(浅猫: "刷新后设置页顶部冒出很长一条 今日/7天/30天/全部"):
        # 这里原先把 range_box 无条件 setVisible(True), 而刷新链路每次都会走到 _apply_page(),
        # 于是**切到设置页后只要一刷新, 时间区间条就会复活**并压在设置页上方。
        # 现在改成"按页算出应有状态, 再与'是否在设置页'求与", 谁都不能单方面把它显示出来。
        self._sync_top_bar()

    def load_initial(self):
        self._apply_page()
        if self.source == "sn":
            self.stats = self._sn_cache or {"source": "sn", "pools": []}
        elif self.source == "dsh":
            # @2026-09-19 第55轮: DSH 页也带上已导入的别机 DSH 数据
            # (只多读一次本地 peers 小文件 + 内存合并, 不会拖慢切页)
            self.stats = self._build_source_stats("dsh")
        elif self.source == "multi":
            # 多机页首次进入: 先渲染一份快速的轻量视图（仅别机列表 + 本机摘要），
            # 完整合并交给随后的后台 refresh，避免切页卡顿。
            # @2026-09-19 第53轮: 打上 pending 标记 —— 轻量视图没有 machines 数据,
            # 若按空态渲染, 后台数据回来后整列统计条会突然长出来("唰一下")。
            # pending 让页面改画同高骨架行, 数据到位后原地替换。
            self.stats = {"source": "multi", "machines": {}, "peers": peer_store.list_peers(),
                          "machineName": peer_store.load_machine_name(),
                          "daily": {}, "models": {}, "dailySessions": {},
                          "firstDay": "", "lastDay": "", "pending": True}
            self._render_multi_page()
            QTimer.singleShot(100, self.refresh)
            return
        else:
            try:
                with open(scanner.STATS_FILE, "r", encoding="utf-8") as f:
                    cached = json.load(f)
            except Exception:
                cached = {"source": "wb", "daily": {}, "dailySessions": {},
                          "sessionsTotal": 0, "today": {}}
            # @2026-09-19 第55轮: 首屏也走合并视图（本机部分用磁盘缓存，不阻塞切页）。
            # 否则会先显示纯本机数字、100ms 后台刷新回来再"跳变"成含别机的数字。
            peers = peer_store.load_all_peers()
            if peers:
                entries = [{"machine": peer_store.load_machine_name(),
                            "local": True, "stats": {"wb": cached}}]
                for _name, _pk in peers.items():
                    entries.append({"machine": _name, "local": False,
                                    "stats": (_pk or {}).get("sources") or {}})
                cached = peer_store.source_view(entries, "wb", include_local=True)
            self.stats = cached
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
        self._apply_page()
        if not s:
            self.subtitle.setText("暂无数据，点击刷新")
            return

        if self.source == "sn":
            self.sn_page.render(s)
            return

        if self.source == "multi":
            self._render_multi_page()
            return

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

        ds = s.get("dailySessions", {})
        n_sess = s.get("sessionsTotal", 0) if self.range == "all" else sum(v for d, v in ds.items() if d in daily)
        # 第72轮: 四张卡片 → 指标区一次喂数据; 第72轮反馈: 趋势线要跟随所选时间区段 → 传入过滤后的 daily
        self.metrics.set_stats(s, tot, n_sess, daily)

        td = s.get("today", {})
        trate = td.get("cached", 0) / td.get("input", 1) * 100 if td.get("input") else 0
        # @2026-10-17 第72轮: 概览条里的「今日花费 ¥」已删除 (浅猫: 计费口径不准确, 暂不展示)
        self.today_bar.setText(
            f"今日概况: 请求 {td.get('requests',0):,} 次 · 输入 {fmt(td.get('input',0))} · 输出 {fmt(td.get('output',0))} "
            f"· 会话 {td.get('sessions',0)} 个 · 缓存命中 {trate:.0f}%")

        while self.model_lay.count():
            it = self.model_lay.takeAt(0)
            w = it.widget()
            if w: w.deleteLater()

        self.model_lay.addWidget(TableHeader("调用" if s.get("dsh") else "请求"))
        rows = sorted(agg.items(), key=lambda kv: -kv[1]["total"])
        # ⚠️ max_total 不能为 0: 真实数据里会出现"今日仅一条 total=0 的调用"
        # (requests=1 但 input/output 全空), rows 非空但首行 total=0 → 除零崩溃。
        # 取前若干非 0 的最大值兜底。
        _max_total = 0
        for _m, _a in rows:
            if _a.get("total", 0) > 0:
                _max_total = _a["total"]
                break
        max_total = _max_total or 1
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

        # 第97轮后半16 修(浅猫: "模型列表满时(选全部时间)切换页面, 模型卡片会闪,
        # 行距先变很小再变正常"):
        #   model_area 是 QScrollArea + setWidgetResizable(True) —— 重建 ModelRow 的
        #   瞬间 model_host 的 sizeHint 还没重算, QScrollArea 会把整个内容**压到
        #   viewport 内**(行被压扁), 下一帧 sizeHint 更新才弹回 → 就是"闪一下 +
        #   行距先小再正常"。模型越多(全部时间口径)越明显。
        #   修法: 渲染完把**已渲染控件的真实高度累加**写进 minimumHeight
        #   (QScrollArea 便无法压扁它), 同时 activate 布局 + updateGeometry,
        #   让 sizeHint 当帧就正确。用累加法而非公式, 是抗未来改动行高/增删行类型。
        _h = 0
        for _i in range(self.model_lay.count()):
            _it = self.model_lay.itemAt(_i)
            _w = _it.widget() if _it is not None else None
            if _w is not None:
                _h += _w.height()
        self.model_host.setMinimumHeight(_h + 4)
        try:
            self.model_lay.activate()
            self.model_host.updateGeometry()
        except Exception:
            pass

        self.chart.set_data(daily, rows)
        self.heat.set_data(self.stats.get("daily", {}))

    def _render_multi_page(self):
        """渲染多机数据源页（别机列表 + 按机统计）。

        @2026-09-19 第53轮: 源里有 `pending` 标记时(首次进入、合并尚未算完)
        传 pending=True 给页面 → 画骨架行而非空态, 消除"唰一下出来"的观感。
        """
        s = self.stats or {}
        peers = s.get("peers") or []
        machines = s.get("machines") or {}
        name = s.get("machineName") or peer_store.load_machine_name()
        self.multi_page.render(peers, machines, name, pending=bool(s.get("pending")))

    # ---------------- 交互与右键菜单 ----------------
    def hideEvent(self, ev):
        super().hideEvent(ev)
        ChartTip.instance().hide_tip()
        # 第86轮: 主窗口隐藏时, 垫在下面的亚克力背板也要一起藏, 否则屏幕上剩一块"玻璃板"
        fw = getattr(self, "_frost_win", None)
        if fw is not None and fw.isVisible():
            fw.hide()

    def mousePressEvent(self, ev):
        if ev.button() == Qt.LeftButton and ev.position().y() < 50:
            # 第79轮(浅猫: 毛玻璃模式下窗口拖不动): 优先交给**系统拖动**。
            # 设过窗口区域(setMask)后, 自己算 self.move() 的手感/命中都容易受区域裁剪影响;
            # startSystemMove() 由 Windows 接管(与原生标题栏一致), 有区域也照样能拖。
            try:
                wh = self.windowHandle()
                if wh is not None and wh.startSystemMove():
                    self._drag = None
                    return
            except Exception:
                pass
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
        act_hide = menu.addAction("🙈  隐藏窗口 (Esc)")
        act_dark = menu.addAction(("◉ " if theme_state["dark"] else "○ ") + "深色模式")

        # 2026-09-25 (第63轮): 三种材质统一为一个"单选组", 与侧栏按钮语义一致 ——
        #   默认(无玻璃) / 液态玻璃 / 毛玻璃, 点当前项 = 取消回默认。
        _cur_glass = bool(theme_state["glass"])
        _cur_frost = bool(theme_state.get("frost"))
        mat_menu = menu.addMenu("🪟  窗口材质")
        act_mat_none = mat_menu.addAction(
            ("◉ " if not (_cur_glass or _cur_frost) else "○ ") + "⬜ 默认 (无玻璃)")
        act_blur = mat_menu.addAction(
            ("◉ " if _cur_glass else "○ ") + "💎 液态玻璃 (iOS 27)")
        act_frost = mat_menu.addAction(
            ("◉ " if _cur_frost else "○ ") + "🫧 毛玻璃 (系统实时模糊)")
        # 第76轮: 静态背景 —— 关掉实时模糊, 改用内置/自定义静态底纹
        act_static = mat_menu.addAction(
            ("◉ " if bool(theme_state.get("frost_static")) else "○ ") + "🖼  静态背景 (静态底纹)")
        # 2026-09-25 (第63轮): 毛玻璃底纹 —— 内置图 或 用户自选图片
        mat_menu.addSeparator()
        _fc = bool(theme_state.get("frost_custom"))
        act_frost_pick = mat_menu.addAction(
            ("● " if _fc else "○ ") + "🖼  选择底纹图片…")
        act_frost_reset = mat_menu.addAction("♻️  恢复默认底纹")

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

        act_auto = menu.addAction(("◉ " if autostart_enabled() else "○ ") + "🚀  开机自启动")
        menu.addSeparator()
        act_quit = menu.addAction("🚪  退出程序")

        chosen = menu.exec(ev.globalPos())
        if chosen == act_hide:
            self.hide()
        elif chosen == act_dark:
            self.set_dark(not theme_state["dark"])
        elif chosen == act_mat_none:
            self._set_material(None)           # 第63轮: 回默认(无玻璃)
        elif chosen == act_blur:
            # 互斥 + 可取消: 点当前项 = 取消回默认; 否则切到液态玻璃(自动关毛玻璃)
            self._set_material(None if theme_state["glass"] else "glass")
        elif chosen == act_static:
            self.set_static_bg(not theme_state.get("frost_static"))
        elif chosen == act_frost:
            self._set_material(None if theme_state.get("frost") else "frost")
        elif chosen == act_frost_pick:
            self.choose_frost_image()
        elif chosen == act_frost_reset:
            self.reset_frost_image()
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

    def _set_always_top(self, on):
        """第97轮后半重写: 窗口置顶开关(设置页用) —— Win32 SetWindowPos, **不重显窗口**。

        前两次失败记录(浅猫两次反馈"还是闪一下"):
          · 第95轮原版: `setWindowFlags(flags)` + `show()` —— Qt 在 Windows 上改 window flags
            会销毁并重建原生窗口, 整窗必然闪;
          · 第97轮前半"改用 Win32"仍失败 —— 真凶是 `SetWindowPos` **没设 argtypes**,
            64 位下 ctypes 按 32 位 int 传 HWND, 句柄被截断 → 调用失败 → 静默回退到
            上面那条 flags 老路, 所以观感一模一样。argtypes 已在 win_backdrop 补上。

        现在的正确做法:
          · 只改 Z 序(SWP_NOACTIVATE|SWP_NOMOVE|SWP_NOSIZE), 不碰窗口式样 → 不闪;
          · frost 背板与主窗口**必须按"先背板、后主窗"的顺序**改 ——
            TOPMOST/NOTOPMOST 都会把目标移到同层顶部, 顺序反了会把背板提到主窗前面盖住面板;
          · Win32 真失败了才退回 flags 路径(非 Windows 平台本来就走这条)。
        """
        try:
            on = bool(on)
            self._always_top = on
            fw = getattr(self, "_frost_win", None)
            ok = False
            try:
                import win_backdrop as _wb
                # ① 先背板(仅当它真的在场上; 非毛玻璃模式下背板不可见, 不碰它)
                ok_fw = True
                fw = getattr(self, "_frost_win", None)
                if fw is not None and fw.isVisible():
                    ok_fw = _wb.set_topmost(int(fw.winId()), on)
                # ② 后主窗 —— TOPMOST/NOTOPMOST 都会把目标移到同层顶部, 所以主窗要后改
                ok_main = _wb.set_topmost(int(self.winId()), on)
                ok = ok_fw and ok_main
            except Exception:
                ok = False
            if not ok:
                # 非 Windows / Win32 失败: 退回 Qt flags 路径(行为与第95轮一致)
                flags = self.windowFlags()
                flags = (flags | Qt.WindowStaysOnTopHint) if on else (flags & ~Qt.WindowStaysOnTopHint)
                was = self.isVisible()
                self.setWindowFlags(flags)
                if fw is not None:
                    ff = fw.windowFlags()
                    ff = (ff | Qt.WindowStaysOnTopHint) if on else (ff & ~Qt.WindowStaysOnTopHint)
                    fw.setWindowFlags(ff)
                if was:
                    self.show()
            theme_state["always_top"] = on
            save_settings()
        except Exception:
            pass
    def _sync_top_bar(self):
        """顶栏该显示什么 —— 第97轮起**唯一**的判据出口。

        之前 range_box 的显隐散在两处: `_apply_page()`(刷新链路每次都走, 无条件 True)
        和 `_show_settings()`(逐子件隐藏)。一刷新后者就被前者覆盖 —— 这就是
        "设置页顶部冒出很长一条 今日/7天/30天/全部" 的真正原因。
        现在两边都只调这里, 由它统一求与: 区间条 = 「不在设置页」且「当前数据源有区间概念」。
        """
        in_set = bool(getattr(self, "_in_settings", False))
        src = getattr(self, "source", "wb")
        self.range_box.setVisible((not in_set) and src not in ("sn", "multi"))
        self.subtitle.setVisible(not in_set)
        if getattr(self, "lbl_set_title", None) is not None:
            self.lbl_set_title.setVisible(in_set)

    def _show_settings(self, on):
        """显示/隐藏设置页, 并维护「设置 与 数据源」的并列单选关系。

        第97轮: 顶栏**不再整体隐藏** —— 左上换成「设置」二字, 右上角的最小化/关闭保持原位,
        与统计页完全同一条基线; 统计区(stack)整体让位给设置页。
        """
        on = bool(on)
        self._in_settings = on
        if getattr(self, "page_settings", None) is None:
            self.page_settings = SettingsPage(self)
            self.work_lay.addWidget(self.page_settings, 1)
        # ① 导航互斥: 进设置页时熄灭全部数据源按钮
        if on:
            for b in (self.btn_nav_wb, self.btn_nav_dsh, self.btn_nav_sn,
                      self.btn_nav_multi):
                b.blockSignals(True)
                b.setChecked(False)
                b.blockSignals(False)
        if getattr(self, "btn_nav_set", None) is not None:
            self.btn_nav_set.blockSignals(True)
            self.btn_nav_set.setChecked(on)
            self.btn_nav_set.blockSignals(False)
        # ② 内容切换: work_lay 只有 top_bar(布局) / stack / page_settings 三项
        self.stack.setVisible(not on)
        self.page_settings.setVisible(on)
        # ③ 顶栏唯一出口(区间条/副标题/设置标题)
        self._sync_top_bar()
        try:
            self.apply_styles()
        except Exception:
            pass
        if on:
            self.page_settings.refresh()



# ============================================================ 开机自启 (双轨保险)
VBS_PATH = os.path.join(os.environ.get("APPDATA", ""),
                        "Microsoft", "Windows", "Start Menu", "Programs",
                        "Startup", "TokenAuditCard.vbs")
_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_RUN_NAME = "TokenAuditCard"


def _launcher_exe():
    """带图标的轻量启动器 exe（由 launcher.py 打包而来，体积约 8~10MB，内含 PySide6 的整包 84MB）。
    存在时，开机自启 / 一键重启 都优先走它 —— 这样对外看起来就是一个正常软件。"""
    for name in ("TokenStats.exe", "Token统计.exe"):
        p = os.path.join(BASE_DIR, name)
        if os.path.exists(p):
            return p
    return None


def _launch_argv():
    """启动本程序所需命令行：
    · 主程序已被打包 → 就是自己
    · 有轻量启动器 exe → 用启动器（双击/自启/重启都统一走它）
    · 开发时 → pythonw + card_app.py
    供"开机自启"和"一键重启"共用，避免打包后指向不存在的 pythonw/脚本。"""
    if getattr(sys, "frozen", False):
        return [sys.executable]
    launcher = _launcher_exe()
    if launcher:
        return [launcher]
    pythonw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    if not os.path.exists(pythonw): pythonw = sys.executable
    # ★ 开发态(没有启动器 exe)也要带 -B (2026-10-25 第99轮):
    #   火绒会把 __pycache__/card_app.cpython-313.pyc 判成 Trojan 并**结束进程**,
    #   表现为"桌宠起来一秒就消失"。带 -B 不写字节码, 从源头绕开。
    return [pythonw, "-B", os.path.abspath(__file__)]


def _autostart_command():
    return " ".join(f'"{a}"' for a in _launch_argv())


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
            # ★ 该脚本由系统按 ANSI(本地代码页) 读取: 用 mbcs 写才不会在路径含中文时编码失败
            #   (原写 ascii, 只要路径里有中文就抛 UnicodeEncodeError 而不是 OSError, 会直接崩菜单)
            try:
                with open(VBS_PATH, "w", encoding="mbcs") as f:
                    f.write(content)
            except (UnicodeEncodeError, LookupError):
                with open(VBS_PATH, "w", encoding="utf-8") as f:
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
        # 2026-09-23 (第60轮): 毛玻璃模式 (与深/浅色、液态玻璃都不冲突)
        theme_state["frost"] = bool(d.get("frost"))
        # 2026-09-25 (第63轮): 毛玻璃底纹用自定义图 or 内置默认图
        theme_state["frost_custom"] = bool(d.get("frost_custom"))
        theme_state["frost_static"] = bool(d.get("frost_static"))
        theme_state["source"] = d.get("source", "wb")
        theme_state["pet"] = bool(d.get("pet"))
        # ★ 一次性迁移到新素材库(v3): 旧版设置里的 pet_theme=v1/v2 会把新素材挡掉。
        # ⚠️ 原写法(只判断标记位 pet_theme_v3)有 bug: save_settings() 落地的是 theme_state,
        #    里面并没有 pet_theme_v3 这个键 -> 标记保存一次就丢, 迁移于是**每次启动都重新触发**,
        #    把浅浅猫新选的 v4/v2 强行改回 v3(2026-09-15 定位到的反复回退根因)。
        #   现改为: 只有"确实还是旧版(v1/v2)"才升级, 且把标记放进 theme_state 让它能被保存。
        _pt = d.get("pet_theme", "v3")
        _v3r = res("assets", "pet_v3r")
        if _pt in ("v1", "v2") and os.path.isdir(_v3r):
            _pt = "v3"
        theme_state["pet_theme_v3"] = True      # 随 theme_state 一起保存, 防止反复迁移
        if d.get("pet_theme") != _pt or not d.get("pet_theme_v3"):
            try:
                d["pet_theme"] = _pt
                d["pet_theme_v3"] = True
                with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                    json.dump(d, f, ensure_ascii=False, indent=1)
            except OSError:
                pass
        theme_state["pet_theme"] = _pt
        theme_state["window_size"] = d.get("window_size", "default")
        theme_state["glass_transparency"] = d.get("glass_transparency", "balanced")
    except Exception:
        pass


# ============================================================ 桌宠形态 (DeepSeek 娘)
PET_THEMES = {
    # update 2026-10-25 (第99轮): 新增 V5 —— 浅浅猫做的「蓝色鲸鱼少女表情贴纸包」
    #   素材源 = 蓝色鲸鱼少女表情贴纸包.png (1422x1106): 左侧「待机」区 2行x3列 + 右侧「睡觉」区 2张
    #   映射(浅猫指定): 待机行1 三张 = idle_01~03 / 待机行2 第一张 = idle_04 /
    #     待机行2 第二张(闭眼+爱心泡泡) = click / 睡觉两张 = sleep_01~02
    #   drag、wake 暂无专属素材, 由 idle_01 / idle_04 派生(同一张站姿画布, 切换时大小不跳),
    #   以后补了专属素材直接替换文件即可, 不用改代码。
    "v5": {"name": "鲸鱼少女 V5", "dir": res("assets", "pet_v5")},
    # update 2026-09-14 (第40轮): 新增 V4 —— 浅浅猫指定右键菜单显示名 "deepseek娘V4Pro"
    #   素材源 = setC (ChatGPT Image 2026年9月14日 07_20_09.png, 2行x6列=12帧, 透明底零抠图)
    #   映射: C1~C3=idle / C4=sleep / C5=wake / C6=drag / C7~C10=click / C11=sidle
    "v4": {"name": "deepseek娘V4Pro", "dir": res("assets", "pet_v4")},
    "v3": {"name": "最新素材 (v3 · 与原版合并)", "dir": res("assets", "pet_v3r")},
    "v2": {"name": "新版素材 (高清)", "dir": res("assets", "pet_v2")},
    "v1": {"name": "经典素材 (旧版)", "dir": res("assets", "pet")},
}
# idle=普通待机 / sleep=睡觉 / wake=睡醒 / drag=拖拽 / click=点击互动
# sidle=特殊待机动作(持续15~60s) / pat=摸摸头(随机取一个)
# update 2026-09-15: 把 "special" 加回列表 —— V2 素材没有 pat 目录, 它的 special/ 才是摸摸头库;
#   少了这一项会导致 pet_v2/special/*.png 根本不加载, 摸摸头只能退化成待机
#   (这是第39轮我把 special 换成 pat 时漏掉的回归)。
PET_ANIMS = ("idle", "sleep", "wake", "drag", "click", "sidle", "pat", "special")
PET_W, PET_H = 118, 148
PET_SLEEP_AFTER = 60            # 待机多久后入睡(秒)
PET_SLEEP_DUR = (90, 240)       # 睡觉时长随机区间(秒) —— 浅浅猫要求"最少大于一分半"
PET_OTHER_EVERY = (150, 420)    # 特殊待机动作触发间隔(秒)
# update 2026-10-23 (浅浅猫): 特殊待机持续 15~60s -> **30~60s** (触发间隔 150~420s 不变)
PET_SIDLE_DUR = (30, 60)        # 特殊待机动作持续时长(秒)
PET_MS = {"idle": 240, "sleep": 1500, "wake": 700, "drag": 140,
          "click": 300, "sidle": 600, "pat": 600}
# 2026-09-17 浅浅猫的想法: 桌宠"顶部 1/3"点= 摸摸头, 其余(底部 2/3)= 普通点击互动;
# 任意位置双击 = 打开面板。判据用**实际绘制区域**的高度比例, 不是窗口高度(见 _pet_click_region)。
PET_PAT_TOP_RATIO = 1.0 / 3.0
APP_BUILD = "v9.4-frost"         # update 2026-10-21 (第87轮): 三菜单统一+emoji+v9.4; 上: v9.3-frost(第62轮)
                                 # 代号 frost = 真·实时高斯模糊毛玻璃材质为主线特性;
                                 # 历史: v9.2-multi(第59轮) 多机同步 / v8.8-auto-sync 商汤真自动


def _pet_idle_seq(n):
    """普通待机序列 (浅浅猫 2026-09-14 定调, 2026-10-23 改数值):
       第 0 帧(idle_01) = **默认待机, 停留 10~20 秒** (旧: 8~20s);
       其它待机帧只是"**随机偶尔**"插进来各停 **5 秒** (旧: 2~3s), 然后回到默认待机。
       —— 绝不能均匀轮播全部帧, 否则看起来就是个循环。
       tick = PET_MS["idle"] = 240ms -> N 拍 ≈ N*0.24s (21 拍 ≈ 5.0s, 42 拍 ≈ 10.1s)。"""
    n = max(1, int(n))
    # ⚠️ 结构要点: 每一段"连续默认帧"都必须完整落在 10~20s 内。
    #   旧写法是 [默认8~20s] + [回默认2~4s] + [插帧2~3s] —— 两段 0 相邻会连成一段,
    #   实测连续默认帧最长到 24s(超出浅浅猫要求的 20s)。现改为插帧后直接接**新的一段
    #   完整 10~20s 默认**, 插帧本身只停 5s, 不再有"2~4s 的小段"。
    seq = [0] * random.randint(42, 84)              # 默认待机 ≈ 10~20s
    for _ in range(random.randint(0, 2)):           # 偶尔(0~2 次)插入一个随机其它帧
        if n >= 2:
            seq += [random.randrange(1, n)] * 21    # 该帧停 5s
        seq += [0] * random.randint(42, 84)         # 再回默认待机 ≈ 10~20s
    return seq


def load_pet_frames(theme=None):
    theme = theme or theme_state.get("pet_theme", "v3")
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


def load_pet_seqs(theme=None):
    """加载「完整动作帧组」—— 通用机制 (第99轮, 浅浅猫要求"以后其它单张动作也能加")。

    目录约定::

        <主题>/seq/<场景>/<组名>/01.png .. NN.png   (+ 可选 seq.json: {"ms": 1000})

    设计要点:
      * **一个场景支持多组**(A/B/C...), 运行时随机挑一组播 —— 以后想给某个动作再多做
        几套完整动作, 只要往 `seq/<场景>/` 下丢一个新目录, **不用改一行代码**。
      * 组内 PNG 按文件名排序顺序播放; **少于 2 帧视为无效**(单张静止图用普通帧库即可)。
      * 场景名必须属于 PET_ANIMS, 其它目录忽略(避免误读)。原始目录不存在则返回空 dict。
      * `seq.json` 的 `ms` 覆盖该场景的 PET_MS 节拍; 不给就沿用 PET_MS。
        组与组可以有不同节奏(例如睡觉慢、点击快)。

    返回: {场景: [{"name": 组名, "frames": [QImage...], "ms": int}, ...]}
    """
    theme = theme or theme_state.get("pet_theme", "v3")
    if theme not in PET_THEMES:
        return {}
    root = os.path.join(PET_THEMES[theme]["dir"], "seq")
    out = {}
    if not os.path.isdir(root):
        return out
    try:
        for scene in sorted(os.listdir(root)):
            sd = os.path.join(root, scene)
            if scene not in PET_ANIMS or not os.path.isdir(sd):
                continue
            groups = []
            for g in sorted(os.listdir(sd)):
                gd = os.path.join(sd, g)
                if not os.path.isdir(gd):
                    continue
                imgs = []
                for fn in sorted(os.listdir(gd)):
                    if not fn.lower().endswith(".png"):
                        continue
                    img = QImage(os.path.join(gd, fn))
                    if not img.isNull():
                        imgs.append(img)
                if len(imgs) < 2:
                    continue
                ms = PET_MS.get(scene, 240)
                cfg = os.path.join(gd, "seq.json")
                if os.path.isfile(cfg):
                    try:
                        with open(cfg, encoding="utf-8") as f:
                            ms = int(json.load(f).get("ms", ms))
                    except Exception:
                        pass
                groups.append({"name": g, "frames": imgs, "ms": max(60, int(ms))})
            if groups:
                out[scene] = groups
    except OSError:
        return {}
    return out


# ============================================================ 悬浮球 / 桌宠
class BallWindow(QWidget):
    def __init__(self, card):
        super().__init__()
        self.card = card
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)

        self.pet_theme = theme_state.get("pet_theme", "v3")
        self.pet_frames = None
        self.pet_seqs = {}                  # update 2026-10-25: 完整动作帧组 (见 load_pet_seqs)
        self._seq_frames = None             # 非 None = 当前场景正在播"完整动作帧组"
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
        # update 2026-10-25: 完整动作帧组与普通帧库**分开存** ——
        #   不塞进 pet_frames, 否则 frames 的 key 不再是纯场景名, 回归里
        #   `sum(len(v) for v in pet_frames.values())` 这类统计会被多算一项。
        self.pet_seqs = load_pet_seqs(self.pet_theme) if fr is not None else {}
        self._loaded_pet_theme = self.pet_theme
        return fr

    # 素材缺失时的回退链 (旧素材没有 wake/sidle/pat 目录时不至于空白)
    _ANIM_FALLBACK = {"wake": ("wake", "sleep", "idle"),
                      "sidle": ("sidle", "special", "idle"),
                      "pat": ("pat", "special", "idle")}

    def _frames_of(self, st):
        fr = self.pet_frames or {}
        for k in self._ANIM_FALLBACK.get(st, (st, "idle")):
            if fr.get(k):
                return fr[k]
        return []

    def _has_anim(self, st):
        """严格判断主题里**真有** st 的素材(排除最后回退到 idle 的那一档)。

        update 2026-10-25 (第99轮): V5 这种"只有基本动作"的主题没有 sidle/pat,
        `_frames_of("sidle")` 会一路回退到 idle 帧 -> 旧写法 `if self._frames_of("sidle")`
        就会被判为"有特殊待机", 于是桌宠定格 30~60 秒不动。这里把回退链里的 idle 摘掉。
        """
        fr = self.pet_frames or {}
        return any(fr.get(k) for k in self._ANIM_FALLBACK.get(st, (st,)) if k != "idle")

    def _pick_seq(self, st):
        """取该场景的一组完整动作帧 (多组时随机挑一组); 没有返回 None。"""
        grp = (self.pet_seqs or {}).get(st)
        if not grp:
            return None
        return random.choice(grp)

    def _pet_state(self, st, seq=None, seq_frames=None, ms=None):
        """切场景。

        update 2026-10-25 (第99轮) 新增参数:
          * `seq_frames`: 传了 = 本场景改播这组**完整动作帧**(paintEvent 从这里取帧),
            `seq` 就是组内下标序列; 不传则清空, 回到普通帧库。
          * `ms`: 覆盖 PET_MS 的节拍(动作帧组自带节奏, 例如睡觉 1000ms/帧)。
        """
        self._state = st
        self._seq_frames = seq_frames        # 每次切场景都重置, 防止上一组残留
        if seq is not None:
            self._seq = seq
        elif st == "idle":
            self._seq = _pet_idle_seq(len(self._frames_of("idle")))
        elif st == "sleep":
            grp = self._pick_seq("sleep")
            if grp is not None:
                # 有完整动作帧(第99轮 = A 套 8 帧循环)时顺序播放、循环到底,
                # 睡姿会缓慢呼吸/眨眼, 比"一次睡觉只取一张静止帧"自然得多。
                self._seq_frames = grp["frames"]
                self._seq = list(range(len(grp["frames"])))
                ms = ms or grp["ms"]
            else:
                # 睡觉(浅浅猫 2026-09-14 修正): 没有动作帧组的主题, 仍然
                #   **一次睡觉只取一帧**, 整段保持不动 —— 不循环、不轮播全部睡觉帧。
                fr = self._frames_of("sleep")
                i = random.randrange(len(fr)) if fr else 0
                self._seq = [i] * 8
            self._sleep_until = time.time() + random.uniform(*PET_SLEEP_DUR)
        elif st == "wake":
            # 睡醒 (浅浅猫 2026-10-23 改): ① 素材换成 2026-10-23 新入库的那批(旧 V3 睡醒帧已退役);
            #   ② 时长加长 —— 旧 3 拍(700ms)≈2.1s -> 6 拍 ≈ 4.2s, 让伸懒腰/揉眼的动作看得完整;
            #   ③ 播完**随机**接「继续睡觉」或「恢复到待机」(见 _pet_tick, 旧行为是固定回待机)。
            grp = self._pick_seq("wake")
            if grp is not None:
                self._seq_frames = grp["frames"]
                self._seq = list(range(len(grp["frames"])))
                ms = ms or grp["ms"]
            else:
                fr = self._frames_of("wake")
                i = random.randrange(len(fr)) if fr else 0
                self._seq = [i] * 6
        elif st == "drag":
            grp = self._pick_seq("drag")
            if grp is not None:
                self._seq_frames = grp["frames"]
                self._seq = list(range(len(grp["frames"])))
                ms = ms or grp["ms"]
            else:
                fr = self._frames_of("drag")
                i = random.randrange(len(fr)) if fr else 0
                self._seq = [i] * 10
        self._si = 0
        self._tm.start(ms or PET_MS.get(st, 240))
        self.update()

    def _pet_tick(self):
        if not self.pet or self.pet_frames is None: return
        now = time.time()
        if self._state == "sleep":
            # 睡够随机时长(>=90s) -> 播"睡醒"帧
            if now >= getattr(self, "_sleep_until", now + PET_SLEEP_DUR[0]):
                self._pet_state("wake")
                return
        elif self._state == "idle":
            if now - self._idle_t > PET_SLEEP_AFTER:
                self._pet_state("sleep")
                return
            if now >= self._next_other:
                self._next_other = now + random.randint(*PET_OTHER_EVERY)
                # update 2026-10-25: 用 _has_anim 严格判断 —— 素材少的主题(V5)没有 sidle,
                #   旧写法会回退到 idle 帧被误判成"有", 结果定格 30~60s 不动。
                if self._has_anim("sidle"):
                    self._pet_sidle()
                    return
        self._si += 1
        if self._si >= len(self._seq):
            if self._state == "idle":
                self._seq = _pet_idle_seq(len(self._frames_of("idle")))
                self._si = 0
            elif self._state in ("sleep", "drag"):
                self._si = 0
            elif self._state == "wake":
                # 浅浅猫 2026-10-23: 睡醒之后**随机**接「继续睡觉」或「恢复到待机」
                #   (旧行为: 睡醒播完必定回待机 —— 醒了就不再睡, 少了"赖床"的自然感)
                self._pet_state("sleep" if random.random() < 0.4 else "idle")
                return
            else:
                self._pet_state("idle")
                return
        # 流畅性: 帧号未变化(静止帧)时跳过重绘, 大幅降低桌宠常驻时的 CPU/绘制开销
        cur = self._seq[self._si % len(self._seq)] if self._seq else -1
        if cur != getattr(self, "_last_drawn", -1):
            self._last_drawn = cur
            self.update()

    def _pet_click_region(self, y):
        """按"点在哪"分流互动 (浅浅猫 2026-09-17 提议):
        角色**顶部 1/3** = 摸摸头(pat), 其余**底部 2/3** = 普通点击互动(click)
        —— 摸头要点在"头上"才自然, 点身体是普通互动。

        边界用**实际绘制区域**的高度比例, 而不是窗口高度: 矮宽的帧(如躺姿)
        只画在窗口下半部分, 按窗口算会把"角色头顶以上的空白"也判成摸头。
        """
        rect = getattr(self, "_pet_draw_rect", None)
        if rect is not None and rect.height() > 0:
            top, hh = rect.top(), rect.height()
        else:
            top, hh = 0.0, float(self.height())
        if y < top + hh * PET_PAT_TOP_RATIO:
            self._pet_pat()
        else:
            self._pet_click()

    def _pet_click(self):
        fr = self._frames_of("click")
        i = random.randrange(len(fr)) if fr else 0
        self._idle_t = time.time()
        self._pet_state("click", seq=[i, i, i])

    def _pet_sidle(self):
        """特殊待机动作: 随机取一个, 持续 15~60 秒 (不是一闪而过)"""
        fr = self._frames_of("sidle")
        if not fr: return
        i = random.randrange(len(fr))
        self._idle_t = time.time()
        ms = PET_MS["sidle"]
        ticks = max(1, int(random.uniform(*PET_SIDLE_DUR) * 1000 / ms))
        self._pet_state("sidle", seq=[i] * ticks)

    def _pet_pat(self):
        """摸摸头: 只随机取"一个"帧播放 (不再把整库依次播一遍)"""
        fr = self._frames_of("pat")
        if not fr: return
        i = random.randrange(len(fr))
        self._idle_t = time.time()
        self._pet_state("pat", seq=[i] * 3)

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
            self.setToolTip("DeepSeek 娘 · 点头部 1/3 摸摸头 / 点身体单击互动 / 双击打开统计 / 右键菜单")
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
            # update 2026-10-25: 正在播"完整动作帧组"时从这里取帧(组内顺序循环),
            #   否则回普通帧库(按场景 + 回退链)。两条路的 _seq 都是帧下标。
            frames = self._seq_frames if self._seq_frames else self._frames_of(self._state)
            if not frames: return
            frame_no = self._seq[self._si % len(self._seq)]
            img = frames[frame_no % len(frames)]
            iw, ih = img.width(), img.height()
            scale = min(138.0 / ih, (PET_W - 10.0) / iw)
            dw, dh = iw * scale, ih * scale
            rect = QRectF((PET_W - dw) / 2.0, PET_H - 4 - dh, dw, dh)
            self._pet_draw_rect = rect      # 供点击分区判断"角色头顶 1/3"用
            p.drawImage(rect, img)
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
            # 第97轮后半13 修(浅猫: "关闭桌宠模式时, 悬浮球无法拖动"):
            #   `_moved` 的置位原来带了 `and self.pet` —— 关掉桌宠后它永远是 False,
            #   `if self._moved: self.move(...)` 永不执行 → 悬浮球拖不动;
            #   而且松手时 `not self._moved` 成立还会**误弹统计面板**(拖一下弹一下)。
            #   拖动本身与桌宠形态无关, 只有"拖动时播 drag 动画"才该看 self.pet。
            if not self._moved and moved_now:
                self._moved = True
                if self.pet:
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
                # 按点击高度分流: 顶部 1/3 = 摸摸头, 底部 2/3 = 点击互动
                self._pet_click_region(ev.position().y())
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
        a2 = menu.addAction("🔃  立即刷新数据")
        a_restart = menu.addAction("🔄  一键重启")
        menu.addSeparator()

        # 2026-09-25 (第63轮): 三种材质统一单选组 (与面板右键/侧栏按钮语义完全一致)
        _cur_glass = bool(theme_state["glass"])
        _cur_frost = bool(theme_state.get("frost"))
        mat_menu = menu.addMenu("🪟  窗口材质")
        a_mat_none = mat_menu.addAction(
            ("◉ " if not (_cur_glass or _cur_frost) else "○ ") + "⬜ 默认 (无玻璃)")
        a_glass = mat_menu.addAction(
            ("◉ " if _cur_glass else "○ ") + "💎 液态玻璃 (iOS 27)")
        a_frost = mat_menu.addAction(
            ("◉ " if _cur_frost else "○ ") + "🫧 毛玻璃 (系统实时模糊)")
        # 第87轮(浅猫): 悬浮球菜单补齐「静态背景」与面板一致
        a_static = mat_menu.addAction(
            ("◉ " if bool(theme_state.get("frost_static")) else "○ ") + "🖼  静态背景 (静态底纹)")
        # 2026-09-25 (第63轮): 毛玻璃底纹入口 (与面板菜单一致)
        mat_menu.addSeparator()
        _fc = bool(theme_state.get("frost_custom"))
        a_frost_pick = mat_menu.addAction(
            ("● " if _fc else "○ ") + "🖼  选择底纹图片…")
        a_frost_reset = mat_menu.addAction("♻️  恢复默认底纹")
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
                for key in PET_THEMES:
                    act = a_theme_menu.addAction(PET_THEMES[key]["name"])
                    act.setCheckable(True)
                    act.setChecked(self.pet_theme == key)
                    act.setData(key)
                a_head = menu.addAction("🤗  摸摸头")
        menu.addSeparator()
        a_quit = menu.addAction("🚪  退出")

        chosen = menu.exec(ev.globalPos())
        if chosen is not None and chosen.data() in PET_THEMES:
            self.set_pet_theme(chosen.data())
        elif chosen == a1:
            self._trigger_popup()
        elif chosen == a2:
            if self.card:
                self.card.popup_from(self.frameGeometry())
                self.card.refresh()
        elif chosen == a_mat_none:
            if self.card:
                self.card._set_material(None)          # 回默认(无玻璃)
        elif chosen == a_glass:
            if self.card:
                self.card._set_material(
                    None if theme_state["glass"] else "glass")   # 可取消
        elif chosen == a_frost:
            if self.card:
                self.card._set_material(
                    None if theme_state.get("frost") else "frost")  # 可取消
        elif chosen == a_static:
            if self.card:
                self.card.set_static_bg(not theme_state.get("frost_static"))
        elif chosen == a_frost_pick:
            if self.card:
                self.card.choose_frost_image()
        elif chosen == a_frost_reset:
            if self.card:
                self.card.reset_frost_image()
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
            self._pet_pat()
        elif chosen == a_restart:
            _restart_app()
        elif chosen == a_quit:
            os._exit(0)


class SettingsPage(QWidget):
    """第97轮: 设置页面 —— 严格照 `docs/设置页面-方案A-v2.html` 落地。

    与示意图逐项对齐:
      · 页面标题「设置」在**顶栏**(lbl_set_title), 与主界面同一条基线、右上最小/关闭按钮原位保留;
      · 卡片 = GlassPodFrame(radius=_PANEL_RADIUS, frame=True) + CardHeader + 一行 hint;
      · 行 = 左「标题 + 副标题」两行、右控件; 行间 1px 细线, 首行无线(示意图 .row:first-of-type);
      · 二选一/多选一 = **真·分段控件**(seg_box_qss 外框 + role "seg" 药丸), 与顶栏区间条同源;
      · 网格候选(桌宠主题) = role "pick": 选中只把描边/淡底/文字换成强调色, 不做实心块;
      · 操作按钮 = role "opt" 独立胶囊(选择图片 / 恢复默认 / 一键重启 …);
      · 滚动条 = style_scroll_area() 自绘细样式;
      · 不含「数据源」卡片(侧栏顶部已有来源切换);
      · 每次操作后重建本页, 但**保住滚动位置**(第97轮: 原来切一次桌宠主题就跳回顶端)。
    """

    ROW_H = 46

    def __init__(self, win):
        super().__init__()
        self.win = win
        self._live = []            # 第97轮: 需要局部刷新的控件登记表
        self._built = False
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.area = QScrollArea()
        self.area.setWidgetResizable(True)
        style_scroll_area(self.area)
        host = QWidget()
        self.v = QVBoxLayout(host)
        # 顶部不留白: 「设置」二字由主窗口顶栏承担, 页面与统计页共用同一条基线
        self.v.setContentsMargins(2, 0, 10, 2)
        self.v.setSpacing(11)
        self.area.setWidget(host)
        outer.addWidget(self.area)

        self._build()

    # ---------------- 基础构件 ----------------
    def _reg(self, w, kind, param=None):
        """登记一个"需要随主题/材质局部刷新"的控件(第97轮)。

        第97轮(浅猫: "设置页切换主题时卡片和文字会弹一下")的根治方案:
        原来 `refresh()` 是全量销毁重建 —— 旧控件 deleteLater 还在、新控件已入布局,
        中间帧必然出现"新旧叠加/高度塌陷", 观感就是弹一下。
        现在改成**局部更新**: 只重设样式表与选中态, 不增删任何控件。
        """
        self._live.append((w, kind, param))
        return w

    def _card(self, title, hint="", accent=None):
        f = GlassPodFrame(radius=_PANEL_RADIUS, rule=False, frame=True)
        lay = QVBoxLayout(f)
        lay.setContentsMargins(15, 9, 15, 9)
        lay.setSpacing(0)
        lay.addWidget(CardHeader(title, accent or BLUE))
        if hint:
            h = QLabel(hint)
            # 左侧 22px 与 CardHeader 的标题文字左缘对齐(CardHeader 从 x=22 起画字)
            h.setStyleSheet("color:%s; font-size:11px; padding:2px 0 4px 22px;" % qname(TEXT3))
            h.setWordWrap(True)
            self._reg(h, "label", "TEXT3")
            lay.addWidget(h)
        self.v.addWidget(f)
        return lay

    def _row(self, lay, title, sub, widget, height=None, sub_out=None):
        row = QWidget()
        row.setFixedHeight(height or self.ROW_H)   # 桌宠主题是 2x2 网格, 要更高一些
        rl = QHBoxLayout(row)
        rl.setContentsMargins(2, 0, 2, 0)
        rl.setSpacing(12)
        box = QWidget()
        bl = QVBoxLayout(box)
        bl.setContentsMargins(0, 0, 0, 0)
        bl.setSpacing(1)
        t = QLabel(title)
        t.setStyleSheet("font-size:12.5px; font-weight:600; color:%s;" % qname(TEXT))
        self._reg(t, "label", "TEXT")
        bl.addWidget(t)
        if sub:
            s = QLabel(sub)
            s.setStyleSheet("color:%s; font-size:11px;" % qname(TEXT3))
            # 副标题可能很长(例如"当前：毛玻璃（系统实时模糊）"): 允许被压窄, 不撑破行
            s.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
            s.setMinimumWidth(0)
            self._reg(s, "label", "TEXT3")
            if isinstance(sub_out, list):
                sub_out.append(s)
            bl.addWidget(s)
        rl.addWidget(box, 1)
        rl.addWidget(widget, 0, Qt.AlignVCenter)
        lay.addWidget(row)
        return row

    def _line(self, lay, out=None):
        ln = QFrame()
        ln.setFrameShape(QFrame.HLine)
        ln.setFixedHeight(1)
        ln.setStyleSheet("background:%s; border:none;" % qname(BORDER))
        self._reg(ln, "line")
        if isinstance(out, list):
            out.append(ln)
        lay.addWidget(ln)
        return ln

    def _btn(self, text, role, checkable=False, checked=False, cb=None, width=None):
        b = QPushButton(text)
        b.setCursor(Qt.PointingHandCursor)
        if checkable:
            b.setCheckable(True)
            b.setChecked(checked)
            if cb:
                b.toggled.connect(cb)
        elif cb:
            b.clicked.connect(cb)
        b.setStyleSheet(material_btn_qss(role, theme_state["dark"], theme_state["glass"],
                                         theme_state["frost"], px=12))
        self._reg(b, "qss", role)
        b.setMinimumHeight(28)
        if width:
            b.setFixedWidth(width)
        return b

    def _seg(self, items, cur, on_pick, min_w=0, sink=None):
        """真·分段控件(示意图 .seg): 外框一个圆角容器, 内部按钮无隔断、选中=实色药丸。

        与顶栏的时间区间条**同一套语言**(都走 seg_box_qss + role "seg")。
        ⚠️ 用 QButtonGroup(exclusive) 保证"点已选中项不会被取消选中" —— 否则会
        先 uncheck 再被重建刷回, 观感是"点了一下闪一下又弹回来"。
        `sink` 用来回收 (key, button) 对, 供 `_resync()` 局部改选中态。
        """
        w = QWidget()
        w.setStyleSheet(seg_box_qss(theme_state["dark"], theme_state["glass"],
                                    theme_state["frost"]))
        self._reg(w, "segbox")
        hl = QHBoxLayout(w)
        hl.setContentsMargins(3, 2, 3, 2)
        hl.setSpacing(0)
        grp = QButtonGroup(w)
        grp.setExclusive(True)
        for key, label in items:
            b = QPushButton(label)
            b.setCursor(Qt.PointingHandCursor)
            b.setCheckable(True)
            b.setChecked(key == cur)
            b.setStyleSheet(material_btn_qss("seg", theme_state["dark"],
                                             theme_state["glass"], theme_state["frost"], px=12))
            self._reg(b, "qss", "seg")
            b.setMinimumHeight(24)
            if min_w:
                b.setMinimumWidth(min_w)
            b.clicked.connect(lambda _=False, k=key: on_pick(k))
            grp.addButton(b)
            if isinstance(sink, list):
                sink.append((key, b))
            hl.addWidget(b)
        return w

    def _switch(self, on, on_pick, yes="开", no="关", sink=None):
        """二选一开关 —— 也是分段控件, 只是两项固定为 开 / 关。"""
        return self._seg([(True, yes), (False, no)], on, on_pick, min_w=54, sink=sink)

    def _grid_pick(self, items, cur, on_pick, cols=2, min_w=148, sink=None):
        """网格候选(示意图 .pick 2x2): 选中只换描边/淡底/文字色, 网格里不做实心块。"""
        w = QWidget()
        gl = QGridLayout(w)
        gl.setContentsMargins(0, 0, 0, 0)
        gl.setHorizontalSpacing(7)
        gl.setVerticalSpacing(7)
        grp = QButtonGroup(w)
        grp.setExclusive(True)
        for i, (key, label) in enumerate(items):
            b = QPushButton(label)
            b.setCursor(Qt.PointingHandCursor)
            b.setCheckable(True)
            b.setChecked(key == cur)
            b.setStyleSheet(material_btn_qss("pick", theme_state["dark"],
                                             theme_state["glass"], theme_state["frost"], px=12))
            self._reg(b, "qss", "pick")
            b.setMinimumHeight(30)
            b.setMinimumWidth(min_w)
            b.clicked.connect(lambda _=False, k=key: on_pick(k))
            grp.addButton(b)
            if isinstance(sink, list):
                sink.append((key, b))
            gl.addWidget(b, i // cols, i % cols)
        return w

    def _pills(self, items, min_w=96):
        """操作按钮组(示意图 .picks): 独立描边胶囊, 非互斥。

        第97轮(浅猫: "选择底图的那两个按钮宽度不够"): 给一个默认最小宽度,
        让「选择图片…」「♻️ 恢复默认」这类按钮不至于被文字撑得歪歪扭扭。
        """
        w = QWidget()
        hl = QHBoxLayout(w)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.setSpacing(7)
        for label, cb in items:
            b = self._btn(label, "opt", cb=cb)
            if min_w:
                b.setMinimumWidth(min_w)
            hl.addWidget(b)
        return w

    def _after(self):
        """操作后: 同步主窗口样式 → 局部刷新本页(不再全量重建, 见 refresh)。"""
        try:
            self.win.apply_styles()
        except Exception:
            pass
        self.refresh()

    def _cur_mat(self):
        """实时读出当前材质 key —— 与 _resync() 同一套判据。"""
        ts = theme_state
        return ("static" if ts.get("frost_static") else
                ("frost" if ts.get("frost") else ("glass" if ts.get("glass") else "")))

    def _act(self, fn):
        """执行一个设置动作, 并让设置页即时跟上(选中态 / "当前：xxx" 文案)。

        第97轮后半4: 材质/透明度/尺寸这些走主窗口方法的动作, 原来**没有**回调设置页,
        点完按钮选中态不更新(看着像"没生效")。统一在这里补一次局部刷新。
        """
        try:
            fn()
        except Exception:
            pass
        self._after()

    def _pick_material(self, k):
        """点材质按钮: 命中当前项 = 取消回默认; 否则切到该项。

        ⚠️ 第97轮后半4(浅猫: "点毛玻璃不生效, 液态/静态下点毛玻璃会切到默认"):
        原来这里的判据是 `_build()` 时算好的 `cur_mat`, 由 lambda 闭包捕获 ——
        改成局部刷新后 `_build()` 只跑一次, 这个**旧值就再也不更新**了。
        于是: 启动时是毛玻璃(cur_mat="frost") → 切液态 → 再点毛玻璃, 仍被判成
        "点的是已选中项" → 传 None → 掉回默认。
        修法: 判据改成**点击当时实时读** `self._cur_mat()`, 不再依赖任何缓存。
        """
        self.win._set_material(None if k == self._cur_mat() else k)
        self._after()

    # ---------------- 局部刷新(第97轮: 不再全量重建) ----------------
    def _retheme(self):
        """只重设已登记控件的**配色** —— 不增删控件, 所以不会弹一下。

        ⚠️ 第97轮后半修(浅猫: "设置页内字体未适配浅色模式"):
        原来登记时存的是**当前主题的 QColor 对象**, 而 `refresh_palette()` 是
        `globals().update(TEXT=QColor(...))` —— 会建**新对象**, 登记表里仍持着旧对象
        → 切到浅色后 label 还是深色主题的字色。现在登记的是**颜色变量名**,
        每次都在 `globals()` 里现取, 永远跟着当前主题走。
        """
        d = bool(theme_state["dark"])
        g = bool(theme_state["glass"])
        f = bool(theme_state["frost"])
        for w, kind, param in self._live:
            try:
                if w is None:
                    continue
                if kind == "qss":
                    w.setStyleSheet(material_btn_qss(param, d, g, f, px=12))
                elif kind == "segbox":
                    w.setStyleSheet(seg_box_qss(d, g, f))
                elif kind == "line":
                    w.setStyleSheet("background:%s; border:none;" % qname(globals()["BORDER"]))
                elif kind == "label":
                    col = globals().get(param, param) if isinstance(param, str) else param
                    w.setStyleSheet("color:%s;" % qname(col))
            except Exception:
                pass

    def _resync(self):
        """把每个控件的**选中态与"当前：xxx"文案**同步到 theme_state / 桌宠实例。

        只改 setChecked / setText, 不碰布局 —— 切主题、切材质、切桌宠主题都走这条,
        观感上就是"按钮变色", 没有重建抖动。
        """
        ts = theme_state
        ball = PET_BALL.get("w")
        cur_mat = ("static" if ts.get("frost_static") else
                   ("frost" if ts.get("frost") else ("glass" if ts.get("glass") else "")))
        tr_name = {"crystal": "晶透水滴", "balanced": "标准液态",
                   "frosted": "柔和微透"}.get(ts.get("glass_transparency", "balanced"), "标准")

        def _pick(pairs, cur):
            for k, b in pairs:
                if b is not None:
                    b.blockSignals(True)
                    b.setChecked(k == cur)
                    b.blockSignals(False)

        _pick(getattr(self, "_dark_btns", []), "dark" if ts["dark"] else "light")
        _pick(getattr(self, "_mat_btns", []), cur_mat)
        _pick(getattr(self, "_tr_btns", []), ts.get("glass_transparency", "balanced"))
        _pick(getattr(self, "_size_btns", []), ts.get("window_size", "default"))
        _pick(getattr(self, "_sw_autostart", []), autostart_enabled())
        _pick(getattr(self, "_sw_top", []), bool(getattr(self.win, "_always_top", True)))
        pet_on = bool(ball.pet) if ball is not None else bool(ts.get("pet"))
        _pick(getattr(self, "_sw_pet", []), pet_on)
        _pick(getattr(self, "_pet_btns", []),
              (ball.pet_theme if ball is not None else ts.get("pet_theme", "v3")))

        # 文案: "当前：xxx"
        if getattr(self, "_lbl_mat", None) is not None:
            self._lbl_mat.setText("当前：" + {"frost": "毛玻璃（系统实时模糊）",
                                             "glass": "液态玻璃",
                                             "static": "静态背景"}.get(cur_mat, "默认（无玻璃）"))
        if getattr(self, "_lbl_tr", None) is not None:
            self._lbl_tr.setText("当前：" + tr_name + "（仅液态玻璃生效）")
        if getattr(self, "_lbl_frost", None) is not None:
            self._lbl_frost.setText("当前：" + ("自定义图片" if ts.get("frost_custom")
                                               else "内置默认底纹"))
        cur_pet = (ball.pet_theme if ball is not None else ts.get("pet_theme", "v3"))
        if getattr(self, "_lbl_pet", None) is not None:
            self._lbl_pet.setText("当前：" + PET_THEMES.get(cur_pet, {}).get("name", cur_pet))

        # 桌宠主题行: 桌宠关闭时整行(含分隔线)隐藏 —— 用显隐而不是重建, 保持无抖动
        vis = bool(pet_on)
        for wdg in getattr(self, "_pet_row", []):
            try:
                wdg.setVisible(vis)
            except Exception:
                pass

    def refresh(self):
        """刷新设置页。

        第97轮后半(浅猫: "切换主题时设置页里的卡片和文字会弹一下"):
        原来这里是**全量销毁重建** —— 旧控件 deleteLater 尚未处理、新控件已入布局,
        中间帧出现新旧叠加/高度塌陷 → 弹一下。现在:
          · 首次(或结构需要变时)才 `_build()`;
          · 其余一律 `_retheme()` + `_resync()` 局部刷新, 不增删控件;
          · 滚动位置**天然保持**(控件没被销毁), 不需要再保存/还原。
        """
        if not getattr(self, "_built", False):
            self._build()          # _build() 内部会置 _built = True
            return
        self._retheme()
        self._resync()

    # ---------------- 内容 ----------------
    def _build(self):
        # ⚠️ 第97轮后半修(浅猫: "设置页卡片重复, 从头到尾有两套完整的设置卡片"):
        #    `_built` 原来在 refresh() 里置位, 而 __init__ 是**直接调 _build()** →
        #    _built 永远是 False → 之后每次 `_show_settings(True)` 里的 refresh()
        #    都会再 _build() 一遍, 于是页面上摞了两套卡片。
        #    现在把标志位挪进 _build() 本身, 谁调用都一样。
        self._built = True
        w = self.win
        ts = theme_state
        ball = PET_BALL.get("w")
        # 第97轮: 局部刷新所需的登记表(每次 _build 都重新收集)
        self._live = []
        self._dark_btns, self._mat_btns, self._tr_btns, self._size_btns = [], [], [], []
        self._sw_autostart, self._sw_top, self._sw_pet, self._pet_btns = [], [], [], []
        self._lbl_mat = self._lbl_tr = self._lbl_frost = self._lbl_pet = None
        self._pet_row = []          # 桌宠主题行 + 分隔线(桌宠关闭时整组隐藏)

        cur_mat = ("static" if ts.get("frost_static") else
                   ("frost" if ts.get("frost") else ("glass" if ts.get("glass") else "")))
        mat_name = {"frost": "毛玻璃（系统实时模糊）", "glass": "液态玻璃",
                    "static": "静态背景"}.get(cur_mat, "默认（无玻璃）")
        tr_name = {"crystal": "晶透水滴", "balanced": "标准液态",
                   "frosted": "柔和微透"}.get(ts.get("glass_transparency", "balanced"), "标准")
        pet_on = bool(ball.pet) if ball is not None else bool(ts.get("pet"))
        cur_pet = (ball.pet_theme if ball is not None else ts.get("pet_theme", "v3"))

        # ① 外观
        l = self._card("外观", "窗口材质四选一；再点一次已选中的项即可取消，回到默认", BLUE)
        self._row(l, "深色模式", "夜间更护眼（与侧栏底部开关同步）",
                  self._seg([("dark", "深色"), ("light", "浅色")],
                            "dark" if ts["dark"] else "light",
                            lambda k: self._act(lambda: w.set_dark(k == "dark")),
                            min_w=62, sink=self._dark_btns))
        self._line(l)
        self._row(l, "窗口材质", "当前：" + mat_name,
                  self._seg([("", "默认"), ("frost", "毛玻璃"),
                             ("glass", "液态"), ("static", "静态")],
                            # ⚠️ 走 _pick_material: 判据实时读, 不再用闭包里的旧 cur_mat
                            cur_mat, self._pick_material,
                            min_w=58, sink=self._mat_btns),
                  sub_out=None)
        # 副标题 label 要能在 _resync 里改文案: 从 layout 里取回来
        self._lbl_mat = self._sub_of(l, -1)
        self._line(l)
        self._row(l, "液态玻璃透明度", "当前：" + tr_name + "（仅液态玻璃生效）",
                  self._seg([("crystal", "💎 晶透"), ("balanced", "💧 标准"),
                             ("frosted", "🌫️ 柔和")],
                            ts.get("glass_transparency", "balanced"),
                            lambda k: self._act(lambda: w.set_glass_transparency(k)),
                            min_w=66, sink=self._tr_btns))
        self._lbl_tr = self._sub_of(l, -1)
        self._line(l)
        self._row(l, "毛玻璃底纹",
                  "当前：" + ("自定义图片" if ts.get("frost_custom") else "内置默认底纹"),
                  self._pills([("选择图片…", lambda: self._pick_frost_image()),
                               ("♻️ 恢复默认", lambda: self._reset_frost_image())]))
        self._lbl_frost = self._sub_of(l, -1)

        # ② 窗口与启动
        l2 = self._card("窗口与启动", "尺寸切换后立即生效并被记住", GREEN)
        self._row(l2, "窗口尺寸", "标准 990×610 / 舒适 1180×730",
                  self._seg([("default", "标准 990×610"), ("large", "舒适 1180×730")],
                            ts.get("window_size", "default"),
                            lambda k: self._act(lambda: w.apply_size_mode(k)),
                            min_w=118, sink=self._size_btns))
        self._line(l2)
        self._row(l2, "开机自启动", "跟随当前用户登录启动",
                  self._switch(autostart_enabled(), lambda v: self._set_autostart(v),
                               sink=self._sw_autostart))
        self._line(l2)
        self._row(l2, "窗口置顶", "始终显示在最前",
                  self._switch(bool(getattr(w, "_always_top", True)),
                               lambda v: self._act(lambda: w._set_always_top(v)),
                               sink=self._sw_top))

        # ③ 桌宠 —— 主题行**常驻**, 靠显隐切换(不再重建, 见 _resync)
        l3 = self._card("桌宠", "顶 1/3 抚摸，底 2/3 点击；双击打开统计面板", PURPLE)
        self._row(l3, "显示桌宠", "关闭时托盘图标仍在",
                  self._switch(pet_on, lambda v: self._set_pet(v), sink=self._sw_pet))
        ln = self._line(l3)
        self._pet_row.append(ln)
        row = QWidget()
        row.setFixedHeight(74)
        rl = QHBoxLayout(row)
        rl.setContentsMargins(2, 0, 2, 0)
        rl.setSpacing(12)
        lb = QWidget()
        lbl = QVBoxLayout(lb)
        lbl.setContentsMargins(0, 0, 0, 0)
        lbl.setSpacing(1)
        t = QLabel("桌宠主题")
        t.setStyleSheet("font-size:12.5px; font-weight:600; color:%s;" % qname(TEXT))
        self._reg(t, "label", "TEXT")
        lbl.addWidget(t)
        s = QLabel("当前：" + PET_THEMES.get(cur_pet, {}).get("name", cur_pet))
        s.setStyleSheet("color:%s; font-size:11px;" % qname(TEXT3))
        s.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        s.setMinimumWidth(0)
        self._reg(s, "label", "TEXT3")
        self._lbl_pet = s
        lbl.addWidget(s)
        rl.addWidget(lb, 1)
        # update 2026-10-25 (第99轮): 主题从 4 个变 5 个 (新增 V5) -> 网格 2 列改 3 列,
        #   否则 5 个按钮会排成 3 行、超出 74px 的行高被裁掉。
        rl.addWidget(self._grid_pick([("v5", PET_THEMES["v5"]["name"]),
                                      ("v4", PET_THEMES["v4"]["name"]),
                                      ("v3", PET_THEMES["v3"]["name"]),
                                      ("v2", PET_THEMES["v2"]["name"]),
                                      ("v1", PET_THEMES["v1"]["name"])],
                                     cur_pet, lambda k: self._set_pet_theme(k),
                                     cols=3, min_w=126, sink=self._pet_btns), 0, Qt.AlignVCenter)
        l3.addWidget(row)
        self._pet_row.append(row)

        # ④ 关于
        l4 = self._card("关于", "", GREEN)
        self._row(l4, "版本", APP_BUILD + " · 双层窗口毛玻璃架构",
                  self._pills([("🔄 一键重启", _restart_app),
                               ("🔃 立即刷新", lambda: w.refresh(force=True))]))

        self.v.addStretch(1)
        self._resync()

    def _sub_of(self, lay, idx):
        """取卡片 layout 里第 idx 个 row 的副标题 label(idx 为负 = 倒数, -1 = 最后一行)。

        第97轮: `_row()` 为了不把 label 散得到处都是, 不直接返回副标题;
        这里按需从布局里取回来, 供 `_resync()` 改"当前：xxx"文案。
        """
        try:
            n = lay.count()
            i = n + idx if idx < 0 else idx
            it = lay.itemAt(i)
            row = it.widget() if it is not None else None
            if row is None or row.layout() is None:
                return None
            rl = row.layout()
            if rl.count() < 1:
                return None
            left = rl.itemAt(0).widget()      # 左侧文字盒子
            if left is None or left.layout() is None:
                return None
            bl = left.layout()
            if bl.count() < 2:
                return None                    # 没有副标题行
            return bl.itemAt(1).widget()
        except Exception:
            return None

    # ---------------- 动作 ----------------
    def _set_pet(self, on):
        """开关桌宠。

        第97轮修: 原来只在 `ball is not None` 时才写 `theme_state["pet"]` ——
        桌宠实例还没创建时(首次启动/极端情况)开关就"点了没反应", 设置页与真实状态脱节。
        现在**无论实例在不在**, 状态都写进 theme_state 并落盘。
        """
        on = bool(on)
        ball = PET_BALL.get("w")
        try:
            if ball is not None:
                ball.set_pet(on)
        except Exception:
            pass
        theme_state["pet"] = on
        try:
            save_settings()
        except Exception:
            pass
        self._after()

    def _set_pet_theme(self, key):
        ball = PET_BALL.get("w")
        try:
            if ball is not None:
                ball.set_pet_theme(key)
        except Exception:
            pass
        # 与 _set_pet 同理: 实例不在也要记住选择, 否则设置页显示与实际不符
        theme_state["pet_theme"] = key
        try:
            save_settings()
        except Exception:
            pass
        self._after()

    def _pick_frost_image(self):
        try:
            self.win.choose_frost_image()
        except Exception:
            pass
        self._after()

    def _reset_frost_image(self):
        try:
            self.win.reset_frost_image()
        except Exception:
            pass
        self._after()

    def _set_autostart(self, v):
        try:
            set_autostart(bool(v))
        except Exception:
            pass
        self._after()



def _restart_app():
    try:
        import subprocess
        # 打包后 argv 就是 exe 自己；开发时是 pythonw + 脚本（见 _launch_argv）
        subprocess.Popen(_launch_argv(), cwd=APP_DIR, env=_clean_spawn_env(),
                         creationflags=0x00000008 | 0x00000200)
    except Exception: pass
    # 150ms 足够新实例完成 pid 接管(_kill_stale_instance 兜底杀旧进程), 又远快于 300ms
    QTimer.singleShot(150, os._exit, 0)


# PyInstaller 6.x onefile 引导器会校验「父进程可执行文件是否与自己一致」
# (Security validation failure: parent process has different executable!)。
# 我们的一键重启是 pythonw.exe → 拉起 TokenStats.exe, 父进程对不上, 引导器直接拒绝启动
# → 拉起子进程时把这些引导器环境变量剥掉, 让新 exe 像"从资源管理器双击"一样干净启动。
_PYI_ENV_KEYS = ("_PYI_APPLICATION_HOME_DIR", "_PYI_ARCHIVE_FILE",
                 "_PYI_PARENT_PROCESS_LEVEL", "_PYI_SPLASH_IPC", "_MEIPASS2")


def _clean_spawn_env():
    env = os.environ.copy()
    for k in list(env):
        if k in _PYI_ENV_KEYS or k.startswith("PYINSTALLER_"):
            env.pop(k, None)
    return env


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


# ============================================================ 系统托盘 (2026-09-16)
class TrayIcon(QObject):
    """系统托盘常驻图标：面板"最小化"收进这里，图标右键有菜单。

    · 图标 = 与 exe / 任务栏 同一张 app_icon（三处统一）
    · 左键单击 / 双击 = 显示或收起统计面板
    · 右键菜单 = 打开面板 / 立即刷新 / 桌宠形态 / 素材版本 / 摸摸头 / 退出
    """

    def __init__(self, app, card, ball):
        super().__init__(app)
        self.app = app
        self.card = card
        self.ball = ball
        self._hint_shown = False

        self.tray = QSystemTrayIcon(app_icon(), app)
        self.tray.setToolTip(f"{APP_NAME} — 单击显示面板 / 右键菜单")
        self.tray.activated.connect(self._on_activated)

        # ★ 与桌宠右键菜单用**同一套自绘样式**(make_menu: 圆角 + 半透明 + 主题配色),
        #   而不是系统默认菜单(默认菜单方角灰底, 和面板风格不搭)。
        self.menu = make_menu(None)
        self.menu.aboutToShow.connect(self._build_menu)   # 每次弹出前重建, 保证勾选状态最新
        self._build_menu()
        self.tray.setContextMenu(self.menu)
        self.tray.show()

    # ---------- 菜单 ----------
    def _build_menu(self):
        m = self.menu
        m.setStyleSheet(menu_qss())      # 主题(明/暗)切换后同步刷新样式
        m.clear()
        self._submenus = []              # ★ 子菜单要留引用: 托盘菜单长期存在,
                                         #   局部变量被子菜单只在 rebuild 期间有效, 会被 GC 回收
        a_open = m.addAction("📊  打开统计面板")
        a_open.triggered.connect(self.card.show_from_tray)
        a_refresh = m.addAction("🔃  立即刷新数据")
        a_refresh.triggered.connect(self._refresh)
        m.addSeparator()

        a_pet = m.addAction("🐳  桌宠形态 (DeepSeek 娘)")
        a_pet.setCheckable(True)
        a_pet.setChecked(bool(self.ball.pet))
        a_pet.triggered.connect(lambda: self.ball.set_pet(not self.ball.pet))

        theme_menu = m.addMenu("🎨  素材版本")
        theme_menu.setStyleSheet(menu_qss())   # 子菜单也显式套上(不依赖样式继承, 保证与桌宠菜单一致)
        self._submenus.append(theme_menu)      # 留引用防 GC
        for key in PET_THEMES:
            act = theme_menu.addAction(PET_THEMES[key]["name"])
            act.setCheckable(True)
            act.setChecked(self.ball.pet_theme == key)
            act.setData(key)
        theme_menu.triggered.connect(
            lambda a: a.data() in PET_THEMES and self.ball.set_pet_theme(a.data()))

        a_pat = m.addAction("🤗  摸摸头（点头部 1/3 也行）")
        a_pat.triggered.connect(self.ball._pet_pat)
        m.addSeparator()

        a_restart = m.addAction("🔄  一键重启")
        a_restart.triggered.connect(_restart_app)
        a_quit = m.addAction("🚪  退出")
        a_quit.triggered.connect(self._quit)

    def _refresh(self):
        self.card.show_from_tray()
        self.card.refresh()

    def _quit(self):
        self.tray.hide()
        os._exit(0)

    # ---------- 交互 ----------
    def _on_activated(self, reason):
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            if self.card.isVisible():
                self.card.hide()
            else:
                self.card.show_from_tray()

    def show_message_once(self):
        """首次从面板最小化到托盘时提示一次, 之后不再打扰。"""
        if self._hint_shown:
            return
        self._hint_shown = True
        try:
            self.tray.showMessage(APP_NAME, "已最小化到托盘，点击图标可重新打开",
                                  app_icon(), 3000)
        except Exception:
            pass


def run_selftest():
    """--selftest: 无界面自检（打包后用它验证资源/图标/托盘是否正常）。

    窗口模式下 exe 没有控制台，所以结果同时写到 数据目录/selftest.txt。
    """
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    lines = []

    def log(msg):
        lines.append(str(msg))

    log(f"frozen     = {getattr(sys, 'frozen', False)}")
    log(f"APP_DIR    = {APP_DIR}")
    log(f"_MEIPASS   = {getattr(sys, '_MEIPASS', '(未打包)')}")
    log(f"BASE_DIR   = {BASE_DIR}")
    log(f"exe        = {sys.executable}")
    app = QApplication([])
    app.setApplicationName(APP_NAME)
    ic = app_icon()
    log(f"app_icon   = {'OK ' + str(ic.availableSizes()[:8]) if not ic.isNull() else '★ 加载失败'}")
    for name in ("app_icon.ico", "app_icon.png"):
        log(f"  {name:<16} exists={os.path.exists(res('assets', name))}  path={res('assets', name)}")
    log(f"tray_available = {QSystemTrayIcon.isSystemTrayAvailable()}")
    for t in PET_THEMES:
        fr = load_pet_frames(t)
        log(f"theme {t:<3} = " + (str({k: len(v) for k, v in sorted(fr.items())})
                                   if fr else "★ 加载失败"))
    ok = (not ic.isNull()) and all(load_pet_frames(t) for t in PET_THEMES)
    log(f"RESULT = {'PASS' if ok else 'FAIL'}")
    try:
        rp = os.path.join(scanner.PLUGIN_DATA_DIR, "selftest.txt")
        with open(rp, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        print(f"(selftest 报告已写入 {rp})")
    except Exception as e:
        print("写报告失败:", e)
    print("\n".join(lines))
    return 0 if ok else 1


def main():
    if "--selftest" in sys.argv:
        sys.exit(run_selftest())
    _kill_stale_instance()
    # 任务栏图标归组: 必须在 QApplication 之前设置, 否则任务栏显示的是 python 图标
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
    except Exception:
        pass
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_NAME)
    app.setWindowIcon(app_icon())          # ② 任务栏/所有窗口 图标
    app.setQuitOnLastWindowClosed(False)   # 托盘常驻: 关掉所有窗口也不退出
    app.setStyle("Fusion")
    load_settings()
    refresh_palette()
    apply_app_qss()

    card = CardWindow()
    ball = BallWindow(card)
    PET_BALL["w"] = ball          # 第96轮: 登记给设置页使用
    # 系统托盘: 可用才启用"最小化到托盘"(不可用时退回原有行为, 并允许关窗即退出)
    tray = TrayIcon(app, card, ball) if QSystemTrayIcon.isSystemTrayAvailable() else None
    card.tray_ok = tray is not None
    if tray is not None:
        card.minimize_to_tray.connect(tray.show_message_once)
        app._tray = tray      # 保持引用, 防止被回收
    else:
        app.setQuitOnLastWindowClosed(True)
    # 2026-09-25 (第63轮): 首次运行时生成毛玻璃内置纹理(抓一次屏 → 模糊 → 存 PNG)。
    # 第64轮: 模糊改用 QGraphicsBlurEffect(QGraphicsScene 系), 不再是纯 QImage 运算 ——
    #   Qt 图形场景类只保证在 GUI 线程可用, 故**不再放后台线程**, 改为事件循环里延后一拍执行
    #   (窗口已画出来才跑, 实测模糊 ~30ms + 存 PNG ~0.2s, 只在底纹文件缺失时发生一次)。
    def _gen_frost_tex():
        try:
            if ensure_frost_texture():
                FrostTexture.instance().load(force=True)
                card._update_all()
        except Exception:
            pass

    if not os.path.exists(FROST_TEX_DEFAULT):
        QTimer.singleShot(0, _gen_frost_tex)

    QTimer.singleShot(0, card.load_initial)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()