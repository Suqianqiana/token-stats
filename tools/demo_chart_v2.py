# -*- coding: utf-8 -*-
"""第97轮后半6: 「每日用量分布」三套方案 —— **同源可切换 demo**。

浅猫要求: "你都实际做出来让我看看实现效果, 用一个同源的卡片做出来可以切换的 demo,
要认真还原, 不能因为是 demo 就简单做。"

所以这里不是 SVG 示意图, 而是:
  · 用**真实的** StackedBarChart / GlassPodFrame / CardHeader 组件;
  · 用**真实的** 主题配色(refresh_palette) 与尺寸度量(curr_metric);
  · 用**真实的** stats.json 数据(与程序跑出来的一模一样);
  · 卡片尺寸 / 内边距 / 圆角 / 字号 **与主程序逐项一致**;
  · 三套画法共用同一份数据与同一套交互(滚轮缩放 / 拖动平移 / 悬浮提示),
    只有 StackedBarChart.mode 不同 —— 对比才有意义。

用法:
    pyside6_python -B tools/demo_chart_v2.py            # 打开窗口自己点着对比
    pyside6_python -B tools/demo_chart_v2.py --shot     # 自动切三套并截图
"""
import os, sys, json, tempfile
sys.dont_write_bytecode = True
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QGuiApplication, QFont
from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
                               QLabel, QPushButton)

import card_app as ca


# ---------------------------------------------------------------- 真实数据
def load_real_data():
    """读真实 stats.json —— 与程序界面里显示的是同一份数据。

    ⚠️ 排行必须按**最近 35 天(图表可见区间)**的用量算, 不能用全历史 ——
    否则"全历史 Top8"里可能有最近没用过的模型, 它们的带厚度为 0 还占着一个
    图例颜色(颜色循环还会和前面的模型撞色)。
    """
    p = ca.scanner.STATS_FILE
    if not os.path.exists(p):
        return None, []
    d = json.load(open(p, encoding="utf-8"))
    daily = d.get("daily") or {}
    days = sorted(x for x in daily if x != "unknown")[-35:]
    window = {day: daily[day] for day in days}
    totals = {}
    for day in days:
        for m, info in daily[day].items():
            totals[m] = totals.get(m, 0) + info.get("total", 0)
    rank = sorted(totals.items(), key=lambda x: -x[1])
    rank = [(m, v) for m, v in rank if v > 0]
    return window, rank


# ---------------------------------------------------------------- demo 窗口
class DemoWin(QWidget):
    """与主程序**同源**的一张卡片 + 切换条。

    卡片用真实 GlassPodFrame(radius=10, frame=True) + CardHeader + StackedBarChart,
    内边距 / 字号 / 配色全部走主程序的 curr_metric() 与 refresh_palette()。
    """

    MODE_LABEL = {
        "stack_area": "D · 堆叠平滑面积",
        "glass_bar": "E · 渐变立体柱",
        "dual": "F · 双视图",
    }

    def __init__(self, daily, rank):
        super().__init__()
        self.setWindowTitle("每日用量分布 · 三套方案对比（同源卡片 demo）")
        self.resize(900, 460)
        # 深色起步 —— 与她日常使用的深色毛玻璃一致(theme_state 默认是浅色, 这里明确指定)
        self.dark = True

        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 14, 16, 14)
        outer.setSpacing(10)

        # ---- 切换条 ----
        bar = QHBoxLayout()
        bar.setSpacing(6)
        self.hint = QLabel("三套画法共用同一份数据与交互（滚轮缩放 / 拖动平移 / 悬浮提示）")
        self.hint.setStyleSheet("color:%s; font-size:11px;" % ca.qname(ca.TEXT3))
        bar.addWidget(self.hint, 1)
        self.mode_btns = {}
        for m in ca.CHART_MODES:
            b = QPushButton(self.MODE_LABEL[m])
            b.setCursor(Qt.PointingHandCursor)
            b.setCheckable(True)
            b.clicked.connect(lambda _=False, mm=m: self.set_mode(mm))
            self.mode_btns[m] = b
            bar.addWidget(b, 0)
        self.btn_theme = QPushButton("🌗 明暗")
        self.btn_theme.setCursor(Qt.PointingHandCursor)
        self.btn_theme.clicked.connect(self.toggle_theme)
        bar.addWidget(self.btn_theme, 0)
        outer.addLayout(bar)

        # ---- 真实卡片(与主程序 chart_card 同构) ----
        self.card = ca.GlassPodFrame(radius=10, rule=False, frame=True)
        cv = QVBoxLayout(self.card)
        cv.setContentsMargins(10, 6, 8, 6)
        cv.setSpacing(0)
        cv.addWidget(ca.CardHeader("每日用量分布", ca.BLUE, bold=False))
        self.chart = ca.StackedBarChart()
        cv.addWidget(self.chart)
        outer.addWidget(self.card, 1)

        # 底部状态
        self.status = QLabel("")
        self.status.setStyleSheet("color:%s; font-size:10.5px;" % ca.qname(ca.TEXT3))
        outer.addWidget(self.status, 0)

        self.chart.set_data(daily, rank)
        self.set_mode(ca.CHART_MODE_DEFAULT)
        self.apply_theme()

    def set_mode(self, m):
        self.chart.set_mode(m)
        for k, b in self.mode_btns.items():
            b.blockSignals(True)
            b.setChecked(k == m)
            b.blockSignals(False)
        n = len(self.chart.data)
        self.status.setText(
            "当前画法：%s    ·    可见 %d 天    ·    滚轮缩放、左右拖动平移、悬停看当日构成"
            % (self.MODE_LABEL[m], n))

    def toggle_theme(self):
        self.dark = not self.dark
        self.apply_theme()

    def apply_theme(self):
        ca.theme_state["dark"] = self.dark
        ca.refresh_palette()
        self.setStyleSheet("background:%s;" % ca.qrgba(ca.BG))
        for k, b in self.mode_btns.items():
            b.setStyleSheet(ca.material_btn_qss(
                "mat", self.dark, bool(ca.theme_state.get("glass")),
                bool(ca.theme_state.get("frost")), px=12))
        self.btn_theme.setStyleSheet(ca.material_btn_qss(
            "opt", self.dark, bool(ca.theme_state.get("glass")),
            bool(ca.theme_state.get("frost")), px=12))
        self.update()


def main():
    ca.SETTINGS_FILE = os.path.join(tempfile.mkdtemp(), "demo_settings.json")
    daily, rank = load_real_data()
    if daily is None:
        print("读不到 stats.json:", ca.scanner.STATS_FILE)
        return 1

    app = QApplication(sys.argv)
    ca.refresh_palette()
    w = DemoWin(daily, rank)
    w.move(160, 120)
    w.show()

    if "--shot" in sys.argv:
        from PySide6.QtTest import QTest
        scr = QGuiApplication.primaryScreen()
        out = os.path.join(ROOT, "docs", "screenshots")
        os.makedirs(out, exist_ok=True)
        QTest.qWait(700)
        ca.ChartTip.instance().hide_tip()      # 防止截图时鼠标恰好停在图上带出悬浮框
        for m in ca.CHART_MODES:
            w.set_mode(m)
            QTest.qWait(500)
            img = scr.grabWindow(0).toImage()
            r = img.width() / float(scr.geometry().width())
            g = w.geometry()
            pad = 6
            crop = img.copy(int((g.x() - pad) * r), int((g.y() - pad) * r),
                            int((g.width() + pad * 2) * r), int((g.height() + pad * 2) * r))
            p = os.path.join(out, "demo_chart_%s.png" % m)
            crop.save(p)
            print("saved", p, crop.width(), "x", crop.height(), flush=True)
        # 浅色版(D 方案)
        w.set_mode("stack_area")
        w.dark = False
        w.apply_theme()
        QTest.qWait(500)
        img = scr.grabWindow(0).toImage()
        r = img.width() / float(scr.geometry().width())
        g = w.geometry()
        crop = img.copy(int((g.x() - 6) * r), int((g.y() - 6) * r),
                        int((g.width() + 12) * r), int((g.height() + 12) * r))
        p = os.path.join(out, "demo_chart_stack_area_light.png")
        crop.save(p)
        print("saved", p, flush=True)
        w.dark = True
        w.apply_theme()
        print("DONE")
        return 0

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
