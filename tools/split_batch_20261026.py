# -*- coding: utf-8 -*-
"""2026-10-26: 切分浅浅猫新做的三张桌宠动作素材(每张 10 帧, 共 30 帧)。

沿用 10-23 那批已验收的管线(alpha 连通域 + 装饰归附 + 标签剔除), 另加:
  ★ **粘连行的列投影谷点切分** —— "日常生活"那张第二行整行连成一片(单连通域
    3792px 宽), 光靠连通域会切成 1 个巨型帧。判据: 某域宽 > 该行中位宽的 1.6 倍
    → 用列投影的谷点把它劈开(与第99轮 V5 贴纸包同一手法)。

输出: assets/pet_new_20261026/
  H01_01.png ... (单帧, 保留原始 alpha, bbox 紧贴)
  thumbs/*.png (高 150px)
  manifest.json
"""
import json
import os
import sys

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")
sys.dont_write_bytecode = True

import numpy as np
from PIL import Image
from scipy import ndimage

S8 = np.ones((3, 3), bool)
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(BASE, "assets", "pet_new_20261026")
THUMB = os.path.join(OUT, "thumbs")
SRC_DIR = r"C:\Users\a3564\Downloads\桌宠动作素材包_4K透明_20帧"

# 2026-10-26 浅浅猫: "素材不只3张, 现在估计有上百张, 记得看文件夹里最新的"
# ⇒ 文件夹里**全部** png 都切(按 mtime 编号); 唯一跳过的是"海洋主题可爱萌宠贴纸合集 (1).png"
#   —— md5 与不带 (1) 的那张完全一致, 是重复下载(见 scan_batch_20261026.py)。
SOURCES = [
    ("H01", "桌宠动作素材_互动反馈_4K透明.png", "互动反馈"),
    ("H02", "桌宠动作素材_日常生活1_4K透明.png", "日常生活1"),
    ("H03", "蓝色鲸鱼主题Q版角色动作贴纸表.png", "Q版角色动作"),
    ("H04", "蓝发鲸鱼主题少女十姿态表情包.png", "少女十姿态"),
    ("H05", "蓝发鲸鱼少女表情贴纸合集 (1).png", "少女表情合集"),
    ("H06", "海洋主题可爱萌宠贴纸合集.png", "海洋萌宠合集"),
    ("H07", "蓝发鲸鱼主题Q版女孩表情贴纸集.png", "Q版女孩表情"),
    ("H08", "桌宠动作素材_交互与特殊待机_4K透明.png", "交互与特殊待机"),
    ("H09", "桌宠动作素材_日常生活_4K透明.png", "日常生活"),
    ("H10", "蓝发少女鲸鱼主题睡眠贴纸集.png", "睡眠贴纸集"),
    ("H11", "蓝发鲸语少女的梦幻贴纸集.png", "梦幻贴纸集"),
    ("H12", "蓝发鲸鱼主题睡梦贴纸集.png", "睡梦贴纸集"),
    ("H13", "蓝发鲸鱼主题的萌系早安贴纸集.png", "萌系早安"),
    ("H14", "鲸语梦境：十款睡意贴纸.png", "十款睡意"),
    ("H15", "蓝鲸主题 chibi 睡梦贴纸集.png", "chibi睡梦"),
    ("H16", "桌宠动作素材_睡觉与睡醒_10帧_4K透明.png", "睡觉与睡醒"),
]

DEC_MIN = 8
THUMB_H = 150


def bbox_dist(a, b):
    dy = max(0, max(a[0], b[0]) - min(a[1], b[1]))
    dx = max(0, max(a[2], b[2]) - min(a[3], b[3]))
    return (dy * dy + dx * dx) ** 0.5


def valley_cuts(col, min_gap, max_val_ratio=0.15):
    """列投影谷点切分: 返回切分点(列索引列表, 不含两端)。

    col = 每列不透明像素数; 只在"明显低谷"(< max*max_val_ratio)且间隔够开处下刀。
    """
    n = len(col)
    if n < 8:
        return []
    sm = np.convolve(col.astype(float), np.ones(9) / 9.0, mode="same")
    mx = sm.max()
    if mx <= 0:
        return []
    thr = mx * max_val_ratio
    cand = []
    for x in range(2, n - 2):
        if sm[x] <= thr and sm[x] <= sm[x - 1] and sm[x] <= sm[x + 1]:
            cand.append((int(sm[x]), x))
    cand.sort()
    cuts = []
    for _v, x in cand:
        if all(abs(x - c) >= min_gap for c in cuts):
            cuts.append(x)
    return sorted(cuts)


def process(gid, fname, cname):
    p = os.path.join(SRC_DIR, fname)
    if not os.path.exists(p):
        print("!! 缺源图:", fname)
        return None
    im = Image.open(p).convert("RGBA")
    A = np.asarray(im).copy()
    al = A[..., 3]
    H, W = al.shape
    scale = max(W, H) / 1536.0
    bg_area = int(20000 * scale * scale)
    dec_dist = 90 * scale
    fg = al > 128
    lbl, n = ndimage.label(fg, S8)
    areas = ndimage.sum(fg, lbl, range(1, n + 1)) if n else []
    objs = ndimage.find_objects(lbl)

    lab_min = int(3000 * scale * scale)
    bigs, smalls = [], []
    for i in range(1, n + 1):
        sl = objs[i - 1]
        if sl is None:
            continue
        bb = (sl[0].start, sl[0].stop - 1, sl[1].start, sl[1].stop - 1)
        hh = bb[1] - bb[0] + 1
        ww = bb[3] - bb[2] + 1
        if areas[i - 1] >= lab_min and hh < 0.08 * H and ww >= 1.5 * hh:
            continue                                   # 标签: 剔除
        if areas[i - 1] >= bg_area:
            bigs.append({"id": i, "bb": bb, "area": int(areas[i - 1])})
        elif areas[i - 1] >= DEC_MIN:
            smalls.append({"id": i, "bb": bb, "area": int(areas[i - 1])})

    # ---- 行分组 ----
    for b in bigs:
        b["yc"] = (b["bb"][0] + b["bb"][1]) / 2.0
    bigs.sort(key=lambda b: (b["yc"], b["bb"][2]))
    rows_g = []
    for b in bigs:
        for r in rows_g:
            if abs(r["yc"] - b["yc"]) < 150 * scale:
                r["items"].append(b)
                r["yc"] = float(np.mean([x["yc"] for x in r["items"]]))
                break
        else:
            rows_g.append({"yc": b["yc"], "items": [b]})
    rows_g.sort(key=lambda r: r["yc"])

    # ---- 粘连行 -> 谷点切分 ----
    units = []            # [(y0, y1, x0, x1)]  最终切分单元(含装饰后用)
    for r in rows_g:
        items = sorted(r["items"], key=lambda b: b["bb"][2])
        widths = [b["bb"][3] - b["bb"][2] + 1 for b in items]
        med = float(np.median(widths)) if widths else 0
        y0 = min(b["bb"][0] for b in items)
        y1 = max(b["bb"][1] for b in items)
        for b in items:
            x0, x1 = b["bb"][2], b["bb"][3]
            w = x1 - x0 + 1
            if med > 0 and w > 1.6 * med and w > 0.35 * W:
                sub_fg = fg[y0:y1 + 1, x0:x1 + 1]
                col = sub_fg.sum(axis=0)
                cuts = valley_cuts(col, min_gap=int(0.35 * med))
                if cuts:
                    print("    ★ 行内粘连: 域宽%d (行中位宽%d) → 列投影谷点 %s 切成 %d 份"
                          % (w, int(med), cuts, len(cuts) + 1))
                    prev = 0
                    for c in cuts + [sub_fg.shape[1]]:
                        units.append((y0, y1, x0 + prev, x0 + c - 1))
                        prev = c
                    continue
            units.append((y0, y1, x0, x1))

    # ---- 装饰归附 ----
    for s in smalls:
        best, bd = None, 1e9
        for (uy0, uy1, ux0, ux1) in units:
            d = bbox_dist(s["bb"], (uy0, uy1, ux0, ux1))
            if d < bd:
                best, bd = (uy0, uy1, ux0, ux1), d
        if best is not None and bd <= dec_dist:
            s["unit"] = best
        else:
            s["dropped"] = True

    units.sort(key=lambda u: (u[0] // 200, u[2]))

    frames = []
    for k, (uy0, uy1, ux0, ux1) in enumerate(units, 1):
        decs = [s for s in smalls if s.get("unit") == (uy0, uy1, ux0, ux1)]
        y0 = min([uy0] + [s["bb"][0] for s in decs])
        y1 = max([uy1] + [s["bb"][1] for s in decs])
        x0 = min([ux0] + [s["bb"][2] for s in decs])
        x1 = max([ux1] + [s["bb"][3] for s in decs])
        sub = A[y0:y1 + 1, x0:x1 + 1].copy()
        sub_lbl = lbl[y0:y1 + 1, x0:x1 + 1]
        # 该单元内"角色级"域 = 落在本单元里的 bigs 的 id
        ids = [b["id"] for b in bigs
               if not (b["bb"][3] < ux0 or b["bb"][2] > ux1
                       or b["bb"][1] < uy0 or b["bb"][0] > uy1)]
        keep = set(ids) | {s["id"] for s in decs}
        foreign = (sub_lbl != 0) & ~np.isin(sub_lbl, list(keep))
        sub[foreign, 3] = 0

        name = "%s_%02d.png" % (gid, k)
        out = Image.fromarray(sub)
        out.save(os.path.join(OUT, name), optimize=True)
        th = out.copy()
        r = THUMB_H / th.height
        th = th.resize((max(1, int(th.width * r)), THUMB_H), Image.LANCZOS)
        th.save(os.path.join(THUMB, name), optimize=True)

        al2 = sub[..., 3]
        l2, n2 = ndimage.label(al2 > 128, S8)
        a2 = ndimage.sum(al2 > 128, l2, range(1, n2 + 1)) if n2 else []
        nbody = int(sum(1 for v in a2 if v >= bg_area))
        semi = int(((al2 > 0) & (al2 <= 128)).sum())
        trans = float((al2 == 0).mean() * 100)
        hh, ww = sub.shape[0], sub.shape[1]
        frames.append(dict(id=name[:-4], source=fname, source_cn=cname,
                           size=[ww, hh], decorations=len(decs),
                           selfcheck_bodies=nbody, semi=semi, trans_pct=round(trans, 1)))
        flag = "" if nbody == 1 else "  ★本体数=%d(粘连?)" % nbody
        print("  %s  %4dx%-4d 装饰%2d 半透明%6d 透明%.0f%%%s" %
              (name, ww, hh, len(decs), semi, trans, flag))
    return dict(gid=gid, source=fname, source_cn=cname, src_size=[W, H], frames=frames)


def main():
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(THUMB, exist_ok=True)
    groups = []
    for gid, fname, cname in SOURCES:
        print("== %s %s" % (gid, cname))
        g = process(gid, fname, cname)
        if g:
            groups.append(g)
    manifest = dict(v=1, generated="2026-10-26", groups=groups,
                    total=sum(len(g["frames"]) for g in groups))
    with open(os.path.join(OUT, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)
    bad = [(g["gid"], fr["id"], fr["selfcheck_bodies"]) for g in groups
           for fr in g["frames"] if fr["selfcheck_bodies"] != 1]
    print("\n合计 %d 帧 / %d 组" % (manifest["total"], len(groups)))
    print("本体数异常:", bad if bad else "无 ✓")


if __name__ == "__main__":
    main()
