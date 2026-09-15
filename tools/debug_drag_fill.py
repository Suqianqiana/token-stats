# -*- coding: utf-8 -*-
"""调试 drag_02 的填充：输出 f/sil/pocket/light 像素的可视化叠加图。"""
import numpy as np
from PIL import Image
from scipy import ndimage
from collections import deque
import os

SRC = r"C:\Users\a3564\.workbuddy\clipboard-images\clipboard-2026-09-12T05-18-41-142Z-4fa99baf.jpg"
A = np.asarray(Image.open(SRC).convert("RGB")).astype(np.int16)
S8 = np.ones((3, 3), int)

# 只处理 drag 面板
PANEL = ("drag", (16, 542, 597, 952), 3)
name, (px0, py0, px1, py1), expect = PANEL

ink = A.min(axis=2) < 200

def denoise(mask, min_px=60):
    lbl, n = ndimage.label(mask, structure=S8)
    if not n:
        return mask
    szs = np.bincount(lbl.ravel())
    small = np.zeros(len(szs), bool); small[1:] = szs[1:] < min_px
    return mask & ~small[lbl]

ink = denoise(ink)
lbl_all, n_all = ndimage.label(ink, structure=S8)

panel = np.zeros_like(ink)
panel[py0:py1 + 1, px0:px1 + 1] = True

comps = []
labels_here = np.unique(lbl_all[panel])
for li in labels_here:
    if li == 0:
        continue
    m = lbl_all == li
    if (m & panel).sum() < 100:
        continue
    ys, xs = np.where(m)
    comps.append(dict(mask=m, x0=int(xs.min()), x1=int(xs.max()),
                      y0=int(ys.min()), y1=int(ys.max()), px=int(m.sum())))

chars, decors = [], []
for c in comps:
    is_char = ((c["y1"] - c["y0"] + 1) >= 80 and
               (c["x1"] - c["x0"] + 1) / float(c["y1"] - c["y0"] + 1) < 2.5)
    (chars if is_char else decors).append(c)
chars.sort(key=lambda c: c["x0"])
base_w = float(min(c["x1"] - c["x0"] + 1 for c in chars))

def split_by_bodies(mask, k):
    sil = ndimage.binary_fill_holes(mask)
    for t in (2, 3, 4, 5, 6, 8, 10, 12):
        er = ndimage.binary_erosion(sil, structure=S8, iterations=t)
        lb, nn = ndimage.label(er, structure=S8)
        if nn < 1:
            continue
        szs = np.bincount(lb.ravel())
        keep = [i for i in range(1, nn + 1) if szs[i] >= 300]
        if len(keep) < k:
            continue
        if len(keep) > k:
            keep = sorted(keep, key=lambda i: -szs[i])[:k]
        lab = np.zeros(sil.shape, np.int32)
        dq = deque()
        for sid, i in enumerate(keep, 1):
            ys, xs = np.where(lb == i)
            for yy, xx in zip(ys, xs):
                lab[yy, xx] = sid
                dq.append((yy, xx))
        while dq:
            y, x = dq.popleft()
            for ny, nx in ((y-1, x), (y+1, x), (y, x-1), (y, x+1),
                           (y-1, x-1), (y-1, x+1), (y+1, x-1), (y+1, x+1)):
                if 0 <= ny < sil.shape[0] and 0 <= nx < sil.shape[1] \
                   and sil[ny, nx] and lab[ny, nx] == 0:
                    lab[ny, nx] = lab[y, x]
                    dq.append((ny, nx))
        parts = []
        for sid in range(1, len(keep) + 1):
            p = lab == sid
            if p.sum() < 500:
                continue
            p = ndimage.binary_fill_holes(p) & sil
            parts.append(p)
        if len(parts) == k:
            return parts
    return []

frames = []
for c in chars:
    w = c["x1"] - c["x0"] + 1
    k = max(1, int(round(w / base_w)))
    if k == 1:
        frames.append(c["mask"])
    else:
        frames.extend(split_by_bodies(c["mask"], k))
frames = [f for f in frames if f.sum() > 500]

# 处理 drag_02 (索引 1)
f = frames[1]
ys0, xs0 = np.where(f)
wx0 = max(0, int(xs0.min()) - 6); wx1 = min(A.shape[1] - 1, int(xs0.max()) + 6)
wy0 = max(0, int(ys0.min()) - 6); wy1 = min(A.shape[0] - 1, int(ys0.max()) + 6)
sub = A[wy0:wy1 + 1, wx0:wx1 + 1]
smn = sub.min(axis=2); ssat = sub.max(axis=2) - smn
light = (smn >= 222) & (ssat <= 30)
blocked = ndimage.binary_dilation(f[wy0:wy1 + 1, wx0:wx1 + 1], structure=S8, iterations=1)
passable = light & ~blocked
hh, ww = passable.shape
rch = np.zeros((hh, ww), bool)
dq2 = deque()
for x in range(ww):
    for y in (0, hh - 1):
        if passable[y, x] and not rch[y, x]:
            rch[y, x] = True; dq2.append((y, x))
for y in range(hh):
    for x in (0, ww - 1):
        if passable[y, x] and not rch[y, x]:
            rch[y, x] = True; dq2.append((y, x))
while dq2:
    y, x = dq2.popleft()
    for ny, nx in ((y-1, x), (y+1, x), (y, x-1), (y, x+1)):
        if 0 <= ny < hh and 0 <= nx < ww and not rch[ny, nx] and passable[ny, nx]:
            rch[ny, nx] = True; dq2.append((ny, nx))
sil = ndimage.binary_fill_holes(f)
sil[wy0:wy1 + 1, wx0:wx1 + 1] &= ~rch

# 可视化
vis = A.copy()
# f 区域标绿色（半透明）
vis[f] = (vis[f] * 0.6 + np.array([0, 255, 0]) * 0.4).astype(np.uint8)
# pocket 区域标红色
pockets = sil & ~f
vis[pockets] = [255, 0, 0]
# 裁剪到 drag_02 区域
bx0, bx1 = max(0, int(xs0.min()) - 10), min(A.shape[1] - 1, int(xs0.max()) + 10)
by0, by1 = max(0, int(ys0.min()) - 10), min(A.shape[0] - 1, int(ys0.max()) + 10)
crop = vis[by0:by1+1, bx0:bx1+1]
Image.fromarray(np.clip(crop, 0, 255).astype(np.uint8)).save("assets/_debug_drag_02_f_sil.png")
print(f"saved _debug_drag_02_f_sil.png  green=f  red=pocket(sil&~f)")
print(f"  f area={f.sum()}, sil area={sil.sum()}, pockets={pockets.sum()}")
print(f"  pocket components >=18px: {ndimage.label(pockets, structure=S8)[1]}")
# 输出 pocket 面积分布
pl, pn = ndimage.label(pockets, structure=S8)
if pn:
    psz = np.bincount(pl.ravel())[1:]
    print(f"  pocket sizes: min={psz.min()}, max={psz.max()}, median={int(np.median(psz))}")
    print(f"  top 10 sizes: {sorted(psz, reverse=True)[:10]}")
