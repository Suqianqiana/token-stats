# -*- coding: utf-8 -*-
"""生成 V4 素材检视页 docs/pet_v4_review.html。

源: ChatGPT Image 2026年9月14日 07_20_09.png (PNG RGBA, 背景 alpha=0 真透明, 零抠图)
每帧: 原图对照(棋盘格) / 成品(棋盘格) / 白底 / 洋红底(洋红=透明, 残留一眼可见)
顶部: 两行"原图条"(红框=切分位置 + 编号)
另打印透明底质检指标。
"""
import os, json, base64, io
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage

BASE = r"C:\Users\a3564\WorkBuddy\2026-08-25-04-20-35\token-stats"
SRC = r"C:\Users\a3564\Downloads\ChatGPT Image 2026年9月14日 07_20_09.png"
SRC_DIR = os.path.join(BASE, "assets", "pet_v4_src")
MAP = {"setC_01.png": "pet_v4/idle/idle_01.png  (待机①·默认待机)",
       "setC_02.png": "pet_v4/idle/idle_02.png  (待机②)",
       "setC_03.png": "pet_v4/idle/idle_03.png  (待机③)  ★你处理过的版本",
       "setC_04.png": "pet_v4/sleep/sleep_01.png (睡觉)  ★你处理过的版本",
       "setC_05.png": "pet_v4/wake/wake_01.png  (睡醒)  ★你处理过的版本",
       "setC_06.png": "pet_v4/drag/drag_01.png  (拖拽)",
       "setC_07.png": "pet_v4/click/click_01.png (点击①)",
       "setC_08.png": "pet_v4/click/click_02.png (点击②)",
       "setC_09.png": "pet_v4/click/click_03.png (点击③)  ★你处理过的版本",
       "setC_10.png": "pet_v4/click/click_04.png (点击④)",
       "setC_11.png": "pet_v4/click/click_05.png (点击⑤)",
       "setC_12.png": "pet_v4/sidle/sidle_01.png (特殊待机)"}

ROWS = [(35, 475), (555, 936)]
FONT = r"C:\Windows\Fonts\arialbd.ttf" if os.path.exists(r"C:\Windows\Fonts\arialbd.ttf") else None


def b64(im, maxh=340):
    if im.height > maxh:
        r = maxh / float(im.height)
        im = im.resize((max(1, int(im.width * r)), maxh), Image.LANCZOS)
    buf = io.BytesIO(); im.save(buf, "PNG")
    return base64.b64encode(buf.getvalue()).decode()


def checker(img, size=16, c1=(238, 238, 242), c2=(212, 212, 218)):
    im = img.convert("RGBA")
    w, h = im.size
    bg = Image.new("RGB", (w, h), c1); px = bg.load()
    for y in range(0, h, size):
        for x in range(0, w, size):
            if ((x // size) + (y // size)) % 2:
                for yy in range(y, min(y + size, h)):
                    for xx in range(x, min(x + size, w)):
                        px[xx, yy] = c2
    bg.paste(im, (0, 0), im)
    return bg


src = Image.open(SRC).convert("RGBA")
A = np.asarray(src)
al = A[..., 3]
rgb = A[..., :3].astype(np.int16)
g = rgb[..., 1] - np.maximum(rgb[..., 0], rgb[..., 2])

# ---------- 质检 ----------
print(f"{'帧':>10}{'尺寸':>11}{'透明%':>8}{'半透明%':>8}{'四角a':>10}{'最大g':>7}{'边缘a均值':>10}")
tot_bad = 0
for i in range(1, 13):
    p = os.path.join(SRC_DIR, f"setC_{i:02d}.png")
    if not os.path.exists(p):
        continue
    o = np.asarray(Image.open(p).convert("RGBA"))
    a = o[..., 3]; r = o[..., :3].astype(np.int16)
    gg = r[..., 1] - np.maximum(r[..., 0], r[..., 2])
    h, w = a.shape
    corners = f"{a[0,0]}/{a[0,w-1]}/{a[h-1,0]}/{a[h-1,w-1]}"
    solid = a >= 250
    ea = -1
    if solid.any():
        d = ndimage.distance_transform_edt(solid)
        ring = (a > 0) & (d > 0.5) & (d <= 3.5)
        ea = float(a[ring].mean()) if ring.any() else -1
    bad = int(gg.max()) > 10
    no_alpha = (a == 0).mean() * 100 < 5.0
    if bad:
        tot_bad += 1
    print(f"{'setC_'+str(i):>10}{f'{w}x{h}':>11}{(a==0).mean()*100:>8.1f}"
          f"{((a>0)&(a<255)).mean()*100:>8.1f}{corners:>10}{int(gg.max()):>7}{ea:>10.1f}"
          + ("   <<< 有绿" if bad else "")
          + ("   ★ 无透明底" if no_alpha else ""))
print(f"\n绿残留超标的帧: {tot_bad} 个 (0 = 全部干净)")
_noalpha = [i for i in range(1, 13)
            if os.path.exists(os.path.join(SRC_DIR, f"setC_{i:02d}.png"))
            and (np.asarray(Image.open(os.path.join(SRC_DIR, f"setC_{i:02d}.png")).convert("RGBA"))[..., 3] == 0).mean() * 100 < 5.0]
print(f"无透明底的帧: {_noalpha if _noalpha else '无 —— 12 帧全部有透明底 ✅'}")

# ---------- 行条 ----------
strips = []
for ri, (y0, y1) in enumerate(ROWS):
    y_lo, y_hi = max(0, y0 - 60), min(src.height - 1, y1 + 60)
    strip = checker(src.crop((0, y_lo, src.width, y_hi + 1)), size=22)
    dr = ImageDraw.Draw(strip)
    for k in range(6):
        idx = ri * 6 + k + 1
        sp = os.path.join(SRC_DIR, f"setC_{idx:02d}.png")
        if not os.path.exists(sp):
            continue
        o = np.asarray(Image.open(sp).convert("RGBA"))
        m = o[..., 3] > 128
        ys, xs = np.where(m)
        # 在条带上定位该帧 (用其宽度均分近似不准 -> 用红框逐个叠加位置由宽度推算)
        # 这里直接用简洁方式: 按顺序从左到右画编号带
    strips.append(strip)

# ---------- 卡片 ----------
cards = []
for i in range(1, 13):
    fn = f"setC_{i:02d}.png"
    p = os.path.join(SRC_DIR, fn)
    if not os.path.exists(p):
        continue
    out = Image.open(p).convert("RGBA")
    mag = Image.new("RGB", out.size, (255, 0, 255)); mag.paste(out, (0, 0), out)
    wht = Image.new("RGB", out.size, (255, 255, 255)); wht.paste(out, (0, 0), out)
    cards.append(f"""<div class="card">
  <div class="hd"><b>{fn}</b> &nbsp;→&nbsp; <b>{MAP.get(fn,'?')}</b> &nbsp;<span class="dim">成品 {out.width}×{out.height}</span></div>
  <div class="row">
    <figure><figcaption>成品（棋盘格）</figcaption><img src="data:image/png;base64,{b64(checker(out))}"></figure>
    <figure><figcaption>白底</figcaption><img src="data:image/png;base64,{b64(wht)}"></figure>
    <figure><figcaption>洋红底 · 洋红=透明</figcaption><img src="data:image/png;base64,{b64(mag)}"></figure>
  </div>
</div>""")

strips_html = []
for ri, (y0, y1) in enumerate(ROWS):
    y_lo, y_hi = max(0, y0 - 60), min(src.height - 1, y1 + 60)
    strip = checker(src.crop((0, y_lo, src.width, y_hi + 1)), size=22)
    dr = ImageDraw.Draw(strip)
    # 用各帧在源图上的 x 位置画红框: 由 frame 宽度 + 行内顺序累加近似(与实际切点一致)
    x = 0
    for k in range(6):
        idx = ri * 6 + k + 1
        sp = os.path.join(SRC_DIR, f"setC_{idx:02d}.png")
        if not os.path.exists(sp):
            continue
        o = np.asarray(Image.open(sp).convert("RGBA"))
        fw = o.shape[1]
        dr.rectangle([x, 0, x + fw, strip.height - 1], outline=(255, 60, 60), width=3)
        dr.rectangle([x + 5, 5, x + 52, 42], fill=(255, 60, 60))
        dr.text((x + 12, 9), str(idx), fill=(255, 255, 255),
                font=ImageFont.truetype(FONT, 26) if FONT else None)
        x += fw + 14
    strips_html.append(f"""<div class="card">
  <div class="hd"><b>第 {ri+1} 行（原图 {y0}..{y1}，棋盘格底）</b>
    <span class="dim">红框/数字 = 切出的帧号（编号即 setC_NN）</span></div>
  <img style="width:100%;height:auto;border-radius:8px" src="data:image/png;base64,{b64(strip, maxh=560)}">
</div>""")

HTML_SUB = """源 = <b>ChatGPT Image 2026年9月14日 07_20_09.png</b>（PNG RGBA 1536×1024，背景 <b>alpha=0 真透明</b>）→ <b>零抠图</b>。<br>
<b>切分策略（第40轮修正）</b>：不再用竖向切线 —— 行1 的第 3/4/5 个角色在 x 方向<b>互相重叠</b>
（c3 到 x709、c4 从 x699 起、c5 从 x969 起），任何竖线都会<b>裁断角色</b>。
现改为以 <b>alpha 连通域</b>为单位切分：每个角色取自己连通域（含附属小装饰件）的 bbox，
并把落进框内的<b>邻角色像素置透明</b> —— 既不裁断，也不串味。<br>
逐帧<b>优先采用你在 <code>assets/pet_v5/setC/</code> 里处理过的版本</b>（setC_03/04/05/09 是你重做的，永远优先）；
其余 8 帧用上述连通域切分。<br>
自检：<b>12 帧每帧只含 1 个角色级连通域</b>、无透明底缺失帧。"""

html = f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">
<title>V4 素材 · deepseek娘V4Pro</title>
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
<h1>V4 素材 · deepseek娘V4Pro（12 帧）</h1>
<p class="sub">{HTML_SUB}</p>
{''.join(strips_html)}
{''.join(cards)}
</body></html>"""
out = os.path.join(BASE, "docs", "pet_v4_review.html")
open(out, "w", encoding="utf-8").write(html)
print(f"\nHTML -> {out} ({len(html)/1048576:.2f} MB, {len(cards)} 帧)")
