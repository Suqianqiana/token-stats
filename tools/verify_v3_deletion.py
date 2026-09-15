# -*- coding: utf-8 -*-
"""v3 抠图误删校验 (第32轮): 校验"头发环"删除规则是否误删了画出来的白。
   判据: 区域自身偏离面板纯白 dev = mean(max|RGB-255|)。
        dev > 8.0  -> 属于"画出来的白"(鲸鱼肚/裙摆/书籍/发饰白), 必须 KEEP
        dev <= 8.0 -> 属于面板背景坑, 应当 DEL(尺寸>=120px)
"""
import numpy as np, json, os
from PIL import Image
from scipy import ndimage
from collections import deque

BASE = r"C:/Users/a3564/WorkBuddy/2026-08-25-04-20-35/token-stats"
SRC = {"setA": r"C:\Users\a3564\.workbuddy\clipboard-images\clipboard-2026-09-13T21-46-03-551Z-a70b73fe.jpg",
       "setB": r"C:\Users\a3564\.workbuddy\clipboard-images\clipboard-2026-09-13T21-46-03-556Z-1fb214d8.jpg"}
ROOT = os.path.join(BASE, "assets", "pet_v3")
W = json.load(open(os.path.join(BASE, "assets", "pet_v3_windows.json"), encoding="utf-8"))
S8 = np.ones((3, 3), int)
BG = np.array([255., 255., 255.])
THRESH = 8.0

del_bad, keep_painted, del_ok, left = [], 0, 0, []
for st, sp in SRC.items():
    A = np.asarray(Image.open(sp).convert("RGB")).astype(np.float64)
    mn = A.min(2); sat = A.max(2) - mn
    white = (mn >= 240) & (sat <= 16)
    for key, d in W.items():
        if not key.startswith(st):
            continue
        nm = key.split("/")[1]; cb = d["cbox"]; fb = d["fbox"]
        o = np.asarray(Image.open(os.path.join(ROOT, st, nm + ".png")).convert("RGBA"))
        oy, ox = o.shape[:2]
        op = np.zeros(A.shape[:2], bool)
        op[fb[1]:fb[1] + oy, fb[0]:fb[0] + ox] = o[..., 3] > 200
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
        for j in range(1, n + 1):
            if szs[j] < 18:
                continue
            m = lab == j
            ring = ndimage.binary_dilation(m, structure=S8, iterations=4) & ~m
            r = A[ring] if ring.sum() else None
            rbr = float((r[:, 2] - r[:, 0]).mean()) if r is not None and len(r) else -1
            if rbr < 25:                      # 只看"头发环"候选(规则的作用域)
                continue
            dev = float(np.abs(A[m] - BG).max(1).mean())
            ys, xs = np.where(m)
            yf = (ys.mean() - cb[1]) / cbh; xf = (xs.mean() - cb[0]) / cbw
            isdel = (m & op).sum() / szs[j] < 0.5
            if dev > THRESH:
                if isdel:
                    del_bad.append((nm, int(szs[j]), round(yf, 2), round(xf, 2), round(dev, 1)))
                else:
                    keep_painted += 1
            elif isdel:
                del_ok += 1
            elif yf < 0.30 or xf < 0.30 or xf > 0.70:
                left.append((nm, int(szs[j]), round(dev, 1)))

print(f"[画出来的白 dev>{THRESH}]  保住 {keep_painted} 处, 误删 {len(del_bad)} 处")
if del_bad:
    print("   误删清单:", del_bad)
print(f"[面板背景坑 dev<={THRESH}] 删除 {del_ok} 处, 残留 {len(left)} 处")
if left:
    left.sort(key=lambda r: -r[1])
    print("   残留(尺寸小, 属轻微):", [(a, b) for a, b, _c in left[:10]])
print()
print(">>> 判定:", "画出来的白零误删 ✅" if not del_bad else "仍有误删 ❌")
