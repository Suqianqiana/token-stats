# -*- coding: utf-8 -*-
"""饱和度对比图: 原 V3 参照 vs 待处理帧的各方案（完整图 + 头部放大 + 头发中位色 + 过曝率）。

用法:
    python tools/review_pet_saturation.py --frame=idle/idle_06.png --ref=idle/idle_01.png \
        --out=docs/pet_saturation_compare.png

列含义（6 列）:
    1 原 V3 参照      —— 目标观感（原有素材）
    2 本帧原样        —— 问题现场（新素材偏淡）
    3 A 只提饱和度     k=1.20，安全但明度仍偏低
    4 B 提饱和+平滑提亮 —— 推荐：S/V 都对齐, 且不增加过曝
    5 k=1.35 过头      —— 说明增益上限在哪
    6 线性提亮 5%      —— 反例：会把 245~253 的像素 100% 推爆（白围裙丢细节）

"头部放大 + 头发中位色块 + 过曝率" 三件套是浅猫要求的判断依据（"通过对比头发处的颜色"），
整帧缩略图上看不出 5% 的饱和度差。
"""
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "tools"))
from analyze_pet_saturation import hair_pixels  # noqa: E402

MAIN = os.path.join(BASE, "assets", "pet_v3r")
EXP = os.path.join(BASE, "assets", "pet_v3_sat")


def font(size, bold=False):
    for p in (r"C:\Windows\Fonts\msyhbd.ttc" if bold else r"C:\Windows\Fonts\msyh.ttc",
              r"C:\Windows\Fonts\arial.ttf"):
        try:
            return ImageFont.truetype(p, size)
        except OSError:
            pass
    return ImageFont.load_default()


def head_crop(path):
    im = Image.open(path).convert("RGBA")
    a = np.asarray(im)
    ys, xs = np.where(a[..., 3] > 128)
    if len(ys) == 0:
        return im, (0, 0, 0), 0, 0, 0.0
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    head = im.crop((x0, y0, x1, int(y0 + (y1 - y0) * 0.45)))
    al = a[..., 3] > 128
    over = 100.0 * float((al & (a[..., :3].max(-1) >= 254)).sum()) / max(1, al.sum())
    r = hair_pixels(path)
    if r is None:
        return head, (0, 0, 0), 0, 0, over
    H, S, V, m, hsv = r
    med = tuple(int(v) for v in np.median(a[..., :3][m], axis=0))
    return head, med, float(np.median(S)), float(np.median(V)), over


def build(frame, ref, out):
    sc, fn = frame.split("/")
    cols = [
        ("原 V3 参照\n%s" % os.path.basename(ref), os.path.join(MAIN, *ref.split("/"))),
        ("本帧原样\n%s" % fn, os.path.join(MAIN, sc, fn)),
        ("A 只提饱和度\nk = 1.20", os.path.join(EXP, "k1.2", sc, fn)),
        ("B 提饱和+平滑提亮\n（推荐）k = 1.20", os.path.join(EXP, "k1.2_lift0.16", sc, fn)),
        ("k = 1.35（过头）", os.path.join(EXP, "k1.35", sc, fn)),
        ("线性提亮 5%（反例）", os.path.join(EXP, "k1.2_v1.05", sc, fn)),
    ]
    cw, ch_img, ch_head, pad = 244, 286, 226, 12
    top, y_head = 58, 58 + 286 + 10
    y_txt = y_head + 226 + 6
    w = pad + len(cols) * (cw + pad)
    h = y_txt + 96
    sheet = Image.new("RGBA", (w, h), (255, 0, 255, 255))
    d = ImageDraw.Draw(sheet)
    f_title, f_lab, f_num = font(21, True), font(15, True), font(14)

    d.text((pad, 8), "饱和度提升对比 · %s — 上：完整帧 / 下：头部放大（洋红=透明底）" % frame,
           font=f_title, fill=(0, 0, 0, 255))
    d.text((pad, 34), "判据：头发中位色 & S/V 中位要贴近「原 V3 参照」；同时看高光溢出率不能上升",
           font=f_num, fill=(60, 60, 60, 255))

    for i, (label, path) in enumerate(cols):
        x = pad + i * (cw + pad)
        if not os.path.exists(path):
            d.text((x, top + 10), "缺失:\n%s" % os.path.basename(path), font=f_num, fill=(190, 0, 0, 255))
            continue
        im = Image.open(path).convert("RGBA")
        s = min(cw / im.width, ch_img / im.height)
        im2 = im.resize((max(1, int(im.width * s)), max(1, int(im.height * s))), Image.LANCZOS)
        sheet.alpha_composite(im2, (x + (cw - im2.width) // 2, top + (ch_img - im2.height) // 2))
        d.rectangle([x, top, x + cw, top + ch_img], outline=(90, 0, 90, 255))

        head, med, smed, vmed, over = head_crop(path)
        hs = min(cw / head.width, ch_head / head.height)
        head2 = head.resize((max(1, int(head.width * hs)), max(1, int(head.height * hs))), Image.LANCZOS)
        sheet.alpha_composite(head2, (x + (cw - head2.width) // 2, y_head + (ch_head - head2.height) // 2))
        d.rectangle([x, y_head, x + cw, y_head + ch_head], outline=(90, 0, 90, 255))

        y = y_txt
        for li, line in enumerate(label.split("\n")):
            d.text((x + 2, y), line, font=f_lab if li == 0 else f_num, fill=(0, 0, 0, 255))
            y += 19
        d.rectangle([x + 2, y + 4, x + 62, y + 32], fill=med + (255,), outline=(0, 0, 0, 255))
        d.text((x + 68, y + 5), "#%02X%02X%02X" % med, font=f_num, fill=(0, 0, 0, 255))
        d.text((x + 68, y + 23), "S %.0f  V %.0f  过曝 %.1f%%" % (smed, vmed, over),
               font=f_num, fill=(0, 0, 0, 255))

    sheet.convert("RGB").save(out, optimize=True)
    print("已生成:", out, sheet.size)
    for label, path in cols:
        if os.path.exists(path):
            _, med, smed, vmed, over = head_crop(path)
            print("   %-30s 头发 #%02X%02X%02X  S %5.1f  V %5.1f  过曝 %5.2f%%"
                  % (label.replace("\n", " "), med[0], med[1], med[2], smed, vmed, over))


if __name__ == "__main__":
    args = sys.argv[1:]
    frame, ref, out = "idle/idle_06.png", "idle/idle_01.png", "docs/pet_saturation_compare.png"
    for a in args:
        if a.startswith("--frame="):
            frame = a.split("=", 1)[1]
        elif a.startswith("--ref="):
            ref = a.split("=", 1)[1]
        elif a.startswith("--out="):
            out = a.split("=", 1)[1]
    build(frame, ref, out if os.path.isabs(out) else os.path.join(BASE, out))
