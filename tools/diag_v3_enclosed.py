# -*- coding: utf-8 -*-
"""诊断: 每帧"被角色包围、但成品里仍不透明的背景白区"(=该扣没扣的连通域)。
   同时给出环上颜色特征, 便于判断是"头发包围(该删)"还是"衣白包围(合法)"。
   用法: python diag_v3_enclosed.py [素材根目录, 默认 assets/pet_v3]
"""
import numpy as np, json, os, sys
from PIL import Image
from scipy import ndimage
from collections import deque

BASE = r"C:/Users/a3564/WorkBuddy/2026-08-25-04-20-35/token-stats"
ROOT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(BASE, "assets", "pet_v3")
SRC = {"setA": r"C:\Users\a3564\.workbuddy\clipboard-images\clipboard-2026-09-13T21-46-03-551Z-a70b73fe.jpg",
       "setB": r"C:\Users\a3564\.workbuddy\clipboard-images\clipboard-2026-09-13T21-46-03-556Z-1fb214d8.jpg"}
W = json.load(open(os.path.join(BASE, "assets", "pet_v3_windows.json"), encoding="utf-8"))
S8 = np.ones((3, 3), int)

tot_px = 0
tot_hair = 0
tot_legit = 0
for st, sp in SRC.items():
    A = np.asarray(Image.open(sp).convert("RGB")).astype(np.int16)
    mn = A.min(2); sat = A.max(2) - mn
    white = (mn >= 240) & (sat <= 16)
    for key, d in W.items():
        if not key.startswith(st):
            continue
        nm = key.split("/")[1]
        fp = os.path.join(ROOT, st, nm + ".png")
        if not os.path.exists(fp):
            continue
        cb = d["cbox"]; fb = d["fbox"]
        out = np.asarray(Image.open(fp).convert("RGBA"))
        oy, ox = out.shape[:2]
        op_src = np.zeros(A.shape[:2], bool)
        op_src[fb[1]:fb[1] + oy, fb[0]:fb[0] + ox] = out[..., 3] > 200
        wy0, wy1 = max(0, cb[1] - 6), min(A.shape[0] - 1, cb[3] + 6)
        wx0, wx1 = max(0, cb[0] - 6), min(A.shape[1] - 1, cb[2] + 6)
        sub = white[wy0:wy1 + 1, wx0:wx1 + 1]
        hh, ww = sub.shape
        rch = np.zeros((hh, ww), bool); dq = deque()
        for x in range(ww):
            for y in (0, hh - 1):
                if sub[y, x] and not rch[y, x]:
                    rch[y, x] = True; dq.append((y, x))
        for y in range(hh):
            for x in (0, ww - 1):
                if sub[y, x] and not rch[y, x]:
                    rch[y, x] = True; dq.append((y, x))
        while dq:
            y, x = dq.popleft()
            for ny, nx in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)):
                if 0 <= ny < hh and 0 <= nx < ww and not rch[ny, nx] and sub[ny, nx]:
                    rch[ny, nx] = True; dq.append((ny, nx))
        enc = np.zeros(A.shape[:2], bool)
        enc[wy0:wy1 + 1, wx0:wx1 + 1] = (sub & ~rch)
        lab, n = ndimage.label(enc, structure=S8)
        szs = np.bincount(lab.ravel()) if n else [0]
        cbh = max(1, cb[3] - cb[1]); cbw = max(1, cb[2] - cb[0])
        hair = 0; legit = 0; det = []
        for j in range(1, n + 1):
            if szs[j] < 40:
                continue
            m = lab == j
            op = int((m & op_src).sum())
            if op / szs[j] < 0.5:            # 已透明 -> 不是问题
                continue
            ring = ndimage.binary_dilation(m, structure=S8, iterations=4) & ~m
            r = A[ring] if ring.sum() else None
            if r is None or len(r) == 0:
                continue
            rbmin = float(r.min(1).mean()); rbr = float((r[:, 2] - r[:, 0]).mean())
            ys, xs = np.where(m)
            yf = round((ys.mean() - cb[1]) / cbh, 2); xf = round((xs.mean() - cb[0]) / cbw, 2)
            is_hair = (rbmin <= 185 and rbr >= 25)
            if is_hair:
                hair += op
            else:
                legit += op
            det.append((int(op), yf, xf, round(rbmin), round(rbr), "HAIR" if is_hair else "legit"))
        if det:
            det.sort(reverse=True)
            print(f"{nm:10} 未扣: 头发类 {hair:>5}px / 合法类 {legit:>5}px   最大3: {det[:3]}")
        tot_px += hair + legit; tot_hair += hair; tot_legit += legit
print(f"\n[合计] 未扣掉的包围域 {tot_px}px  (其中头发类应删 {tot_hair}px / 合法类应留 {tot_legit}px)")
