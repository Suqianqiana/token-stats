# -*- coding: utf-8 -*-
"""V3 补充素材 · 结构探测 (只读, 不改任何文件)。

回答四个问题:
  ① 每张图有几个角色 (连通域计数 + 宽度法)
  ② 行带怎么分 (行投影)
  ③ 能不能用竖线切 (列投影的"干净空隙"够不够) —— 不够就必须走连通域切分
  ④ 透明区是否有噪点残留 (半透明散点), 需要清理的量级
"""
import numpy as np
from PIL import Image
from scipy import ndimage

S8 = np.ones((3, 3), bool)
P = [r"C:\Users\a3564\Downloads\ChatGPT Image 2026年9月17日 03_19_52 (1).png",
     r"C:\Users\a3564\Downloads\ChatGPT Image 2026年9月17日 03_19_53 (2).png"]


def bands(prof, thr, min_w):
    """把一维投影按 >thr 切成连续段, 过滤掉窄于 min_w 的"""
    on = prof > thr
    out = []
    i = 0
    n = len(on)
    while i < n:
        if on[i]:
            j = i
            while j + 1 < n and on[j + 1]:
                j += 1
            if j - i + 1 >= min_w:
                out.append((i, j))
            i = j + 1
        else:
            i += 1
    return out


def gaps(prof, thr, min_w):
    """投影里的"干净空隙"段 (>min_w 宽的空段)"""
    off = prof <= thr
    out, i, n = [], 0, len(off)
    while i < n:
        if off[i]:
            j = i
            while j + 1 < n and off[j + 1]:
                j += 1
            if j - i + 1 >= min_w:
                out.append((i, j, j - i + 1))
            i = j + 1
        else:
            i += 1
    return out


for idx, path in enumerate(P, 1):
    im = Image.open(path).convert("RGBA")
    a = np.asarray(im)
    al = a[..., 3]
    H, W = al.shape
    print("=" * 72)
    print("图%d  %dx%d" % (idx, W, H))
    fg = al > 128

    # ---- 连通域 ----
    lbl, n = ndimage.label(fg, S8)
    areas = ndimage.sum(fg, lbl, range(1, n + 1))
    order = np.argsort(areas)[::-1]
    big = [(int(o) + 1, int(areas[o])) for o in order if areas[o] >= 20000]
    mid = [(int(o) + 1, int(areas[o])) for o in order if 8 <= areas[o] < 20000]
    print("  连通域: 总 %d | 面积>=20000 的 %d 个 | 8~20000 的小件 %d 个"
          % (n, len(big), len(mid)))
    print("  最大 8 块面积:", [a2 for _, a2 in big[:8]])
    if big:
        med = int(np.median([a2 for _, a2 in big[:max(1, len(big) // 2)]]))
        print("  大块面积中位数 %d → 角色数估计(面积法) ≈ %.1f" % (med, sum(a2 for _, a2 in big) / med))
    # 宽度法
    ws = []
    for i2, _ in big:
        ys, xs = np.where(lbl == i2)
        ws.append((xs.max() - xs.min() + 1, ys.max() - ys.min() + 1, i2))
    if ws:
        wmed = int(np.median([w for w, _, _ in ws]))
        print("  大块宽度中位数 %d → 宽度比:" % wmed,
              ["%.2f" % (w / wmed) for w, _, _ in ws[:14]])
        print("  (比值 >=1.45 的块 = 两个角色粘连)")

    # ---- 行带 ----
    rp = fg.sum(1)
    rb = bands(rp, max(2, W // 400), 6)
    rb = [(y0, y1) for y0, y1 in rb if y1 - y0 >= 20]
    print("  行带: %d 条" % len(rb), [(y0, y1, y1 - y0 + 1) for y0, y1 in rb])

    # ---- 每行带的竖切可行性 ----
    for bi, (y0, y1) in enumerate(rb, 1):
        sub = fg[y0:y1 + 1]
        cp = sub.sum(0)
        gs = [g for g in gaps(cp, 0, 6) if g[0] > 2 and g[1] < W - 3]
        inner = gs
        nfig = len(bands(cp, max(2, (y1 - y0) // 60), 12))
        print("    行%d y=%d~%d  内部干净空隙 %d 个 %s"
              % (bi, y0, y1, len(inner), [g[2] for g in inner][:12]))
        print("         投影段落数(粗估对象数)=%d → 竖切需要 %d 个空隙, %s"
              % (nfig, max(0, nfig - 1), "够" if len(inner) >= nfig - 1 else "★不够, 必裁断"))

    # ---- 透明区噪点 ----
    semi = (al > 0) & (al <= 128)
    core = al > 200
    d = ndimage.distance_transform_edt(~core)
    noise = semi & (d > 12)          # 离实体 12px 之外的半透明像素 = 背景噪点
    print("  半透明像素(0<a<=128)总数 %d | 其中离实体>12px 的噪点 %d (%.1f%%)"
          % (int(semi.sum()), int(noise.sum()), 100.0 * noise.sum() / max(1, semi.sum())))
    if noise.sum():
        ys, xs = np.where(noise)
        print("     噪点分布 y:%d~%d x:%d~%d" % (ys.min(), ys.max(), xs.min(), xs.max()))
    # 全不透明确认
    print("  alpha=255 的像素数 %d | alpha>=250 的 %d" % (int((al == 255).sum()), int((al >= 250).sum())))
