# -*- coding: utf-8 -*-
"""V2 素材重建 —— 用浅浅猫 2026-09-15 提供的**透明原图**替换原 V2 素材。零抠图。

源 = `C:\\Users\\a3564\\Downloads\\ChatGPT Image 2026年9月15日 11_18_35.png`
     (PNG RGBA 1536x1024, 四角 alpha=0 真透明)

【为什么不能用竖向切分】(浅浅猫明确要求 "不能简单切分, 不然又像上次那样了")
  实测该图排布极紧凑:
    · 行1 (y167..521): 6 个角色, 但**只有 2 处干净空隙**(需要 5)
    · 行2 (y612..959): 7 个角色, 也**只有 2 处干净空隙**(需要 6)
    · 且行2 的 #2|#3 重叠 9px、#6|#7 重叠 3px
  => 任何竖线都会裁断角色。必须按 **alpha 连通域** 切分 (见下)。

【切分算法】
  1. `lbl = label(fg)` (fg = alpha > 128); 面积 >= CHAR_MIN 判为角色本体,
     8 ~ CHAR_MIN 判为附属装饰件(音符/星星/爱心)。
  2. 装饰件按 bbox 最短距离归附最近角色 (阈值 DEC_MAXDIST), 超出则丢弃。
  3. 每个角色 = 其本体 + 归附装饰 的并集 bbox。
  4. 把框内属于**其它角色**的连通域像素 alpha 置 0。
     ⚠️ 绝不能把 `label == 0` 当外来像素清掉 —— 那是本角色自己的半透明抗锯齿边缘!
  5. 自检: 每帧应只含 1 个 >= CHAR_MIN 的连通域。

【动作映射 (来源: 全局最优形状匹配, 与旧 V2 顺序完全一致)】
  n1..n4  -> idle_01..04   (待机)
  n5..n6  -> sleep_01..02  (睡觉)
  n7..n9  -> drag_01..03   (拖拽)
  n10..n11-> click_01..02  (点击)
  n12..n13-> special_01..02(特殊)
  依据: 无顺序约束的 linear_sum_assignment 最优解恰为此顺序(总分 10.978);
        备选顺序 B(点击/特殊互换)10.756, C(睡觉提前)9.509 —— 均更低。

用法: python tools/build_pet_v2_alpha.py   (幂等)
"""
import json
import os
import shutil

import numpy as np
from PIL import Image
from scipy import ndimage

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = "C:/Users/a3564/Downloads/ChatGPT Image 2026年9月15日 11_18_35.png"
SRC_DIR = os.path.join(BASE, "assets", "pet_v2_src")
DST = os.path.join(BASE, "assets", "pet_v2")
DISC = os.path.join(BASE, "assets", "pet_v2_discard")

BANDS = [(167, 521), (612, 959)]      # 两行的 y 范围
S8 = np.ones((3, 3), int)
CHAR_MIN = 20000        # 面积 >= 此值 = 角色本体
DEC_MIN = 8             # 8 ~ CHAR_MIN = 装饰小件
DEC_MAXDIST = 90        # 装饰件到最近角色的最大距离(px)

# 行优先后的动作槽位 (每行按 x 从小到大)
PLAN = [
    ("idle",    [1, 2, 3, 4]),
    ("sleep",   [5, 6]),
    ("drag",    [7, 8, 9]),
    ("click",   [10, 11]),
    ("special", [12, 13]),
]


def _bbox(mask):
    ys, xs = np.where(mask)
    return int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())


def _gapd(a, b):
    dx = max(a[0] - b[2], 0, b[0] - a[2])
    dy = max(a[1] - b[3], 0, b[1] - a[3])
    return (dx * dx + dy * dy) ** 0.5


def split_by_components():
    A = np.asarray(Image.open(SRC).convert("RGBA"))
    fg = A[..., 3] > 128
    lbl, n = ndimage.label(fg, structure=S8)
    szs = np.bincount(lbl.ravel())
    objs = ndimage.find_objects(lbl)
    info = {}
    for i in range(1, n + 1):
        if szs[i] < DEC_MIN or objs[i - 1] is None:
            continue
        sl = objs[i - 1]
        info[i] = dict(size=int(szs[i]),
                       bbox=(sl[1].start, sl[0].start, sl[1].stop - 1, sl[0].stop - 1))
    out = {}
    qc = {}
    idx = 0
    for ri, (y0, y1) in enumerate(BANDS):
        inb = {i: v for i, v in info.items()
               if y0 <= (v["bbox"][1] + v["bbox"][3]) / 2 <= y1}
        chars = sorted([(i, v) for i, v in inb.items() if v["size"] >= CHAR_MIN],
                       key=lambda t: (t[1]["bbox"][0] + t[1]["bbox"][2]) / 2)
        decors = [(i, v) for i, v in inb.items() if v["size"] < CHAR_MIN]
        print(f"  行{ri+1} y{y0}..{y1}: 角色 {len(chars)} 个, 装饰件 {len(decors)} 个")
        stake = {i: [] for i, _ in chars}
        for di, dv in decors:
            best, bd = None, 1e18
            for ci, cv in chars:
                d = _gapd(dv["bbox"], cv["bbox"])
                if d < bd:
                    best, bd = ci, d
            if best is not None and bd <= DEC_MAXDIST:
                stake[best].append(di)
        n_att = sum(len(v) for v in stake.values())
        print(f"        装饰件归附 {n_att} 个, 丢弃 {len(decors)-n_att} 个")
        for ci, cv in chars:
            keep = [ci] + stake[ci]
            km = np.isin(lbl, keep)
            bx0, by0, bx1, by1 = _bbox(km)
            crop = A[by0:by1 + 1, bx0:bx1 + 1].copy()
            sub_lbl = lbl[by0:by1 + 1, bx0:bx1 + 1]
            # ★ 只清"其它角色/已归附他人"的像素; label==0 是本角色的抗锯齿边缘, 必须保留
            foreign = (sub_lbl != 0) & ~np.isin(sub_lbl, keep)
            fn_ = int((foreign & (crop[..., 3] > 0)).sum())
            if fn_:
                crop[foreign, 3] = 0
            idx += 1
            out[idx] = crop
            qc[idx] = dict(row=ri + 1, src_bbox=[bx0, by0, bx1, by1],
                           size=[crop.shape[1], crop.shape[0]],
                           decors=len(stake[ci]), removed=fn_)
            print(f"    n{idx:>2}  角色#{ci:>3} {crop.shape[1]}x{crop.shape[0]}  "
                  f"装饰 {len(stake[ci])} 个  剔除邻角色像素 {fn_}")
    return out, qc


def main():
    print("=" * 94)
    print("step 1/3  按 alpha 连通域切分 (不用竖线)")
    frames, qc = split_by_components()
    if len(frames) != 13:
        print(f"  !! 期望 13 帧, 实得 {len(frames)} —— 请检查后再继续")

    print("=" * 94)
    print("step 2/3  落盘源帧 + 按动作池组装")
    os.makedirs(SRC_DIR, exist_ok=True)
    for i in sorted(frames):
        Image.fromarray(frames[i], "RGBA").save(os.path.join(SRC_DIR, f"v2n_{i:02d}.png"))
    plan_files = {}
    imported = {}
    for anim, ids in PLAN:
        names = []
        for k, src_i in enumerate(ids, 1):
            if src_i not in frames:
                print(f"  !! 缺源帧 n{src_i}, 跳过 {anim}")
                continue
            names.append(f"{anim}_{k:02d}.png")
            od = os.path.join(DST, anim)
            os.makedirs(od, exist_ok=True)
            Image.fromarray(frames[src_i], "RGBA").save(os.path.join(od, names[-1]))
            q = dict(qc[src_i]); q["src_frame"] = f"v2n_{src_i:02d}.png"
            imported[f"{anim}/{names[-1]}"] = q
        plan_files[anim] = set(names)
    with open(os.path.join(BASE, "assets", "pet_v2_alpha2_qc.json"), "w", encoding="utf-8") as f:
        json.dump(imported, f, ensure_ascii=False, indent=1)
    # 清掉不在计划内的旧文件 (只移走, 不删除)
    os.makedirs(DISC, exist_ok=True)
    moved = []
    for anim in sorted(os.listdir(DST)):
        od = os.path.join(DST, anim)
        if not os.path.isdir(od):
            continue
        keep = plan_files.get(anim, set())
        for fn in sorted(os.listdir(od)):
            if fn not in keep:
                shutil.move(os.path.join(od, fn), os.path.join(DISC, f"dropped_{anim}_{fn}"))
                moved.append(f"{anim}/{fn}")
    if moved:
        print(f"  残留 -> 废弃库 ({len(moved)}): {moved}")
    total = 0
    for anim in sorted(os.listdir(DST)):
        od = os.path.join(DST, anim)
        if not os.path.isdir(od):
            continue
        fs = sorted(f for f in os.listdir(od) if f.lower().endswith(".png"))
        total += len(fs)
        print(f"    {anim:8} {len(fs)} 帧  {fs}")
    print(f"  合计 {total} 帧 -> {DST}")

    print("=" * 94)
    print("step 3/3  自检: 每帧应只含 1 个角色级连通域; 并检查透明底")
    bad = 0
    for anim in sorted(os.listdir(DST)):
        od = os.path.join(DST, anim)
        if not os.path.isdir(od):
            continue
        for fn in sorted(os.listdir(od)):
            a = np.asarray(Image.open(os.path.join(od, fn)).convert("RGBA"))
            m = a[..., 3] > 128
            lb, _ = ndimage.label(m, structure=S8)
            sz = np.bincount(lb.ravel()); sz[0] = 0
            big = [int(s) for s in sz if s >= CHAR_MIN]
            trans = (a[..., 3] == 0).mean() * 100
            ok = (len(big) == 1) and trans > 3
            if not ok:
                bad += 1
            print(f"    {anim}/{fn:<16} {a.shape[1]:>4}x{a.shape[0]:<4} 角色级连通域 {len(big)} "
                  f"透明 {trans:5.1f}%  {'OK' if ok else '★ 异常'}")
    print(f"  异常帧数: {bad} (0 = 全部正常)")
    print("=" * 94)


if __name__ == "__main__":
    main()
