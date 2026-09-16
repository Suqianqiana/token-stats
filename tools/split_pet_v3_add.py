# -*- coding: utf-8 -*-
"""V3 补充素材切分 —— 零抠图 + 连通域切分（不做任何 alpha 修改）。

源（浅浅猫 2026-09-17 提供的两张透明 PNG，RGBA / 四角 alpha=0）:
  图1 = ChatGPT Image 2026年9月17日 03_19_52 (1).png   (1536x1024, 2 行 x 6 列)
  图2 = ChatGPT Image 2026年9月17日 03_19_53 (2).png   (1535x1024, 2 行 x 6 列)
两张图各 12 个角色, 且**各自都是独立连通域**（宽度比 0.90~1.14, 无粘连）→ 连通域切分安全。

为什么不用竖线切: 图1 第 2 行有 6 个角色却只有 4 个"干净空隙" → 任何竖线都会裁断角色。

输出: assets/pet_v3_add/
  A01..A12.png（图1, 行优先: 左→右、上→下）
  B01..B12.png（图2, 同上）
  manifest.json（每帧: 源图/裁剪框/尺寸/本体面积/归附装饰数/自检结果）

口径对齐: 输出帧就是"紧贴角色的 bbox", 保留原始 alpha —— 与 assets/pet_v3r/ 现有帧一致
（现有帧 200~365px 宽, 半透明像素 10k~22k, 含轻微光环）。

用法: python tools/split_pet_v3_add.py [--denoise]
      --denoise 额外清掉"离角色 >4px 且 alpha<=8"的像素（默认关闭: 实测这些像素
      100% 是 alpha=1~2, 0.4% 不透明度, 肉眼不可见, 不做无谓改动）
"""
import json
import os
import sys

import numpy as np
from PIL import Image
from scipy import ndimage

S8 = np.ones((3, 3), bool)
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(BASE, "assets", "pet_v3_add")
BG_AREA = 20000        # >= 此面积 = 角色本体
DEC_MIN = 8            # 小件下限
DEC_DIST = 90          # 小件归附本体的最大 bbox 距离
SRC = [
    ("A", r"C:\Users\a3564\Downloads\ChatGPT Image 2026年9月17日 03_19_52 (1).png"),
    ("B", r"C:\Users\a3564\Downloads\ChatGPT Image 2026年9月17日 03_19_53 (2).png"),
]


def bbox_dist(a, b):
    """两个 bbox(y0,y1,x0,x1) 的最短距离(不相交则为欧氏距离)"""
    dy = max(0, max(a[0], b[0]) - min(a[1], b[1]))
    dx = max(0, max(a[2], b[2]) - min(a[3], b[3]))
    return (dy * dy + dx * dx) ** 0.5


def main():
    denoise = "--denoise" in sys.argv
    os.makedirs(OUT, exist_ok=True)
    manifest = {"v": 1, "generated": "2026-09-17", "denoise": denoise, "frames": []}
    print("=" * 74)
    print("V3 补充素材切分  (denoise=%s)" % denoise)
    print("=" * 74)

    for prefix, path in SRC:
        im = Image.open(path).convert("RGBA")
        A = np.asarray(im).copy()
        al = A[..., 3]
        H, W = al.shape
        fg = al > 128
        lbl, n = ndimage.label(fg, S8)
        areas = ndimage.sum(fg, lbl, range(1, n + 1))
        objs = ndimage.find_objects(lbl)

        bigs, smalls = [], []
        for i in range(1, n + 1):
            sl = objs[i - 1]
            if sl is None:
                continue
            bb = (sl[0].start, sl[0].stop - 1, sl[1].start, sl[1].stop - 1)
            if areas[i - 1] >= BG_AREA:
                bigs.append({"id": i, "bb": bb, "area": int(areas[i - 1])})
            elif areas[i - 1] >= DEC_MIN:
                smalls.append({"id": i, "bb": bb, "area": int(areas[i - 1])})

        # 小件归附最近的本体 (超过 DEC_DIST 丢弃)
        for s in smalls:
            best, bd = None, 1e9
            for b in bigs:
                d = bbox_dist(s["bb"], b["bb"])
                if d < bd:
                    best, bd = b, d
            if best is not None and bd <= DEC_DIST:
                best.setdefault("decs", []).append(s["id"])
            else:
                s["dropped"] = True

        # 行带分组 → 行优先排序
        bigs.sort(key=lambda b: (b["bb"][0], b["bb"][2]))
        rows = []
        for b in bigs:
            yc = (b["bb"][0] + b["bb"][1]) / 2.0
            for r in rows:
                if abs(r["yc"] - yc) < 120:
                    r["items"].append(b)
                    r["yc"] = np.mean([(x["bb"][0] + x["bb"][1]) / 2.0 for x in r["items"]])
                    break
            else:
                rows.append({"yc": yc, "items": [b]})
        rows.sort(key=lambda r: r["yc"])
        ordered = []
        for r in rows:
            r["items"].sort(key=lambda b: b["bb"][2])
            ordered += r["items"]

        print("\n【%s】%s  %dx%d" % (prefix, os.path.basename(path), W, H))
        print("  本体 %d 个 / 小件 %d 个（丢弃 %d）| 行带 %d 条"
              % (len(bigs), len(smalls), sum(1 for s in smalls if s.get("dropped")), len(rows)))

        for k, b in enumerate(ordered, 1):
            keep = [b["id"]] + b.get("decs", [])
            y0 = min([b["bb"][0]] + [next(s["bb"][0] for s in smalls if s["id"] == i) for i in b.get("decs", [])])
            y1 = max([b["bb"][1]] + [next(s["bb"][1] for s in smalls if s["id"] == i) for i in b.get("decs", [])])
            x0 = min([b["bb"][2]] + [next(s["bb"][2] for s in smalls if s["id"] == i) for i in b.get("decs", [])])
            x1 = max([b["bb"][3]] + [next(s["bb"][3] for s in smalls if s["id"] == i) for i in b.get("decs", [])])

            sub = A[y0:y1 + 1, x0:x1 + 1].copy()
            sub_lbl = lbl[y0:y1 + 1, x0:x1 + 1]
            # ★ 清外来对象: 必须带 (sub_lbl != 0) —— label==0 是本角色自己的抗锯齿边缘
            foreign = (sub_lbl != 0) & ~np.isin(sub_lbl, keep)
            sub[foreign, 3] = 0

            if denoise:
                al2 = sub[..., 3]
                core = al2 > 200
                d = ndimage.distance_transform_edt(~core) if core.any() else np.zeros_like(al2)
                noise = (al2 > 0) & (al2 <= 8) & (d > 4)
                sub[noise, 3] = 0

            name = "%s%02d.png" % (prefix, k)
            Image.fromarray(sub).save(os.path.join(OUT, name), optimize=True)

            # 自检: 成品里应该只有 1 个"本体级"连通域
            l2, n2 = ndimage.label(sub[..., 3] > 128, S8)
            a2 = ndimage.sum(sub[..., 3] > 128, l2, range(1, n2 + 1)) if n2 else []
            nbody = int(sum(1 for v in a2 if v >= BG_AREA))
            hh, ww = sub.shape[0], sub.shape[1]
            semi = int(((sub[..., 3] > 0) & (sub[..., 3] <= 128)).sum())
            ok = "OK" if nbody == 1 else "★本体数=%d" % nbody
            print("  %s  %3dx%-3d  本体面积%6d  装饰%2d  半透明%6d  %s"
                  % (name, ww, hh, b["area"], len(b.get("decs", [])), semi, ok))
            manifest["frames"].append({
                "file": name, "prefix": prefix, "index": k,
                "source": os.path.basename(path),
                "crop": [int(x0), int(y0), int(x1), int(y1)],
                "size": [int(ww), int(hh)], "body_area": b["area"],
                "decorations": len(b.get("decs", [])), "selfcheck_bodies": nbody,
            })

    with open(os.path.join(OUT, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)
    print("\n输出目录: %s" % OUT)
    print("帧清单: manifest.json（含裁剪框, 便于回溯到源图坐标）")


if __name__ == "__main__":
    main()
