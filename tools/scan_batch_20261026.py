# -*- coding: utf-8 -*-
"""第101轮: 扫一遍素材文件夹里**所有** png 的布局(尺寸 / 连通域 / 网格 / 内容去重)。

浅浅猫纠正: "素材不只3张, 现在估计有上百张, 记得看文件夹里最新的" —— 所以这里
不写死文件名, 直接扫描目录, 并按**内容 md5 去重**(她下载时经常有 (1).png 同名副本)。

用法: python -B tools/scan_batch_20261026.py
"""
import glob
import hashlib
import os
import sys

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")
sys.dont_write_bytecode = True

import numpy as np
from PIL import Image
from scipy import ndimage

SRC = r"C:\Users\a3564\Downloads\桌宠动作素材包_4K透明_20帧"


def md5(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    files = sorted(glob.glob(os.path.join(SRC, "*.png")), key=os.path.getmtime)
    print("目录:", SRC)
    print("png 数量:", len(files))
    seen = {}
    print("\n%-46s %-12s %6s %6s %8s" % ("文件名", "尺寸", "域数", "大域", "md5[:8]"))
    print("-" * 92)
    rows = []
    for p in files:
        nm = os.path.basename(p)
        im = Image.open(p)
        W, H = im.size
        h = md5(p)
        dup = "(重复:%s)" % seen[h] if h in seen else ""
        seen.setdefault(h, nm)
        a = np.asarray(im.convert("RGBA"))[:, :, 3]
        k = 4 if max(W, H) > 2500 else 2
        fg = (a > 128)[::k, ::k]
        lab, n = ndimage.label(fg, np.ones((3, 3), bool))
        sz = ndimage.sum(fg, lab, range(1, n + 1)) if n else []
        big = int(sum(1 for v in sz if v * k * k >= 15000))
        rows.append((nm, W, H, n, big, h[:8], dup))
        print("%-46s %-12s %6d %6d %8s %s" % (nm[:44], "%dx%d" % (W, H), n, big, h[:8], dup))
    print("\n不重复源图:", len(seen), " / 总 png:", len(files))


if __name__ == "__main__":
    main()
