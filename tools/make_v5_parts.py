# -*- coding: utf-8 -*-
"""V5 贴纸包 -> 7 个动作切片 (只读源文件)。
布局 (由列投影谷点确定):
  待机行1 y113..590: x[27,325] [325,605] [605,910]   -> idle 1/2/3
  待机行2 y594..1082: x[40,400] [400,790]             -> idle 4 / click 1
  睡觉      : 连通域 #5 (958,224)-(1383,573)           -> sleep 1
             连通域 #15 (897,623)-(1359,1062)         -> sleep 2
用法: python -B tools/make_v5_parts.py
"""
import sys
sys.dont_write_bytecode = True
import os
import json
import numpy as np
from PIL import Image, ImageDraw

SRC = r"C:\Users\a3564\Downloads\蓝色鲸鱼少女表情贴纸包.png"
ROOT = r"C:\Users\a3564\WorkBuddy\2026-08-25-04-20-35\token-stats"
PARTS = os.path.join(ROOT, "assets", "_v5_parts")
DOCS = os.path.join(ROOT, "docs")

BOXES = [
    ("idle_01", 27, 113, 325, 590),
    ("idle_02", 325, 113, 605, 590),
    ("idle_03", 605, 113, 912, 590),
    ("idle_04", 40, 594, 400, 1082),
    ("click_01", 400, 594, 792, 1082),
    ("sleep_01", 950, 200, 1392, 580),
    ("sleep_02", 890, 610, 1366, 1070),
]


def bbox_of(a, thr=8):
    ys, xs = np.where(a > thr)
    if len(xs) == 0:
        return None
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1


def main():
    im = Image.open(SRC).convert("RGBA")
    os.makedirs(PARTS, exist_ok=True)
    meta = []
    for name, x0, y0, x1, y1 in BOXES:
        sub = im.crop((x0, y0, x1, y1))
        a = np.asarray(sub)[:, :, 3]
        bb = bbox_of(a)
        if bb is None:
            print("!! %s 空" % name)
            continue
        cut = sub.crop(bb)
        p = os.path.join(PARTS, name + ".png")
        cut.save(p)
        meta.append({"name": name, "x0": x0, "y0": y0, "x1": x1, "y1": y1,
                     "src_bbox": [x0 + bb[0], y0 + bb[1], x0 + bb[2], y0 + bb[3]],
                     "w": cut.width, "h": cut.height,
                     "ratio": round(cut.width / float(cut.height), 4)})
        print("%-9s bbox=%s  %dx%d  ratio=%.3f" % (name, meta[-1]["src_bbox"],
                                                   cut.width, cut.height, meta[-1]["ratio"]))
    with open(os.path.join(PARTS, "parts.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)

    # 切片对照表 (白底, 每格 260px 高)
    cell_h, pad = 260, 10
    tiles = []
    for m in meta:
        im2 = Image.open(os.path.join(PARTS, m["name"] + ".png"))
        s = cell_h / float(im2.height)
        tiles.append((m["name"], im2.resize((max(1, int(im2.width * s)), cell_h), Image.LANCZOS)))
    W = sum(t.width for _, t in tiles) + pad * (len(tiles) + 1)
    sheet = Image.new("RGB", (W, cell_h + 40), (250, 250, 252))
    dr = ImageDraw.Draw(sheet)
    x = pad
    for name, t in tiles:
        sheet.paste(t, (x, 30), t)
        dr.text((x + 2, 10), name, fill=(20, 20, 20))
        x += t.width + pad
    p = os.path.join(DOCS, "_v5_parts_sheet.png")
    sheet.save(p)
    print("切片对照 ->", p, sheet.size)


if __name__ == "__main__":
    main()
