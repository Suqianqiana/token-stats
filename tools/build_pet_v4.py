# -*- coding: utf-8 -*-
"""V4 素材 ("deepseek娘V4Pro") 构建脚本 —— 零抠图。

源 = `ChatGPT Image 2026年9月14日 07_20_09.png` (PNG RGBA 1536x1024, 背景真透明)
版面: 2 行 x 6 列 = 12 帧

【切分策略 (第40轮修正) —— 不再用"竖向切线"】
问题: 行1 的第 3/4/5 个角色在 x 方向**互相重叠**(c3 到 x709, c4 从 x699 起, c5 从 x969 起),
      任何竖向切线都会**裁断**角色。浅浅猫正是为此亲自重做了这几帧。
正解: 以 **alpha 连通域**为单位切分 —— 每个角色取自己连通域(含附属小装饰件)的 bbox,
      并把落入裁剪框内的**其它连通域像素置为透明**, 从而既不裁断、也不带入邻角色的边角。
      实测: 行1 的 c3/c4/c5 本就是三个独立连通域, 只是投影重叠 -> 可完美分开。

【逐帧优先采用浅浅猫处理过的版本】
  USER_FIXED = {3,4,5,9} —— 她 2026-09-14 12:37/12:39/12:41 等时间点亲自重做并覆盖到
  `assets/pet_v5/setC/` 的帧。这些帧是她的标准, **永远优先采用**。
  其余帧用本脚本的连通域切分生成(已修正为不裁断)。
  若某帧在 pet_v5/setC 里但**丢了透明底**(alpha==0 占比 <5%), 只打印告警、不静默替代。

动作映射 (浅浅猫 2026-09-14 更正后):
  C1 C2 C3          -> idle_01..03   (待机, idle_01 为默认待机)
  C4                -> sleep_01      (睡觉)
  C5                -> wake_01       (睡醒)
  C6                -> drag_01       (拖拽)
  C7 C8 C9 C10 C11  -> click_01..05  (点击, 共 5 帧)
  C12               -> sidle_01      (特殊待机)

用法: python tools/build_pet_v4.py   (幂等, 可反复运行)
"""
import os
import shutil

import numpy as np
from PIL import Image
from scipy import ndimage

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = "C:/Users/a3564/Downloads/ChatGPT Image 2026年9月14日 07_20_09.png"
P5C = os.path.join(BASE, "assets", "pet_v5", "setC")
SRC_DIR = os.path.join(BASE, "assets", "pet_v4_src")
DST = os.path.join(BASE, "assets", "pet_v4")
DISC = os.path.join(BASE, "assets", "pet_v4_discard")

ROWS = [(35, 475), (555, 936)]      # 两行的 y 范围(行投影的空隙之间)
PER_ROW = 6
S8 = np.ones((3, 3), int)

CHAR_MIN = 20000        # 面积 >= 此值 = 角色本体
DEC_MIN = 8             # 面积 >= 此值且 < CHAR_MIN = 装饰小件(音符/星星等)
DEC_MAXDIST = 90        # 装饰件到最近角色的最大距离(px), 超出则丢弃
MIN_TRANS = 5.0         # 透明像素占比低于此值 -> 判定"丢了透明底"

# 浅浅猫亲自重做过的帧 —— 永远优先采用她 pet_v5/setC 里的版本
USER_FIXED = {3, 4, 5, 9}

PLAN = [
    ("idle",  [1, 2, 3]),
    ("sleep", [4]),
    ("wake",  [5]),
    ("drag",  [6]),
    ("click", [7, 8, 9, 10, 11]),
    ("sidle", [12]),
]


def _bbox(mask):
    ys, xs = np.where(mask)
    return int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())


def _gap_dist(a, b):
    """两个 bbox 之间的最短水平/垂直距离(重叠为 0)。"""
    dx = max(a[0] - b[2], 0, b[0] - a[2])
    dy = max(a[1] - b[3], 0, b[1] - a[3])
    return (dx * dx + dy * dy) ** 0.5


def split_by_components():
    """按 alpha 连通域逐角色切分 (不裁断、不带邻角色边角)。"""
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
    idx = 0
    for ri, (y0, y1) in enumerate(ROWS):
        inband = {i: v for i, v in info.items()
                  if y0 <= (v["bbox"][1] + v["bbox"][3]) / 2 <= y1}
        chars = sorted([(i, v) for i, v in inband.items() if v["size"] >= CHAR_MIN],
                       key=lambda t: (t[1]["bbox"][0] + t[1]["bbox"][2]) / 2)
        decors = [(i, v) for i, v in inband.items() if v["size"] < CHAR_MIN]
        if len(chars) != PER_ROW:
            print(f"  !! 行{ri+1} 识别到 {len(chars)} 个角色 (期望 {PER_ROW}), 请检查")
        stake = {i: [] for i, _ in chars}
        for di, dv in decors:
            best, bd = None, 1e18
            for ci, cv in chars:
                d = _gap_dist(dv["bbox"], cv["bbox"])
                if d < bd:
                    best, bd = ci, d
            if best is not None and bd <= DEC_MAXDIST:
                stake[best].append(di)
        print(f"  行{ri+1}: 角色 {len(chars)} 个, 装饰件 {len(decors)} 个"
              f"(归附 {sum(len(v) for v in stake.values())}, 丢弃 {len(decors)-sum(len(v) for v in stake.values())})")
        for si, (ci, cv) in enumerate(chars):
            keep = [ci] + stake[ci]
            keep_mask = np.isin(lbl, keep)
            bx0, by0, bx1, by1 = _bbox(keep_mask)
            crop = A[by0:by1 + 1, bx0:bx1 + 1].copy()
            sub_lbl = lbl[by0:by1 + 1, bx0:bx1 + 1]
            # ★ 只清除"属于其它角色/已归附到其它角色的装饰件"的像素。
            #   绝不能清 label==0 —— 那正是本角色自己的半透明抗锯齿边缘(alpha<=128)!
            #   也保留未归附的极小碎片(可能是角色的细发丝/贴身小件)。
            foreign = (sub_lbl != 0) & ~np.isin(sub_lbl, keep)
            foreign_n = int((foreign & (crop[..., 3] > 0)).sum())
            if foreign_n:
                crop[foreign, 3] = 0
            idx += 1
            out[idx] = crop
            print(f"    C{idx:>2}  角色#{ci:>3} {crop.shape[1]}x{crop.shape[0]}  "
                  f"含装饰 {len(stake[ci])} 个  剔除邻角色像素 {foreign_n}")
    return out


def main():
    print("=" * 96)
    print("step 1/2  收集 12 帧")
    fresh = split_by_components()
    os.makedirs(SRC_DIR, exist_ok=True)
    worn = []
    for i in range(1, 13):
        src_p5 = os.path.join(P5C, f"setC_{i:02d}.png")
        arr, src_kind = None, ""
        if i in USER_FIXED and os.path.exists(src_p5):
            cand = np.asarray(Image.open(src_p5).convert("RGBA"))
            trans = float((cand[..., 3] == 0).mean() * 100)
            if trans >= MIN_TRANS:
                arr, src_kind = cand, "浅浅猫版"
            else:
                worn.append(i)
                print(f"  ⚠ setC_{i:02d} 是浅浅猫处理过的帧, 但透明像素只有 {trans:.1f}%"
                      f"(丢了透明底) -> 回退连通域切分; **这件事要汇报给她**")
        if arr is None:
            arr = fresh.get(i)
            src_kind = src_kind or "连通域切分"
        if arr is None:
            print(f"  !! setC_{i:02d} 取不到, 跳过")
            continue
        Image.fromarray(arr, "RGBA").save(os.path.join(SRC_DIR, f"setC_{i:02d}.png"))
        print(f"  setC_{i:02d}: {src_kind}  {arr.shape[1]}x{arr.shape[0]}")
    if worn:
        print(f"  ⚠ 需向浅浅猫汇报: 这些她处理过的帧丢了透明底 -> {worn}")

    print("=" * 96)
    print("step 2/2  按动作池组装")
    plan_files = {}
    for anim, ids in PLAN:
        names = []
        for k, src_i in enumerate(ids, 1):
            sf = os.path.join(SRC_DIR, f"setC_{src_i:02d}.png")
            if not os.path.exists(sf):
                print(f"  !! 缺源帧 setC_{src_i:02d}.png, 跳过 {anim}")
                continue
            names.append(f"{anim}_{k:02d}.png")
            od = os.path.join(DST, anim)
            os.makedirs(od, exist_ok=True)
            shutil.copy2(sf, os.path.join(od, names[-1]))
        plan_files[anim] = set(names)
    os.makedirs(DISC, exist_ok=True)
    moved = []
    for anim in sorted(os.listdir(DST)):
        od = os.path.join(DST, anim)
        if not os.path.isdir(od):
            continue
        keep = plan_files.get(anim, set())
        for fn in sorted(os.listdir(od)):
            if fn not in keep:
                shutil.move(os.path.join(od, fn),
                            os.path.join(DISC, f"dropped_{anim}_{fn}"))
                moved.append(f"{anim}/{fn}")
    if moved:
        print(f"  残留清理 -> 废弃库 ({len(moved)} 个): {moved}")
    total = 0
    for anim in sorted(os.listdir(DST)):
        od = os.path.join(DST, anim)
        if not os.path.isdir(od):
            continue
        fs = sorted(f for f in os.listdir(od) if f.lower().endswith(".png"))
        total += len(fs)
        print(f"    {anim:6} {len(fs)} 帧  {fs}")
    print(f"  合计 {total} 帧 -> {DST}")
    print("=" * 96)


if __name__ == "__main__":
    main()
