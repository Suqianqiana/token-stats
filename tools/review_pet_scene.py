# -*- coding: utf-8 -*-
"""单场景放大检视页: 把某个场景的所有帧按序号拼成一张大图(便于逐帧指认/核对)。

用法:
    python tools/review_pet_scene.py click
    python tools/review_pet_scene.py idle --cols 4
输出: docs/pet_<scene>_review.png

为什么单独做一页: 汇总页(47 帧)里每格只有 170px 宽, 帧数一多就难分辨细节;
指认"第几张要换"时容易被缩略图误导。
"""
import sys
import os
import io
import json
import glob

from PIL import Image, ImageDraw, ImageFont

SCENES = ["idle", "sleep", "wake", "drag", "click", "sidle", "pat"]


def font(size):
    for p in (r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\arial.ttf"):
        try:
            return ImageFont.truetype(p, size)
        except OSError:
            pass
    return ImageFont.load_default()


def source_labels(scene):
    """反查 installed_map.json: {现文件名: 原始素材编号}, 便于追溯"这张原本是 A/B 哪张"。

    退役 + 重排编号后, 光看 click_03 已经不知道它来自哪批素材了 —— 标签上带源编号可避免歧义。
    """
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    mp_file = os.path.join(base, "assets", "pet_v3_add", "installed_map.json")
    out = {}
    try:
        with io.open(mp_file, encoding="utf-8") as fp:
            mp = json.load(fp)
        for orig, path in (mp.get("map") or {}).items():
            if isinstance(path, str) and path.startswith(scene + "/"):
                out[os.path.basename(path)] = orig
    except Exception:
        pass
    return out


def build(scene, cols=None):
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    files = sorted(glob.glob(os.path.join(base, "assets", "pet_v3r", scene, "*.png")))
    if not files:
        print("没有帧:", scene)
        return None
    if cols is None:
        cols = 4 if len(files) <= 12 else (4 if len(files) > 8 else len(files))
    cw, ch, lab, pad = 250, 320, 26, 12
    rows = (len(files) + cols - 1) // cols
    w = cols * (cw + pad) + pad
    h = rows * (ch + lab + pad) + pad + 34
    sheet = Image.new("RGBA", (w, h), (255, 0, 255, 255))
    d = ImageDraw.Draw(sheet)
    f_lab, f_title = font(18), font(20)
    d.text((pad, 7), "%s 场景共 %d 帧 — 放大检视(编号即文件名)" % (scene, len(files)),
           font=f_title, fill=(0, 0, 0, 255))
    src = source_labels(scene)
    for i, p in enumerate(files):
        r, c = divmod(i, cols)
        x = pad + c * (cw + pad)
        y = 34 + pad + r * (ch + lab + pad)
        im = Image.open(p).convert("RGBA")
        s = min(cw / im.width, ch / im.height)
        im2 = im.resize((max(1, int(im.width * s)), max(1, int(im.height * s))), Image.LANCZOS)
        sheet.alpha_composite(im2, (x + (cw - im2.width) // 2, y + (ch - im2.height) // 2))
        d.rectangle([x, y, x + cw, y + ch], outline=(90, 0, 90, 255), width=1)
        name = os.path.basename(p)[:-4]
        tag = src.get(os.path.basename(p))
        d.text((x + 4, y + ch + 3), name + ("  ←%s" % tag if tag else "  (原有)"),
               font=f_lab, fill=(0, 0, 0, 255))
    out = os.path.join(base, "docs", "pet_%s_review.png" % scene)
    sheet.convert("RGB").save(out, optimize=True)
    print("已生成:", out, sheet.size, "帧数:", len(files))
    return out


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    cols = None
    for a in sys.argv[1:]:
        if a.startswith("--cols"):
            cols = int(a.split("=")[1]) if "=" in a else None
    scene = args[0] if args else "click"
    build(scene, cols)
