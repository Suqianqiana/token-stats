# -*- coding: utf-8 -*-
"""2026-10-23: 新批次素材饱和度量化 (沿用 docs/素材饱和度优化.md 口径)。

口径: 每帧 alpha bbox 顶部 45% 高度区域, 挑蓝发像素 (H∈[130,185], S>20, V>20),
统计 HSV 的 S/V。分组: 现有 v3r 45 帧 (基准) vs 浅浅猫新选 95 帧。
"""
import glob
import io
import json
import os
import sys

sys.dont_write_bytecode = True
import numpy as np
from PIL import Image
from scipy import ndimage

S8 = np.ones((3, 3), bool)
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NEW = os.path.join(BASE, "assets", "pet_new_20261023")
LIB = os.path.join(BASE, "assets", "pet_v3r")
SEL = os.path.join(BASE, "docs", "pet_selection_20261023.json")


def hair_stats(path):
    """返回 (S中位, S均值, V均值, 头发中位色 hex)。口径与 docs/素材饱和度优化.md 完全一致:
    PIL HSV(H 为 0~255 刻度), 顶部 45% 高度, H∈[130,185] 即蓝色系。"""
    im = Image.open(path).convert("RGBA")
    a = np.asarray(im)
    al = a[..., 3]
    ys, xs = np.where(al > 128)
    if not len(ys):
        return None
    y0, y1 = int(ys.min()), int(ys.max())
    ycut = int(y0 + (y1 - y0 + 1) * 0.45)
    hsv = np.asarray(im.convert("HSV")).astype(np.int16)
    H, S, V = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    rowmask = np.arange(a.shape[0])[:, None] < ycut
    m = (al > 128) & rowmask & (H >= 130) & (H <= 185) & (S > 20) & (V > 20)
    if m.sum() < 500:
        return None
    rgb = np.asarray(im)[..., :3].astype(np.float64)
    med_rgb = np.median(rgb[m], axis=0)
    hexc = "#%02X%02X%02X" % tuple(int(round(x)) for x in med_rgb)
    return float(np.median(S[m])), float(S[m].mean()), float(V[m].mean()), hexc


def group(paths):
    ss, sv, vv, cols = [], [], [], []
    for p in paths:
        r = hair_stats(p)
        if r:
            ss.append(r[0]); sv.append(r[1]); vv.append(r[2]); cols.append(r[3])
    n = len(ss)
    return dict(n=n, s_med=float(np.median(ss)), s_mean=float(np.mean(sv)),
                v_mean=float(np.mean(vv)), color=cols[len(cols) // 2] if cols else "-")


def main():
    sel = json.load(io.open(SEL, encoding="utf-8"))
    new_ids = [fid for ids in sel["assignments"].values() for fid in ids]
    old_paths = sorted(glob.glob(os.path.join(LIB, "*", "*.png")))
    new_paths = [os.path.join(NEW, i + ".png") for i in new_ids]
    old = group(old_paths)
    new = group(new_paths)
    print("=" * 74)
    print("头发色量化 (口径: 帧顶部45%% 高度, H∈[130,185] 蓝发像素)")
    print("=" * 74)
    print("%-14s %5s %9s %9s %9s  %s" % ("组", "帧数", "S中位", "S均值", "V均值", "中位色"))
    print("%-14s %5d %9.1f %9.1f %9.1f  %s" % ("现有 v3r(基准)", old["n"], old["s_med"], old["s_mean"], old["v_mean"], old["color"]))
    print("%-14s %5d %9.1f %9.1f %9.1f  %s" % ("新选 95 帧", new["n"], new["s_med"], new["s_mean"], new["v_mean"], new["color"]))
    ds = new["s_med"] - old["s_med"]
    dv = new["v_mean"] - old["v_mean"]
    print("\n差距: 饱和度 %+.1f (%.0f%%), 明度 %+.1f" % (ds, ds / max(old["s_med"], 1) * 100, dv))
    if ds < -5 or dv < -3:
        print("结论: 新素材明显偏淡 -> 建议做饱和度+平滑提亮优化 (参照 09-17 B 方案 k≈1.20/lift≈0.16)")
    else:
        print("结论: 与现有素材基本一致, 可不做饱和度优化")


if __name__ == "__main__":
    main()
