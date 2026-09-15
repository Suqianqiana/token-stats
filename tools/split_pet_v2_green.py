# -*- coding: utf-8 -*-
"""V2 素材重建 v2: 绿幕抠图 —— 改用"物理 alpha + unpremultiply + 边缘颜色继承"。

为什么改 (用户反馈"边缘绿色还是有"):
  v1 用线性 alpha `clip((130-g)/90)` + 去溢色 `G -= spill*(G-max(R,B))`:
    · alpha 偏小 (g=77 时算 0.59, 物理值应为 1-77/241=0.68) -> 反解色偏移;
    · "把 G 压到 max(R,B)" 在 max 是**蓝色**时, 边缘会变成**青色**, 视觉上依旧带绿。
  v2 三步:
    ① alpha 用物理式: 背景 g=G_bg -> alpha = clip((T_hi - g)/(T_hi - T_lo), 0, 1)
    ② unpremultiply:  C_fg = (C_obs - (1-alpha)*C_bg) / alpha
    ③ **边缘颜色继承**: 取最近"完全不透明"像素(core)的本体色, 按 (1-alpha) 权重混回边缘
       -> 边缘颜色直接来自角色本体(蓝), 从根上不会有绿/青
  兜底再 `G <= max(R,B)` 一次(此时已无绿可削)。

源图 (用户 2026-09-14 第二版, "优化了绿幕和素材边缘质量"):
  Gemini_Generated_Image_a12s5ia12s5ia12s.jfif — JPEG RGB 2528x1686
  背景深绿 RGB=(13.3,173.7,55.5) 绿纯度 g 分位 1/5/50/99 = 101/105/121/126
  角色内部 g 为负 (<=-11) -> 双峰干净可分, 中间过渡带约 15 万像素
"""
import os, json
import numpy as np
from PIL import Image
from scipy import ndimage

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = r"C:\Users\a3564\Downloads\Gemini_Generated_Image_a12s5ia12s5ia12s.jfif"
OUT = os.path.join(BASE, "assets", "pet_v2_green")

BG_RGB = np.array([7.74, 249.2, 4.24], np.float32)   # 实测新版绿幕底色(最外5圈均值)
G_BG_G = 241.0    # 背景绿纯度 g 的均值 -> alpha = 1 - g/G_BG_G (物理式; g>=G_BG_G 即纯背景)
                  # 注意: 这版绿幕偏暗, 背景 g 只有 101~126 (旧版是 216~251),
                  #       ★ 背景 g **高**、角色 g **低**(负值) —— 方向别搞反
BAND_MIN_H = 300  # 角色行最小高度
EDGE_W = 10.0       # 羽化带宽度: 距 core <= 此值的像素, 颜色直接采用本体色
EDGE_W = 10.0       # 羽化带宽度: 距 core <= 此值的像素, 颜色直接采用本体色
G_FG_MAX = 25.0   # g <= 此值 = 角色本体(实测角色内部 g>25 仅占 0.01%) -> 强制不透明
G_FG_MAX = 25.0   # g <= 此值 = 角色本体(实测角色内部 g>25 仅占 0.01%) -> 强制不透明
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
    k = nseg - 1
    W = len(col)
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
    cuts.reverse()
    return cuts


def estimate_nseg(fg):
    """按"连通域宽度/宽度中位数"估角色数(用面积会被粘连大块拉偏 -> 低估)。"""
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
    med = float(np.median(ws))
    tot = 0
    for wv in ws:
        r = wv / med
        if r < 0.55: continue
        tot += 2 if r >= 1.45 else 1
    return max(2, min(9, tot))


def main():
    img = Image.open(SRC).convert("RGB")
    A = np.asarray(img).astype(np.int16)
    h, w = A.shape[:2]
    print(f"源 {w}x{h} {img.mode}")
    g = A[..., 1] - np.maximum(A[..., 0], A[..., 2])
    fg = np.clip((G_BG_G - g) / G_BG_G, 0.0, 1.0) > 0.5
    print(f"G_BG_G={G_BG_G:.0f}  前景(alpha>0.5)占比 {fg.mean()*100:.1f}%")

    rb = [b for b in bands(fg.sum(1), 8, 6) if b[1] - b[0] + 1 >= BAND_MIN_H]
    lb = [b for b in bands(fg.sum(1), 8, 6) if b[1] - b[0] + 1 < BAND_MIN_H]
    print(f"角色行 {len(rb)} 段 {rb}   矮带 {len(lb)} 段 {lb}")

    os.makedirs(OUT, exist_ok=True)
    qc = {}
    idx = 0
    for ri, (y0, y1) in enumerate(rb):
        sub = fg[y0:y1 + 1]
        nseg = estimate_nseg(sub)
        cuts = best_cuts(sub.sum(0), nseg)
        bnds = [0] + list(cuts) + [sub.shape[1]]
        seg_px = [int(sub[:, bnds[t]:bnds[t + 1]].sum()) for t in range(nseg)]
        ratio = max(seg_px) / max(1, min(seg_px))
        print(f"  行{ri+1} y{y0}..{y1}: {nseg} 个  切点 {cuts}  面积比 {ratio:.2f}"
              + ("   <<< 偏大" if ratio > 1.7 else ""))
        for si in range(nseg):
            x0, x1 = bnds[si], bnds[si + 1]
            sub_g = g[y0:y1 + 1, x0:x1].astype(np.float32)
            sub_rgb = A[y0:y1 + 1, x0:x1].astype(np.float32)
            # ① 物理 alpha
            al = np.clip((G_BG_G - sub_g) / G_BG_G, 0.0, 1.0)
            # 角色本体强制不透明(并填掉本体内部的空洞), 否则内部柔和像素会变半透明
            core = sub_g <= G_FG_MAX
            if core.any():
                al[ndimage.binary_fill_holes(core)] = 1.0
            m = al > 0.5
            if m.sum() < 500:
                print(f"    !! 第{si+1}段 前景过少, 跳过"); continue
            far = ndimage.distance_transform_edt(m) >= 1.6
            al[far] = 1.0
            # ② unpremultiply (反解前景真实色)
            a3 = np.maximum(al, 0.15)[..., None]
            fg_rgb = np.clip((sub_rgb - (1.0 - al[..., None]) * BG_RGB) / a3, 0.0, 255.0)
            # ③ 边缘颜色继承 (第38轮: 改成"羽化带完全采用本体色")
            #   诊断: 源图角色**内部**色相 229(蓝), 而**边缘** 0~3px 色相 190(青)
            #   —— 即偏绿/青是**原图自带**的轮廓色溢(深入 3px+), 不是抠图残留。
            #   所以只要边缘还保留"自己反解出来的颜色", 就一定会带青。
            #   做法: 取"最近的内侧本体像素颜色"(core 先内缩 4px 保证源色纯净),
            #        把**整条羽化带(距 core <= EDGE_W)**的颜色直接替换成它 —— alpha 羽化保留,
            #        颜色则完全等于角色本体色, 于是色相与内部一致, 绿/青彻底消失。
            core = al >= 0.98
            core_in = ndimage.binary_erosion(core, structure=S8, iterations=4)
            if core_in.any():
                _, nidx = ndimage.distance_transform_edt(~core_in, return_indices=True)
                near = fg_rgb[nidx[0], nidx[1]]
                d_core = ndimage.distance_transform_edt(core)
                band = (al > 0) & (d_core <= EDGE_W)
                fg_rgb[band] = near[band]
            # 兜底: 确保没有像素偏绿
            fg_rgb[..., 1] = np.minimum(fg_rgb[..., 1],
                                        np.maximum(fg_rgb[..., 0], fg_rgb[..., 2]))
            # bbox (按 alpha>0.02)
            ys, xs = np.where(al > 0.02)
            by0, by1 = y0 + int(ys.min()), y0 + int(ys.max())
            bx0, bx1 = x0 + int(xs.min()), x0 + int(xs.max())
            al_c = al[by0 - y0:by1 - y0 + 1, bx0 - x0:bx1 - x0 + 1]
            rgb_c = fg_rgb[by0 - y0:by1 - y0 + 1, bx0 - x0:bx1 - x0 + 1]
            a8 = np.clip(al_c * 255.0, 0, 255).astype(np.uint8)
            out = np.dstack([np.clip(rgb_c, 0, 255).astype(np.uint8), a8])
            idx += 1
            fn = f"v2g_{idx:02d}.png"
            Image.fromarray(out, "RGBA").save(os.path.join(OUT, fn))
            op = int((a8 > 200).sum())
            qc[fn] = dict(size=[out.shape[1], out.shape[0]], opaque=op,
                          semi=int(((a8 > 0) & (a8 < 250)).sum()),
                          src=[bx0, by0, bx1, by1])
            print(f"      #{idx:>2} {fn}  {out.shape[1]}x{out.shape[0]}  不透明{op} "
                  f"半透明{int(((a8>0)&(a8<250)).sum())}  源 y{by0}..{by1}")
    json.dump(qc, open(os.path.join(BASE, "assets", "pet_v2_green_qc.json"), "w",
                       encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"合计 {idx} 帧 -> {OUT}")


if __name__ == "__main__":
    main()
