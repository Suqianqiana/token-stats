# -*- coding: utf-8 -*-
"""第101轮: 分析 2026-10-26 新素材包的布局(尺寸 / 透明分隔 / 连通域 / 网格)。

用法: python -B tools/analyze_batch_20261026.py
"""
import os
import sys

# 低内存救生符(第100轮): OpenBLAS 按核数开线程会分配失败
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")
sys.dont_write_bytecode = True

import numpy as np
from PIL import Image
from scipy import ndimage

SRC = r"C:\Users\a3564\Downloads\桌宠动作素材包_4K透明_20帧"
NAMES = [
    "桌宠动作素材_互动反馈_4K透明.png",
    "桌宠动作素材_交互与特殊待机_4K透明.png",
    "桌宠动作素材_日常生活1_4K透明.png",
    "桌宠动作素材_日常生活_4K透明.png",
    "桌宠动作素材_睡觉与睡醒_10帧_4K透明.png",
]


def main():
    for nm in NAMES:
        p = os.path.join(SRC, nm)
        if not os.path.exists(p):
            print("!! 缺少", nm)
            continue
        im = Image.open(p)
        print("=" * 78)
        print(nm, im.size, im.mode)
        a = np.asarray(im.convert("RGBA"))[:, :, 3]
        H, W = a.shape
        # 整体不透明占比
        ink = (a > 8)
        print("  不透明占比 %.1f%%" % (100.0 * ink.sum() / (H * W)))
        # 连通域(4 邻域, 缩小 4 倍加速)
        k = 4
        small = ink[::k, ::k]
        lab, n = ndimage.label(small, np.ones((3, 3), bool))
        print("  连通域(1/%d 采样): %d" % (k, n))
        sizes = ndimage.sum(small, lab, range(1, n + 1)) * k * k
        order = np.argsort(-sizes)
        big = [(int(i + 1), int(sizes[i])) for i in order[:14] if sizes[i] > 2000]
        print("  前几大域(编号, 面积px):", big[:10])
        # 每个大域的 bbox(还原到原图) —— 用于判断网格布局
        boxes = []
        for i, _s in big[:12]:
            ys, xs = np.where(lab == i)
            if len(xs) == 0:
                continue
            boxes.append((int(xs.min() * k), int(ys.min() * k),
                          int(xs.max() * k), int(ys.max() * k)))
        boxes.sort(key=lambda b: (b[1] // 200, b[0]))
        for b in boxes:
            print("    bbox x %4d..%4d (w%4d)  y %4d..%4d (h%4d)" %
                  (b[0], b[2], b[2] - b[0], b[1], b[3], b[3] - b[1]))
        # 行/列投影谷点: 找全透明的"分隔带"
        col = ink.sum(axis=0)
        row = ink.sum(axis=1)
        gapc = (col == 0)
        gapr = (row == 0)
        runs_c, runs_r = [], []
        x = 0
        while x < W:
            if gapc[x]:
                y = x
                while y < W and gapc[y]:
                    y += 1
                if y - x >= 8:
                    runs_c.append((x, y))
                x = y
            else:
                x += 1
        y = 0
        while y < H:
            if gapr[y]:
                z = y
                while z < H and gapr[z]:
                    z += 1
                if z - y >= 8:
                    runs_r.append((y, z))
                y = z
            else:
                y += 1
        print("  列方向透明分隔带(>=8px):", runs_c[:12])
        print("  行方向透明分隔带(>=8px):", runs_r[:12])


if __name__ == "__main__":
    main()
