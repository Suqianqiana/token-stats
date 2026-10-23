# -*- coding: utf-8 -*-
"""2026-10-23: 新批次饱和度优化样张 (原样 vs B方案对比, 给浅浅猫确认)。

口径/公式与 docs/素材饱和度优化.md 完全一致:
  S' = S * k ; V' = V + a*V*(1-V)  (平滑提亮, 不动 alpha)
候选档位: k=1.06 + lift=0.10 (按本次量化差距 -6% S / -7.2 V 线性折算, 比 09-17 的 1.20/0.16 温和)
输出: docs/pet_saturation_compare_20261023.png
"""
import io
import json
import os
import sys

sys.dont_write_bytecode = True
import numpy as np
from PIL import Image, ImageDraw, ImageFont

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NEW = os.path.join(BASE, "assets", "pet_new_20261023")
SEL = os.path.join(BASE, "docs", "pet_selection_20261023.json")
OUT = os.path.join(BASE, "docs", "pet_saturation_compare_20261023.png")

CANDIDATES = ["G01_01", "G09_01", "G10_05"]     # idle / sleep / click 三个代表
K, LIFT = 1.06, 0.10


def enhance_array(a, k, lift):
    """RGBA float 数组 -> 只改 S/V, alpha 原样 (与 09-17 同公式)"""
    im = Image.fromarray(a, "RGBA")
    hsv = np.asarray(im.convert("HSV")).astype(np.float64)
    H, S, V = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    S2 = np.clip(S * k, 0, 255)
    V2 = np.clip(V + lift * V * (1.0 - V / 255.0), 0, 255)
    out_hsv = np.dstack([H, S2, V2]).astype(np.uint8)
    out = np.asarray(Image.fromarray(out_hsv, "HSV").convert("RGBA")).copy()
    out[..., 3] = a[..., 3]
    return out


def hair_color(img_arr, a_min=128, top=0.45):
    """头发中位色 + 过曝率 (与 analyze 口径一致)"""
    a = img_arr[..., 3]
    ys, xs = np.where(a > a_min)
    if not len(ys):
        return None
    y0, y1 = int(ys.min()), int(ys.max())
    ycut = int(y0 + (y1 - y0 + 1) * top)
    hsv = np.asarray(Image.fromarray(img_arr, "RGBA").convert("HSV")).astype(np.int16)
    H, S, V = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    rowmask = np.arange(a.shape[0])[:, None] < ycut
    m = (a > a_min) & rowmask & (H >= 130) & (H <= 185) & (S > 20) & (V > 20)
    if m.sum() < 500:
        return None
    med = np.median(img_arr[..., :3][m], axis=0)
    over = float(((a > a_min) & (img_arr[..., :3].max(-1) >= 254)).sum()) / max(1, (a > a_min).sum())
    return med, over


def font(sz):
    for p in (r"C:/Windows/Fonts/msyh.ttc", r"C:/Windows/Fonts/msyhbd.ttc", r"C:/Windows/Fonts/arial.ttf"):
        try:
            return ImageFont.truetype(p, sz)
        except OSError:
            pass
    return ImageFont.load_default()


def composite_on(arr, bg):
    im = Image.fromarray(arr, "RGBA")
    b = Image.new("RGBA", im.size, bg)
    b.alpha_composite(im)
    return b.convert("RGB")


def main():
    d = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    fT, fS, fM = font(22), font(15), font(13)
    CW, CH = 250, 300          # 完整帧格子
    HEAD = 110                  # 头部放大高度
    PAD = 16
    blocks = []
    for fid in CANDIDATES:
        src = os.path.join(NEW, fid + ".png")
        if not os.path.exists(src):
            continue
        a = np.asarray(Image.open(src).convert("RGBA"))
        b = enhance_array(a, K, LIFT)
        blocks.append((fid, a, b))

    W = PAD * 2 + CW * 2 + 24
    H = 70 + len(blocks) * (CH + HEAD + 78) + PAD
    sheet = Image.new("RGB", (W, H), (250, 250, 252))
    d = ImageDraw.Draw(sheet)
    d.text((PAD, 14), "新素材饱和度优化样张 · 2026-10-23 · k=%.2f + 平滑提亮 lift=%.2f" % (K, LIFT),
           font=fT, fill=(20, 24, 32))
    d.text((PAD, 44), "左=原样  右=优化后  ｜  下面两行: 头部放大对比 + 头发中位色块（与过曝率）",
           font=fM, fill=(110, 118, 132))
    y = 76
    for fid, a, b in blocks:
        ca, cb = hair_color(a), hair_color(b)
        # 完整帧
        fa = composite_on(a, (255, 255, 255)).resize((CW, CH), Image.LANCZOS)
        fb = composite_on(b, (255, 255, 255)).resize((CW, CH), Image.LANCZOS)
        sheet.paste(fa, (PAD, y))
        sheet.paste(fb, (PAD + CW + 24, y))
        d.rectangle([PAD, y, PAD + CW, y + CH], outline=(150, 150, 160), width=1)
        d.rectangle([PAD + CW + 24, y, PAD + 24 + 2 * CW, y + CH], outline=(80, 120, 240), width=2)
        d.text((PAD, y + CH + 6), "原样", font=fS, fill=(90, 95, 105))
        d.text((PAD + CW + 24, y + CH + 6), "优化后", font=fS, fill=(60, 100, 220))
        # 头部放大 (取顶部 45% 区域, 等比放大)
        ys, xs = np.where(a[..., 3] > 8)
        hh = int(ys.max() - ys.min() + 1)
        hcut = int(ys.min() + hh * 0.45)
        ha = composite_on(a[:hcut], (255, 255, 255))
        hb = composite_on(b[:hcut], (255, 255, 255))
        ra = HEAD / ha.height
        ha = ha.resize((int(ha.width * ra), HEAD), Image.LANCZOS)
        rb = HEAD / hb.height
        hb = hb.resize((int(hb.width * rb), HEAD), Image.LANCZOS)
        sheet.paste(ha, (PAD, y + CH + 28))
        sheet.paste(hb, (PAD + CW + 24, y + CH + 28))
        d.rectangle([PAD, y + CH + 28, PAD + ha.width, y + CH + 28 + HEAD], outline=(150, 150, 160), width=1)
        d.rectangle([PAD + CW + 24, y + CH + 28, PAD + CW + 24 + hb.width, y + CH + 28 + HEAD],
                    outline=(80, 120, 240), width=2)
        # 头发色块 + 数值
        bx = PAD + 24 + 2 * CW + 10
        if ca and cb:
            for i, (tag, cc) in enumerate((("原", ca), ("优", cb))):
                med, over = cc
                yy = y + 10 + i * 96
                d.rectangle([bx, yy, bx + 60, yy + 44], fill=tuple(int(round(x)) for x in med))
                d.rectangle([bx, yy, bx + 60, yy + 44], outline=(120, 120, 130), width=1)
                d.text((bx, yy + 48), "%s #%02X%02X%02X" % (tag, *[int(round(x)) for x in med]),
                       font=fM, fill=(60, 66, 76))
                d.text((bx, yy + 66), "过曝 %.2f%%" % (over * 100), font=fM, fill=(110, 118, 132))
        d.text((PAD, y + CH + 28 + HEAD + 6), fid, font=fM, fill=(140, 148, 162))
        y += CH + HEAD + 78
    sheet.save(OUT)
    print("saved:", OUT, sheet.size)


if __name__ == "__main__":
    main()
