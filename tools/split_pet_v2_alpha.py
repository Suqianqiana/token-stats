# -*- coding: utf-8 -*-
"""V2 素材重建: 从"用户自己抠好的透明 PNG"切分 —— 零抠图。
源: Gemini_Generated_Image_jjmed3jjmed3jjme-no-bg.png (PNG RGBA 2528x1686, 背景 alpha=0)
处理: 行带分离 -> DP 最优竖向切分 -> 裁剪(保留原 alpha)
      + 一次"去绿兜底"(G <= max(R,B)): 用户版边缘仍有 961px 轻微绿残留, 该操作只影响真正偏绿的像素。
"""
import os
import numpy as np
from PIL import Image
from scipy import ndimage

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = "C:/Users/a3564/Downloads/Gemini_Generated_Image_jjmed3jjmed3jjme-no-bg.png"
OUT = os.path.join(BASE, "assets", "pet_v2_alpha")
BAND_MIN_H = 300
MINW = 250
S8 = np.ones((3, 3), int)


def bands(v, thr, gap):
    on = v > thr
    segs = []; s = None
    for i, x in enumerate(on):
        if x and s is None: s = i
        if not x and s is not None: segs.append([s, i - 1]); s = None
    if s is not None: segs.append([s, len(on) - 1])
    m = []
    for b in segs:
        if m and b[0] - m[-1][1] <= gap: m[-1][1] = b[1]
        else: m.append(b)
    return m


def best_cuts(col, nseg, minw=MINW):
    k = nseg - 1; W = len(col)
    if k <= 0: return []
    INF = float("inf")
    def cost(i): return int(col[i]) if 0 <= i < W else 0
    dp = [[INF] * W for _ in range(k + 1)]
    bk = [[-1] * W for _ in range(k + 1)]
    for t in range(minw, W): dp[1][t] = cost(t)
    for j in range(2, k + 1):
        best, bi = INF, -1
        for t in range(minw, W):
            s = t - minw
            if s >= 1 and dp[j - 1][s] < best: best, bi = dp[j - 1][s], s
            if best < INF: dp[j][t] = best + cost(t); bk[j][t] = bi
    bestv, last = INF, -1
    for t in range(minw, W - minw + 1):
        if dp[k][t] < bestv: bestv, last = dp[k][t], t
    if last < 0: return []
    cuts = []; i = last
    for j in range(k, 0, -1):
        cuts.append(i); i = bk[j][i]
    cuts.reverse(); return cuts


def estimate_nseg(fg):
    lbl, n = ndimage.label(fg, structure=S8)
    if not n: return 1
    szs = np.bincount(lbl.ravel()); szs[0] = 0
    objs = ndimage.find_objects(lbl)
    ws = []
    for i in range(1, n + 1):
        if szs[i] < 2000: continue
        sl = objs[i - 1]
        if sl is None: continue
        ws.append(sl[1].stop - sl[1].start)
    if not ws: return 1
    med = float(np.median(ws)); tot = 0
    for wv in ws:
        r = wv / med
        if r < 0.55: continue
        tot += 2 if r >= 1.45 else 1
    return max(2, min(9, tot))


def main():
    img = Image.open(SRC).convert("RGBA")
    A = np.asarray(img)
    al = A[..., 3]
    op = al > 128
    print(f"源 {img.width}x{img.height} RGBA  不透明 {op.mean()*100:.1f}%")
    rb = [b for b in bands(op.sum(1), 8, 6) if b[1] - b[0] + 1 >= BAND_MIN_H]
    lb = [b for b in bands(op.sum(1), 8, 6) if b[1] - b[0] + 1 < BAND_MIN_H]
    print(f"角色行 {len(rb)} 段 {rb}  矮带 {len(lb)} 段 {lb}")
    os.makedirs(OUT, exist_ok=True)
    rgb_all = A[..., :3].astype(np.int16)
    idx = 0
    for ri, (y0, y1) in enumerate(rb):
        sub = op[y0:y1 + 1]
        nseg = estimate_nseg(sub)
        cuts = best_cuts(sub.sum(0), nseg)
        bnds = [0] + list(cuts) + [sub.shape[1]]
        seg_px = [int(sub[:, bnds[t]:bnds[t + 1]].sum()) for t in range(nseg)]
        ratio = max(seg_px) / max(1, min(seg_px))
        print(f"  行{ri+1} y{y0}..{y1}: {nseg} 个  切点 {cuts}  面积比 {ratio:.2f}"
              + ("   <<< 偏大" if ratio > 1.7 else ""))
        for si in range(nseg):
            x0, x1 = bnds[si], bnds[si + 1]
            sub_al = al[y0:y1 + 1, x0:x1]
            m = sub_al > 8
            if not m.any(): continue
            ys, xs = np.where(m)
            by0, by1 = y0 + int(ys.min()), y0 + int(ys.max())
            bx0, bx1 = x0 + int(xs.min()), x0 + int(xs.max())
            a_c = A[by0:by1 + 1, bx0:bx1 + 1, 3]
            rgb_c = rgb_all[by0:by1 + 1, bx0:bx1 + 1].copy()
            # 去绿兜底(只影响真正 G>max(R,B) 的像素)
            gr = np.maximum(rgb_c[..., 0], rgb_c[..., 2])
            rgb_c[..., 1] = np.minimum(rgb_c[..., 1], gr)
            out = np.dstack([np.clip(rgb_c, 0, 255).astype(np.uint8), a_c])
            idx += 1
            fn = f"v2g_{idx:02d}.png"
            Image.fromarray(out, "RGBA").save(os.path.join(OUT, fn))
            print(f"      #{idx:>2} {fn}  {out.shape[1]}x{out.shape[0]}  "
                  f"不透明{int((a_c>200).sum())} 半透明{int(((a_c>0)&(a_c<250)).sum())}  源 y{by0}..{by1}")
    print(f"合计 {idx} 帧 -> {OUT}")


if __name__ == "__main__":
    main()
