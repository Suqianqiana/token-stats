# -*- coding: utf-8 -*-
"""诊断成品 PNG: 把每帧『不透明浅色(alpha>=250 & mn>=210 & sat<=40)』连通块列出,
   报告 数量/面积/y 占比(0=顶 1=底)/暖冷(皮肤 R>G>B -> B-R<0 暖; 白/蓝白 B-R>=0)。
   重点 drag_02/03 special_01: 看残留是否在腿部区(回归风险)还是上半身(可安全清)。"""
import numpy as np
from PIL import Image
from scipy import ndimage
import os

OUT = r"C:\Users\a3564\WorkBuddy\2026-08-25-04-20-35\token-stats\assets\pet_v2"
GROUPS = ["idle", "sleep", "drag", "click", "special"]


def analyze(fn):
    im = np.asarray(Image.open(fn).convert("RGBA")).astype(np.int16)
    a = im[..., 3]
    rgb = im[..., :3]
    mn = rgb.min(axis=2)
    mx = rgb.max(axis=2)
    sat = mx - mn
    light = (a >= 250) & (mn >= 210) & (sat <= 40)
    if not light.any():
        return None, []
    lbl, n = ndimage.label(light, structure=np.ones((3, 3), int))
    comps = []
    for j in range(1, n + 1):
        m = lbl == j
        ys, xs = np.where(m)
        h = im.shape[0]
        yf = float(ys.mean()) / max(1, h)
        mean = rgb[m].mean(axis=0)
        br = int(mean[2] - mean[0])          # B-R: 暖(皮肤)负, 冷(白/蓝白)非负
        comps.append(dict(px=int(m.sum()), yf=round(yf, 2),
                          color=tuple(int(v) for v in mean),
                          br=br, warm=(br < -4)))
    comps.sort(key=lambda c: -c["px"])
    return dict(n=n, total=int(light.sum()), h=h), comps


for g in GROUPS:
    od = os.path.join(OUT, g)
    for fn in sorted(os.listdir(od)):
        if not fn.endswith(".png"):
            continue
        stat, comps = analyze(os.path.join(od, fn))
        if stat is None:
            print(f"{fn:>12}  无浅色不透明块")
            continue
        big = [c for c in comps if c["px"] >= 60]
        print(f"\n{fn:>12}  浅色不透明块 {stat['n']} 个, ≥60px 的 {len(big)} 个, 总 {stat['total']}px")
        for c in big[:12]:
            tag = "暖(皮肤?)" if c["warm"] else "冷(白/蓝白)"
            print(f"    px={c['px']:>5}  yf={c['yf']:.2f}  mean={c['color']}  B-R={c['br']:>4}  {tag}")
