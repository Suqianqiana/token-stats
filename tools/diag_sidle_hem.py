# -*- coding: utf-8 -*-
"""诊断：setA_07 / setA_09（= sidle_01 / sidle_03）里"被扣掉的白"到底在哪、是什么。
口径：在源图窗口内找白色像素，用成品 alpha 判断是否被删，按连通块列出。
同时区分两类白：
  · 面板背景白（背景 -> 应透明）
  · 画出来的白（衣服下摆/裙摆/蕾丝 -> 应保留）
判据用"区域自身偏离纯白 dev" + "是否与窗口边界连通（真背景）"。
"""
import os, json, sys
import numpy as np
from PIL import Image
from scipy import ndimage
from collections import deque

BASE = r"C:/Users/a3564/WorkBuddy/2026-08-25-04-20-35/token-stats"
SRC = {"setA": r"C:\Users\a3564\.workbuddy\clipboard-images\clipboard-2026-09-13T21-46-03-551Z-a70b73fe.jpg",
       "setB": r"C:\Users\a3564\.workbuddy\clipboard-images\clipboard-2026-09-13T21-46-03-556Z-1fb214d8.jpg"}
S8 = np.ones((3, 3), int)
BG = np.array([255., 255., 255.])
asset_root = sys.argv[1] if len(sys.argv) > 1 else "pet_v3"
W = json.load(open(os.path.join(BASE, "assets", "pet_v3_windows.json"), encoding="utf-8"))

for nm in ("setA_07", "setA_09"):
    st = "setA"
    key = f"{st}/{nm}"
    d = W[key]
    A = np.asarray(Image.open(SRC[st]).convert("RGB")).astype(np.float64)
    mn = A.min(2)
    sat = A.max(2) - mn
    white = (mn >= 235) & (sat <= 20)
    cb = d["cbox"]
    fb = d["fbox"]
    p = os.path.join(BASE, "assets", asset_root, st, nm + ".png")
    o = np.asarray(Image.open(p).convert("RGBA"))
    oy, ox = o.shape[:2]
    op = np.zeros(A.shape[:2], bool)
    op[fb[1]:fb[1] + oy, fb[0]:fb[0] + ox] = o[..., 3] > 200

    # 窗口 = 角色包围盒外扩
    wy0, wy1 = max(0, cb[1] - 6), min(A.shape[0] - 1, cb[3] + 6)
    wx0, wx1 = max(0, cb[0] - 6), min(A.shape[1] - 1, cb[2] + 6)
    sub = white[wy0:wy1 + 1, wx0:wx1 + 1]
    hh, ww = sub.shape
    # 从窗口边界泛洪 -> 真正的"外部背景"
    reach = np.zeros((hh, ww), bool)
    dq = deque()
    for x in range(ww):
        for y in (0, hh - 1):
            if sub[y, x] and not reach[y, x]:
                reach[y, x] = True; dq.append((y, x))
    for y in range(hh):
        for x in (0, ww - 1):
            if sub[y, x] and not reach[y, x]:
                reach[y, x] = True; dq.append((y, x))
    while dq:
        y, x = dq.popleft()
        for ny, nx in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)):
            if 0 <= ny < hh and 0 <= nx < ww and not reach[ny, nx] and sub[ny, nx]:
                reach[ny, nx] = True; dq.append((ny, nx))
    enclosed = np.zeros(A.shape[:2], bool)
    enclosed[wy0:wy1 + 1, wx0:wx1 + 1] = (sub & ~reach)

    lab, n = ndimage.label(enclosed, structure=S8)
    cbh = max(1, cb[3] - cb[1]); cbw = max(1, cb[2] - cb[0])
    print("=" * 96)
    print(f"[{nm}] 成品 {ox}x{oy}  窗口内'被角色包围的白'连通块（>=25px）")
    print(f"{'#':>3}{'px':>7}{'yf':>6}{'xf':>6}{'dev':>7}{'std':>6}{'环rbr':>7}{'环rbmin':>8}{'成品状态':>10}")
    rows = []
    for j in range(1, n + 1):
        if (lab == j).sum() < 25:
            continue
        m = lab == j
        px = A[m]
        dev = float(np.abs(px - BG).max(1).mean())
        std = float(px.std())
        ring = ndimage.binary_dilation(m, structure=S8, iterations=4) & ~m
        r = A[ring] if ring.sum() else None
        rbr = float((r[:, 2] - r[:, 0]).mean()) if r is not None and len(r) else -1
        rbmin = float(r.min(1).mean()) if r is not None and len(r) else -1
        ys, xs = np.where(m)
        yf = (ys.mean() - cb[1]) / cbh
        xf = (xs.mean() - cb[0]) / cbw
        kept = (m & op).sum() / m.sum()
        state = "KEEP" if kept >= 0.5 else ("DEL" if kept < 0.1 else f"MIX{kept*100:.0f}%")
        rows.append((int(m.sum()), yf, xf, dev, std, rbr, rbmin, state, j))
    rows.sort(reverse=True)
    for sz, yf, xf, dev, std, rbr, rbmin, state, j in rows[:16]:
        print(f"{j:>3}{sz:>7}{yf:>6.2f}{xf:>6.2f}{dev:>7.1f}{std:>6.1f}{rbr:>7.0f}{rbmin:>8.0f}{state:>10}")
    # 汇总: 被删的块里, dev 分布
    delrows = [r for r in rows if r[7] != "KEEP"]
    print(f"  -- 被删块 {len(delrows)} 个; dev<=10 的 {sum(1 for r in delrows if r[3] <= 10)} 个,"
          f" dev>10 的 {sum(1 for r in delrows if r[3] > 10)} 个")
    if delrows:
        print("  -- 被删块明细(按 dev 降序, 最像'画出来的白'的在前):")
        for sz, yf, xf, dev, std, rbr, rbmin, state, j in sorted(delrows, key=lambda r: -r[3])[:10]:
            print(f"       blk#{j:<3} {sz:>6}px yf={yf:.2f} xf={xf:.2f} dev={dev:5.1f} std={std:4.1f} "
                  f"环rbr={rbr:4.0f} 环rbmin={rbmin:4.0f} {state}")
