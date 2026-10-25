# -*- coding: utf-8 -*-
"""分析「桌宠睡觉动作帧」A/B 两套 (2048x2048 PNG) —— 只看不动, 输出 bbox/透明度/标签嫌疑。
用法: python -B tools/analyze_sleep_seq.py
"""
import sys
sys.dont_write_bytecode = True
import os
import numpy as np
from PIL import Image

SRC = r"C:\Users\a3564\Downloads\%E6%A1%8C%E5%AE%A0%E7%9D%A1%E8%A7%89%E5%8A%A8%E4%BD%9C%E5%B8%A7_%E4%B8%A4%E5%A5%978%E5%B8%A7_2K%E9%80%8F%E6%98%8EPNG"


def alpha_bbox(a, thr=8):
    ys, xs = np.where(a > thr)
    if len(xs) == 0:
        return None
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1


def main():
    for grp in sorted(os.listdir(SRC)):
        d = os.path.join(SRC, grp)
        if not os.path.isdir(d):
            continue
        print("=== %s ===" % grp)
        for fn in sorted(os.listdir(d)):
            if not fn.lower().endswith(".png"):
                continue
            im = Image.open(os.path.join(d, fn))
            im = im.convert("RGBA")
            a = np.asarray(im.split()[-1]).astype(np.uint8)
            bb = alpha_bbox(a)
            H, W = a.shape
            nz = int((a > 8).sum())
            print("  %-14s %dx%d  alpha>8=%7d (%.1f%%)  bbox=%s  wh=%dx%d"
                  % (fn, W, H, nz, 100.0 * nz / (W * H), bb,
                     bb[2] - bb[0], bb[3] - bb[1]))
            # 顶部 8% 是否有横向长条(标签嫌疑)
            top = a[: int(0.10 * H)]
            cols = (top > 8).sum(axis=0)
            if cols.max() > 0.6 * W:
                print("      ⚠ 顶部疑似横幅: 覆盖列数 %d/%d" % (int((cols > 0).sum()), W))


if __name__ == "__main__":
    main()
