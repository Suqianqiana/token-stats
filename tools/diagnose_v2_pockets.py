# -*- coding: utf-8 -*-
"""诊断 v2 素材腔删除：输出用户指定的 5 帧中每个候选腔的属性，
   看哪些该删却被保留了（尤其是头发包围域）。"""
import numpy as np
from PIL import Image
from scipy import ndimage
import os
from collections import deque

SRC = r"C:\Users\a3564\.workbuddy\clipboard-images\clipboard-2026-09-12T05-18-41-142Z-4fa99baf.jpg"
A = np.asarray(Image.open(SRC).convert("RGB")).astype(np.int16)
S8 = np.ones((3, 3), int)
mn_all = A.min(axis=2)
sat_all = A.max(axis=2) - mn_all
b_r = A[..., 2] - A[..., 0]

PANELS = [
    ("idle",    (16, 96, 935, 526), 4),
    ("sleep",   (945, 96, 1523, 526), 2),
    ("drag",    (16, 542, 597, 952), 3),
    ("click",   (604, 540, 1088, 953), 2),
    ("special", (1096, 536, 1522, 952), 2),
]
ink = mn_all < 200

def denoise(mask, min_px=60):
    lbl, n = ndimage.label(mask, structure=S8)
    if not n:
        return mask
    szs = np.bincount(lbl.ravel())
    small = np.zeros(len(szs), bool); small[1:] = szs[1:] < min_px
    return mask & ~small[lbl]

ink = denoise(ink)
lbl_all, n_all = ndimage.label(ink, structure=S8)

def split_by_valleys(mask, k):
    ys, xs = np.where(mask)
    lo, hi = int(xs.min()), int(xs.max())
    w = hi - lo + 1
    cols = mask.sum(axis=0)
    cuts = []
    for j in range(1, k):
        ctr = lo + int(w * j / k)
        span = max(6, int(w * 0.16))
        a, b = max(lo + 1, ctr - span), min(hi - 1, ctr + span)
        cuts.append(a + int(np.argmin(cols[a:b + 1])))
    cuts = sorted(set(cuts))
    edges = [lo - 1] + cuts + [hi + 1]
    parts = []
    for j in range(len(edges) - 1):
        p = mask.copy()
        p[:, :edges[j] + 1] = False
        p[:, edges[j + 1]:] = False
        ys2, xs2 = np.where(p)
        p[:, :int(xs2.min())] = False
        parts.append(p)
    return parts

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
    return split_by_valleys(mask, k)

# 目标帧
targets = {
    ("idle", 1), ("idle", 2),
    ("sleep", 2),
    ("drag", 2), ("drag", 3),
}

for name, (px0, py0, px1, py1), expect in PANELS:
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
    if not chars:
        continue
    base_w = float(min(c["x1"] - c["x0"] + 1 for c in chars))
    frames = []
    for c in chars:
        w = c["x1"] - c["x0"] + 1
        k = max(1, int(round(w / base_w)))
        if k == 1:
            frames.append(c["mask"])
        else:
            frames.extend(split_by_bodies(c["mask"], k))
    frames = [f for f in frames if f.sum() > 500]

    for idx, f in enumerate(frames):
        if (name, idx + 1) not in targets:
            continue
        print(f"\n========== {name}_{idx+1:02d} ==========")
        # 复用原脚本的 sil 生成（包括白描边泛洪）
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

        ink_core = ndimage.binary_erosion(f, structure=S8, iterations=2)
        dist_out = ndimage.distance_transform_edt(sil)
        _ys0, _ = np.where(sil)
        y_top, y_bot = int(_ys0.min()), int(_ys0.max())
        leg_y = y_bot - int((y_bot - y_top) * 0.30)

        for it in range(2):
            pockets = sil & ~f
            pl, pn = ndimage.label(pockets, structure=S8)
            if not pn:
                print("  无腔")
                break
            psz = np.bincount(pl.ravel())
            cand = [j for j in range(1, pn + 1) if psz[j] >= 18
                    and float((f & (pl == j)).sum()) / psz[j] < 0.02
                    and float(A[pl == j].min(axis=1).mean()) >= 210
                    and float(b_r[pl == j].mean()) >= -2
                    and float(sat_all[pl == j].mean()) <= 32]
            biggest = max(cand, key=lambda j: psz[j]) if cand else None
            print(f"  迭代{it+1}: 候选腔 {len(cand)} 个, 最大腔面积 {psz[biggest] if biggest else 0}")
            kept_reasons = []
            for j in sorted(cand, key=lambda j: -psz[j]):
                m = pl == j
                yy, xx = np.where(m)
                cx, cy = int(xx.mean()), int(yy.mean())
                med_depth = float(np.median(dist_out[m]))
                ring = ndimage.binary_dilation(m, structure=S8, iterations=3) & f
                ring_ink_ratio = float((ring & ink_core).sum()) / max(1, int(ring.sum()))
                reason = []
                if j == biggest:
                    reason.append("biggest(围裙)")
                if med_depth > 28:
                    reason.append(f"deep(depth>{med_depth:.1f})")
                if cy > leg_y:
                    reason.append("leg_guard")
                if psz[j] < 120 and ring_ink_ratio >= 0.30:
                    reason.append(f"small_ring_ink({ring_ink_ratio:.2f})")
                action = "DROP" if not reason else "KEEP"
                print(f"    #{j} area={psz[j]:5d} depth={med_depth:5.1f} cy={cy:4d} leg_y={leg_y:4d} "
                      f"mn={A[pl==j].min(axis=1).mean():5.1f} sat={sat_all[pl==j].mean():5.1f} "
                      f"b_r={b_r[pl==j].mean():5.1f} ring_ink={ring_ink_ratio:.2f} "
                      f"-> {action} {','.join(reason) if reason else ''}")
            drop = np.zeros_like(sil)
            for j in cand:
                m = pl == j
                if j == biggest:
                    continue
                if float(np.median(dist_out[m])) > 28:
                    continue
                yy, _xx = np.where(m)
                if int(yy.mean()) > leg_y:
                    continue
                if psz[j] < 120:
                    ring = ndimage.binary_dilation(m, structure=S8, iterations=3) & f
                    if float((ring & ink_core).sum()) / max(1, int(ring.sum())) >= 0.30:
                        continue
                drop |= m
            if not drop.any() or float(drop.sum()) > 0.25 * max(1.0, float(sil.sum())):
                break
            sil = sil & ~drop
