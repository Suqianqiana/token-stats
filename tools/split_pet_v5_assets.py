# -*- coding: utf-8 -*-
"""桌宠 v5 素材: 直接从"透明背景 PNG 原图"切分 —— 零抠图。

源图 = 用户 ChatGPT 生成的 1536x1024 RGBA PNG, 背景 alpha=0 (真透明)。
因此**不需要任何前景/背景判断**(那些误删下摆白/呆毛没扣/发丝断的问题全部不存在),
只需要: 行带分离 -> 每行竖向最优切分 -> 裁剪(保留原始 alpha 羽化)。

版面: 每张 2 行 x N 列; 每行角色下方有一条"蓝色圆角标签"(动作名) -> 按行高排除(标签高 ~40px)。
切分: 对每行用动态规划求最优切点, 使"切在角色身上的像素"最少, 且每段宽度 >= MINW。

用法: python tools/split_pet_v5_assets.py
输出: assets/pet_v5/{setA,setB,setC}/<name>_NN.png  +  assets/pet_v5_windows.json
"""
import os, json, sys
import numpy as np
from PIL import Image

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_ROOT = os.path.join(BASE_DIR, "assets", "pet_v5")
DL = r"C:\Users\a3564\Downloads"

SRC = [
    ("setA", os.path.join(DL, "ChatGPT Image 2026年9月14日 05_37_23.png")),
    ("setB", os.path.join(DL, "ChatGPT Image 2026年9月14日 05_28_15.png")),
    ("setC", os.path.join(DL, "ChatGPT Image 2026年9月14日 07_20_09.png")),
]

MINW = 185          # 单角色最小宽度
ALPHA_ON = 128      # 前景判定
BAND_MIN_H = 150    # 行高 >= 此值 = 角色行 (标签行只有 ~40px)
BLK_MIN = 1000      # 参与"角色数估计"的连通域最小面积


def row_bands(op, min_h=BAND_MIN_H, gap=2):
    """返回角色行的 [y0,y1] 列表 (排除标签行)。
       gap 必须 <= 2: setB 的标签条(行1的标签在 y479..517)与行2角色(y522起)之间
       只有 2 行真空隙(rows 从 380 骤降到 2), gap=3 就会把标签并进角色行。"""
    rows = op.sum(1)
    on = rows > 3
    segs = []
    s = None
    for i, v in enumerate(on):
        if v and s is None:
            s = i
        if not v and s is not None:
            segs.append([s, i - 1]); s = None
    if s is not None:
        segs.append([s, len(on) - 1])
    merged = []
    for b in segs:
        if merged and b[0] - merged[-1][1] <= gap:
            merged[-1][1] = b[1]
        else:
            merged.append(b)
    return [b for b in merged if b[1] - b[0] + 1 >= min_h]


def label_rows(op, min_h=BAND_MIN_H, gap=2):
    """非角色行(标签/装饰带), 用于对照检查。"""
    rows = op.sum(1)
    on = rows > 3
    segs = []; s = None
    for i, v in enumerate(on):
        if v and s is None:
            s = i
        if not v and s is not None:
            segs.append([s, i - 1]); s = None
    if s is not None:
        segs.append([s, len(on) - 1])
    merged = []
    for b in segs:
        if merged and b[0] - merged[-1][1] <= gap:
            merged[-1][1] = b[1]
        else:
            merged.append(b)
    return [b for b in merged if b[1] - b[0] + 1 < min_h]


def best_cuts(col, nseg, minw=MINW):
    """DP: 在列投影 col 上切 nseg-1 刀, 使切点列的不透明像素之和最小。"""
    k = nseg - 1
    W = len(col)
    if k <= 0:
        return []
    INF = float("inf")

    def cost(i):
        return int(col[i]) if 0 <= i < W else 0

    dp = [[INF] * W for _ in range(k + 1)]
    bk = [[-1] * W for _ in range(k + 1)]
    for t in range(minw, W):
        dp[1][t] = cost(t)
    for j in range(2, k + 1):
        best, bi = INF, -1
        for t in range(minw, W):
            s = t - minw
            if s >= 1 and dp[j - 1][s] < best:
                best, bi = dp[j - 1][s], s
            if best < INF:
                dp[j][t] = best + cost(t)
                bk[j][t] = bi
    bestv, last = INF, -1
    for t in range(minw, W - minw + 1):
        if dp[k][t] < bestv:
            bestv, last = dp[k][t], t
    if last < 0:
        return []
    cuts = []
    i = last
    for j in range(k, 0, -1):
        cuts.append(i)
        i = bk[j][i]
    cuts.reverse()
    return cuts


def estimate_nseg(op):
    """角色数估计: 只取"大块"(面积>=最大块的 35%, 滤掉装饰件/飘带碎片)算面积中位数,
       再用 行内总前景 / 中位数 取整。直接用全部 >=BLK_MIN 的块会被小装饰件拉低中位数,
       导致角色数被高估(setB 行2 曾因此从 5 估成 8)。"""
    from scipy import ndimage
    S8 = np.ones((3, 3), int)
    lbl, n = ndimage.label(op, structure=S8)
    if not n:
        return 1
    szs = np.bincount(lbl.ravel()); szs[0] = 0
    big = sorted([int(s) for s in szs if s >= BLK_MIN], reverse=True)
    if not big:
        return 1
    thr = max(BLK_MIN, 0.35 * big[0])
    core = [s for s in big if s >= thr]
    med = float(np.median(core)) if core else float(big[0])
    total = int(op.sum())
    n_est = int(round(total / max(1.0, med)))
    return max(4, min(8, n_est))


def main():
    info = {}
    qc = {}
    for name, path in SRC:
        if not os.path.exists(path):
            print(f"!! 源图不存在: {path}"); continue
        img = Image.open(path).convert("RGBA")
        A = np.asarray(img)
        al = A[..., 3]
        op = al > ALPHA_ON
        print("=" * 92)
        print(f"[{name}] {os.path.basename(path)}  {img.width}x{img.height}  不透明 {int(op.sum())}px")
        rb = row_bands(op)
        lb = label_rows(op)
        print(f"   角色行 {len(rb)} 段: {rb}    标签/装饰带 {len(lb)} 段: {lb}   (已排除标签)")
        od = os.path.join(OUT_ROOT, name)
        os.makedirs(od, exist_ok=True)
        idx = 0
        for ri, (y0, y1) in enumerate(rb):
            sub = op[y0:y1 + 1]
            nseg = estimate_nseg(sub)
            cuts = best_cuts(sub.sum(0), nseg)
            bnds = [0] + list(cuts) + [sub.shape[1]]
            seg_px = [int(sub[:, bnds[t]:bnds[t + 1]].sum()) for t in range(nseg)]
            ratio = max(seg_px) / max(1, min(seg_px))
            warn = "   <<< 面积比偏大, 可能切错" if ratio > 1.7 else ""
            print(f"   行{ri+1} (y {y0}..{y1}): 估计角色数 {nseg}  切点 {cuts}  "
                  f"面积比 {ratio:.2f}{warn}")
            for si in range(nseg):
                x0, x1 = bnds[si], bnds[si + 1]
                # 取该列区间内的所有前景(含半透明羽化) -> 用 alpha>8 定 bbox
                seg_al = al[y0:y1 + 1, x0:x1]
                m = seg_al > 8
                if not m.any():
                    print(f"      !! {i+1} 段无内容, 跳过"); continue
                yy, xx = np.where(m)
                by0, by1 = y0 + int(yy.min()), y0 + int(yy.max())
                bx0, bx1 = x0 + int(xx.min()), x0 + int(xx.max())
                crop = A[by0:by1 + 1, bx0:bx1 + 1]
                idx += 1
                fn = f"{name}_{idx:02d}.png"
                Image.fromarray(crop, "RGBA").save(os.path.join(od, fn))
                o = crop[..., 3]
                qc[f"{name}_{idx:02d}"] = dict(
                    size=[crop.shape[1], crop.shape[0]],
                    opaque=int((o > 200).sum()),
                    semi=int(((o > 0) & (o < 250)).sum()),
                    zero=int((o == 0).sum()),
                    cut_src=[bx0, by0, bx1, by1],
                )
                info[f"{name}/{name}_{idx:02d}"] = dict(cbox=[bx0, by0, bx1, by1])
                print(f"      #{idx:>2} {fn}  {crop.shape[1]}x{crop.shape[0]}  "
                      f"不透明{int((o>200).sum())} 半透明{int(((o>0)&(o<250)).sum())}")

    with open(os.path.join(BASE_DIR, "assets", "pet_v5_qc.json"), "w", encoding="utf-8") as f:
        json.dump(qc, f, ensure_ascii=False, indent=1)
    with open(os.path.join(BASE_DIR, "assets", "pet_v5_windows.json"), "w", encoding="utf-8") as f:
        json.dump(info, f, ensure_ascii=False, indent=1)
    print("=" * 92)
    print(f"合计 {len(qc)} 帧 -> {OUT_ROOT}")


if __name__ == "__main__":
    main()
