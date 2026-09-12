# -*- coding: utf-8 -*-
"""v2 素材拆帧: 按『角色自身闭合描边』分割, 不用矩形框裁切。
   流程: 深色描边 -> 连通域 -> 排除标题栏 -> 合并粘连帧按谷值分开
        -> fill_holes 得到完整轮廓(内部白色自动保留) -> 邻接非背景像素补抗锯齿边
        -> 4 倍超采样平滑 -> 按轮廓外接框输出
   输出: assets/pet_v2/{idle,sleep,drag,click,special}/
"""
import numpy as np
from PIL import Image
from scipy import ndimage
import os, shutil, json

SRC = r"C:\Users\a3564\.workbuddy\clipboard-images\clipboard-2026-09-12T05-18-41-142Z-4fa99baf.jpg"
BASE = r"C:\Users\a3564\WorkBuddy\2026-08-25-04-20-35\token-stats"
OUT = os.path.join(BASE, "assets", "pet_v2")
im = Image.open(SRC).convert("RGB")
A = np.asarray(im).astype(np.int16)
S8 = np.ones((3, 3), int)

# (组名, 面板 x0,y0,x1,y1, 期望帧数)
PANELS = [
    ("idle",    (16, 96, 935, 526), 4),
    ("sleep",   (945, 96, 1523, 526), 2),
    ("drag",    (16, 542, 597, 952), 3),
    ("click",   (604, 540, 1088, 953), 2),
    ("special", (1096, 536, 1522, 952), 2),
]

ink = A.min(axis=2) < 200


def denoise(mask, min_px=60):
    lbl, n = ndimage.label(mask, structure=S8)
    if not n:
        return mask
    szs = np.bincount(lbl.ravel())
    small = np.zeros(len(szs), bool); small[1:] = szs[1:] < min_px
    return mask & ~small[lbl]


ink = denoise(ink)
lbl_all, n_all = ndimage.label(ink, structure=S8)

info = {}
# 沙箱回收站不可用 -> 直接覆盖写出; 若上次残留多余帧, 末尾统一清理
os.makedirs(OUT, exist_ok=True)

for name, (px0, py0, px1, py1), expect in PANELS:
    panel = np.zeros_like(ink)
    panel[py0:py1 + 1, px0:px1 + 1] = True
    # 面板内背景色 (排除描边区后取中位数)
    region = A[py0:py1 + 1, px0:px1 + 1]
    excl = ndimage.binary_dilation(panel & ink, structure=S8, iterations=2)[py0:py1 + 1, px0:px1 + 1]
    bg_px = region[~excl]
    bg = np.median(bg_px.reshape(-1, 3), axis=0) if len(bg_px) else np.array([255, 255, 255])
    bg_dist = np.abs(A - bg).max(axis=2)
    not_bg = bg_dist > 16

    # 面板内描边组件
    comps = []
    labels_here = np.unique(lbl_all[panel])
    for li in labels_here:
        if li == 0:
            continue
        m = lbl_all == li
        if (m & panel).sum() < 100:
            continue
        ys, xs = np.where(m)
        comps.append(dict(mask=m, x0=int(xs.min()), x1=int(xs.max()),
                          y0=int(ys.min()), y1=int(ys.max()), px=int(m.sum())))
    # 角色 = 高>=80 且 宽高比<2.5 (标题栏宽高比 >=2.5)
    chars, decors = [], []
    for c in comps:
        is_char = ((c["y1"] - c["y0"] + 1) >= 80 and
                   (c["x1"] - c["x0"] + 1) / float(c["y1"] - c["y0"] + 1) < 2.5)
        (chars if is_char else decors).append(c)

    chars.sort(key=lambda c: c["x0"])
    base_w = float(min(c["x1"] - c["x0"] + 1 for c in chars))

    # 过宽的组件 = 多帧粘连 -> 用『内部腐蚀断桥 + 测地 Voronoi』按角色躯干分开
    def split_by_valleys(mask, k):
        """退化方案: 按列密度谷值纵向切开"""
        ys, xs = np.where(mask)
        lo, hi = int(xs.min()), int(xs.max())
        w = hi - lo + 1
        cols = mask.sum(axis=0)
        cuts = []
        for j in range(1, k):
            ctr = lo + int(w * j / k)
            span = max(6, int(w * 0.16))
            a, b = max(lo + 1, ctr - span), min(hi - 1, ctr + span)
            cuts.append(a + int(np.argmin(cols[a:b + 1])))
        cuts = sorted(set(cuts))
        edges = [lo - 1] + cuts + [hi + 1]
        parts = []
        for j in range(len(edges) - 1):
            p = mask.copy()
            p[:, :edges[j] + 1] = False
            p[:, edges[j + 1]:] = False
            ys2, xs2 = np.where(p)
            p[:, :int(xs2.min())] = False
            parts.append(p)
        return parts

    def split_by_bodies(mask, k):
        """主方案: 对『实心轮廓』做腐蚀 -> 细桥(尾巴/发丝搭接)断开 -> 每个角色一个种子
        -> 测地 BFS 把桥上的像素各归其主。角色之间只通过细笔画相连时, 各自都能完整还原;
        真正互相遮挡的部分本来就画在对方身上, 无法也不需要还原。"""
        from collections import deque
        sil = ndimage.binary_fill_holes(mask)
        for t in (2, 3, 4, 5, 6, 8, 10, 12):
            er = ndimage.binary_erosion(sil, structure=S8, iterations=t)
            lb, nn = ndimage.label(er, structure=S8)
            if nn < 1:
                continue
            szs = np.bincount(lb.ravel())
            keep = [i for i in range(1, nn + 1) if szs[i] >= 300]
            if len(keep) < k:
                continue
            if len(keep) > k:                       # 取最大的 k 个(其余是零碎)
                keep = sorted(keep, key=lambda i: -szs[i])[:k]
            lab = np.zeros(sil.shape, np.int32)
            dq = deque()
            for sid, i in enumerate(keep, 1):
                ys, xs = np.where(lb == i)
                for yy, xx in zip(ys, xs):
                    lab[yy, xx] = sid
                    dq.append((yy, xx))
            while dq:
                y, x = dq.popleft()
                for ny, nx in ((y-1, x), (y+1, x), (y, x-1), (y, x+1),
                               (y-1, x-1), (y-1, x+1), (y+1, x-1), (y+1, x+1)):
                    if 0 <= ny < sil.shape[0] and 0 <= nx < sil.shape[1] \
                       and sil[ny, nx] and lab[ny, nx] == 0:
                        lab[ny, nx] = lab[y, x]
                        dq.append((ny, nx))
            parts = []
            for sid in range(1, len(keep) + 1):
                p = lab == sid
                if p.sum() < 500:
                    continue
                p = ndimage.binary_fill_holes(p) & sil
                parts.append(p)
            if len(parts) == k:
                return parts
        return split_by_valleys(mask, k)

    frames = []
    for c in chars:
        w = c["x1"] - c["x0"] + 1
        k = max(1, int(round(w / base_w)))
        if k == 1:
            frames.append(c["mask"])
        else:
            frames.extend(split_by_bodies(c["mask"], k))
    frames = [f for f in frames if f.sum() > 500]
    # 兜底: 仍不足期望帧数 -> 反复把最宽的切开
    while len(frames) < expect:
        widest = max(range(len(frames)), key=lambda i: (lambda ys, xs: xs.max() - xs.min() + 1)(*np.where(frames[i])))
        ys, xs = np.where(frames[widest])
        if (xs.max() - xs.min() + 1) < 1.4 * base_w:
            break
        frames[widest:widest + 1] = split_by_valleys(frames[widest], 2)
    print(f"[{name}] 组件 {len(comps)} (角色 {len(chars)}) -> 帧 {len(frames)} (期望 {expect})")


    # 装饰件(水花/星星/气泡) 归到最近的帧
    frame_boxes = []
    for f in frames:
        ys, xs = np.where(f)
        frame_boxes.append([int(xs.min()), int(xs.max()), int(ys.min()), int(ys.max())])
    attach = [[] for _ in frames]
    for d in decors:
        if (d["y1"] - d["y0"] + 1) < 8 or (d["x1"] - d["x0"] + 1) / max(1, (d["y1"] - d["y0"] + 1)) >= 2.5:
            continue          # 标题栏/细线 不要
        if d["px"] < 40:
            continue
        cx = (d["x0"] + d["x1"]) / 2.0
        cy = (d["y0"] + d["y1"]) / 2.0
        best, bd = -1, 1e9
        for i, b in enumerate(frame_boxes):
            dx = max(b[0] - cx, 0, cx - b[1])
            dy = max(b[2] - cy, 0, cy - b[3])
            dist = (dx * dx + dy * dy) ** 0.5
            if dist < bd:
                bd, best = dist, i
        if best >= 0 and bd <= 22:
            attach[best].append(d)

    od = os.path.join(OUT, name)
    os.makedirs(od, exist_ok=True)
    for i, f in enumerate(frames):
        sil = ndimage.binary_fill_holes(f)
        # ---- 发丝间隙清除: 小封闭腔 且 颜色≈面板背景 且 贴近轮廓外侧 -> 透明
        pockets = sil & ~f
        pl, pn = ndimage.label(pockets, structure=S8)
        d_out = ndimage.distance_transform_edt(sil)
        if pn:
            psz = np.bincount(pl.ravel())
            drop = np.zeros_like(sil)
            reg = A[py0:py1 + 1, px0:px1 + 1]
            for j in range(1, pn + 1):
                m = pl == j
                if psz[j] > 900:
                    continue
                px = A[m]
                bg_like = float((np.abs(px - bg).max(axis=1) <= 10).mean())
                if bg_like >= 0.55 and float(d_out[m].max()) <= 6.0:
                    drop |= m
            sil = sil & ~drop
        for d in attach[i]:                       # 贴上邻近装饰件
            dm = ndimage.binary_fill_holes(d["mask"])
            sil |= dm
        # 轮廓外扩 1px 收进抗锯齿像素 (只收"非背景"的)
        ring = ndimage.binary_dilation(sil, structure=S8, iterations=1) & not_bg
        sil = sil | ring
        ys, xs = np.where(sil)
        bx0, bx1 = max(0, int(xs.min()) - 1), min(A.shape[1] - 1, int(xs.max()) + 1)
        by0, by1 = max(0, int(ys.min()) - 1), min(A.shape[0] - 1, int(ys.max()) + 1)
        m = sil[by0:by1 + 1, bx0:bx1 + 1]
        rgb = A[by0:by1 + 1, bx0:bx1 + 1].astype(np.uint8)
        # ---- 边缘平滑: 形态学去毛刺 -> 4 倍超采样 + 高斯 -> 中值滤波 -> 柔和抗锯齿边
        m = ndimage.binary_opening(m, structure=S8, iterations=1)
        m = ndimage.binary_closing(m, structure=S8, iterations=1)
        up = 4
        big = ndimage.zoom(m.astype(np.float32), up, order=1)
        big = ndimage.gaussian_filter(big, 1.3)
        soft = np.clip((big - 0.32) / 0.34, 0.0, 1.0)
        a2 = (np.clip(ndimage.zoom(soft, 1.0 / up, order=1), 0, 1) * 255).astype(np.uint8)
        a2 = ndimage.median_filter(a2, size=3)
        far = ndimage.distance_transform_edt(m) >= 2.0
        a2[far] = 255
        # 清掉与主体不相连的透明度碎屑 (毛刺残留)
        av = a2 > 40
        al, an = ndimage.label(av, structure=S8)
        if an > 1:
            asz = np.bincount(al.ravel())
            main = int(asz.argmax())
            near_m = ndimage.binary_dilation(al == main, structure=S8, iterations=3)
            for j in range(1, an + 1):
                if j == main or asz[j] >= 40:
                    continue
                mj = al == j
                if not (mj & near_m).any():
                    a2[mj] = 0
        out = Image.fromarray(np.dstack([rgb, a2]), "RGBA")
        bb = out.getbbox()
        if bb:
            out = out.crop(bb)
        out.save(os.path.join(od, f"{name}_{i + 1:02d}.png"))
        info[f"{name}_{i + 1:02d}"] = dict(box=[bx0, bx1, by0, by1], size=[out.width, out.height])

n = sum(len(os.listdir(os.path.join(OUT, g))) for g in os.listdir(OUT))
print("frames:", n)
json.dump(info, open(os.path.join(BASE, "assets", "pet_v2_windows.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)

# 自检拼图 (深/浅双底)
from PIL import ImageDraw
for g in sorted(os.listdir(OUT)):
    od = os.path.join(OUT, g)
    files = sorted(os.listdir(od))
    TH, pads, tiles = 260, 16, []
    for fn in files:
        f = Image.open(os.path.join(od, fn)).convert("RGBA")
        r = TH / f.height
        tiles.append((fn[:-4], f.resize((max(1, int(f.width * r)), TH), Image.LANCZOS)))
    W = sum(t.width + pads for _, t in tiles) + pads
    sheet = Image.new("RGBA", (W, TH * 2 + 60), (52, 56, 64, 255))
    d = ImageDraw.Draw(sheet)
    x = pads
    for nm, t in tiles:
        dk = Image.new("RGBA", t.size, (30, 34, 42, 255)); dk.alpha_composite(t)
        lt = Image.new("RGBA", t.size, (246, 248, 252, 255)); lt.alpha_composite(t)
        sheet.alpha_composite(dk, (x, 26)); sheet.alpha_composite(lt, (x, TH + 42))
        d.text((x + 2, 8), nm, fill=(255, 214, 110, 255))
        x += t.width + pads
    sheet.convert("RGB").save(os.path.join(os.path.dirname(OUT), "_v2_%s.png" % g))
print("self-check sheets saved")
