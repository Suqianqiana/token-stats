# -*- coding: utf-8 -*-
"""生成 V2 新素材检视页 docs/pet_v2_new_review.html

源 = ChatGPT Image 2026年9月15日 11_18_35.png (PNG RGBA, 透明底) -> 零抠图, 按连通域切分。
每帧: 成品(棋盘格) / 白底 / 洋红底(洋红=透明); 顶部两行原图条(红框=切分位置 + 编号 + 对应动作)。
"""
import os, io, json, base64
import numpy as np
from PIL import Image, ImageDraw, ImageFont

BASE = r"C:\Users\a3564\WorkBuddy\2026-08-25-04-20-35\token-stats"
SRC = r"C:\Users\a3564\Downloads\ChatGPT Image 2026年9月15日 11_18_35.png"
QC = json.load(open(os.path.join(BASE, "assets", "pet_v2_alpha2_qc.json"), encoding="utf-8"))
FONT = r"C:\Windows\Fonts\arialbd.ttf" if os.path.exists(r"C:\Windows\Fonts\arialbd.ttf") else None


def b64(im, maxh=340):
    if im.height > maxh:
        r = maxh / float(im.height)
        im = im.resize((max(1, int(im.width * r)), maxh), Image.LANCZOS)
    buf = io.BytesIO(); im.save(buf, "PNG")
    return base64.b64encode(buf.getvalue()).decode()


def checker(img, size=16, c1=(238, 238, 242), c2=(212, 212, 218)):
    im = img.convert("RGBA"); w, h = im.size
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

# ---- 行条: 用各自的 src_bbox 画真实切框 ----
strips = []
for ri, (y0, y1) in enumerate([(167, 521), (612, 959)]):
    y_lo, y_hi = max(0, y0 - 90), min(src.height - 1, y1 + 30)
    strip = checker(src.crop((0, y_lo, src.width, y_hi + 1)), size=22)
    dr = ImageDraw.Draw(strip)
    items = [(k, v) for k, v in QC.items() if v["row"] == ri + 1]
    items.sort(key=lambda kv: kv[1]["src_bbox"][0])
    for k, v in items:
        bx0, by0, bx1, by1 = v["src_bbox"]
        dr.rectangle([bx0, by0 - y_lo, bx1, by1 - y_lo], outline=(255, 60, 60), width=3)
        num = v["src_frame"].replace("v2n_", "").replace(".png", "").lstrip("0")
        dr.rectangle([bx0 + 4, by0 - y_lo + 4, bx0 + 4 + 30, by0 - y_lo + 34], fill=(255, 60, 60))
        dr.text((bx0 + 9, by0 - y_lo + 7), num, fill=(255, 255, 255),
                font=ImageFont.truetype(FONT, 22) if FONT else None)
    strips.append((ri, strip, [k for k, _ in items]))

# ---- 卡片 ----
cards = []
for k in sorted(QC, key=lambda k: (QC[k]["row"], QC[k]["src_bbox"][0])):
    v = QC[k]
    p = os.path.join(BASE, "assets", "pet_v2", k.replace("/", os.sep))
    out = Image.open(p).convert("RGBA")
    mag = Image.new("RGB", out.size, (255, 0, 255)); mag.paste(out, (0, 0), out)
    wht = Image.new("RGB", out.size, (255, 255, 255)); wht.paste(out, (0, 0), out)
    bx0, by0, bx1, by1 = v["src_bbox"]
    cards.append(f"""<div class="card">
  <div class="hd"><b>{v['src_frame']}</b> &nbsp;→&nbsp; <b>{k}</b>
    <span class="dim">第 {v['row']} 行 · 成品 {out.width}×{out.height} · 源 x{bx0}..{bx1} y{by0}..{by1} · 装饰 {v['decors']} 个 · 剔除邻角色像素 {v['removed']}</span></div>
  <div class="row">
    <figure><figcaption>成品（棋盘格）</figcaption><img src="data:image/png;base64,{b64(checker(out))}"></figure>
    <figure><figcaption>白底</figcaption><img src="data:image/png;base64,{b64(wht)}"></figure>
    <figure><figcaption>洋红底 · 洋红=透明</figcaption><img src="data:image/png;base64,{b64(mag)}"></figure>
  </div>
</div>""")

strips_html = []
for ri, strip, names in strips:
    strips_html.append(f"""<div class="card">
  <div class="hd"><b>第 {ri+1} 行 原图条</b> <span class="dim">红框/编号 = 切出的角色（棋盘格底）。该行共 {len(names)} 个</span></div>
  <img style="width:100%;height:auto;border-radius:8px" src="data:image/png;base64,{b64(strip, maxh=560)}">
</div>""")

html = f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">
<title>V2 素材 · 透明原图重建</title>
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
<h1>V2 素材 · 透明原图重建（{len(cards)} 帧）</h1>
<p class="sub">源 = <b>ChatGPT Image 2026年9月15日 11_18_35.png</b>（PNG RGBA 1536×1024，四角 alpha=0 <b>真透明</b>）→ <b>零抠图</b>。<br>
<b>切分方式：按 alpha 连通域，不用竖向切线。</b>实测该图排布极紧凑：行1 有 6 个角色但只有 <b>2 处干净空隙</b>（需要 5），
行2 有 7 个角色也只有 2 处空隙，且行2 的 #2|#3 重叠 9px、#6|#7 重叠 3px —— 任何竖线都会裁断角色。<br>
映射来源：<b>无顺序约束的全局最优形状匹配</b>恰好得到与旧 V2 相同的顺序（总分 10.978，备选 10.756 / 9.509）。<br>
自检：13 帧<b>每帧只含 1 个角色级连通域</b>、透明底正常（13.6%~24.5%）。</p>
{''.join(strips_html)}
{''.join(cards)}
</body></html>"""
out = os.path.join(BASE, "docs", "pet_v2_new_review.html")
open(out, "w", encoding="utf-8").write(html)
print(f"HTML -> {out} ({len(html)/1048576:.2f} MB, {len(cards)} 帧)")
