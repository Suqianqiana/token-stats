# -*- coding: utf-8 -*-
"""分析桌宠帧的「头发色」饱和度: 新素材 vs 原 V3 素材。

为什么单独做这个: 浅浅猫反馈"09-17 新入库的素材整体偏淡"。要证明/量化这件事,
必须锁定**同一类像素**(头发), 否则肤色/白围裙/黑裙子会把均值稀释掉。

思路:
  1. 从 installed_map.json 区分「原 V3 帧」与「09-17 新素材帧」;
  2. 每帧先用 alpha 求角色 bbox, 取**顶部 45% 高度**区域(头所在位置, 避开裙摆/道具);
  3. 在该区域内按色相挑出蓝色系像素(头发是深蓝) → 统计 HSV 的 S/V;
  4. 输出两组的均值/中位数对比, 供决定饱和度增益 k。

用法: python tools/analyze_pet_saturation.py [--hist]
"""
import io
import json
import os
import sys
import glob

import numpy as np
from PIL import Image

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAIN_DIR = os.path.join(BASE, "assets", "pet_v3r")
SCENES = ["idle", "sleep", "wake", "drag", "click", "sidle", "pat"]


def load_new_frames():
    """返回 {'<场景>/<文件名>'} —— 09-17 那批新素材装进来的帧。"""
    p = os.path.join(BASE, "assets", "pet_v3_add", "installed_map.json")
    with io.open(p, encoding="utf-8") as f:
        mp = json.load(f).get("map") or {}
    return set(v for v in mp.values() if isinstance(v, str))


def hair_pixels(path, h_lo=130, h_hi=185, top_ratio=0.45, a_min=128):
    """取「头部区域内的蓝色系像素」→ (H, S, V) 数组, 单位 0~255(8bit HSV)。"""
    im = Image.open(path).convert("RGBA")
    a = np.asarray(im)
    alpha = a[..., 3]
    ys, xs = np.where(alpha > a_min)
    if len(ys) == 0:
        return None
    y0, y1 = ys.min(), ys.max() + 1
    ycut = int(y0 + (y1 - y0) * top_ratio)
    hsv = np.asarray(im.convert("HSV")).astype(np.int16)
    H, S, V = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    m = (alpha > a_min) & (np.arange(alpha.shape[0])[:, None] < ycut)
    m &= (H >= h_lo) & (H <= h_hi) & (S > 20) & (V > 20)
    if m.sum() < 500:
        return None
    return H[m], S[m], V[m], m, hsv


def stats_of(vals):
    return (float(np.mean(vals)), float(np.median(vals)),
            float(np.percentile(vals, 25)), float(np.percentile(vals, 75)))


def main():
    # --root=<dir>: 改为统计指定目录下的全部帧(用于评估"全量增强后的实验区")
    root = MAIN_DIR
    for a in sys.argv[1:]:
        if a.startswith("--root="):
            root = a.split("=", 1)[1]
    if root != MAIN_DIR:
        Ss, Vs, names, over = [], [], [], []
        for sc in SCENES:
            for f in sorted(glob.glob(os.path.join(root, sc, "*.png"))):
                r = hair_pixels(f)
                if not r:
                    continue
                _, S, V, m, hsv = r
                Ss.append(S)
                Vs.append(V)
                a_img = np.asarray(Image.open(f).convert("RGBA"))
                al = a_img[..., 3] > 128
                over.append(float((al & (a_img[..., :3].max(-1) >= 254)).sum()) / max(1, al.sum()))
        if not Ss:
            print("该目录没有可统计的帧:", root)
            return
        S_all = np.concatenate(Ss)
        V_all = np.concatenate(Vs)
        print("目录: %s" % os.path.relpath(root, BASE))
        print("  帧数=%-3d 像素=%7d | 头发 S: 均%6.1f 中位%6.1f (25%%~75%%: %.0f~%.0f) | V 均%6.1f 中位%6.1f"
              % (len(Ss), len(S_all), S_all.mean(), np.median(S_all),
                 np.percentile(S_all, 25), np.percentile(S_all, 75), V_all.mean(), np.median(V_all)))
        print("  高光溢出(V>=254 占比): 均 %.3f%%  最大 %.3f%%" % (100 * np.mean(over), 100 * np.max(over)))
        return

    new_set = load_new_frames()
    groups = {"原 V3 帧": [], "新素材帧": []}
    rows = []
    for sc in SCENES:
        for f in sorted(glob.glob(os.path.join(BASE, "assets", "pet_v3r", sc, "*.png"))):
            rel = "%s/%s" % (sc, os.path.basename(f))
            r = hair_pixels(f)
            if not r:
                continue
            _, S, V, m, hsv = r
            key = "新素材帧" if rel in new_set else "原 V3 帧"
            groups[key].append((S, V))
            rows.append((rel, key, float(S.mean()), float(np.median(S)),
                         float(V.mean()), int(m.sum()), hsv))
    print("=" * 78)
    for k, vs in groups.items():
        if not vs:
            print("%-10s 无样本" % k)
            continue
        S_all = np.concatenate([v[0] for v in vs])
        V_all = np.concatenate([v[1] for v in vs])
        sm, sd, s25, s75 = stats_of(S_all)
        vm, vd, v25, v75 = stats_of(V_all)
        print("%-10s 帧数=%-3d 像素=%7d | 头发 S: 均%6.1f 中位%6.1f (25%%~75%%: %.0f~%.0f) | V: 均%6.1f"
              % (k, len(vs), len(S_all), sm, sd, s25, s75, vm))
    print("=" * 78)
    # 注意: groups 里存的是 (S, V) 两个数组 —— 之前误写成 v[1](取到 V), 打印出"中位 161"很误导
    S_new = np.concatenate([v[0] for v in groups["新素材帧"]])
    S_old = np.concatenate([v[0] for v in groups["原 V3 帧"]])
    print("饱和度差距: 原 V3 中位 %.1f vs 新素材中位 %.1f → 需增益 ×%.3f 才对等"
          % (np.median(S_old), np.median(S_new), np.median(S_old) / max(1e-6, np.median(S_new))))
    print()
    print("逐帧（新素材，按亮度/饱和度排序看一致性）:")
    for rel, key, sm, sd, vm, n, _ in sorted(rows, key=lambda r: -r[2]):
        if key == "新素材帧":
            print("   %-24s S均%6.1f 中位%6.1f V均%6.1f  px=%d" % (rel, sm, sd, vm, n))
    print()
    print("逐帧（原 V3 参照）:")
    for rel, key, sm, sd, vm, n, _ in sorted(rows, key=lambda r: -r[2]):
        if key == "原 V3 帧":
            print("   %-24s S均%6.1f 中位%6.1f V均%6.1f  px=%d" % (rel, sm, sd, vm, n))

    if "--hist" in sys.argv:
        print()
        print("头部蓝色像素的色相直方图（8bit H, 每 5 一档）:")
        for k in groups:
            hs = []
            for sc in SCENES:
                for f in sorted(glob.glob(os.path.join(BASE, "assets", "pet_v3r", sc, "*.png"))):
                    rel = "%s/%s" % (sc, os.path.basename(f))
                    if (rel in new_set) != (k == "新素材帧"):
                        continue
                    r = hair_pixels(f)
                    if r:
                        hs.append(r[0])
            if not hs:
                continue
            H = np.concatenate(hs)
            hist = np.bincount((H // 5).astype(int), minlength=52)
            top = np.argsort(hist)[::-1][:6]
            print("   %-8s 峰位: %s" % (k, ", ".join("H%d~%d(%d)" % (i * 5, i * 5 + 4, hist[i]) for i in sorted(top))))


if __name__ == "__main__":
    main()
