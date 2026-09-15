# -*- coding: utf-8 -*-
"""生成 v5 素材检视页 docs/pet_v5_review.html。
每帧三格: 原图对照(从透明 PNG 源直接裁, 含下方/上方蓝色动作标签) / 成品(棋盘格) / 洋红底(残留一眼可见)。
"""
import os, json, base64, io
import numpy as np
from PIL import Image

BASE = r"C:\Users\a3564\WorkBuddy\2026-08-25-04-20-35\token-stats"
SRC = {
    "setA": r"C:\Users\a3564\Downloads\ChatGPT Image 2026年9月14日 05_37_23.png",
    "setB": r"C:\Users\a3564\Downloads\ChatGPT Image 2026年9月14日 05_28_15.png",
    "setC": r"C:\Users\a3564\Downloads\ChatGPT Image 2026年9月14日 07_20_09.png",
}
V5 = os.path.join(BASE, "assets", "pet_v5")
W = json.load(open(os.path.join(BASE, "assets", "pet_v5_windows.json"), encoding="utf-8"))


def b64(im, fmt="PNG", maxh=330):
    """缩放到 maxh 高再嵌入(否则全尺寸源图会让 HTML 膨胀到 20MB+)。"""
    if im.height > maxh:
        r = maxh / float(im.height)
        im = im.resize((max(1, int(im.width * r)), maxh), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, fmt)
    return base64.b64encode(buf.getvalue()).decode()


def bands(mask1d, thr, gap):
    on = mask1d > thr
    segs = []; s = None
    for i, v in enumerate(on):
        if v and s is None: s = i
        if not v and s is not None: segs.append([s, i - 1]); s = None
    if s is not None: segs.append([s, len(on) - 1])
    m = []
    for b in segs:
        if m and b[0] - m[-1][1] <= gap: m[-1][1] = b[1]
        else: m.append(b)
    return m


def checker(img, size=16, c1=(238, 238, 242), c2=(214, 214, 220)):
    w, h = img.size
    bg = Image.new("RGB", (w, h), c1)
    px = bg.load()
    for y in range(0, h, size):
        for x in range(0, w, size):
            if ((x // size) + (y // size)) % 2:
                for yy in range(y, min(y + size, h)):
                    for xx in range(x, min(x + size, w)):
                        px[xx, yy] = c2
    bg.paste(img, (0, 0), img)
    return bg


rows_html = []
for st, path in SRC.items():
    src_img = Image.open(path).convert("RGBA")
    A = np.asarray(src_img)
    op = A[..., 3] > 128
    rb = [b for b in bands(op.sum(1), 3, 2) if b[1] - b[0] + 1 >= 150]
    lb = [b for b in bands(op.sum(1), 3, 2) if b[1] - b[0] + 1 < 150]
    keys = [k for k in W if k.startswith(st + "/")]
    keys.sort()
    for k in keys:
        nm = k.split("/")[1]
        cb = W[k]["cbox"]
        # 找该帧属于哪个角色行
        row = None
        for b in rb:
            if b[0] - 12 <= cb[1] <= b[1] + 12: row = b; break
        if row is None: row = (cb[1], cb[3])
        y_lo, y_hi = row[0] - 8, row[1] + 8
        for l in lb:                                  # 紧邻的标签带(上下都可)
            if 0 <= row[0] - l[1] <= 22: y_lo = min(y_lo, l[0] - 8)
            if 0 <= l[0] - row[1] <= 22: y_hi = max(y_hi, l[1] + 8)
        x_lo, x_hi = max(0, cb[0] - 12), min(src_img.width - 1, cb[2] + 12)
        y_lo, y_hi = max(0, y_lo), min(src_img.height - 1, y_hi)
        ref = src_img.crop((x_lo, y_lo, x_hi + 1, y_hi + 1))
        out = Image.open(os.path.join(V5, st, nm + ".png")).convert("RGBA")
        # 洋红底
        mag = Image.new("RGB", out.size, (255, 0, 255))
        mag.paste(out, (0, 0), out)
        rows_html.append(f"""<div class="card">
  <div class="hd"><b>{st}</b> / {nm} &nbsp;<span class="dim">成品 {out.width}x{out.height} · 源 x{cb[0]}..{cb[2]} y{cb[1]}..{cb[3]}</span></div>
  <div class="row">
    <figure><figcaption>原图对照（含动作标签）</figcaption><img src="data:image/png;base64,{b64(ref)}"></figure>
    <figure><figcaption>成品（棋盘格）</figcaption><img src="data:image/png;base64,{b64(checker(out))}"></figure>
    <figure><figcaption>洋红底 · 洋红=透明</figcaption><img class="mag" src="data:image/png;base64,{b64(mag)}"></figure>
  </div>
</div>""")

html = f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">
<title>桌宠 v5 素材检视（透明 PNG 原图直切）</title>
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
figure img{{display:block;max-height:300px;width:auto;image-rendering:auto}}
figure img.mag{{background:#ff00ff}}
</style></head><body>
<h1>桌宠 v5 素材检视 · 透明 PNG 原图直切</h1>
<p class="sub">源 = ChatGPT 直出的 1536×1024 RGBA PNG（背景 alpha=0 真透明）→ 零抠图，只做行带分离 + 最优竖向切分 + 裁剪。
共 {len(rows_html)} 帧。第三列洋红底：<b>洋红=透明区</b>，若角色内部出现洋红即为被误删；若出现白色小块即为残留。</p>
{''.join(rows_html)}
</body></html>"""

out = os.path.join(BASE, "docs", "pet_v5_review.html")
open(out, "w", encoding="utf-8").write(html)
print(f"HTML -> {out}  ({len(html)/1048576:.2f} MB, {len(rows_html)} 帧)")
