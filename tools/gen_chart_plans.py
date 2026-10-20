# -*- coding: utf-8 -*-
"""第97轮后半3: 「每日用量分布」视觉优化 —— 三套方案 1:1 示意页生成器。

读真实 stats.json 的最近 35 天数据, 按真实页面几何(990x610 / 侧栏190 / 卡片尺寸)
复刻三个完整窗口, 只有 chart_card 里的图表部分按三种方案分别绘制。
输出: docs/每日用量分布-三套方案.html
"""
import json, os, sys
sys.dont_write_bytecode = True

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATS = os.path.join(os.path.expanduser("~/.workbuddy"), "plugins", "data",
                     "token-usage-stats", "stats.json")
OUT = os.path.join(ROOT, "docs", "每日用量分布-三套方案.html")

# ---------------------------------------------------------------- 真实参数
# ⚠️ 全部与 card_app.py 对齐, 一个数都不许拍脑袋:
#   work_lay.setContentsMargins(18, 14, 18, 14)  → 左18 上14 右18 下14
#   cv.setContentsMargins(10, 6, 8, 6)           → chart 卡片内边距
#   StackedBarChart._geom() → (padL=38, padR=8, padT=4, padB=16)
WIN_W, WIN_H = 990, 610
SIDEBAR = 190
ML, MT, MR, MB = 18, 14, 18, 14
MAIN_W = WIN_W - SIDEBAR - ML - MR                 # 764
TOP_BAR_H, GAP = 26, 10
METRICS_H, TODAY_H = 116, 28
BODY_H = WIN_H - MT - MB - TOP_BAR_H - GAP - METRICS_H - GAP - TODAY_H - GAP   # 382
CHART_CARD_H = round((BODY_H - GAP) * 0.56)        # 208
HEAT_CARD_H = (BODY_H - GAP) - CHART_CARD_H        # 164
CV_L, CV_T, CV_R = 10, 6, 8                        # chart_card 的 cv margins
HEADER_H = 22                                      # CardHeader 固定高
CHART_W = MAIN_W - CV_L - CV_R                     # 746 (StackedBarChart 控件宽)
CHART_H = CHART_CARD_H - CV_T - 6 - HEADER_H       # 174
PAD_L, PAD_R, PAD_T, PAD_B = 38, 8, 4, 16          # _geom() 实测值

SEM = {
    "deepseek-v4.1-flash": "#3b6fe0",
    "hy4-preview": "#3fa45b",
    "hy3": "#e05252",
    "deepseek-v4-flash": "#8b5cd6",
    "step-5-preview": "#d6a72c",
}
DEFAULT_CYCLE = ["#3b6fe0", "#3fa45b", "#e05252", "#8b5cd6", "#d6a72c",
                 "#2fa8bc", "#e06fb8", "#e0813f"]

TH = {
    "dark":  dict(bg="#12141a", side="#171921", card="#1c1f27", card2="#22252e",
                  line="#2e3340", tx="#f0f3f8", tx2="#cdd3de", tx3="#8c94a2",
                  track="#262b34", seg="#23273240", segbd="#3a4152"),
    "light": dict(bg="#f6f8fb", side="#eff3f8", card="#ffffff", card2="#f7f9fc",
                  line="#e2e7f0", tx="#141821", tx2="#5c6473", tx3="#969ea e".replace(" ", ""),
                  track="#edf1f7", seg="#ffffff59", segbd="#e4e8f0"),
}

# ---------------------------------------------------------------- 数据
def load():
    d = json.load(open(STATS, encoding="utf-8"))
    daily, models = d["daily"], d["models"]
    rank = [m for m in sorted(models, key=lambda x: -models[x]["total"])][:5]
    days = sorted(x for x in daily if x != "unknown")[-35:]
    rows = []
    for day in days:
        parts = [(m, daily[day].get(m, {}).get("total", 0)) for m in rank]
        rows.append({"date": day, "parts": parts,
                     "total": sum(v for _, v in parts)})
    return rows, rank

def fmt(v):
    if v >= 1e8:
        return "%.1f亿" % (v / 1e8)
    if v >= 1e4:
        return "%.0f万" % (v / 1e4)
    return "%.0f" % v

def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

# ---------------------------------------------------------------- 图表绘制
def chart_common_open(x, y, w, h, t):
    """chart_card 的外框 + CardHeader(常规字重, 与真实一致)。"""
    return (f'<g><rect x="{x}" y="{y}" width="{w}" height="{h}" rx="10" '
            f'fill="{t["card"]}" stroke="{t["line"]}"/>'
            f'<rect x="{x+15}" y="{y+15}" width="16" height="3" rx="1.5" fill="#3b6fe0"/>'
            f'<text x="{x+37}" y="{y+22}" font-family="Microsoft YaHei UI" font-size="11.3" '
            f'fill="{t["tx"]}">每日用量分布</text></g>')

def chart_body_open(x, y, w, h):
    """图表绘图区左上角(扣掉 cv 左边距 + 上边距 + CardHeader)。

    返回 (cx, cy) —— 即 StackedBarChart 控件自身坐标 (0,0) 在卡片里的位置。
    """
    return x + CV_L, y + CV_T + HEADER_H

def chart_geom(w, h):
    """StackedBarChart 控件自身的绘图区: (px, py, iw, ih) —— 与 _geom()/paintEvent 一致。"""
    iw = (w - CV_L - CV_R) - PAD_L - PAD_R
    ih = (h - CV_T - 6 - HEADER_H) - PAD_T - PAD_B
    return PAD_L, PAD_T, iw, ih

# ---- 方案 A: 圆角胶囊柱 ----
def plan_a(x, y, w, h, rows, rank, t):
    cx, cy = chart_body_open(x, y, w, h)
    px, py, iw, ih = chart_geom(w, h)
    px += cx
    py += cy
    s = []
    maxv = max(r["total"] for r in rows) or 1
    # 网格: 极淡虚线, 只标顶/底/中
    # ⚠️ 标签要与高度对应: k=0 在**底部** → 0; k=2 在**顶部** → maxv(与真实 paintEvent 一致)
    for k, lab in ((0, "0"), (1, fmt(maxv / 2)), (2, fmt(maxv))):
        gy = py + ih - ih * k / 2
        s.append(f'<line x1="{px}" y1="{gy:.1f}" x2="{px+iw}" y2="{gy:.1f}" '
                 f'stroke="{t["line"]}" stroke-dasharray="2 3" stroke-width="1"/>')
        s.append(f'<text x="{px-6}" y="{gy+3:.1f}" text-anchor="end" font-family="Consolas" '
                 f'font-size="7.5" fill="{t["tx3"]}">{lab}</text>')
    n = len(rows)
    slot = iw / n
    bw = max(3.0, min(16.0, slot * 0.6))
    for i, r in enumerate(rows):
        cxx = px + slot * i + slot / 2
        yc = py + ih
        segs = [(m, v) for m, v in r["parts"] if v]
        for j, (m, v) in enumerate(segs):
            hh = v / maxv * ih
            col = SEM.get(m, DEFAULT_CYCLE[rank.index(m) % len(DEFAULT_CYCLE)])
            top = yc - hh
            rr = bw / 2 if j == 0 else 0            # 只有最上一段画圆角
            s.append(f'<rect x="{cxx-bw/2:.1f}" y="{top:.1f}" width="{bw:.1f}" '
                     f'height="{hh:.1f}" rx="{rr:.1f}" fill="{col}"/>')
            yc = top
        if i % max(1, n // 7) == 0 or i == n - 1:
            s.append(f'<text x="{cxx:.1f}" y="{py+ih+PAD_B-4}" text-anchor="middle" '
                     f'font-family="Consolas" font-size="7" fill="{t["tx3"]}">'
                     f'{r["date"][5:].replace("-", "/")}</text>')
    # 峰值标注
    pi = max(range(n), key=lambda i: rows[i]["total"])
    pcx = px + slot * pi + slot / 2
    s.append(f'<circle cx="{pcx:.1f}" cy="{py + ih - rows[pi]["total"]/maxv*ih - 5:.1f}" '
             f'r="2" fill="{t["tx2"]}"/>')
    return "".join(s)

# ---- 方案 B: 平滑面积 + 构成柱 ----
def plan_b(x, y, w, h, rows, rank, t):
    cx, cy = chart_body_open(x, y, w, h)
    px, py, iw, ih = chart_geom(w, h)
    px += cx
    py += cy
    maxv = max(r["total"] for r in rows) or 1
    n = len(rows)
    xs = [px + iw * (i + 0.5) / n for i in range(n)]
    ys = [py + ih - r["total"] / maxv * ih for r in rows]

    # Catmull-Rom -> Bezier 平滑
    def smooth(pts):
        if len(pts) < 2:
            return ""
        d = "M %.1f %.1f" % pts[0]
        for i in range(len(pts) - 1):
            p0 = pts[i - 1] if i > 0 else pts[i]
            p1, p2 = pts[i], pts[i + 1]
            p3 = pts[i + 2] if i + 2 < len(pts) else p2
            c1 = (p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6)
            c2 = (p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6)
            d += " C %.1f %.1f %.1f %.1f %.1f %.1f" % (c1 + c2 + p2)
        return d
    line = smooth(list(zip(xs, ys)))
    area = line + f" L {xs[-1]:.1f} {py+ih:.1f} L {xs[0]:.1f} {py+ih:.1f} Z"

    s = [f'<defs><linearGradient id="gB" x1="0" y1="0" x2="0" y2="1">'
         f'<stop offset="0" stop-color="#3b6fe0" stop-opacity="0.34"/>'
         f'<stop offset="1" stop-color="#3b6fe0" stop-opacity="0.02"/></linearGradient></defs>']
    # 底部淡构成柱
    slot = iw / n
    bw = max(3.0, min(16.0, slot * 0.6))
    for i, r in enumerate(rows):
        cxx = px + slot * i + slot / 2
        yc = py + ih
        for m, v in r["parts"]:
            if not v:
                continue
            hh = v / maxv * ih
            col = SEM.get(m, DEFAULT_CYCLE[rank.index(m) % len(DEFAULT_CYCLE)])
            s.append(f'<rect x="{cxx-bw/2:.1f}" y="{yc-hh:.1f}" width="{bw:.1f}" '
                     f'height="{hh:.1f}" fill="{col}" opacity="0.28"/>')
            yc -= hh
    s.append(f'<path d="{area}" fill="url(#gB)"/>')
    s.append(f'<path d="{line}" fill="none" stroke="#3b6fe0" stroke-width="1.6" '
             f'stroke-linejoin="round"/>')
    # Y 轴只标顶/底
    s.append(f'<text x="{px-6}" y="{py+4}" text-anchor="end" font-family="Consolas" '
             f'font-size="7.5" fill="{t["tx3"]}">{fmt(maxv)}</text>')
    s.append(f'<text x="{px-6}" y="{py+ih+3:.1f}" text-anchor="end" font-family="Consolas" '
             f'font-size="7.5" fill="{t["tx3"]}">0</text>')
    # 日期: 只标首/中/尾
    for i in (0, n // 2, n - 1):
        cxx = px + slot * i + slot / 2
        s.append(f'<text x="{cxx:.1f}" y="{py+ih+12}" text-anchor="middle" '
                 f'font-family="Consolas" font-size="7" fill="{t["tx3"]}">'
                 f'{rows[i]["date"][5:].replace("-", "/")}</text>')
    # 右上: 区间总量 + 环比
    tot = sum(r["total"] for r in rows)
    half = len(rows) // 2
    a, b = sum(r["total"] for r in rows[half:]), sum(r["total"] for r in rows[:half])
    wow = (a - b) / b * 100 if b else 0
    bx = px + iw - 118
    s.append(f'<rect x="{bx}" y="{py-2}" width="118" height="34" rx="8" '
             f'fill="{t["card2"]}" stroke="{t["line"]}"/>')
    s.append(f'<text x="{bx+10}" y="{py+10}" font-family="Microsoft YaHei UI" font-size="8" '
             f'fill="{t["tx3"]}">区间总量</text>')
    s.append(f'<text x="{bx+10}" y="{py+24}" font-family="Microsoft YaHei UI" font-size="13" '
             f'font-weight="700" fill="{t["tx"]}">{fmt(tot)}</text>')
    up = wow >= 0
    s.append(f'<text x="{bx+108}" y="{py+24}" text-anchor="end" font-family="Consolas" '
             f'font-size="9" fill="{"#3fa45b" if up else "#e05252"}">'
             f'{"▲" if up else "▼"} {abs(wow):.0f}%</text>')
    return "".join(s)

# ---- 方案 C: 每日横条 ----
def plan_c(x, y, w, h, rows, rank, t):
    cx, cy = chart_body_open(x, y, w, h)
    chart_w = w - CV_L - CV_R
    s = []
    maxv = max(r["total"] for r in rows) or 1
    row_h = 19.0
    show = min(8, len(rows))
    sub = rows[-show:]
    bar_x = cx + 52
    bar_w = chart_w - 52 - 62
    for i, r in enumerate(sub):
        ry = cy + 3 + i * row_h
        s.append(f'<text x="{cx+8}" y="{ry+11}" font-family="Consolas" font-size="8" '
                 f'fill="{t["tx2"]}">{r["date"][5:].replace("-", "/")}</text>')
        # 轨道
        s.append(f'<rect x="{bar_x}" y="{ry+3}" width="{bar_w}" height="10" rx="5" '
                 f'fill="{t["track"]}"/>')
        # 分段圆角横条
        full = bar_w * (r["total"] / maxv)
        xx = bar_x
        segs = [(m, v) for m, v in r["parts"] if v]
        for j, (m, v) in enumerate(segs):
            ww = full * (v / r["total"])
            col = SEM.get(m, DEFAULT_CYCLE[rank.index(m) % len(DEFAULT_CYCLE)])
            rr = 5 if (j == 0 or j == len(segs) - 1) else 0
            s.append(f'<rect x="{xx:.1f}" y="{ry+3}" width="{ww:.1f}" height="10" rx="{rr}" '
                     f'fill="{col}"/>')
            xx += ww
        s.append(f'<text x="{cx+chart_w-2}" y="{ry+11}" text-anchor="end" font-family="Consolas" '
                 f'font-size="8" fill="{t["tx"]}">{fmt(r["total"])}</text>')
    # 滚动暗示(底部渐隐)
    fade_y = cy + 3 + show * row_h
    s.append(f'<defs><linearGradient id="gC" x1="0" y1="0" x2="0" y2="1">'
             f'<stop offset="0" stop-color="{t["card"]}" stop-opacity="0"/>'
             f'<stop offset="1" stop-color="{t["card"]}" stop-opacity="1"/></linearGradient></defs>')
    s.append(f'<rect x="{cx+2}" y="{fade_y}" width="{chart_w}" height="{max(0, h - CV_T - 6 - HEADER_H - (fade_y - cy)):.0f}" '
             f'fill="url(#gC)"/>')
    return "".join(s)

# ---------------------------------------------------------------- 页面骨架
def window(tag, title, desc, plan_fn, rows, rank, t, dark):
    """复刻一个完整 990x610 窗口(只有 chart_card 内部按方案绘制)。"""
    p = []
    p.append(f'<div class="win" data-theme="{"dark" if dark else "light"}">')
    # 侧栏
    p.append(f'<div class="side" style="background:{t["side"]};border-color:{t["line"]}">')
    p.append('<div class="brand">Token 统计</div>')
    for name, on in (("📘 WorkBuddy", True), ("🗄️ DSH 本地", False),
                     ("⚡ 商汤额度", False), ("🔀 多机合并", False)):
        cls = "nav on" if on else "nav"
        p.append(f'<div class="{cls}">{name}</div>')
    p.append('<div class="sp"></div>')
    p.append(f'<div class="mat" style="background:{t["card"]};border-color:{t["line"]}">'
             f'<b>默认</b><b class="on">毛玻璃</b><b>液态</b><b>静态</b></div>')
    p.append(f'<div class="drow"><span>{"🌙 暗色" if dark else "☀️ 亮色"}</span>'
             f'<span class="sw on"><i></i></span></div>')
    p.append('<div class="btnset">⚙️ 设置</div><div class="ver">v9.4-frost</div>')
    p.append('</div>')
    # 主区
    p.append(f'<div class="main" style="background:{t["bg"]}">')
    # 顶栏
    p.append(f'<div class="topbar"><span class="sub" style="color:{t["tx3"]}">'
             f'WorkBuddy · 真实 usage · 已更新 05:30</span>'
             f'<span class="seg" style="background:{t["seg"]};border-color:{t["segbd"]}">'
             f'<b class="on">今日</b><b>7天</b><b>30天</b><b>全部</b></span>'
             f'<span class="ib">–</span><span class="ib ic">✕</span></div>')
    # MetricsBand
    p.append(f'<div class="metrics" style="background:{t["card"]};border-color:{t["line"]}">'
             f'<div class="mbig"><div class="mlbl" style="color:{t["tx3"]}">合计 TOKEN</div>'
             f'<div class="mval" style="color:{t["tx"]}">1.12<span class="munit">B</span></div>'
             f'<div class="mrow"><span class="chip up">▲ 12.4%</span>'
             f'<span class="mhint" style="color:{t["tx3"]}">近 7 天 6.7 亿 · 今日 4,692 万</span></div></div>'
             f'<div class="mright"><div class="mr"><span class="mk" style="color:{t["tx3"]}">会话</span>'
             f'<span class="mv" style="color:{t["tx"]}">98</span></div>'
             f'<div class="mr"><span class="mk" style="color:{t["tx3"]}">请求</span>'
             f'<span class="mv" style="color:{t["tx"]}">5.6 万</span></div>'
             f'<div class="mr"><span class="mk" style="color:{t["tx3"]}">缓存命中</span>'
             f'<span class="mv" style="color:{t["tx"]}">71.2%</span></div></div></div>')
    # 今日概况条
    p.append(f'<div class="today" style="background:{t["card"]};border-color:{t["line"]};'
             f'color:{t["tx2"]}">今日 4,692 万 · 会话 2 · 已同步 05:30</div>')
    # body
    p.append('<div class="body">')
    p.append('<div class="colL">')
    # chart_card
    p.append(f'<svg class="card" viewBox="0 0 {MAIN_W} {CHART_CARD_H}" width="{MAIN_W}" '
             f'height="{CHART_CARD_H}">')
    p.append(chart_common_open(0, 0, MAIN_W, CHART_CARD_H, t))
    p.append(plan_fn(0, 0, MAIN_W, CHART_CARD_H, rows, rank, t))
    p.append('</svg>')
    # heat_card(按真实复刻: 自绘细样式)
    p.append(f'<svg class="card" viewBox="0 0 {MAIN_W} {HEAT_CARD_H}" width="{MAIN_W}" '
             f'height="{HEAT_CARD_H}">')
    p.append(f'<rect x="0" y="0" width="{MAIN_W}" height="{HEAT_CARD_H}" rx="10" '
             f'fill="{t["card"]}" stroke="{t["line"]}"/>'
             f'<rect x="15" y="15" width="16" height="3" rx="1.5" fill="#3fa45b"/>'
             f'<text x="37" y="22" font-family="Microsoft YaHei UI" font-size="11.3" '
             f'fill="{t["tx"]}">近期活跃热力</text>'
             f'<text x="{MAIN_W-15}" y="22" text-anchor="end" font-family="Microsoft YaHei UI" '
             f'font-size="8" fill="{t["tx3"]}">少 → 多</text>')
    # 热力格子(示意)
    cols = 18
    cell, gapc = 10.0, 2.5
    ox, oy = 15, 40
    for r_ in range(4):
        for c_ in range(cols):
            v = ((r_ * 31 + c_ * 17) % 10) / 9.0
            op = 0.10 + v * 0.72
            p.append(f'<rect x="{ox + c_*(cell+gapc):.1f}" y="{oy + r_*(cell+gapc):.1f}" '
                     f'width="{cell}" height="{cell}" rx="2.5" fill="#3fa45b" '
                     f'opacity="{op:.2f}"/>')
    p.append('</svg>')
    p.append('</div>')  # colL
    # 右栏: 模型明细表(真实复刻)
    p.append('<div class="colR">')
    p.append(f'<div class="tcard" style="background:{t["card"]};border-color:{t["line"]}">')
    p.append(f'<div class="tbar"><span style="color:{t["tx3"]}">模型明细</span>'
             f'<span class="seg2" style="background:{t["seg"]};border-color:{t["segbd"]}">'
             f'<b class="on">今日</b><b>总量</b></span></div>')
    for i, m in enumerate(rank):
        v = rows[-1]["parts"][i][1] if i < len(rows[-1]["parts"]) else 0
        col = SEM.get(m, DEFAULT_CYCLE[i % len(DEFAULT_CYCLE)])
        tot = sum(x[1] for x in rows[-1]["parts"]) or 1
        pct = v / tot * 100
        p.append(f'<div class="trow"><span class="dot" style="background:{col}"></span>'
                 f'<span class="tn" style="color:{t["tx2"]}">{esc(m)}</span>'
                 f'<span class="tv" style="color:{t["tx"]}">{fmt(v)}</span>'
                 f'<span class="tp" style="color:{t["tx3"]}">{pct:.1f}%</span></div>')
    p.append('</div></div>')  # colR
    p.append('</div>')  # body
    p.append('</div>')  # main
    p.append('</div>')  # win
    return "".join(p)

# ---------------------------------------------------------------- 主流程
def main():
    rows, rank = load()
    html = ["""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">
<title>每日用量分布 · 三套方案（1:1 复刻真实页面）</title>
<style>
*{box-sizing:border-box}
body{margin:0;background:#0f1116;color:#eef1f6;
     font:14px/1.6 "Microsoft YaHei UI","Segoe UI",system-ui,sans-serif;padding:26px}
html.light body{background:#f2f4f8;color:#161a22}
h1{font-size:19px;margin:0 0 4px}
.sub{color:#8b93a3;font-size:12.5px;margin-bottom:14px}
.bar{display:flex;gap:10px;align-items:center;margin-bottom:18px}
.theme{padding:7px 14px;border-radius:8px;border:1px solid #2c313b;background:#1a1d24;
       color:#b6bdca;cursor:pointer;font-size:13px}
html.light .theme{border-color:#e4e8f0;background:#fff;color:#5c6473}
.wrap{margin:0 0 34px}
.cap{display:flex;align-items:baseline;gap:12px;margin:0 0 8px}
.cap b{font-size:15px}
.cap span{color:#8b93a3;font-size:12.5px}
/* ==== 真实窗口 990x610 ==== */
.win{width:990px;height:610px;border:1px solid #2c313b;border-radius:12px;overflow:hidden;
     display:flex;box-shadow:0 18px 44px rgba(0,0,0,.4);transform-origin:top left}
html.light .win{border-color:#e4e8f0;box-shadow:0 18px 44px rgba(31,41,61,.14)}
.side{width:190px;flex:none;border-right:1px solid #2c313b;padding:14px 10px 10px;
      display:flex;flex-direction:column;gap:2px}
.brand{font-size:14px;font-weight:700;padding:2px 8px 10px}
.nav{padding:7px 9px;border-radius:8px;color:#b6bdca;font-size:12.5px}
.nav.on{background:rgba(107,138,253,.16);color:#6b8afd;font-weight:600}
.side .sp{flex:1}
.mat{display:flex;gap:2px;border:1px solid #2c313b;border-radius:9px;padding:2px;
     margin:0 2px 6px}
.mat b{flex:1;text-align:center;padding:5px 0;border-radius:7px;font-size:11.5px;
       font-weight:600;color:#8b93a3}
.mat b.on{background:#3b6fe0;color:#fff}
.drow{display:flex;align-items:center;justify-content:space-between;padding:6px 8px;
      border-radius:8px;font-size:12px;color:#b6bdca}
.sw{width:34px;height:19px;border-radius:10px;background:#3b6fe0;position:relative;flex:none}
.sw i{position:absolute;top:2.5px;left:17.5px;width:14px;height:14px;border-radius:50%;background:#fff}
.btnset{margin:4px 2px 6px;padding:8px 0;border-radius:9px;text-align:center;
        background:#3b6fe0;color:#fff;font-size:12.5px;font-weight:700}
.ver{font-size:10.5px;color:#8b93a3;text-align:center;padding-bottom:2px}
.main{flex:1;padding:14px 14px 14px 18px;display:flex;flex-direction:column;gap:10px}
.topbar{display:flex;gap:10px;align-items:center;height:26px;flex:none}
.sub{font-size:9px;flex:1;overflow:hidden;white-space:nowrap}
.seg{display:flex;gap:0;border:1px solid #2c313b;border-radius:9px;padding:2px;flex:none}
.seg b{padding:3px 9px;border-radius:7px;font-size:11px;font-weight:600;color:#b6bdca}
.seg b.on{background:#3b6fe0;color:#fff}
.ib{width:26px;height:26px;border-radius:6px;border:1px solid #2c313b;background:#23273240;
    color:#cdd3de;display:flex;align-items:center;justify-content:center;font-size:13px;
    font-weight:700;flex:none}
.ib.ic:hover{background:rgba(224,82,82,.22);color:#e05252}
.metrics{height:116px;border:1px solid #2c313b;border-radius:10px;display:flex;
         align-items:center;padding:0 22px;gap:26px;flex:none}
.mbig{flex:1}
.mlbl{font-size:8.3pt;color:#8c94a2;letter-spacing:.5px}
.mval{font-size:25.5pt;font-weight:700;line-height:1.15;margin:2px 0 3px}
.munit{font-size:12pt;font-weight:600;margin-left:2px;opacity:.75}
.mrow{display:flex;align-items:center;gap:8px}
.chip{font-size:9.5px;padding:1px 7px;border-radius:6px;font-weight:600}
.chip.up{background:rgba(63,164,91,.16);color:#3fa45b}
.mhint{font-size:8.6pt}
.mright{display:flex;gap:22px;align-items:center}
.mr{display:flex;flex-direction:column;gap:3px;align-items:flex-end}
.mk{font-size:8.3pt}
.mv{font-size:11.3pt;font-weight:600}
.today{height:28px;border:1px solid #2c313b;border-radius:6px;display:flex;
       align-items:center;padding:0 10px;font-size:11px;flex:none}
.body{flex:1;display:flex;gap:10px;min-height:0}
.colL{flex:1;display:flex;flex-direction:column;gap:10px;min-width:0}
.colR{width:250px;flex:none;display:flex;flex-direction:column}
.card{display:block}
.tcard{border:1px solid #2c313b;border-radius:10px;padding:8px 10px;display:flex;
       flex-direction:column;min-height:0;flex:1}
.tbar{display:flex;align-items:center;justify-content:space-between;font-size:8.5pt;
      padding-bottom:6px}
.seg2{display:flex;gap:0;border:1px solid #2c313b;border-radius:8px;padding:2px}
.seg2 b{padding:2px 8px;border-radius:6px;font-size:10px;font-weight:600;color:#b6bdca}
.seg2 b.on{background:#3b6fe0;color:#fff}
.trow{display:flex;align-items:center;gap:8px;height:28px;font-size:8.8pt;
      border-top:1px solid #2c313b}
.trow:first-of-type{border-top:0}
.dot{width:8px;height:8px;border-radius:2.5px;flex:none}
.tn{flex:1;overflow:hidden;white-space:nowrap}
.tv{font-family:Consolas;font-weight:600}
.tp{font-family:Consolas;width:46px;text-align:right}
</style></head><body>
<h1>每日用量分布 · 三套方案（与真实页面 1:1 复刻）</h1>
<div class="sub">三个窗口都是真实 990×610 / 侧栏 190 / 同一套 MetricsBand·今日条·模型明细·活跃热力；
只有「每日用量分布」卡片内部按三种方案绘制。数据取真实 stats.json 最近 35 天 × 用量 Top5 模型。</div>
<div class="bar"><div class="theme" onclick="document.documentElement.classList.toggle('light')">🌗 明/暗切换</div></div>
"""]

    plans = [
        ("方案 A · 圆角胶囊柱", "最小改动：柱子改顶部圆角 + 分段细缝 + 极淡虚线网格 + 峰值标注。"
         "保留原有堆叠语义与交互，观感从「工程图」变成「精致卡片」。", plan_a),
        ("方案 B · 平滑面积 + 构成柱", "主视觉改平滑面积图（渐变填充 + 1.6px 线），底部淡构成柱暗示模型占比，"
         "右上角加区间总量与环比 chip。现代仪表盘风，趋势一眼可读。", plan_b),
        ("方案 C · 每日横条", "放弃柱状，改成「日期 + 圆角横条 + 数值」的列表。无坐标轴无网格，"
         "最干净、可读性最强，代价是只能看最近 8 天（可滚动）。", plan_c),
    ]
    for tag, (name, desc, fn) in zip("ABC", plans):
        html.append(f'<div class="wrap"><div class="cap"><b>{name}</b><span>{desc}</span></div>')
        html.append(window(tag, name, desc, fn, rows, rank, TH["dark"], True))
        html.append('</div>')
    # 浅色版(方案 A 为主, 便于看浅色适配)
    html.append('<div class="wrap"><div class="cap"><b>方案 A · 浅色模式适配</b>'
                '<span>同一套方案在浅色下的表现（字色/网格/描边都走真实浅色主题值）</span></div>')
    html.append(window("A", "A", "", plan_a, rows, rank, TH["light"], False))
    html.append('</div>')
    html.append('</body></html>')

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("".join(html))
    print("saved", OUT, os.path.getsize(OUT), "bytes")

if __name__ == "__main__":
    main()
