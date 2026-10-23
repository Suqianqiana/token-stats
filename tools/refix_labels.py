# -*- coding: utf-8 -*-
"""2026-10-23: 通用标签剔除重切 (浅浅猫报告 G01/G03 也有标签污染)。

小标签形态: ~150x44 / 180x44 胶囊 (面积 5k~8k), 第一版口径 (面积>=30000) 漏掉它们,
被当作装饰件归附进角色 bbox。
新口径 (按图幅自适应): 面积 >= 3000*scale^2 且 高 < 8%图高 且 宽 >= 1.5高 -> 标签,
不参与角色/装饰归附, crop 时作为外来像素清掉。
用法: python tools/refix_labels.py G01 G03
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
THUMB_H = 150

SRC = {
    "G01": "蓝发鲸鱼女仆日常贴纸合集.png",
    "G02": "桌宠新动作素材_4K透明.png",
    "G03": "蓝发鲸鱼少女表情贴纸合集.png",
    "G04": "桌宠新动作素材_无标签第三批_4K透明.png",
    "G05": "蓝鲸主题女仆少女贴纸表情集.png",
    "G06": "蓝鲸主题少女贴纸图鉴.png",
    "G07": "蓝发鲸鱼女仆十二格贴纸合集.png",
    "G08": "蓝发鲸鱼女仆日常贴纸集.png",
    "G09": "桌宠睡觉睡醒与日常动作_6x2_4K透明.png",
    "G10": "蓝色鲸鱼女仆的日常贴纸集.png",
    "G11": "蓝鲸少女的十二种日常姿态.png",
}


def bbox_dist(a, b):
    dy = max(0, max(a[0], b[0]) - min(a[1], b[1]))
    dx = max(0, max(a[2], b[2]) - min(a[3], b[3]))
    return (dy * dy + dx * dx) ** 0.5


def process(gid):
    fn = SRC[gid]
    A = np.asarray(Image.open(os.path.join(DL, fn)).convert("RGBA"))
    H, W = A.shape[:2]
    scale = max(W, H) / 1536.0
    bg_area = int(20000 * scale * scale)
    lab_min = int(3000 * scale * scale)
    dec_dist = 90 * scale
    fg = A[..., 3] > 128
    lbl, n = ndimage.label(fg, S8)
    szs = np.bincount(lbl.ravel())
    objs = ndimage.find_objects(lbl)

    chars, decors, labels = [], [], []
    for i in range(1, n + 1):
        sl = objs[i - 1]
        if sl is None or szs[i] < 8:
            continue
        bb = (sl[0].start, sl[0].stop - 1, sl[1].start, sl[1].stop - 1)
        h = bb[1] - bb[0] + 1
        w = bb[3] - bb[2] + 1
        if szs[i] >= lab_min and h < 0.08 * H and w >= 1.5 * h:
            labels.append(bb)
            continue
        if szs[i] >= bg_area:
            chars.append({"id": i, "bb": bb, "area": int(szs[i])})
        else:
            decors.append({"id": i, "bb": bb})
    print("  %s: 角色 %d, 装饰 %d, 剔除标签 %d" % (gid, len(chars), len(decors), len(labels)))

    for s in decors:
        best, bd = None, 1e9
        for b in chars:
            d = bbox_dist(s["bb"], b["bb"])
            if d < bd:
                best, bd = b, d
        if best is not None and bd <= dec_dist:
            best.setdefault("decs", []).append(s["id"])

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

    for f in glob.glob(os.path.join(OUT, gid + "_*.png")) + glob.glob(os.path.join(THUMB, gid + "_*.png")):
        os.remove(f)

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
        fid = "%s_%02d" % (gid, k)
        Image.fromarray(sub).save(os.path.join(OUT, fid + ".png"), optimize=True)
        th = Image.fromarray(sub).copy()
        r = THUMB_H / th.height
        th = th.resize((max(1, int(th.width * r)), THUMB_H), Image.LANCZOS)
        th.save(os.path.join(THUMB, fid + ".png"), optimize=True)
        # QC: 本体数 + 帧宽 vs 本体宽
        al2 = sub[..., 3]
        l2, n2 = ndimage.label(al2 > 128, S8)
        a2 = ndimage.sum(al2 > 128, l2, range(1, n2 + 1)) if n2 else []
        nbody = int(sum(1 for v in a2 if v >= bg_area))
        bys, bxs = np.where(al2 > 128)
        body_w = int(bxs.max() - bxs.min() + 1)
        semi = int(((al2 > 0) & (al2 <= 128)).sum())
        frames.append(dict(
            id=fid, source=fn, source_cn=None,
            size=[sub.shape[1], sub.shape[0]], body_area=b["area"],
            decorations=len(b.get("decs", [])), selfcheck_bodies=nbody, semi=semi,
            trans_pct=round(float((al2 == 0).mean() * 100), 1),
            label_removed=True))
        print("    %s  %4dx%-4d 本体宽%4d 装饰%d 本体数%d %s"
              % (fid, sub.shape[1], sub.shape[0], body_w, len(b.get("decs", [])), nbody,
                 "" if nbody == 1 else "★"))
    return frames


def main():
    gids = [a for a in sys.argv[1:] if not a.startswith("-")]
    if not gids:
        print(__doc__)
        sys.exit(1)
    man = json.load(open(os.path.join(OUT, "manifest.json"), encoding="utf-8"))
    for gid in gids:
        print("== %s %s" % (gid, SRC[gid]))
        frames = process(gid)
        g = next(g for g in man["groups"] if g["gid"] == gid)
        cn = g["source_cn"]
        for fr in frames:
            fr["source_cn"] = cn
        g["frames"] = frames
        g["note"] = "源图带头部小胶囊标签(已剔除)"
    man["total"] = sum(len(g["frames"]) for g in man["groups"])
    with open(os.path.join(OUT, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(man, f, ensure_ascii=False, indent=1)
    bad = [(g["gid"], fr["id"]) for g in man["groups"] for fr in g["frames"] if fr["selfcheck_bodies"] != 1]
    print("\n合计 %d 帧; 本体数异常: %s" % (man["total"], bad if bad else "无 ✓"))


if __name__ == "__main__":
    main()
