# -*- coding: utf-8 -*-
"""第101轮: 158 帧检视拼图(每 4 组一张, 共 4 张) —— 供我人工读图做**预选**。

用法: python -B tools/gen_review_20261026.py
输出: docs/_review101_p1.png ... _p4.png
"""
import json
import os
import sys

sys.dont_write_bytecode = True
from PIL import Image, ImageDraw

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTD = os.path.join(BASE, "assets", "pet_new_20261026")
THUMB = os.path.join(OUTD, "thumbs")
DOCS = os.path.join(BASE, "docs")
PER_SHEET = 4          # 每张拼几组
COLS = 10
CELL_W, CELL_H = 118, 176


def main():
    with open(os.path.join(OUTD, "manifest.json"), encoding="utf-8") as f:
        mf = json.load(f)
    sheets = []
    cur = None
    for gi, g in enumerate(mf["groups"]):
        if gi % PER_SHEET == 0:
            cur = []
            sheets.append(cur)
        cur.append(g)
    for si, groups in enumerate(sheets, 1):
        rows = 0
        for g in groups:
            rows += (len(g["frames"]) + COLS - 1) // COLS
        W = COLS * CELL_W
        H = rows * CELL_H + 40
        sheet = Image.new("RGB", (W, H), (236, 238, 243))
        d = ImageDraw.Draw(sheet)
        y = 26
        for g in groups:
            d.text((6, y - 18), "%s  %s" % (g["gid"], g["source_cn"]),
                   fill=(40, 44, 52))
            for k, fr in enumerate(g["frames"]):
                c, r = k % COLS, k // COLS
                x = c * CELL_W
                yy = y + r * CELL_H
                p = os.path.join(THUMB, fr["id"] + ".png")
                if os.path.exists(p):
                    im = Image.open(p).convert("RGBA")
                    sc = min((CELL_W - 8) / im.width, (CELL_H - 26) / im.height)
                    im = im.resize((max(1, int(im.width * sc)), max(1, int(im.height * sc))),
                                   Image.LANCZOS)
                    sheet.paste(im, (x + (CELL_W - im.width) // 2, yy + 18), im)
                d.text((x + 4, yy + 4), fr["id"], fill=(70, 76, 88))
            y += ((len(g["frames"]) + COLS - 1) // COLS) * CELL_H + 14
        out = os.path.join(DOCS, "_review101_p%d.png" % si)
        sheet.save(out)
        print("->", out, sheet.size)


if __name__ == "__main__":
    main()
