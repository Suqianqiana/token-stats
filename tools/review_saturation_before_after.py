# -*- coding: utf-8 -*-
"""饱和度全量替换的「前后对比图」: 上半 = 替换前（备份原图）, 下半 = 替换后（当前生效）。

用法:
    python tools/review_saturation_before_after.py
输出: docs/pet_saturation_before_after.png

数据来源: `assets/pet_v3r/_saturation.json` 里的 `backup_dir` 与 `frames` ——
所以这张图**只对真正被替换过的那批帧**成立, 不依赖"我猜哪些是新素材"。
"""
import io
import json
import os
import sys

from PIL import Image, ImageDraw, ImageFont

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "tools"))
import analyze_pet_saturation as A  # noqa: E402


def font(size, bold=False):
    for p in (r"C:\Windows\Fonts\msyhbd.ttc" if bold else r"C:\Windows\Fonts\msyh.ttc",
              r"C:\Windows\Fonts\arial.ttf"):
        try:
            return ImageFont.truetype(p, size)
        except OSError:
            pass
    return ImageFont.load_default()


def main():
    mark_path = os.path.join(A.MAIN_DIR, "_saturation.json")
    if not os.path.exists(mark_path):
        print("没有找到 _saturation.json → 说明还没做过饱和度替换, 无需出对比图")
        return
    with io.open(mark_path, encoding="utf-8") as f:
        mark = json.load(f)
    bk = os.path.join(BASE, mark["backup_dir"])
    rels = mark["frames"]
    if not os.path.isdir(bk):
        print("备份目录不存在:", bk)
        return

    cw, ch, cols, pad = 168, 224, 8, 8
    rows = (len(rels) + cols - 1) // cols
    block_h = rows * (ch + 22 + pad)
    w = pad + cols * (cw + pad)
    h = 42 + block_h + 52 + block_h + 16
    sheet = Image.new("RGBA", (w, h), (255, 0, 255, 255))
    d = ImageDraw.Draw(sheet)
    d.text((pad, 8), "饱和度全量替换 前后对比 · %d 帧新素材（洋红=透明底）  k=%s lift=%s"
           % (len(rels), mark.get("k"), mark.get("lift")), font=font(21, True), fill=(0, 0, 0, 255))
    f_title, f_small = font(17, True), font(12)

    def block(y0, title, root):
        d.text((pad, y0 - 20), title, font=f_title, fill=(0, 0, 0, 255))
        for i, rel in enumerate(rels):
            r, c = divmod(i, cols)
            x = pad + c * (cw + pad)
            y = y0 + r * (ch + 22 + pad)
            p = os.path.join(root, *rel.split("/"))
            if not os.path.exists(p):
                d.text((x + 2, y + 10), "缺失\n%s" % rel, font=f_small, fill=(190, 0, 0, 255))
                continue
            im = Image.open(p).convert("RGBA")
            s = min(cw / im.width, ch / im.height)
            im2 = im.resize((max(1, int(im.width * s)), max(1, int(im.height * s))), Image.LANCZOS)
            sheet.alpha_composite(im2, (x + (cw - im2.width) // 2, y + (ch - im2.height) // 2))
            d.rectangle([x, y, x + cw, y + ch], outline=(90, 0, 90, 255))
            d.text((x + 2, y + ch + 2), os.path.basename(rel)[:-4], font=f_small, fill=(0, 0, 0, 255))

    block(42, "替换前（备份原图）", bk)
    block(42 + block_h + 52, "替换后（当前生效）", A.MAIN_DIR)

    out = os.path.join(BASE, "docs", "pet_saturation_before_after.png")
    sheet.convert("RGB").save(out, optimize=True)
    print("已生成:", out, sheet.size, "帧数:", len(rels))


if __name__ == "__main__":
    main()
