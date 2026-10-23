# -*- coding: utf-8 -*-
"""2026-10-23: 新素材全帧检视拼图 (洋红底, 按组分区, docs/pet_new_20261023_review.png)。"""
import json, os, sys
sys.dont_write_bytecode = True
from PIL import Image, ImageDraw, ImageFont

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTDIR = os.path.join(BASE, "assets", "pet_new_20261023")
man = json.load(open(os.path.join(OUTDIR, "manifest.json"), encoding="utf-8"))
OUT = os.path.join(BASE, "docs", "pet_new_20261023_review.png")

def font(sz):
    for p in (r"C:/Windows/Fonts/msyh.ttc", r"C:/Windows/Fonts/msyh.ttf", r"C:/Windows/Fonts/arial.ttf"):
        try: return ImageFont.truetype(p, sz)
        except OSError: pass
    return ImageFont.load_default()

TH, PAD, LAB = 210, 10, 34
rows = []
for g in man["groups"]:
    fs = [os.path.join(OUTDIR, fr["id"] + ".png") for fr in g["frames"]]
    if fs: rows.append((g["gid"], g["source_cn"], g.get("note"), fs))
cols = max(len(fs) for _, _, _, fs in rows)
W = PAD + cols * (TH + PAD)
H = 64 + sum(TH + LAB + 26 for _ in rows) + PAD
sheet = Image.new("RGBA", (W, H), (255, 0, 255, 255))
d = ImageDraw.Draw(sheet)
d.text((PAD, 10), "桌宠新素材全帧检视 · 2026-10-23 · 共 %d 帧 / %d 组 (洋红底 = 真 alpha 合成, 无白边污染)"
       % (man["total"], len(rows)), font=font(20), fill=(0, 0, 0, 255))
y = 64
for gid, cn, note, fs in rows:
    for i, p in enumerate(fs):
        im = Image.open(p).convert("RGBA")
        r = TH / im.height
        im2 = im.resize((max(1, int(im.width * r)), TH), Image.LANCZOS)
        x = PAD + i * (TH + PAD)
        sheet.alpha_composite(im2, (x + (TH - im2.width) // 2, y))
        d.rectangle([x, y, x + TH, y + TH], outline=(80, 0, 80, 255))
        d.text((x + 2, y + TH + 4), os.path.basename(p)[:-4], font=font(13), fill=(0, 0, 0, 255))
    head = "%s · %s (%d 帧)" % (gid, cn, len(fs))
    if note: head += "  — " + note[:60]
    d.text((PAD + 2, y - 22), head, font=font(15), fill=(0, 0, 90, 255))
    y += TH + LAB + 26
sheet.convert("RGB").save(OUT, optimize=True)
print("saved:", OUT, sheet.size)
