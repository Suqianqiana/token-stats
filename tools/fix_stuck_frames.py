# -*- coding: utf-8 -*-
"""2026-10-23: 拆分两帧粘连素材 (G02_09 三角色接触 / G05_11 双角色接触)。

方法: alpha>128 掩码的**列投影谷点**切分 —— 接触处 alpha 列和显著下降。
切分后逐段 crop bbox、重新编号、重建缩略图与 manifest 条目, 并 QC(本体数应=1)。
"""
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
THUMB_H = 150

# (组, 粘连帧, 期望拆出段数)
JOBS = [("G02", "G02_09", 3), ("G05", "G05_11", 2)]


def valley_cuts(alpha, k):
    """在 alpha>128 的列投影上找 k-1 个谷点作为切分线(返回排序后的 x 坐标)。"""
    col = (alpha > 128).sum(axis=0).astype(np.float64)
    col = ndimage.gaussian_filter1d(col, 3)
    on = np.where(col > col.max() * 0.02)[0]
    lo, hi = int(on.min()), int(on.max())
    seg = col[lo:hi + 1]
    # 候选谷点: 局部极小
    cand = []
    for i in range(3, len(seg) - 3):
        if seg[i] <= seg[i - 3:i].min() and seg[i] <= seg[i + 1:i + 4].min():
            cand.append((i, seg[i]))
    # 谷点之间至少间隔 1/4 宽度, 从深到浅取
    cand.sort(key=lambda t: t[1])
    picks, min_gap = [], max(40, (hi - lo) // (k + 2))
    for i, v in cand:
        if all(abs(i - p) >= min_gap for p in picks):
            picks.append(i)
        if len(picks) == k - 1:
            break
    picks.sort()
    return [lo + p for p in picks], col, lo, hi


def split_frame(gid, fid, k):
    src = os.path.join(OUT, fid + ".png")
    A = np.asarray(Image.open(src).convert("RGBA"))
    al = A[..., 3]
    H, W = al.shape
    cuts, col, lo, hi = valley_cuts(al, k)
    print("  %s: 宽 %d, 内容 [%d,%d], 谷点切分线 x=%s (期望 %d 段)"
          % (fid, W, lo, hi, cuts, k))
    bounds = [lo - 1] + cuts + [hi + 1]
    parts = []
    for i in range(k):
        x0, x1 = max(0, bounds[i]), min(W - 1, bounds[i + 1])
        seg = A[:, x0:x1 + 1].copy()
        sal = seg[..., 3]
        ys, xs = np.where(sal > 0)
        if len(ys) == 0:
            continue
        y0, y1 = int(ys.min()), int(ys.max())
        seg = seg[y0:y1 + 1].copy()
        # 段内若仍含多个本体(串联未断), 报告
        l2, n2 = ndimage.label(seg[..., 3] > 128, S8)
        a2 = ndimage.sum(seg[..., 3] > 128, l2, range(1, n2 + 1)) if n2 else []
        big_n = int(sum(1 for v in a2 if v >= 20000))
        parts.append((seg, big_n, (x0, x1)))
        print("    段%d: x[%d,%d]  %dx%d  本体数=%d %s"
              % (i + 1, x0, x1, seg.shape[1], seg.shape[0], big_n,
                 "" if big_n == 1 else "★仍有粘连"))
    return parts


def main():
    man = json.load(open(os.path.join(OUT, "manifest.json"), encoding="utf-8"))
    for gid, fid, k in JOBS:
        print("== %s 拆分 %d 段" % (fid, k))
        parts = split_frame(gid, fid, k)
        assert len(parts) == k, "拆分出的段数不符: %d != %d" % (len(parts), k)
        # 新帧名: 该组内按顺序占位 —— 简化处理: 拆出的帧依次为 fid, fid_a, fid_b...
        # 但为了编号连续, 直接重排该组全部帧
        g = next(g for g in man["groups"] if g["gid"] == gid)
        old_files = [fr["id"] for fr in g["frames"]]
        idx = old_files.index(fid)
        new_frames = []
        for i, (seg, big_n, _) in enumerate(parts):
            new_id = "%s_%02d" % (gid, idx + 1 + i)   # 先占位, 稍后统一重排
            Image.fromarray(seg).save(os.path.join(OUT, new_id + ".png"), optimize=True)
            th = Image.fromarray(seg).copy()
            r = THUMB_H / th.height
            th = th.resize((max(1, int(th.width * r)), THUMB_H), Image.LANCZOS)
            th.save(os.path.join(THUMB, new_id + ".png"), optimize=True)
            al2 = seg[..., 3]
            semi = int(((al2 > 0) & (al2 <= 128)).sum())
            new_frames.append(dict(
                id=new_id, source=g["source"], source_cn=g["source_cn"],
                size=[seg.shape[1], seg.shape[0]],
                body_area=int((al2 > 128).sum()),
                decorations=0, selfcheck_bodies=big_n, semi=semi,
                trans_pct=round(float((al2 == 0).mean() * 100), 1),
                note="由 %s 拆分" % fid))
            print("    -> %s (%dx%d)" % (new_id, seg.shape[1], seg.shape[0]))
        # 替换 frames 列表
        keep = [fr for fr in g["frames"] if fr["id"] != fid]
        g["frames"] = g["frames"][:idx] + new_frames + g["frames"][idx + 1:]
        # 统一重排编号
        for i, fr in enumerate(g["frames"], 1):
            new_id = "%s_%02d" % (gid, i)
            if fr["id"] != new_id:
                os.replace(os.path.join(OUT, fr["id"] + ".png"), os.path.join(OUT, new_id + ".png"))
                tp, tn = os.path.join(THUMB, fr["id"] + ".png"), os.path.join(THUMB, new_id + ".png")
                if os.path.exists(tp):
                    os.replace(tp, tn)
                fr["id"] = new_id
        print("  重排后 %s: %d 帧 %s" % (gid, len(g["frames"]), [fr["id"] for fr in g["frames"]]))

    man["total"] = sum(len(g["frames"]) for g in man["groups"])
    with open(os.path.join(OUT, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(man, f, ensure_ascii=False, indent=1)
    bad = [(g["gid"], fr["id"]) for g in man["groups"] for fr in g["frames"] if fr["selfcheck_bodies"] != 1]
    print("\n合计 %d 帧; 本体数异常: %s" % (man["total"], bad if bad else "无 ✓"))


if __name__ == "__main__":
    main()
