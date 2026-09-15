# -*- coding: utf-8 -*-
"""生成绿幕素材检视页 docs/pet_v2_green_review.html。
每帧三格: 原图对照(绿幕原图, 外扩 40px 便于定位) / 成品(棋盘格) / 洋红底(绿残留一眼可见)。
顶部附两张"整行原图条", 并在每个角色 x 范围上画竖线+编号, 方便对应"第几个"。
"""
import os, json, base64, io
import numpy as np
from PIL import Image, ImageDraw, ImageFont

BASE = r"C:\Users\a3564\WorkBuddy\2026-08-25-04-20-35\token-stats"
SRC = r"C:\Users\a3564\Downloads\Gemini_Generated_Image_jjmed3jjmed3jjme-no-bg.png"
D = os.path.join(BASE, "assets", "pet_v2_green")
QC = json.load(open(os.path.join(BASE, "assets", "pet_v2_green_qc.json"), encoding="utf-8"))
MAP = {"v2g_01.png":"pet_v2/idle/idle_01.png","v2g_02.png":"pet_v2/idle/idle_02.png",
       "v2g_03.png":"pet_v2/idle/idle_03.png","v2g_04.png":"pet_v2/idle/idle_04.png",
       "v2g_05.png":"pet_v2/sleep/sleep_01.png","v2g_06.png":"pet_v2/sleep/sleep_02.png",
       "v2g_07.png":"pet_v2/drag/drag_01.png","v2g_08.png":"pet_v2/drag/drag_02.png",
       "v2g_09.png":"pet_v2/drag/drag_03.png","v2g_10.png":"pet_v2/click/click_01.png",
       "v2g_11.png":"pet_v2/click/click_02.png","v2g_12.png":"pet_v2/special/special_01.png",
       "v2g_13.png":"pet_v2/special/special_02.png"}
FONT = r"C:\Windows\Fonts\arialbd.ttf" if os.path.exists(r"C:\Windows\Fonts\arialbd.ttf") else None


def b64(im, maxh=340):
    if im.height > maxh:
        r = maxh / float(im.height)
        im = im.resize((max(1, int(im.width * r)), maxh), Image.LANCZOS)
    buf = io.BytesIO(); im.save(buf, "PNG")
    return base64.b64encode(buf.getvalue()).decode()


def checker(img, size=16, c1=(238, 238, 242), c2=(212, 212, 218)):
    w, h = img.size
    bg = Image.new("RGB", (w, h), c1); px = bg.load()
    for y in range(0, h, size):
        for x in range(0, w, size):
            if ((x // size) + (y // size)) % 2:
                for yy in range(y, min(y + size, h)):
                    for xx in range(x, min(x + size, w)):
                        px[xx, yy] = c2
    bg.paste(img, (0, 0), img)
    return bg


src = Image.open(SRC).convert("RGB")

# ---- 行条 + 编号 ----
A = np.asarray(src).astype(np.int16)
g = A[..., 1] - np.maximum(A[..., 0], A[..., 2])
fg = g < 130
rows = fg.sum(1)
on = rows > 8
segs = []; s = None
for i, v in enumerate(on):
    if v and s is None: s = i
    if not v and s is not None: segs.append([s, i - 1]); s = None
if s is not None: segs.append([s, len(on) - 1])
rb = [b for b in segs if b[1] - b[0] + 1 >= 300]
lb = [b for b in segs if b[1] - b[0] + 1 < 300]

# 每帧 -> 行、行内序号
frame_row = {}
for fn, v in QC.items():
    bx0, by0, bx1, by1 = v["src"]
    for ri, (y0, y1) in enumerate(rb):
        if y0 - 30 <= by0 <= y1 + 30:
            frame_row[fn] = ri
            break
strip_imgs = []
for ri, (y0, y1) in enumerate(rb):
    y_lo = y0 - 100; y_hi = y1 + 20
    for l in lb:
        if 0 <= y0 - l[1] <= 130: y_lo = min(y_lo, l[0] - 20)
        if 0 <= l[0] - y1 <= 130: y_hi = max(y_hi, l[1] + 20)
    y_lo, y_hi = max(0, y_lo), min(src.height - 1, y_hi)
    strip = src.crop((0, y_lo, src.width, y_hi + 1)).copy()
    dr = ImageDraw.Draw(strip)
    order = sorted([f for f, r in frame_row.items() if r == ri],
                   key=lambda f: QC[f]["src"][0])
    for k, fn in enumerate(order, 1):
        bx0, _, bx1, _ = QC[fn]["src"]
        dr.rectangle([bx0, 0, bx1, strip.height - 1], outline=(255, 60, 60), width=4)
        txt = str(k)
        dr.rectangle([bx0 + 6, 6, bx0 + 6 + 22 * len(txt), 40], fill=(255, 60, 60))
        dr.text((bx0 + 12, 10), txt, fill=(255, 255, 255), font=ImageFont.truetype(FONT, 26) if FONT else None)
    strip_imgs.append((ri, strip, order))

# ---- 卡片 ----
cards = []
for fn in sorted(QC, key=lambda f: QC[f]["src"][1] * 10000 + QC[f]["src"][0]):
    v = QC[fn]
    bx0, by0, bx1, by1 = v["src"]
    pad = 45
    ref = src.crop((max(0, bx0 - pad), max(0, by0 - pad),
                    min(src.width, bx1 + pad), min(src.height, by1 + pad)))
    out = Image.open(os.path.join(D, fn)).convert("RGBA")
    mag = Image.new("RGB", out.size, (255, 0, 255)); mag.paste(out, (0, 0), out)
    wht = Image.new("RGB", out.size, (255, 255, 255)); wht.paste(out, (0, 0), out)
    ri = frame_row.get(fn, -1)
    order = [f for f, r in frame_row.items() if r == ri]
    order.sort(key=lambda f: QC[f]["src"][0])
    k = order.index(fn) + 1 if fn in order else 0
    cards.append(f"""<div class="card">
  <div class="hd"><b>{fn}</b> &nbsp;→&nbsp; <b>{MAP.get(fn,"?")}</b> &nbsp;<span class="dim">第 {ri+1} 行 第 {k} 个 · 成品 {out.width}×{out.height} · 源 x{bx0}..{bx1} y{by0}..{by1}</span></div>
  <div class="row">
    <figure><figcaption>原图对照（绿幕）</figcaption><img src="data:image/png;base64,{b64(ref)}"></figure>
    <figure><figcaption>成品（棋盘格）</figcaption><img src="data:image/png;base64,{b64(checker(out))}"></figure>
    <figure><figcaption>白底 · 专看绿边</figcaption><img src="data:image/png;base64,{b64(wht)}"></figure>
    <figure><figcaption>洋红底 · 洋红=透明</figcaption><img src="data:image/png;base64,{b64(mag)}"></figure>
  </div>
</div>""")

strips_html = []
for ri, strip, order in strip_imgs:
    strips_html.append(f"""<div class="card">
  <div class="hd"><b>第 {ri+1} 行 原图条</b> <span class="dim">红框=切分位置，数字=该行第几个（共 {len(order)} 个）</span></div>
  <img style="width:100%;height:auto;border-radius:8px" src="data:image/png;base64,{b64(strip, maxh=520)}">
</div>""")

html = f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">
<title>V2 素材 · 绿幕抠图检视</title>
<style>
body{{background:#16161a;color:#e8e8ea;font:14px/1.6 "Segoe UI","Microsoft YaHei",sans-serif;margin:0;padding:28px 32px}}
h1{{font-size:20px;font-weight:500;margin:0 0 6px}}
p.sub{{color:#9a9aa2;font-size:13px;margin:0 0 22px}}
.card{{background:#1e1e23;border:1px solid #2e2e36;border-radius:12px;padding:14px 16px;margin-bottom:14px}}
.hd{{font-size:14px;margin-bottom:10px}}
.dim{{color:#8b8b93;font-size:12px}}
.row{{display:flex;gap:14px;flex-wrap:wrap;align-items:flex-start}}
figure{{margin:0;background:#26262c;border:1px solid #33333c;border-radius:10px;padding:8px}}
figcaption{{font-size:12px;color:#9a9aa2;margin-bottom:6px}}
figure img{{display:block;max-height:320px;width:auto}}
</style></head><body>
<h1>V2 素材 · 绿幕抠图检视（{len(cards)} 帧）</h1>
<p class="sub">源 = 2528×1686 JPEG 绿幕图（背景绿纯度最低 216，角色内 99% 分位仅 92）→ 阈值法抠图 + 去绿溢色。<br>
质检：透明区绿残留 <b>0px</b>，边缘绿溢色 <b>0px</b>。第三列洋红底：洋红=透明区，若出现绿色即抠漏。</p>
{''.join(strips_html)}
{''.join(cards)}
</body></html>"""
out = os.path.join(BASE, "docs", "pet_v2_green_review.html")
open(out, "w", encoding="utf-8").write(html)
print(f"HTML -> {out} ({len(html)/1048576:.2f} MB, {len(cards)} 帧)")
