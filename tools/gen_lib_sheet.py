# -*- coding: utf-8 -*-
"""第101轮: 生成"主题素材总览图"（README 用），样式与 docs/_v5_installed101.png 一致。

版式: 浅灰底 + 按场景分行 + 每格左上角标帧名 + 帧图等比缩放(底部对齐/水平居中)。
用法:
    python -B tools/gen_lib_sheet.py pet_v4 --cols 6
    python -B tools/gen_lib_sheet.py pet_v3r --cols 10 --scenes idle,sleep,wake,drag,click --out docs/assets/previews/pet_v3_sheet_1.png
    python -B tools/gen_lib_sheet.py pet_v3r --cols 10 --scenes sidle,pat --out docs/assets/previews/pet_v3_sheet_2.png
"""
import os
import sys

sys.dont_write_bytecode = True
from PIL import Image, ImageDraw, ImageFont

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCENES = ("idle", "sleep", "wake", "drag", "click", "sidle", "pat")
CELL_W, CELL_H = 112, 150
BG = (236, 238, 243)
INK = (60, 66, 78)
PAD_TOP = 8


def load_font():
    for p in (r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\simhei.ttf"):
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, 12)
            except OSError:
                break
    return ImageFont.load_default()


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return 1
    lib = args[0]
    cols = 8
    scenes = None
    out = None
    flow = "--flow" in args          # 流式: 所有帧连续排满(场景帧数少时更紧凑)
    for a in args[1:]:
        if a.startswith("--cols="):
            cols = int(a.split("=", 1)[1])
        elif a.startswith("--scenes="):
            scenes = [s.strip() for s in a.split("=", 1)[1].split(",") if s.strip()]
        elif a.startswith("--out="):
            out = a.split("=", 1)[1]
    lib_dir = os.path.join(BASE, "assets", lib)
    if not os.path.isdir(lib_dir):
        print("!! 没有这个库:", lib_dir)
        return 1
    if scenes is None:
        scenes = [s for s in SCENES if os.path.isdir(os.path.join(lib_dir, s))]
    out = out or os.path.join(BASE, "docs", "assets", "previews", "%s_sheet.png" % lib)

    # 逐场景收集帧
    plan = []          # [(scene, [files])]
    total = 0
    for sc in scenes:
        d = os.path.join(lib_dir, sc)
        if not os.path.isdir(d):
            continue
        fs = sorted(f for f in os.listdir(d) if f.lower().endswith(".png"))
        if fs:
            plan.append((sc, fs))
            total += len(fs)
    if not total:
        print("!! 库是空的:", lib_dir)
        return 1

    if flow:
        rows = (total + cols - 1) // cols
    else:
        rows = sum((len(fs) + cols - 1) // cols for _sc, fs in plan)
    W = cols * CELL_W
    H = rows * CELL_H + PAD_TOP * 2
    sheet = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(sheet)
    font = load_font()

    y = PAD_TOP
    if flow:
        # 流式: 所有帧按场景顺序连续排, 每行 cols 个 —— 场景帧数很少时(如 V4 的
        # sleep/wake/drag/sidle 各 1 帧)不会出现大片空白。
        allf = [(sc, f) for sc, fs in plan for f in fs]
        for i, (sc, f) in enumerate(allf):
            c, r = i % cols, i // cols
            x = c * CELL_W
            yy = PAD_TOP + r * CELL_H
            im = Image.open(os.path.join(lib_dir, sc, f)).convert("RGBA")
            s = min((CELL_W - 6) / im.width, (CELL_H - 22) / im.height)
            im = im.resize((max(1, int(im.width * s)), max(1, int(im.height * s))), Image.LANCZOS)
            sheet.paste(im, (x + (CELL_W - im.width) // 2, yy + CELL_H - 4 - im.height), im)
            d.text((x + 3, yy + 3), f[:-4], fill=INK, font=font)
    else:
      for sc, fs in plan:
        for i, f in enumerate(fs):
            c, r = i % cols, i // cols
            x = c * CELL_W
            yy = y + r * CELL_H
            im = Image.open(os.path.join(lib_dir, sc, f)).convert("RGBA")
            s = min((CELL_W - 6) / im.width, (CELL_H - 22) / im.height)
            im = im.resize((max(1, int(im.width * s)), max(1, int(im.height * s))), Image.LANCZOS)
            # 底部对齐 + 水平居中(与桌宠绘制口径一致)
            sheet.paste(im, (x + (CELL_W - im.width) // 2, yy + CELL_H - 4 - im.height), im)
            d.text((x + 3, yy + 3), f[:-4], fill=INK, font=font)
        y += ((len(fs) + cols - 1) // cols) * CELL_H

    os.makedirs(os.path.dirname(out), exist_ok=True)
    sheet.save(out)
    print("-> %s  %dx%d  %d 帧  %d 行  cols=%d  场景=%s"
          % (os.path.relpath(out, BASE), sheet.width, sheet.height, total, rows, cols,
             ",".join(sc for sc, _ in plan)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
