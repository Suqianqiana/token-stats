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
        # 全不透明 PNG(白底)无法按 alpha 切分 → 跳过(K05 实测)
        print("  !! 全图不透明(无透明通道), 跳过: %s" % os.path.basename(path))
        return None
    scale = max(W, H) / 1536.0
    bg_area = int(20000 * scale * scale)
    lab_min = int(3000 * scale * scale)

    # ---- 第102轮第3版: 源图级**清底噪** ----
    # 一批导出图带 alpha=1~25 的极淡背景(雾感 25~38%), 桌宠放深色底上显灰蒙,
    # 浅浅猫: "不是完全透明的素材图那一整套都不需要" —— 清掉后就是完全透明,
    # 整套内容得以保留。贴纸本体(alpha≥200)不受影响。
    noise = int(((al >= 1) & (al <= 15)).sum())
    al[al <= 15] = 0
    fg = al > 128
    lbl, n = ndimage.label(fg, S8)
    areas = ndimage.sum(fg, lbl, range(1, n + 1)) if n else []
    objs = ndimage.find_objects(lbl)
    print("   清底噪 %d px (%.1f%%)" % (noise, 100.0 * noise / (H * W)))

    # 标签(细长文字带)剔除
    labels = set()
    for i in range(1, n + 1):
        sl = objs[i - 1]
        if sl is None:
            continue
        bb = (sl[0].start, sl[0].stop - 1, sl[1].start, sl[1].stop - 1)
        hh = bb[1] - bb[0] + 1
        ww = bb[3] - bb[2] + 1
        if areas[i - 1] >= lab_min and hh < 0.08 * H and ww >= 1.5 * hh:
            labels.add(i)

    # ---- 网格投影切分(行带递归 → 行带内列带), **只作归属分区** ----
    def col_bands(y0, y1):
        cs = valley_cuts(fg[y0:y1].sum(axis=0), int(0.06 * W), 0.15)
        cuts = [0] + cs + [W]
        return [(x0, x1) for x0, x1 in zip(cuts, cuts[1:]) if x1 - x0 > 0.04 * W]

    cs0 = valley_cuts(fg.sum(axis=1), int(0.06 * H), 0.12)
    bands, prev = [], 0
    for c in cs0:
        bands.append((prev, c))
        prev = c
    bands.append((prev, H))
    bands = [(a, b) for a, b in bands if b - a > 0.04 * H] or [(0, H)]
    for _depth in range(2):
        hs = [b[1] - b[0] for b in bands]
        med = float(np.median(hs)) if hs else 0.0
        new = []
        for (a, b) in bands:
            if med > 0 and (b - a) > 1.4 * med:
                cs = valley_cuts(fg[a:b].sum(axis=1), int(0.08 * (b - a)), 0.22)
                if cs:
                    p2, seq = a, []
                    for c in cs:
                        seq.append((p2, a + c))
                        p2 = a + c
                    seq.append((p2, b))
                    new += seq
                    continue
            new.append((a, b))
        if not new or len(new) == len(bands):
            bands = new or bands
            break
        bands = new
    bands = [(a, b) for a, b in bands if b - a > 0.04 * H] or [(0, H)]
    row_cols = [(a, b, col_bands(a, b)) for a, b in bands]

    # ---- 域按**中心点**归格; 格的裁剪范围 = 格内域 bbox 并集(允许溢出格子) ----
    # 这样呆毛/爱心气泡等跨格元素会完整跟着"中心所在格"走, 不再被切线腰斩
    # (浅浅猫: K10_08 的爱心对话框一半截到了 K10_09)。
    cells = {}
    for i in range(1, n + 1):
        if i in labels:
            continue
        sl = objs[i - 1]
        if sl is None:
            continue
        cy = (sl[0].start + sl[0].stop) / 2.0
        cx = (sl[1].start + sl[1].stop) / 2.0
        for bi, (a, b, cols) in enumerate(row_cols):
            if not (a <= cy < b):
                continue
            for xi, (x0, x1) in enumerate(cols):
                if x0 <= cx < x1:
                    cells.setdefault((bi, xi), []).append(i)
                    break
            break

    units = []
    for (bi, xi), ids in sorted(cells.items()):
        y0 = min(objs[i - 1][0].start for i in ids)
        y1 = max(objs[i - 1][0].stop for i in ids) - 1
        x0 = min(objs[i - 1][1].start for i in ids)
        x1 = max(objs[i - 1][1].stop for i in ids) - 1
        units.append((y0, y1, x0, x1, ids))
    units.sort(key=lambda u: (u[0], u[2]))
    print("   网格: %d 行带 → %d 格 / %d 域" % (len(bands), len(units), n))

    inks = [int(fg[u[0]:u[1] + 1, u[2]:u[3] + 1].sum()) for u in units]
    med_ink = float(np.median(inks)) if inks else 1.0

    frames = []
    for k, (uy0, uy1, ux0, ux1, ids) in enumerate(units, 1):
        sub = A[uy0:uy1 + 1, ux0:ux1 + 1].copy()
        sub_lbl = lbl[uy0:uy1 + 1, ux0:ux1 + 1]
        keep = [i for i in ids if i not in labels]
        if not keep:
            continue
        foreign = (sub_lbl != 0) & ~np.isin(sub_lbl, keep)
        sub[foreign, 3] = 0
        if not (sub[..., 3] > 0).any():
            continue
        # ---- 统一补安全边距(剪完再 pad, 不依赖源图边缘) ----
        # 顶部留最多(头发/呆毛/帽尖), 底部与左右少一些; 桌宠绘制是"底部对齐 + 居中",
        # 四周有留白就不会出现被削顶的观感。
        h0, w0 = sub.shape[0], sub.shape[1]
        pad_top = max(12, int(0.06 * h0))
        pad_bot = max(6, int(0.03 * h0))
        pad_side = max(6, int(0.03 * w0))
        sub = np.pad(sub, ((pad_top, pad_bot), (pad_side, pad_side), (0, 0)),
                     mode="constant", constant_values=0)

        m2 = sub[..., 3] > 128
        l2, n2 = ndimage.label(m2, S8)
        a2 = ndimage.sum(m2, l2, range(1, n2 + 1)) if n2 else []
        nbody = int(sum(1 for v in a2 if v >= bg_area))
        ink = int(m2.sum())

        if ink < 0.5 * med_ink or nbody < 1:
            print("    ★★ 丢弃残片 %s_?? %dx%d 墨水%d(中位%.0f) 本体%d"
                  % (gid, sub.shape[1], sub.shape[0], ink, med_ink, nbody))
            continue

        if nbody >= 2:
            proj = m2.sum(axis=1)
            cs = valley_cuts(proj, int(0.22 * sub.shape[0]), 0.20)
            pieces, prev = [], 0
            if cs:
                for c in cs + [sub.shape[0]]:
                    pieces.append(sub[prev:c].copy())
                    prev = c
            if pieces and all(_qc(p, bg_area, med_ink) for p in pieces):
                for pi, pc in enumerate(pieces):
                    nm2 = "%s_%03d.png" % (gid, len(frames) + 1 + pi)
                    Image.fromarray(pc).save(os.path.join(out_dir, nm2), optimize=True)
                    th = Image.fromarray(pc)
                    r = THUMB_H / th.height
                    th = th.resize((max(1, int(th.width * r)), THUMB_H), Image.LANCZOS)
                    th.save(os.path.join(thumb_dir, nm2), optimize=True)
                    frames.append(dict(id=nm2[:-4], source=os.path.basename(path),
                                       source_cn=cname, size=[pc.shape[1], pc.shape[0]],
                                       decorations=len(keep) - nbody,
                                       selfcheck_bodies=1))
                print("    ★ 多本体格 %dx%d → 深谷纵切 %d 份" % (sub.shape[1], sub.shape[0], len(pieces)))
                continue
            print("    ★★ 丢弃多本体格 %s_?? %dx%d 本体%d" % (gid, sub.shape[1], sub.shape[0], nbody))
            continue

        name = "%s_%02d.png" % (gid, len(frames) + 1)
        out = Image.fromarray(sub)
        out.save(os.path.join(out_dir, name), optimize=True)
        th = out.copy()
        r = THUMB_H / th.height
        th = th.resize((max(1, int(th.width * r)), THUMB_H), Image.LANCZOS)
        th.save(os.path.join(thumb_dir, name), optimize=True)
        frames.append(dict(id=name[:-4], source=os.path.basename(path), source_cn=cname,
                           size=[sub.shape[1], sub.shape[0]],
                           decorations=len(keep) - nbody,
                           selfcheck_bodies=nbody))
        print("  %s  %4dx%-4d 域%2d 墨水%6d" % (name, sub.shape[1], sub.shape[0],
                                               len(keep), ink))
    return dict(gid=gid, source=os.path.basename(path), source_cn=cname,
                src_size=[W, H], frames=frames)


def _qc(piece, bg_area, med_ink):
    m = piece[..., 3] > 128
    l, nn = ndimage.label(m, S8)
    if not nn:
        return False
    sz = ndimage.sum(m, l, range(1, nn + 1))
    return (sum(1 for v in sz if v >= bg_area) == 1) and (int(m.sum()) >= 0.5 * med_ink)


def _save(sub, name):
    """占位: 多本体切分后保存(当前调用点已被 process 内联处理)"""
    pass


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
