# -*- coding: utf-8 -*-
"""第97轮后半5: 「每日用量分布」视觉优化 v2 —— 学习高星前端库后的三套方案。

调研结论(浅猫: "看看 github 上有没有高星的前端库, 学习一下经验"):
  · 排名: D3 113k / Chart.js 67.7k / **Apache ECharts 67.5k** / Plotly 18.4k /
    ApexCharts 15.2k / visx 21k / Nivo 14k。
  · ECharts 官方示例 `area-stack-gradient` 的配置精髓(本次直接借鉴):
      smooth: true          —— 曲线平滑
      stack: 'Total'        —— 堆叠
      showSymbol: false     —— 不画数据点
      lineStyle.width: 0    —— 不要粗描边, 靠面积本身说话
      areaStyle.opacity + LinearGradient(0,0,0,1, [主色 -> 协调色])
                            —— **面积渐变**, 这是"漂亮"的主要来源
      tooltip.axisPointer.type='cross'  —— 十字指示线
  · 社区总结的两条美学经验:
      面积图 → 渐变透明度从实色平滑消散到全透明, 营造"呼吸感";
      柱状图 → 用渐变模拟光源, 让扁平柱产生轻微立体光影。

据此重做三套(全部按真实页面 1:1 复刻, 并针对"玻璃材质"做适配:
半透明叠加、色彩够饱和才能在毛玻璃上看清、圆角与卡片一致)。

输出: docs/每日用量分布-三套方案-v2.html
"""
import os, sys, re
sys.dont_write_bytecode = True

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
OUT = os.path.join(ROOT, "docs", "每日用量分布-三套方案-v2.html")

# 复用 v1 的真实几何 / 配色 / 页面骨架 —— 保证 1:1 与 v1 完全一致, 只换图表画法
from gen_chart_plans import (MAIN_W, CHART_CARD_H, HEAT_CARD_H, CV_L, CV_R, CV_T, HEADER_H,
                             PAD_L, PAD_R, PAD_T, PAD_B, SEM, DEFAULT_CYCLE, TH,
                             load, fmt, esc, window, chart_common_open)

_ctr = [0]
def _uid():
    _ctr[0] += 1
    return "u%d" % _ctr[0]

def _geom(cx, cy, w, h):
    """StackedBarChart 控件绘图区: 返回 (px, py, iw, ih)。"""
    iw = (w - CV_L - CV_R) - PAD_L - PAD_R
    ih = (h - CV_T - 6 - HEADER_H) - PAD_T - PAD_B
    return cx + PAD_L, cy + PAD_T, iw, ih

def _smooth(pts):
    """Catmull-Rom → 三次贝塞尔(与 ECharts smooth 观感一致)。"""
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

def _band(upper_pts, lower_pts):
    """两层曲线之间的带状区域(真正的 stack, 各层渐变互不累积)。"""
    up = _smooth(upper_pts)
    rev = _smooth(list(reversed(lower_pts)))
    return up + " " + rev.replace("M", "L", 1) + " Z"

def _mix(hexc, ratio):
    """把颜色往白/黑方向推: ratio>0 变亮, ratio<0 变暗。"""
    h = hexc.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    if ratio >= 0:
        r = int(r + (255 - r) * ratio); g = int(g + (255 - g) * ratio); b = int(b + (255 - b) * ratio)
    else:
        k = 1 + ratio
        r, g, b = int(r * k), int(g * k), int(b * k)
    return "#%02x%02x%02x" % (r, g, b)

# ---------------------------------------------------------------- 方案 D
def plan_d(x, y, w, h, rows, rank, t):
    """方案 D · 堆叠平滑面积 + 逐层渐变(ECharts area-stack-gradient 风格)

    借鉴点: smooth 平滑 / stack 堆叠 / 不画数据点 / 靠**面积渐变**出彩 /
            层与层之间用一条极细的高光线代替粗描边。
    玻璃适配: 顶不透明度压到 0.62(玻璃底会再透一层, 太实会闷), 底部衰减到 0.10。
    """
    cx, cy = x + CV_L, y + CV_T + HEADER_H
    px, py, iw, ih = _geom(cx, cy, w, h)
    n = len(rows)
    xs = [px + iw * i / (n - 1) for i in range(n)]

    # 累计层(从下往上)
    cum = [0.0] * n
    layers = []
    for m in rank:
        for i, r in enumerate(rows):
            cum[i] += sum(v for mm, v in r["parts"] if mm == m)
        layers.append((m, list(cum)))
    maxv = max(cum) or 1

    s = ['<defs>']
    gids = []
    for i, (m, vals) in enumerate(layers):
        col = SEM.get(m, DEFAULT_CYCLE[rank.index(m) % len(DEFAULT_CYCLE)])
        gid = _uid() + "g"
        gids.append(gid)
        top = _mix(col, 0.18)
        bot = _mix(col, -0.12)
        s.append(f'<linearGradient id="{gid}" x1="0" y1="0" x2="0" y2="1">'
                 f'<stop offset="0" stop-color="{top}" stop-opacity="0.62"/>'
                 f'<stop offset="1" stop-color="{bot}" stop-opacity="0.10"/></linearGradient>')
    s.append('</defs>')

    # 极淡水平网格(只 3 条)
    for k in range(3):
        gy = py + ih - ih * k / 2
        s.append(f'<line x1="{px}" y1="{gy:.1f}" x2="{px+iw}" y2="{gy:.1f}" '
                 f'stroke="{t["line"]}" stroke-opacity="0.55" stroke-width="1"/>')
    s.append(f'<text x="{px-6}" y="{py+4}" text-anchor="end" font-family="Consolas" '
             f'font-size="7.5" fill="{t["tx3"]}">{fmt(maxv)}</text>')
    s.append(f'<text x="{px-6}" y="{py+ih+3:.1f}" text-anchor="end" font-family="Consolas" '
             f'font-size="7.5" fill="{t["tx3"]}">0</text>')

    # 逐层带状面积(从下往上画, 后画的在上)
    prev_pts = [(xs[i], py + ih) for i in range(n)]
    for i, (m, vals) in enumerate(layers):
        col = SEM.get(m, DEFAULT_CYCLE[rank.index(m) % len(DEFAULT_CYCLE)])
        cur_pts = [(xs[j], py + ih - v / maxv * ih) for j, v in enumerate(vals)]
        s.append(f'<path d="{_band(cur_pts, prev_pts)}" fill="url(#{gids[i]})"/>')
        # 层间细高光线(ECharts 的 lineStyle.width=0 我们改成极细一亮线, 玻璃上更有层次)
        s.append(f'<path d="{_smooth(cur_pts)}" fill="none" stroke="{_mix(col, 0.45)}" '
                 f'stroke-width="0.9" stroke-opacity="0.85"/>')
        prev_pts = cur_pts

    # 日期: 首/中/尾
    for i in (0, n // 2, n - 1):
        s.append(f'<text x="{xs[i]:.1f}" y="{py+ih+12}" text-anchor="middle" '
                 f'font-family="Consolas" font-size="7" fill="{t["tx3"]}">'
                 f'{rows[i]["date"][5:].replace("-", "/")}</text>')

    # 悬浮指示线示意(ECharts axisPointer cross)
    hi = max(range(n), key=lambda i: cum[i])
    s.append(f'<line x1="{xs[hi]:.1f}" y1="{py}" x2="{xs[hi]:.1f}" y2="{py+ih}" '
             f'stroke="{t["tx2"]}" stroke-opacity="0.4" stroke-width="1" '
             f'stroke-dasharray="3 2"/>')
    hy = py + ih - cum[hi] / maxv * ih
    s.append(f'<circle cx="{xs[hi]:.1f}" cy="{hy:.1f}" r="2.6" fill="{t["card"]}" '
             f'stroke="{_mix(SEM[rank[-1]], 0.3)}" stroke-width="1.4"/>')
    return "".join(s)

# ---------------------------------------------------------------- 方案 E
def plan_e(x, y, w, h, rows, rank, t):
    """方案 E · 渐变立体柱 + 光影(柱状的美化极限)

    借鉴社区总结的"柱状立体光影": 用**垂直渐变模拟顶光**, 让扁平柱产生轻微立体感;
    柱顶小圆角(与卡片语言一致, 不是卡通胶囊); 柱身左侧 1px 高光; 底部极淡网格。
    """
    cx, cy = x + CV_L, y + CV_T + HEADER_H
    px, py, iw, ih = _geom(cx, cy, w, h)
    n = len(rows)
    slot = iw / n
    bw = max(3.0, min(16.0, slot * 0.62))
    maxv = max(r["total"] for r in rows) or 1

    s = ['<defs>']
    gids = {}
    for m in rank:
        col = SEM.get(m, DEFAULT_CYCLE[rank.index(m) % len(DEFAULT_CYCLE)])
        gid = _uid() + "b"
        gids[m] = gid
        s.append(f'<linearGradient id="{gid}" x1="0" y1="0" x2="0" y2="1">'
                 f'<stop offset="0" stop-color="{_mix(col, 0.26)}"/>'
                 f'<stop offset="0.55" stop-color="{col}"/>'
                 f'<stop offset="1" stop-color="{_mix(col, -0.16)}"/></linearGradient>')
    s.append('</defs>')

    for k in range(3):
        gy = py + ih - ih * k / 2
        s.append(f'<line x1="{px}" y1="{gy:.1f}" x2="{px+iw}" y2="{gy:.1f}" '
                 f'stroke="{t["line"]}" stroke-opacity="0.5" stroke-width="1"/>')
    s.append(f'<text x="{px-6}" y="{py+4}" text-anchor="end" font-family="Consolas" '
             f'font-size="7.5" fill="{t["tx3"]}">{fmt(maxv)}</text>')
    s.append(f'<text x="{px-6}" y="{py+ih+3:.1f}" text-anchor="end" font-family="Consolas" '
             f'font-size="7.5" fill="{t["tx3"]}">0</text>')

    pi = max(range(n), key=lambda i: rows[i]["total"])
    for i, r in enumerate(rows):
        cxx = px + slot * i + slot / 2
        yc = py + ih
        segs = [(m, v) for m, v in r["parts"] if v]
        for j, (m, v) in enumerate(segs):
            hh = v / maxv * ih
            top = yc - hh
            gid = gids[m]
            rr = 2.0 if j == 0 else 0          # 顶部小圆角(与卡片语言一致)
            s.append(f'<rect x="{cxx-bw/2:.1f}" y="{top:.1f}" width="{bw:.1f}" '
                     f'height="{hh:.1f}" rx="{rr}" fill="url(#{gid})"/>')
            # 左侧 1px 高光(模拟来自左上方的光)
            s.append(f'<rect x="{cxx-bw/2:.1f}" y="{top+1:.1f}" width="1" '
                     f'height="{max(0, hh-2):.1f}" fill="#ffffff" opacity="0.16"/>')
            yc = top
        if i == pi:                             # 峰值: 顶部一颗高光点
            s.append(f'<circle cx="{cxx:.1f}" cy="{py + ih - r["total"]/maxv*ih - 5:.1f}" '
                     f'r="1.8" fill="{t["tx2"]}"/>')
        if i % max(1, n // 7) == 0 or i == n - 1:
            s.append(f'<text x="{cxx:.1f}" y="{py+ih+PAD_B-4}" text-anchor="middle" '
                     f'font-family="Consolas" font-size="7" fill="{t["tx3"]}">'
                     f'{r["date"][5:].replace("-", "/")}</text>')
    return "".join(s)

# ---------------------------------------------------------------- 方案 F
def plan_f(x, y, w, h, rows, rank, t):
    """方案 F · 双视图(上: 总量趋势面积 / 下: 构成带)

    把"趋势"和"构成"分成上下两块, 各自只做一件事 ——
    上面一眼看走势(单色渐变面积), 下面一条矮矮的堆叠带看每天由哪些模型构成。
    借鉴 ApexCharts 组合图的思想: 同一 X 轴上下对齐, 共用一个悬浮指示。
    """
    cx, cy = x + CV_L, y + CV_T + HEADER_H
    px, py, iw, ih = _geom(cx, cy, w, h)
    n = len(rows)
    xs = [px + iw * i / (n - 1) for i in range(n)]

    band_h = 26                       # 下方构成带高度
    gap = 6
    area_ih = ih - band_h - gap       # 上方趋势区高度
    maxv = max(r["total"] for r in rows) or 1

    s = ['<defs>']
    gid_area = _uid() + "a"
    s.append(f'<linearGradient id="{gid_area}" x1="0" y1="0" x2="0" y2="1">'
             f'<stop offset="0" stop-color="#3b6fe0" stop-opacity="0.34"/>'
             f'<stop offset="1" stop-color="#3b6fe0" stop-opacity="0.02"/></linearGradient>')
    s.append('</defs>')

    # ---- 上: 总量趋势 ----
    pts = [(xs[i], py + area_ih - r["total"] / maxv * area_ih) for i, r in enumerate(rows)]
    line = _smooth(pts)
    area = line + f" L {xs[-1]:.1f} {py+area_ih:.1f} L {xs[0]:.1f} {py+area_ih:.1f} Z"
    s.append(f'<path d="{area}" fill="url(#{gid_area})"/>')
    s.append(f'<path d="{line}" fill="none" stroke="#3b6fe0" stroke-width="1.5" '
             f'stroke-linejoin="round"/>')
    s.append(f'<text x="{px-6}" y="{py+4}" text-anchor="end" font-family="Consolas" '
             f'font-size="7.5" fill="{t["tx3"]}">{fmt(maxv)}</text>')
    # 峰值点
    pi = max(range(n), key=lambda i: rows[i]["total"])
    s.append(f'<circle cx="{xs[pi]:.1f}" cy="{py + area_ih - rows[pi]["total"]/maxv*area_ih:.1f}" '
             f'r="2.4" fill="#3b6fe0" stroke="{t["card"]}" stroke-width="1.2"/>')

    # ---- 分隔 ----
    sep_y = py + area_ih + gap / 2
    s.append(f'<line x1="{px}" y1="{sep_y:.1f}" x2="{px+iw}" y2="{sep_y:.1f}" '
             f'stroke="{t["line"]}" stroke-opacity="0.7" stroke-width="1"/>')

    # ---- 下: 构成带(迷你堆叠柱, 无间隙) ----
    by = py + area_ih + gap
    slot = iw / n
    bw = max(2.0, min(10.0, slot * 0.72))
    for i, r in enumerate(rows):
        cxx = px + slot * i + slot / 2
        yc = by + band_h
        for m, v in r["parts"]:
            if not v:
                continue
            hh = v / maxv * band_h
            col = SEM.get(m, DEFAULT_CYCLE[rank.index(m) % len(DEFAULT_CYCLE)])
            s.append(f'<rect x="{cxx-bw/2:.1f}" y="{yc-hh:.1f}" width="{bw:.1f}" '
                     f'height="{hh:.1f}" fill="{col}" opacity="0.82"/>')
            yc -= hh

    # 日期(共用一行)
    for i in (0, n // 2, n - 1):
        s.append(f'<text x="{xs[i]:.1f}" y="{by+band_h+11}" text-anchor="middle" '
                 f'font-family="Consolas" font-size="7" fill="{t["tx3"]}">'
                 f'{rows[i]["date"][5:].replace("-", "/")}</text>')
    return "".join(s)

# ---------------------------------------------------------------- 主流程
def main():
    rows, rank = load()
    html = ["""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">
<title>每日用量分布 · 三套方案 v2（学习 ECharts/ApexCharts 后重做）</title>
<style>
*{box-sizing:border-box}
body{margin:0;background:#0f1116;color:#eef1f6;
     font:14px/1.6 "Microsoft YaHei UI","Segoe UI",system-ui,sans-serif;padding:26px}
html.light body{background:#f2f4f8;color:#161a22}
h1{font-size:19px;margin:0 0 4px}
.lead{color:#8b93a3;font-size:12.5px;margin-bottom:6px;max-width:900px}
.lead b{color:#cdd3de}
.bar{display:flex;gap:10px;align-items:center;margin:12px 0 18px}
.theme{padding:7px 14px;border-radius:8px;border:1px solid #2c313b;background:#1a1d24;
       color:#b6bdca;cursor:pointer;font-size:13px}
html.light .theme{border-color:#e4e8f0;background:#fff;color:#5c6473}
.wrap{margin:0 0 34px}
.cap{display:flex;align-items:baseline;gap:12px;margin:0 0 8px;flex-wrap:wrap}
.cap b{font-size:15px}
.cap span{color:#8b93a3;font-size:12.5px}
.src{color:#6b8afd;font-size:11.5px}
""" + open(os.path.join(ROOT, "docs", "每日用量分布-三套方案.html"), encoding="utf-8"
           ).read().split("<style>")[1].split("</style>")[0].replace("h1{font-size:19px;margin:0 0 4px}", "") + """
</style></head><body>
<h1>每日用量分布 · 三套方案 v2</h1>
<div class="lead">调研了 GitHub 高星图表库（D3 113k / Chart.js 67.7k / <b>Apache ECharts 67.5k</b> /
Plotly 18.4k / ApexCharts 15.2k / visx 21k），重点借鉴 ECharts 官方 <b>area-stack-gradient</b> 的
<b>smooth 平滑 + stack 堆叠 + 逐层面积渐变 + 不画数据点</b>，以及社区总结的两条美学经验：
面积图用渐变透明度消散营造「呼吸感」、柱状图用渐变模拟光源做「立体光影」。</div>
<div class="bar"><div class="theme" onclick="document.documentElement.classList.toggle('light')">🌗 明/暗切换</div></div>
"""]

    plans = [
        ("方案 D · 堆叠平滑面积 + 逐层渐变",
         "每层一条平滑曲线，面积用该模型色的垂直渐变（顶 62% → 底 10%），层间一条极细高光线。趋势与构成同时可读。",
         "ECharts area-stack-gradient", plan_d),
        ("方案 E · 渐变立体柱 + 光影",
         "保留柱状，但每根柱用垂直渐变模拟顶光（亮→本色→暗），柱顶小圆角，柱身左侧 1px 高光。",
         "社区总结的「柱状立体光影」", plan_e),
        ("方案 F · 双视图（趋势 + 构成带）",
         "上块看总量走势（单色渐变面积），下块一条矮堆叠带看每天由哪些模型构成，共用同一 X 轴。",
         "ApexCharts 组合图思想", plan_f),
    ]
    for name, desc, src, fn in plans:
        html.append(f'<div class="wrap"><div class="cap"><b>{name}</b><span>{desc}</span>'
                    f'<span class="src">← {src}</span></div>')
        html.append(window(name[3], name, desc, fn, rows, rank, TH["dark"], True))
        html.append('</div>')
    html.append('<div class="wrap"><div class="cap"><b>方案 D · 浅色模式适配</b>'
                '<span>同一套方案在浅色下的表现</span></div>')
    html.append(window("D", "D", "", plan_d, rows, rank, TH["light"], False))
    html.append('</div>')
    html.append('</body></html>')

    with open(OUT, "w", encoding="utf-8") as f:
        f.write("".join(html))
    print("saved", OUT, os.path.getsize(OUT), "bytes")

if __name__ == "__main__":
    main()
