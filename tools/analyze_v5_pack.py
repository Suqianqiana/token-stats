# -*- coding: utf-8 -*-
"""分析 V5 素材源「蓝色鲸鱼少女表情贴纸包.png」—— 尺寸/透明/网格带/连通域。只读。
用法: python -B tools/analyze_v5_pack.py
"""
import sys
sys.dont_write_bytecode = True
import os
import numpy as np
from PIL import Image
from scipy import ndimage

SRC = r"C:\Users\a3564\Downloads\蓝色鲸鱼少女表情贴纸包.png"


def main():
    im = Image.open(SRC)
    print("mode", im.mode, "size", im.size)
    rgba = im.convert("RGBA")
    arr = np.asarray(rgba)
    a = arr[:, :, 3]
    print("alpha: min %d max %d  >8: %.1f%%  ==0: %.1f%%"
          % (a.min(), a.max(), 100.0 * (a > 8).mean(), 100.0 * (a == 0).mean()))
    # 背景是否透明
    corners = [a[0, 0], a[0, -1], a[-1, 0], a[-1, -1], a[a.shape[0] // 2, 0]]
    print("四角/边缘 alpha:", corners)
    # 行投影: 找透明间隔带
    row = (a > 8).sum(axis=1)
    col = (a > 8).sum(axis=0)
    H, W = a.shape
    print("H,W =", H, W)

    def bands(proj, name, thr_ratio=0.02):
        thr = thr_ratio * proj.max()
        empty = proj <= thr
        segs = []
        s = None
        for i, e in enumerate(empty):
            if e and s is None:
                s = i
            elif not e and s is not None:
                segs.append((s, i))
                s = None
        if s is not None:
            segs.append((s, len(proj)))
        big = [t for t in segs if t[1] - t[0] > 4]
        print("%s 空白带(%d): %s" % (name, len(big), big[:40]))
        return big

    rb = bands(row, "row")
    cb = bands(col, "col")
    # 由空白带推出网格
    if rb:
        bounds = [(0, rb[0][0])] + [(rb[i][1], rb[i + 1][0]) for i in range(len(rb) - 1)] + [(rb[-1][1], H)]
        bounds = [b for b in bounds if b[1] - b[0] > 40]
        print("行区间:", bounds)
    if cb:
        bounds = [(0, cb[0][0])] + [(cb[i][1], cb[i + 1][0]) for i in range(len(cb) - 1)] + [(cb[-1][1], W)]
        bounds = [b for b in bounds if b[1] - b[0] > 40]
        print("列区间:", bounds)


if __name__ == "__main__":
    main()
