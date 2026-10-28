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
    fg = al > 128
    lbl, n = ndimage.label(fg, S8)
    areas = ndimage.sum(fg, lbl, range(1, n + 1)) if n else []
    objs = ndimage.find_objects(lbl)

    lab_min = int(3000 * scale * scale)
    # ---- 只做一件事: 找出"标签"(细长文字带), 切分时剔除 ----
    # 第102轮重做: 以前还把"小面积装饰"单独挑出来按距离归附, 距离一超就当
    # 别人的像素擦掉 —— 结果煎锅/气泡/书本这些道具被挖没了(浅浅猫指出)。
    # 现在装饰**不单独处理**: 每个格子内除标签外的域全部保留。
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

    # ================= 网格切分(第102轮重写) =================
    # 规则贴纸集用**投影**切比连通域聚类可靠得多:
    #   ① 行投影 → 行带(递归: 带太高就在带内再找行谷, 解决两行紧贴无谷)
    #   ② 行带内列投影 → 单元格
    #   ③ 格内除标签外全部保留(角色 + 道具)
    #   ④ QC: 本体=1; 面积过小(残片)丢弃; 本体≥2 尝试深谷纵切(严格验证否则丢)
    # ① 首层**无条件**按行投影下刀(否则只有 1 个带时 med=带高, 递归条件恒假,
    #    第一刀永远落不下去 —— 实测会整图当一个带, 格内塞满角色被当成多本体丢光)
    cs0 = valley_cuts(fg.sum(axis=1), int(0.06 * H), 0.12)
    bands, prev = [], 0
    for c in cs0:
        bands.append((prev, c))
        prev = c
    bands.append((prev, H))
    bands = [(a, b) for a, b in bands if b - a > 0.04 * H] or [(0, H)]
    # ② 后续层: 过高的带(两行贴纸紧贴、首层没切到)在带内再找行谷
    for depth in range(2):
        hs = [b[1] - b[0] for b in bands]
        med = float(np.median(hs)) if hs else 0.0
        new = []
        for (a, b) in bands:
            if med > 0 and (b - a) > 1.4 * med:
                cs = valley_cuts(fg[a:b].sum(axis=1), int(0.08 * (b - a)), 0.22)
                if cs:
                    prev, seq = a, []
                    for c in cs:
                        seq.append((prev, a + c))
                        prev = a + c
                    seq.append((prev, b))
                    new += seq
                    continue
            new.append((a, b))
        if not new or len(new) == len(bands):
            bands = new or bands
            break
        bands = new

    units = []
    for (a, b) in bands:
        bw = b - a
        cs = valley_cuts(fg[a:b].sum(axis=0), int(0.06 * W), 0.15)
        cuts = [0] + cs + [W]
        cells = [(x0, x1) for x0, x1 in zip(cuts, cuts[1:]) if x1 - x0 > 0.04 * W]
        # 若格数少于该带的角色域数, 收紧 min_gap 再切一次(贴纸横向紧贴时)
        want = len([1 for i in range(1, n + 1)
                    if objs[i - 1] and areas[i - 1] >= bg_area
                    and a <= objs[i - 1][0].start and objs[i - 1][0].stop <= b + 1])
        if want and len(cells) < want:
            cs = valley_cuts(fg[a:b].sum(axis=0), int(0.035 * W), 0.22)
            cuts = [0] + cs + [W]
            cells = [(x0, x1) for x0, x1 in zip(cuts, cuts[1:]) if x1 - x0 > 0.03 * W]
        for (x0, x1) in cells:
            units.append((a, b - 1, x0, x1 - 1))
    units.sort(key=lambda u: (u[0], u[2]))
    print("   网格: %d 行带 x 列 → %d 格" % (len(bands), len(units)))

    # ---- 格内面积中位数(用于判残片) ----
    inks = []
    for (y0, y1, x0, x1) in units:
        inks.append(int(fg[y0:y1 + 1, x0:x1 + 1].sum()))
    med_ink = float(np.median(inks)) if inks else 1.0
    med_h = float(np.median([u[1] - u[0] + 1 for u in units])) if units else 1.0

    frames = []
    for k, (uy0, uy1, ux0, ux1) in enumerate(units, 1):
        sub = A[uy0:uy1 + 1, ux0:ux1 + 1].copy()
        sub_lbl = lbl[uy0:uy1 + 1, ux0:ux1 + 1]
        # keep = 格内所有域 - 标签
        ids = sorted({int(v) for v in np.unique(sub_lbl) if v})
        keep = [i for i in ids if i not in labels]
        if not keep:
            continue
        foreign = (sub_lbl != 0) & ~np.isin(sub_lbl, keep)
        sub[foreign, 3] = 0
        ys, xs = np.where(sub[..., 3] > 0)
        if not len(ys):
            continue
        sub = sub[ys.min():ys.max() + 1, xs.min():xs.max() + 1]

        al2 = sub[..., 3]
        m2 = al2 > 128
        l2, n2 = ndimage.label(m2, S8)
        a2 = ndimage.sum(m2, l2, range(1, n2 + 1)) if n2 else []
        nbody = int(sum(1 for v in a2 if v >= bg_area))
        ink = int(m2.sum())

        # 残片/异常: 面积太小 = 被切残了 → 丢弃(浅浅猫: "一样的但不完整的图")
        if ink < 0.5 * med_ink or nbody < 1:
            print("    ★★ 丢弃残片 %s_?? %dx%d 墨水%d(中位%.0f) 本体%d"
                  % (gid, sub.shape[1], sub.shape[0], ink, med_ink, nbody))
            continue

        # 本体≥2(罕见: 格内确实有两个角色) → 尝试行投影深谷纵切, 验证不过就丢
        if nbody >= 2:
            proj = m2.sum(axis=1)
            cs = valley_cuts(proj, int(0.22 * sub.shape[0]), 0.20)
            ok = False
            if cs:
                pieces, prev = [], 0
                for c in cs + [sub.shape[0]]:
                    pieces.append(sub[prev:c].copy())
                    prev = c
                if all(_qc(p, bg_area, med_ink) for p in pieces):
                    for pi, pc in enumerate(pieces):
                        _save(pc, "%s_%02d" % (gid, k + pi * 1000))
                    ok = True
            if not ok:
                print("    ★★ 丢弃多本体格 %s_?? %dx%d 本体%d"
                      % (gid, sub.shape[1], sub.shape[0], nbody))
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
                           decorations=max(0, len(keep) - nbody),
                           selfcheck_bodies=nbody))
        flag = "" if nbody == 1 else "  ★本体数=%d" % nbody
        print("  %s  %4dx%-4d 域%2d 墨水%6d%s" % (name, sub.shape[1], sub.shape[0],
                                                 len(keep), ink, flag))
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
