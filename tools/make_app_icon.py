# -*- coding: utf-8 -*-
"""从浅浅猫的原始图标 PNG 生成程序用图标 (任务栏 / 托盘 统一)。

源: C:\\Users\\a3564\\Downloads\\Gemini_Generated_Image_ht12ymht12ymht12.png
     (2048x2048 RGBA 透明底, **满幅圆角方形图标** —— 内容几乎占满画布, 只在圆角处透明)

产出:
  assets/app_icon.png   1024x1024 (运行时备用的 PNG 形态)
  assets/app_icon.ico   多尺寸 (16,24,32,48,64,128,256) —— 任务栏/托盘通用

两种源图自适应:
  · 满幅型(内容占画布 >=92%): **不裁剪** —— 图标自带圆角与留白, 裁了反而破坏设计。
  · 带透明边距型(内容明显居中偏小): 裁到内容 + 4% 边距, 再补成正方形, 避免图标显得过小。
各尺寸用 LANCZOS 重采样; <=32 额外轻微锐化, 免得小尺寸糊成一团。
"""
import os

from PIL import Image, ImageFilter

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = r"C:\Users\a3564\Downloads\Gemini_Generated_Image_ht12ymht12ymht12.png"
OUT_PNG = os.path.join(BASE, "assets", "app_icon.png")
OUT_ICO = os.path.join(BASE, "assets", "app_icon.ico")
SIZES = [16, 24, 32, 48, 64, 128, 256]
FULL_BLEED = 0.92        # 内容占画布比例 >= 此值 -> 视为"满幅图标", 不裁边


def build_canvas(im):
    """返回一张正方形画布 (必要时裁内容+补边, 满幅图则原样返回)。"""
    al = im.split()[3]
    bb = al.getbbox()
    if not bb:
        return im
    cw, ch = bb[2] - bb[0], bb[3] - bb[1]
    fill = max(cw / im.width, ch / im.height)
    if fill >= FULL_BLEED:
        print(f"  满幅图标(内容占画布 {fill*100:.0f}%) -> 不裁剪, 直接按画布缩放")
        return im
    pad = int(max(cw, ch) * 0.04)
    bb = (max(0, bb[0] - pad), max(0, bb[1] - pad),
          min(im.width, bb[2] + pad), min(im.height, bb[3] + pad))
    im = im.crop(bb)
    print(f"  带边距图标 -> 裁到内容+4%边距 {im.width}x{im.height}")
    side = max(im.width, im.height)
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    canvas.paste(im, ((side - im.width) // 2, (side - im.height) // 2), im)
    return canvas


def main():
    im = Image.open(SRC).convert("RGBA")
    print(f"源 {SRC}")
    print(f"    {im.width}x{im.height} {im.mode}")
    canvas = build_canvas(im)

    canvas.resize((1024, 1024), Image.LANCZOS).save(OUT_PNG)
    print(f"  -> {OUT_PNG}")

    frames = []
    for s in SIZES:
        f = canvas.resize((s, s), Image.LANCZOS)
        if s <= 32:                       # 小尺寸轻微锐化, 提升辨识度
            f = f.filter(ImageFilter.UnsharpMask(radius=1.0, percent=60, threshold=0))
        frames.append(f)
    frames[-1].save(OUT_ICO, format="ICO",
                    sizes=[(s, s) for s in SIZES], append_images=frames[:-1])
    print(f"  -> {OUT_ICO}  ({os.path.getsize(OUT_ICO)/1024:.0f} KB)")

    # 自检: 确认 ICO 里真的有多尺寸帧
    chk = Image.open(OUT_ICO)
    got = sorted(getattr(chk, "ico", None).sizes()) if getattr(chk, "ico", None) else []
    print(f"  ICO 内含尺寸: {got}  {'OK' if len(got) == len(SIZES) else '★ 帧数不足'}")


if __name__ == "__main__":
    main()
