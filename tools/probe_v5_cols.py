# -*- coding: utf-8 -*-
"""在 V5 源图的指定区域内按列投影找角色间隙, 输出分割点与带刻度的放大预览。
用法: python -B tools/probe_v5_cols.py
"""
import sys
sys.dont_write_bytecode = True
import os
import numpy as np
from PIL import Image, ImageDraw

SRC = r"C:\Users\a3564\Downloads\蓝色鲸鱼少女表情贴纸包.png"
OUT_DIR = r"C:\Users\a3564\WorkBuddy\2026-08-25-04-20-35\token-stats\docs"

REGIONS = [
    ("idle_row1", 20, 113, 915, 590),
    ("idle_row2", 20, 592, 800, 1082),
]


def main():
    im = Image.open(SRC).convert("RGBA")
    a = np.asarray(im)[:, :, 3]
    for name, x0, y0, x1, y1 in REGIONS:
        sub = a[y0:y1, x0:x1] > 16
        col = sub.sum(axis=0)
        H = y1 - y0
        print("=== %s  x %d..%d  y %d..%d  (h=%d, maxcol=%d) ===" % (name, x0, x1, y0, y1, H, col.max()))
        # 打印稀疏曲线: 每 10 列一个值
        line = []
        for i in range(0, len(col), 10):
            v = int(col[i])
            line.append("%d:%d" % (x0 + i, v))
        print("  " + " ".join(line))
        # 找低谷: 阈值 8% 高度
        thr = max(3, int(0.08 * H))
        empty = col <= thr
        segs = []
        s = None
        for i, e in enumerate(empty):
            if e and s is None:
                s = i
            elif not e and s is not None:
                segs.append((s, i))
                s = None
        if s is not None:
            segs.append((s, len(col)))
        segs = [(x0 + s, x0 + e) for s, e in segs if e - s >= 3]
        print("  低谷(x范围):", segs)

    # 带刻度预览: 原图 2x 放大 + 每 50px 网格
    scale = 2
    big = im.resize((im.width * scale, im.height * scale), Image.LANCZOS).convert("RGB")
    dr = ImageDraw.Draw(big)
    for x in range(0, im.width, 50):
        X = x * scale
        c = (255, 0, 0) if x % 200 == 0 else (0, 160, 255)
        dr.line([(X, 0), (X, big.height)], fill=c, width=1)
        if x % 100 == 0:
            dr.text((X + 2, 2), str(x), fill=(255, 255, 0))
    for y in range(0, im.height, 50):
        Y = y * scale
        c = (255, 0, 0) if y % 200 == 0 else (0, 160, 255)
        dr.line([(0, Y), (big.width, Y)], fill=c, width=1)
        if y % 100 == 0:
            dr.text((2, Y + 1), str(y), fill=(255, 255, 0))
    p = os.path.join(OUT_DIR, "_v5_grid.png")
    big.save(p)
    print("网格预览 ->", p, big.size)


if __name__ == "__main__":
    main()
