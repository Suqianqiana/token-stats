# -*- coding: utf-8 -*-
"""V5 素材源「蓝色鲸鱼少女表情贴纸包.png」连通域切分 + 标注预览 (只读源文件, 输出 docs/)。
用法: python -B tools/split_v5_pack.py
"""
import sys
sys.dont_write_bytecode = True
import os
import json
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

SRC = r"C:\Users\a3564\Downloads\蓝色鲸鱼少女表情贴纸包.png"
OUT_DIR = r"C:\Users\a3564\WorkBuddy\2026-08-25-04-20-35\token-stats\docs"
PREVIEW = os.path.join(OUT_DIR, "_v5_pack_preview.png")


def main():
    im = Image.open(SRC).convert("RGBA")
    arr = np.asarray(im)
    a = arr[:, :, 3]
    m = a > 16
    lab, n = ndimage.label(m, structure=np.ones((3, 3)))
    print("连通域总数:", n)
    objs = ndimage.find_objects(lab)
    items = []
    for i, sl in enumerate(objs, start=1):
        if sl is None:
            continue
        ys, xs = sl
        area = int((lab[sl] == i).sum())
        w = xs.stop - xs.start
        h = ys.stop - ys.start
        items.append({"id": i, "x0": int(xs.start), "y0": int(ys.start),
                      "x1": int(xs.stop), "y1": int(ys.stop),
                      "w": int(w), "h": int(h), "area": area})
    items.sort(key=lambda d: (round(d["y0"] / 60), d["x0"]))
    big = [d for d in items if d["area"] >= 3000]
    print("面积>=3000 的域:", len(big))
    for d in big:
        print("  #%-3d (%4d,%4d)-(%4d,%4d)  %4dx%-4d area=%d"
              % (d["id"], d["x0"], d["y0"], d["x1"], d["y1"], d["w"], d["h"], d["area"]))
    print("小域(面积<3000)个数:", len(items) - len(big))

    # 标注预览
    pv = im.convert("RGB").copy()
    dr = ImageDraw.Draw(pv)
    for k, d in enumerate(big, start=1):
        dr.rectangle([d["x0"], d["y0"], d["x1"] - 1, d["y1"] - 1], outline=(255, 0, 0), width=3)
        dr.text((d["x0"] + 6, d["y0"] + 6), "#%d" % k, fill=(255, 255, 0))
    os.makedirs(OUT_DIR, exist_ok=True)
    pv.save(PREVIEW)
    print("预览 ->", PREVIEW)
    with open(os.path.join(OUT_DIR, "_v5_pack_parts.json"), "w", encoding="utf-8") as f:
        json.dump(big, f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
