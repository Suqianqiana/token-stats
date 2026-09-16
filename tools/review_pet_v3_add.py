# -*- coding: utf-8 -*-
"""生成 V3 补充素材的洋红底检视页（按真实 alpha 合成, 所见即桌宠所见）。

输出 docs/pet_v3_add_review.png：24 帧（A01..A12 / B01..B12）按编号排列并标注文件名,
另附"原图行优先顺序"提示, 便于浅浅猫核对编号与动作。
"""
import os
from PIL import Image, ImageDraw, ImageFont

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(BASE, "assets", "pet_v3_add")
OUT = os.path.join(BASE, "docs", "pet_v3_add_review.png")

COLS, CELL_W, CELL_H = 8, 210, 340
PAD = 10
LABEL_H = 26


def load_font(size):
    for p in (r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\msyhbd.ttc",
              r"C:\Windows\Fonts\simhei.ttf", r"C:\Windows\Fonts\arial.ttf"):
        try:
            return ImageFont.truetype(p, size)
        except OSError:
            continue
    return ImageFont.load_default()


def main():
    names = ["%s%02d.png" % (p, i) for p in ("A", "B") for i in range(1, 13)]
    rows = (len(names) + COLS - 1) // COLS
    W = COLS * (CELL_W + PAD) + PAD
    H = rows * (CELL_H + LABEL_H + PAD) + PAD + 34
    sheet = Image.new("RGBA", (W, H), (255, 0, 255, 255))     # 洋红底
    d = ImageDraw.Draw(sheet)
    f_lbl = load_font(17)
    f_head = load_font(20)
    d.text((PAD, 8), "V3 补充素材检视 (A=第1张图 / B=第2张图, 编号为行优先: 左→右、上→下)",
           font=f_head, fill=(0, 0, 0, 255))

    for idx, name in enumerate(names):
        r, c = divmod(idx, COLS)
        x = PAD + c * (CELL_W + PAD)
        y = 34 + PAD + r * (CELL_H + LABEL_H + PAD)
        p = os.path.join(SRC, name)
        if not os.path.exists(p):
            d.rectangle([x, y, x + CELL_W, y + CELL_H], outline=(0, 0, 0, 255))
            d.text((x + 4, y + 4), "缺失", font=f_lbl, fill=(0, 0, 0, 255))
            continue
        im = Image.open(p).convert("RGBA")
        s = min(CELL_W / im.width, CELL_H / im.height)
        im2 = im.resize((max(1, int(im.width * s)), max(1, int(im.height * s))), Image.LANCZOS)
        ox = x + (CELL_W - im2.width) // 2
        oy = y + (CELL_H - im2.height) // 2
        sheet.alpha_composite(im2, (ox, oy))          # 真 alpha 合成, 洋红底透出来
        d.rectangle([x, y, x + CELL_W, y + CELL_H], outline=(80, 0, 80, 255))
        d.text((x + 4, y + CELL_H + 3), name[:-4], font=f_lbl, fill=(0, 0, 0, 255))

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    sheet.convert("RGB").save(OUT, optimize=True)
    print("已生成:", OUT, sheet.size)


if __name__ == "__main__":
    main()
