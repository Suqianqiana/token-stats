# -*- coding: utf-8 -*-
"""2026-10-23: 重切 G02 (桌宠新动作素材_4K透明) —— 剔除 6 个蓝色文字标签。

问题定位: 标签(591x150 等宽矮物体, 面积 8 万+)被"距离<=225 的装饰归附"并进角色 bbox,
        把帧宽撑到 2035px (G02_09), 后续按粘连硬切出空壳, 且重排覆盖丢了旧帧。
正解: 标签类连通域(面积>=30000 且 高<8%图高 且 宽>=2高) 不参与角色/装饰归附。
G02 实为 2 行 x 5 角色 = 10 帧, 全部单体独立, 无粘连。
"""
import glob
import json
import os
import sys

sys.dont_write_bytecode = True
import numpy as np
from PIL import Image
from scipy import ndimage

S8 = np.ones((3, 3), bool)
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(BASE, "assets", "pet_new_20261023")
THUMB = os.path.join(OUT, "thumbs")
DL = os.path.join(os.path.expanduser("~"), "Downloads")
SRC = os.path.join(DL, "桌宠新动作素材_4K透明.png")
THUMB_H = 150

# 浅浅猫原图的分组标签 (按水平位置, 供行为库分配参考)
GROUP_HINTS = ["日常小动作", "互动娱乐", "应援动作", "道具动作", "活力动作", "友好互动"]


def bbox_dist(a, b):
    dy = max(0, max(a[0], b[0]) - min(a[1], b[1]))
    dx = max(0, max(a[2], b[2]) - min(a[3], b[3]))
    return (dy * dy + dx * dx) ** 0.5


def main():
    A = np.asarray(Image.open(SRC).convert("RGBA"))
    H, W = A.shape[:2]
    scale = max(W, H) / 1536.0
    bg_area = int(20000 * scale * scale)      # 125000
    dec_dist = 90 * scale                     # 225
    fg = A[..., 3] > 128
    lbl, n = ndimage.label(fg, S8)
    szs = np.bincount(lbl.ravel())
    objs = ndimage.find_objects(lbl)

    chars, decors = [], []
    for i in range(1, n + 1):
        sl = objs[i - 1]
        if sl is None or szs[i] < 8:
            continue
        bb = (sl[0].start, sl[0].stop - 1, sl[1].start, sl[1].stop - 1)
        h = bb[1] - bb[0] + 1
        w = bb[3] - bb[2] + 1
        # 标签类: 剔除
        if szs[i] >= 30000 and h < 0.08 * H and w >= 2 * h:
            print("  跳过标签: 面积%d %dx%d@(%d,%d)" % (szs[i], w, h, bb[2], bb[0]))
            continue
        if szs[i] >= bg_area:
            chars.append({"id": i, "bb": bb, "area": int(szs[i])})
        else:
            decors.append({"id": i, "bb": bb})

    for s in decors:
        best, bd = None, 1e9
        for b in chars:
            d = bbox_dist(s["bb"], b["bb"])
            if d < bd:
                best, bd = b, d
        if best is not None and bd <= dec_dist:
            best.setdefault("decs", []).append(s["id"])

    # 行分组(按 y 中心) -> 行优先
    chars.sort(key=lambda b: (b["bb"][0], b["bb"][2]))
    rows_g = []
    for b in chars:
        yc = (b["bb"][0] + b["bb"][1]) / 2.0
        for r in rows_g:
            if abs(r["yc"] - yc) < 150 * scale:
                r["items"].append(b)
                break
        else:
            rows_g.append({"yc": yc, "items": [b]})
    rows_g.sort(key=lambda r: r["yc"])
    ordered = []
    for r in rows_g:
        r["items"].sort(key=lambda b: b["bb"][2])
        ordered += r["items"]
    print("  角色 %d 个 (行分布 %s), 装饰 %d 个" %
          (len(ordered), [len(r["items"]) for r in rows_g], len(decors)))

    # 清掉旧 G02 产物(含之前误拆的)
    for f in glob.glob(os.path.join(OUT, "G02_*.png")) + glob.glob(os.path.join(THUMB, "G02_*.png")):
        os.remove(f)
    print("  已清除旧 G02 产物")

    frames = []
    for k, b in enumerate(ordered, 1):
        keep = [b["id"]] + b.get("decs", [])
        decs_bb = [next(s["bb"] for s in decors if s["id"] == i) for i in b.get("decs", [])]
        y0 = min([b["bb"][0]] + [d[0] for d in decs_bb])
        y1 = max([b["bb"][1]] + [d[1] for d in decs_bb])
        x0 = min([b["bb"][2]] + [d[2] for d in decs_bb])
        x1 = max([b["bb"][3]] + [d[3] for d in decs_bb])
        sub = A[y0:y1 + 1, x0:x1 + 1].copy()
        sub_lbl = lbl[y0:y1 + 1, x0:x1 + 1]
        foreign = (sub_lbl != 0) & ~np.isin(sub_lbl, keep)
        sub[foreign, 3] = 0
        fid = "G02_%02d" % k
        Image.fromarray(sub).save(os.path.join(OUT, fid + ".png"), optimize=True)
        th = Image.fromarray(sub).copy()
        r = THUMB_H / th.height
        th = th.resize((max(1, int(th.width * r)), THUMB_H), Image.LANCZOS)
        th.save(os.path.join(THUMB, fid + ".png"), optimize=True)
        # QC
        al2 = sub[..., 3]
        l2, n2 = ndimage.label(al2 > 128, S8)
        a2 = ndimage.sum(al2 > 128, l2, range(1, n2 + 1)) if n2 else []
        nbody = int(sum(1 for v in a2 if v >= bg_area))
        semi = int(((al2 > 0) & (al2 <= 128)).sum())
        # 帧内本体 bbox (核对装饰/标签是否还有残留)
        bys, bxs = np.where(al2 > 128)
        body_w = int(bxs.max() - bxs.min() + 1)
        frames.append(dict(
            id=fid, source="桌宠新动作素材_4K透明.png", source_cn="新动作素材·第二批",
            size=[sub.shape[1], sub.shape[0]], body_area=b["area"],
            decorations=len(b.get("decs", [])), selfcheck_bodies=nbody, semi=semi,
            trans_pct=round(float((al2 == 0).mean() * 100), 1),
            hint=GROUP_HINTS[k - 1] if k <= len(GROUP_HINTS) else None))
        print("  %s  %4dx%-4d 本体宽%4d 装饰%d 半透明%6d 本体数%d %s"
              % (fid, sub.shape[1], sub.shape[0], body_w, len(b.get("decs", [])), semi, nbody,
                 "" if nbody == 1 else "★"))

    man = json.load(open(os.path.join(OUT, "manifest.json"), encoding="utf-8"))
    g = next(g for g in man["groups"] if g["gid"] == "G02")
    g["frames"] = frames
    g["note"] = "原图带 6 个蓝色分组标签(已剔除): " + " / ".join(GROUP_HINTS)
    man["total"] = sum(len(g["frames"]) for g in man["groups"])
    with open(os.path.join(OUT, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(man, f, ensure_ascii=False, indent=1)
    bad = [(g["gid"], fr["id"]) for g in man["groups"] for fr in g["frames"] if fr["selfcheck_bodies"] != 1]
    print("\n合计 %d 帧; 本体数异常: %s" % (man["total"], bad if bad else "无 ✓"))


if __name__ == "__main__":
    main()
