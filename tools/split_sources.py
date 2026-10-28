# -*- coding: utf-8 -*-
"""第102轮: 通用切分脚本 —— 从"唯一源图清单"(scan_sources.py 产出)切帧。

与 20261026 那批同一套管线(alpha 连通域 + 装饰归附 + 标签剔除 + 粘连行谷点切分),
只是源图改从清单 JSON 读(先做过精确/感知去重, 不会把重复图切两遍)。

用法: python -B tools/split_sources.py <清单json> --batch=20261028 [--thumb=300]
输出: assets/pet_new_<批次>/  K01_01.png ...  thumbs/*.png  manifest.json
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
THUMB_H = 300


def bbox_dist(a, b):
    dy = max(0, max(a[0], b[0]) - min(a[1], b[1]))
    dx = max(0, max(a[2], b[2]) - min(a[3], b[3]))
    return (dy * dy + dx * dx) ** 0.5


def valley_cuts(col, min_gap, max_val_ratio=0.15):
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


def process(gid, path, cname, out_dir, thumb_dir):
    if not os.path.exists(path):
        print("!! 缺源图:", path)
        return None
    im = Image.open(path).convert("RGBA")
    A = np.asarray(im).copy()
    al = A[..., 3]
    H, W = al.shape
    if al.min() == 255:
        # 第102轮: 混进来的**全不透明 PNG**(白底图, 没有透明通道)无法按 alpha
        # 切分 —— 直接跳过。实测 K05(萌系日常贴纸合集)整图 alpha=255,
        # 内容与其它组同质(感知相似 0.90), 跳过零损失。
        print("  !! 全图不透明(无透明通道), 跳过: %s" % os.path.basename(path))
        return None
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
            continue                                   # 标签剔除
        if areas[i - 1] >= bg_area:
            bigs.append({"id": i, "bb": bb, "area": int(areas[i - 1])})
        elif areas[i - 1] >= 8:
            smalls.append({"id": i, "bb": bb, "area": int(areas[i - 1])})

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

    units = []
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
                    print("    ★ 粘连: 域宽%d(行中位%d) → 谷点%s 切 %d 份"
                          % (w, int(med), cuts, len(cuts) + 1))
                    prev = 0
                    for c in cuts + [sub_fg.shape[1]]:
                        units.append((y0, y1, x0 + prev, x0 + c - 1))
                        prev = c
                    continue
            units.append((y0, y1, x0, x1))

    for s in smalls:
        best, bd = None, 1e9
        for u in units:
            d = bbox_dist(s["bb"], u[:4])
            if d < bd:
                best, bd = u, d
        s["unit"] = best if bd <= dec_dist else None

    units.sort(key=lambda u: (u[0] // 200, u[2]))

    # ---- 第102轮修正: "上下堆叠"的 unit 纵向切开 ----
    # 实测(K11/K12/K13/K16/K18 等 4 行贴纸集): 某个跨行域会把两行拉进同一分组,
    # 横向谷点切出的 unit 就包含**上下两个角色**。修法: 高度超过中位域高 1.35 倍
    # 且 bbox 内含 ≥2 个角色级域的 unit, 按"域与域的间隙带内投影最低行"切成
    # N 份, 每份**显式携带自己的 keep 域**(foreign 清除把别人的像素擦掉)。
    med_h = float(np.median([b["bb"][1] - b["bb"][0] + 1 for b in bigs])) if bigs else 0.0

    def split_stacked(u):
        uy0, uy1, ux0, ux1 = u
        ins = sorted((b for b in bigs
                      if not (b["bb"][3] < ux0 or b["bb"][2] > ux1
                              or b["bb"][1] < uy0 or b["bb"][0] > uy1)),
                     key=lambda b: (b["bb"][0] + b["bb"][1]) / 2)
        if len(ins) < 2:
            # 单域但高度异常: 上下两个角色**粘成一片**(同一连通域), foreign 清除
            # 帮不上忙 —— 用行投影找"深谷"(两角色连接处)直接纵切; 裁剪范围不同,
            # 域像素自然被切开。找不到深谷就放弃(保持原样)。
            if not ins:
                return [(uy0, uy1, ux0, ux1, [])]
            proj = fg[uy0:uy1 + 1, ux0:ux1 + 1].sum(axis=1)
            cuts = valley_cuts(proj, min_gap=int(0.22 * (uy1 - uy0 + 1)),
                               max_val_ratio=0.20)
            if not cuts:
                return [(uy0, uy1, ux0, ux1, [ins[0]["id"]])]
            iid = ins[0]["id"]
            subs, prev = [], uy0
            for c in cuts + [uy1 - uy0 + 1]:
                end = uy0 + c - 1
                subs.append((prev, end, ux0, ux1, [iid]))
                prev = end + 1
            print("    ★ 单域粘连 %dx%d → 行投影深谷%s 切 %d 份"
                  % (ux1 - ux0 + 1, uy1 - uy0 + 1, cuts, len(subs)))
            return subs
        cuts = []
        for a, b in zip(ins, ins[1:]):
            lo, hi = a["bb"][1], b["bb"][0]           # a.y1 .. b.y0 (可能重叠)
            if hi < lo:
                lo, hi = hi, lo
            band = fg[lo:hi + 1, ux0:ux1 + 1].sum(axis=1)
            cuts.append(lo + int(np.argmin(band)) if len(band) else (lo + hi) // 2)
        subs, prev, gi = [], uy0, 0
        for c in cuts:
            subs.append((prev, c, ux0, ux1, [ins[gi]["id"]]))
            prev, gi = c + 1, gi + 1
        subs.append((prev, uy1, ux0, ux1, [ins[gi]["id"]]))
        print("    ★ 上下堆叠 %dx%d 含 %d 个角色 → 按域间隙切 %d 份 (切线 y=%s)"
              % (ux1 - ux0 + 1, uy1 - uy0 + 1, len(ins), len(subs), cuts))
        return subs

    if med_h > 0:
        out_units = []
        for u in units:
            if (u[1] - u[0] + 1) > 1.35 * med_h:
                out_units.extend(split_stacked(u))
            else:
                out_units.append((u[0], u[1], u[2], u[3],
                                  [b["id"] for b in bigs
                                   if not (b["bb"][3] < u[2] or b["bb"][2] > u[3]
                                           or b["bb"][1] < u[0] or b["bb"][0] > u[1])]))
        units = out_units
    units.sort(key=lambda u: (u[0] // 200, u[2]))

    frames = []
    for k, u in enumerate(units, 1):
        uy0, uy1, ux0, ux1, keep_ids = u
        if not keep_ids:
            continue                              # 防御: 空.unit 不该出现
        decs = [s for s in smalls if s.get("unit") == u]
        y0 = min([uy0] + [s["bb"][0] for s in decs])
        y1 = max([uy1] + [s["bb"][1] for s in decs])
        x0 = min([ux0] + [s["bb"][2] for s in decs])
        x1 = max([ux1] + [s["bb"][3] for s in decs])
        sub = A[y0:y1 + 1, x0:x1 + 1].copy()
        sub_lbl = lbl[y0:y1 + 1, x0:x1 + 1]
        keep = set(keep_ids) | {s["id"] for s in decs}
        foreign = (sub_lbl != 0) & ~np.isin(sub_lbl, list(keep))
        sub[foreign, 3] = 0
        # 第102轮: 紧裁 —— 纵向切线穿过相邻域 bbox 重叠区时, 清除后会有全透明边
        ys, xs = np.where(sub[..., 3] > 0)
        if len(ys):
            sub = sub[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
        else:
            print("    ★★ 空帧跳过 unit y%d..%d x%d..%d keep=%s"
                  % (uy0, uy1, ux0, ux1, keep_ids))
            continue

        name = "%s_%02d.png" % (gid, k)
        al2 = sub[..., 3]
        l2, n2 = ndimage.label(al2 > 128, S8)
        a2 = ndimage.sum(al2 > 128, l2, range(1, n2 + 1)) if n2 else []
        nbody = int(sum(1 for v in a2 if v >= bg_area))
        if nbody == 0:
            # 切线归属错位产生的空份 —— 角色像素都在另一份里, 这份直接丢弃
            print("    ★★ 空内容份 %s 跳过 (keep=%s)" % (name, keep_ids))
            continue
        out = Image.fromarray(sub)
        out.save(os.path.join(out_dir, name), optimize=True)
        th = out.copy()
        r = THUMB_H / th.height
        th = th.resize((max(1, int(th.width * r)), THUMB_H), Image.LANCZOS)
        th.save(os.path.join(thumb_dir, name), optimize=True)

        frames.append(dict(id=name[:-4], source=os.path.basename(path), source_cn=cname,
                           size=[sub.shape[1], sub.shape[0]], decorations=len(decs),
                           selfcheck_bodies=nbody))
        flag = "" if nbody == 1 else "  ★本体数=%d" % nbody
        print("  %s  %4dx%-4d 装饰%2d%s" % (name, sub.shape[1], sub.shape[0], len(decs), flag))
    return dict(gid=gid, source=os.path.basename(path), source_cn=cname,
                src_size=[W, H], frames=frames)


def main():
    args = sys.argv[1:]
    paths = [a for a in args if not a.startswith("--")]
    if not paths:
        print(__doc__)
        return 1
    batch = "20261028"
    for a in args:
        if a.startswith("--batch="):
            batch = a.split("=", 1)[1]
        elif a.startswith("--thumb="):
            global THUMB_H
            THUMB_H = int(a.split("=", 1)[1])
    src = json.load(open(paths[0], encoding="utf-8"))
    out_dir = os.path.join(BASE, "assets", "pet_new_%s" % batch)
    thumb_dir = os.path.join(out_dir, "thumbs")
    os.makedirs(out_dir, exist_ok=True)
    os.makedirs(thumb_dir, exist_ok=True)

    groups = []
    for i, item in enumerate(src["keep"], 1):
        gid = "K%02d" % i
        cname = os.path.splitext(item["name"])[0][:12]
        print("== %s %s" % (gid, item["name"]))
        g = process(gid, item["path"], cname, out_dir, thumb_dir)
        if g:
            groups.append(g)
    manifest = dict(v=1, generated=batch, groups=groups,
                    total=sum(len(g["frames"]) for g in groups),
                    source_note=src.get("dir", ""))
    with open(os.path.join(out_dir, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)
    bad = [(g["gid"], fr["id"], fr["selfcheck_bodies"]) for g in groups
           for fr in g["frames"] if fr["selfcheck_bodies"] != 1]
    print("\n合计 %d 帧 / %d 组   缩略图高 %dpx" % (manifest["total"], len(groups), THUMB_H))
    print("本体数异常:", bad if bad else "无 ✓")


if __name__ == "__main__":
    sys.exit(main())
