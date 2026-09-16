# -*- coding: utf-8 -*-
"""桌宠帧「饱和度提升」——实验版(不改原文件)。

为什么不用 PIL 的 ImageEnhance.Color / 8bit HSV 往返:
  PIL 的 HSV 是 8bit 量化, RGB→HSV→RGB 往返本身就有 ±1~2 的误差; 反复试参数会累积。
  这里用 numpy 浮点自己做 RGB↔HSV, 只改 S(保持 H/V), alpha 通道原样搬过去。

用法:
    python tools/enhance_pet_saturation.py --k 1.25 idle/idle_06.png click/click_05.png
    python tools/enhance_pet_saturation.py --ks 1.15,1.25,1.35 idle/idle_06.png
    python tools/enhance_pet_saturation.py --k 1.25 --v 1.04 <帧...>     # 顺带轻微提亮

输出: assets/pet_v3_sat/k<增益>/<场景>/<文件名>   (实验区, 原素材一个字节都不动)
"""
import io
import json
import os
import sys

import numpy as np
from PIL import Image

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAIN = os.path.join(BASE, "assets", "pet_v3r")
EXP = os.path.join(BASE, "assets", "pet_v3_sat")


def rgb_to_hsv(rgb):
    """rgb: (..., 3) float 0~1 → (h 0~360, s 0~1, v 0~1)"""
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    mx = rgb.max(-1)
    mn = rgb.min(-1)
    d = mx - mn
    h = np.zeros_like(mx)
    nz = d > 1e-12
    for idx, (chan, off) in enumerate(((r, 0.0), (g, 2.0), (b, 4.0))):
        m = nz & (mx == chan)
        if idx == 0:      # r 最大: (g-b)/d
            h[m] = ((g - b)[m] / d[m]) % 6.0
        elif idx == 1:    # g 最大: (b-r)/d + 2
            h[m] = ((b - r)[m] / d[m]) + 2.0
        else:             # b 最大: (r-g)/d + 4
            h[m] = ((r - g)[m] / d[m]) + 4.0
    h = (h * 60.0) % 360.0
    s = np.where(mx > 1e-12, d / np.maximum(mx, 1e-12), 0.0)
    return h, s, mx


def hsv_to_rgb(h, s, v):
    c = v * s
    hp = (h / 60.0) % 6.0
    x = c * (1.0 - np.abs(hp % 2.0 - 1.0))
    z = np.zeros_like(hp)
    conds = [hp < 1, hp < 2, hp < 3, hp < 4, hp < 5]
    r = np.select(conds, [c, x, z, z, x], default=c)
    g = np.select(conds, [x, c, c, x, z], default=z)
    b = np.select(conds, [z, z, x, c, c], default=x)
    m = v - c
    return np.clip(np.stack([r + m, g + m, b + m], -1), 0.0, 1.0)


def enhance_array(a, k=1.25, kv=1.0, lift=0.0):
    """a: uint8 (H,W,4) RGBA → 只改 RGB 的饱和度/明度, alpha 原样。

    lift: 平滑提亮强度 a（0=不提亮）。用 v' = v + a·v·(1-v) 这条 S 曲线:
      · 中间调(v≈0.5)提亮最多, 最大约 a/4;
      · 高光(v→1)与极暗部(v→0)几乎不动 → **不会把 245~253 的像素推成过曝**
        (线性 ×1.05 会把它们 100% 推爆, 实测溢出率 2.3%→16.3%, 白围裙会丢褶皱细节)。
    """
    rgb = a[..., :3].astype(np.float64) / 255.0
    h, s, v = rgb_to_hsv(rgb)
    s = np.clip(s * k, 0.0, 1.0)
    if lift:
        v = np.clip(v + lift * v * (1.0 - v), 0.0, 1.0)
    elif kv != 1.0:
        v = np.clip(v * kv, 0.0, 1.0)
    out = np.empty_like(a)
    out[..., :3] = np.rint(hsv_to_rgb(h, s, v) * 255.0).astype(np.uint8)
    out[..., 3] = a[..., 3]                      # alpha 一字不动
    return out


def enhance_file(rel, k, kv=1.0, out_root=None, lift=0.0):
    src = os.path.join(MAIN, *rel.split("/"))
    if not os.path.exists(src):
        print("  跳过(不存在):", rel)
        return None
    a = np.asarray(Image.open(src).convert("RGBA"))
    out_a = enhance_array(a, k, kv, lift)
    sc, fn = rel.split("/", 1)
    tag = "k%g" % k
    if lift:
        tag += "_lift%g" % lift
    elif kv != 1.0:
        tag += "_v%g" % kv
    d = os.path.join(out_root or EXP, tag, sc)
    os.makedirs(d, exist_ok=True)
    dst = os.path.join(d, fn)
    Image.fromarray(out_a, "RGBA").save(dst)
    return dst


def main():
    argv = sys.argv[1:]
    k = 1.25
    kv = 1.0
    lift = 0.0
    rels = []
    for a in argv:
        if a.startswith("--ks="):
            for x in a.split("=", 1)[1].split(","):
                rels.append(("__K__", float(x)))
        elif a.startswith("--k="):
            k = float(a.split("=", 1)[1])
        elif a.startswith("--v="):
            kv = float(a.split("=", 1)[1])
        elif a.startswith("--lift="):
            lift = float(a.split("=", 1)[1])
        elif not a.startswith("--"):
            rels.append(a)
    if not rels:
        print(__doc__)
        return
    ks = [x[1] for x in rels if x[0] == "__K__"] or [k]
    frames = [x for x in rels if x[0] != "__K__"]
    for kk in ks:
        print("k=%g%s" % (kk, (" lift=%g" % lift) if lift else ("" if kv == 1.0 else " v=%g" % kv)))
        for rel in frames:
            dst = enhance_file(rel, kk, kv, lift=lift)
            if dst:
                print("  %s → %s" % (rel, os.path.relpath(dst, BASE)))


if __name__ == "__main__":
    main()
