# -*- coding: utf-8 -*-
"""生成 pet_v3r 全量帧检视页（洋红底 + 真 alpha 合成），按场景分组标注。

用法: python tools/review_pet_v3r.py
输出: docs/pet_v3r_review.png
"""
import glob
import os

from PIL import Image, ImageDraw, ImageFont

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(BASE, "docs", "pet_v3r_review.png")
SCENES = ["idle", "sleep", "wake", "drag", "click", "sidle", "pat"]
CW, CH, LAB, PAD = 160, 225, 20, 8


def font(size):
    for p in (r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\arial.ttf"):
        try:
            return ImageFont.truetype(p, size)
        except OSError:
            pass
    return ImageFont.load_default()


def main():
    rows = []
    for sc in SCENES:
        fs = sorted(glob.glob(os.path.join(BASE, "assets", "pet_v3r", sc, "*.png")))
        if fs:
            rows.append((sc, fs))
    total = sum(len(f) for _, f in rows)
    cols = max(len(f) for _, f in rows)
    W = PAD + cols * (CW + PAD)
    H = 30 + sum(CH + LAB + PAD for _ in rows) + PAD
    sheet = Image.new("RGBA", (W, H), (255, 0, 255, 255))
    d = ImageDraw.Draw(sheet)
    fl, fh = font(13), font(18)
    d.text((PAD, 6), "pet_v3r 全量 %d 帧（按场景分组; 场景内为实际播放池）" % total,
           font=fh, fill=(0, 0, 0, 255))
    y = 30
    for sc, fs in rows:
        for i, p in enumerate(fs):
            x = PAD + i * (CW + PAD)
            im = Image.open(p).convert("RGBA")
            s = min(CW / im.width, CH / im.height)
            im2 = im.resize((max(1, int(im.width * s)), max(1, int(im.height * s))),
                            Image.LANCZOS)
            sheet.alpha_composite(im2, (x + (CW - im2.width) // 2,
                                        y + (CH - im2.height) // 2))
            d.rectangle([x, y, x + CW, y + CH], outline=(80, 0, 80, 255))
            d.text((x + 3, y + CH + 2), os.path.basename(p)[:-4], font=fl, fill=(0, 0, 0, 255))
        d.text((PAD + 2, y - 16), "%s (%d)" % (sc, len(fs)), font=fl, fill=(0, 0, 90, 255))
        y += CH + LAB + PAD
    sheet.convert("RGB").save(OUT, optimize=True)
    print("已生成:", OUT, sheet.size, "帧数:", total)


if __name__ == "__main__":
    main()
