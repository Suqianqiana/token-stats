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
from collections import deque

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
    mn_all = A.min(axis=2)
    sat_all = A.max(axis=2) - mn_all
    # bg_like = 淡蓝白系像素 (亮 + 低饱和 + 偏蓝): 面板底色/背景缝隙/阴影腔; 皮肤(暖)/头发(深蓝) 不属
    bg_like = ((mn_all >= 195) & (sat_all <= 38) & ((A[..., 2] - A[..., 0]) >= 2))
    reach = np.zeros(A.shape[:2], bool)      # 从帧边界对 bg_like 泛洪 = 与外部背景连通区
    dq = deque()
    hA, wA = A.shape[:2]
    for x in np.where(bg_like[0, :] | bg_like[hA - 1, :])[0]:
        if not reach[0, x]:
            reach[0, x] = True; dq.append((0, x))
        if not reach[hA - 1, x]:
            reach[hA - 1, x] = True; dq.append((hA - 1, x))
    for y in np.where(bg_like[:, 0] | bg_like[:, wA - 1])[0]:
        if not reach[y, 0]:
            reach[y, 0] = True; dq.append((y, 0))
        if not reach[y, wA - 1]:
            reach[y, wA - 1] = True; dq.append((y, wA - 1))
    while dq:
        y, x = dq.popleft()
        for ny, nx in ((y-1, x), (y+1, x), (y, x-1), (y, x+1),
                       (y-1, x-1), (y-1, x+1), (y+1, x-1), (y+1, x+1)):
            if 0 <= ny < hA and 0 <= nx < wA and not reach[ny, nx] and bg_like[ny, nx]:
                reach[ny, nx] = True; dq.append((ny, nx))
    for i, f in enumerate(frames):
        # ---- 去掉贴纸白描边 (浅浅猫指定): 白描边与面板底色同为白色且相连,
        #   从帧窗口边界对『浅色像素』泛洪 -> 面板底色 + 白描边 + 流进发丝缝的白料 一次全透明;
        #   深色描边挡住泛洪 -> 角色主体 (含围裙等内部白) 完整保留。
        #   passable 排除描边外扩 1px, 防止 JPEG 断点让泛洪漏进衣服内部。
        ys0, xs0 = np.where(f)
        wx0 = max(0, int(xs0.min()) - 6); wx1 = min(A.shape[1] - 1, int(xs0.max()) + 6)
        wy0 = max(0, int(ys0.min()) - 6); wy1 = min(A.shape[0] - 1, int(ys0.max()) + 6)
        sub = A[wy0:wy1 + 1, wx0:wx1 + 1]
        smn = sub.min(axis=2); ssat = sub.max(axis=2) - smn
        light = (smn >= 222) & (ssat <= 30)
        blocked = ndimage.binary_dilation(f[wy0:wy1 + 1, wx0:wx1 + 1], structure=S8, iterations=1)
        passable = light & ~blocked
        hh, ww = passable.shape
        rch = np.zeros((hh, ww), bool)
        dq2 = deque()
        for x in range(ww):
            for y in (0, hh - 1):
                if passable[y, x] and not rch[y, x]:
                    rch[y, x] = True; dq2.append((y, x))
        for y in range(hh):
            for x in (0, ww - 1):
                if passable[y, x] and not rch[y, x]:
                    rch[y, x] = True; dq2.append((y, x))
        while dq2:
            y, x = dq2.popleft()
            for ny, nx in ((y-1, x), (y+1, x), (y, x-1), (y, x+1)):
                if 0 <= ny < hh and 0 <= nx < ww and not rch[ny, nx] and passable[ny, nx]:
                    rch[ny, nx] = True; dq2.append((ny, nx))
        sil = ndimage.binary_fill_holes(f)
        sil[wy0:wy1 + 1, wx0:wx1 + 1] &= ~rch          # 白描边/背景/缝里的白料 -> 透明
        # ---- 发丝间隙的封闭腔清除 (只在"顶部/两侧发丝区"生效, 且必须远离腿部区)
        #   判据: 浅腔(到外轮廓距离中位<=28) + 亮 + 偏蓝不偏暖 + 腔内无描边 + 非帧内最大腔(围裙)
        #   腿/白袜/鞋 = 位于画面下部 30% 的腔 -> 一律跳过 (避免"腿被扣没")
        ink_core = ndimage.binary_erosion(f, structure=S8, iterations=2)
        b_r = A[..., 2] - A[..., 0]
        dist_out = ndimage.distance_transform_edt(sil)
        _ys0, _ = np.where(sil)
        leg_guard = int(_ys0.max() - (sil.shape[0] if False else 0))  # 占位, 下面按 bbox 计算
        y_top, y_bot = int(_ys0.min()), int(_ys0.max())
        leg_y = y_bot - int((y_bot - y_top) * 0.30)     # 下方 30% 视为腿部区
        for _ in range(2):
            pockets = sil & ~f
            pl, pn = ndimage.label(pockets, structure=S8)
            if not pn:
                break
            psz = np.bincount(pl.ravel())
            cand = [j for j in range(1, pn + 1) if psz[j] >= 30
                    and float((f & (pl == j)).sum()) / psz[j] < 0.02
                    and float(A[pl == j].min(axis=1).mean()) >= 210
                    and float(b_r[pl == j].mean()) >= -2
                    and float(sat_all[pl == j].mean()) <= 32]
            biggest = max(cand, key=lambda j: psz[j]) if cand else None
            drop = np.zeros_like(sil)
            for j in cand:
                m = pl == j
                if j == biggest:                                   # 围裙 = 帧内最大腔
                    continue
                if float(np.median(dist_out[m])) > 28:             # 深腔 -> 衣物/身体内部
                    continue
                yy, _xx = np.where(m)
                if int(yy.mean()) > leg_y:                         # 腿部区 -> 不碰
                    continue
                drop |= m
            if drop.any():
                print(f"      [{name}_{i+1:02d}] 删腔总像素 {int(drop.sum())}")
            if not drop.any() or float(drop.sum()) > 0.25 * max(1.0, float(sil.sum())):
                break
            sil = sil & ~drop
        for d in attach[i]:                       # 贴上邻近装饰件
            dm = d["mask"]
            # 实体装饰(鲸鱼/星星/爱心: 描边密实, 填充率>=0.16) -> 填洞保住内部图案;
            # 圈状描边(呆毛圈: 细环, 填充率低) -> 只贴描边本身, 圈内背景保持透明。
            ys_d, xs_d = np.where(dm)
            bbox = max(1, (ys_d.max() - ys_d.min() + 1) * (xs_d.max() - xs_d.min() + 1))
            if float(dm.sum()) / bbox >= 0.16:
                dm = ndimage.binary_fill_holes(dm)
            sil |= dm
        # 注意: 不再向轮廓外扩任何像素 —— 实测描边外侧那层"过渡像素"(mn 160~250)
        # 正是深底上看得见的白晕/毛刺来源, 一律不收。
        # 再把最外圈的『浅色且低饱和(近似底色)』边界像素选择性削掉 —— 深色描边与
        # 发丝本体(偏蓝, 饱和度高) 一律不动, 避免把左侧头发外缘削坏。
        for _ in range(2):
            inner = ndimage.binary_erosion(sil, structure=S8, iterations=1)
            edge = sil & ~inner
            if not edge.any():
                break
            light_edge = edge & (mn_all >= 225) & (sat_all <= 25)
            if not light_edge.any():
                break
            sil = sil & ~light_edge
        ys, xs = np.where(sil)
        bx0, bx1 = max(0, int(xs.min()) - 1), min(A.shape[1] - 1, int(xs.max()) + 1)
        by0, by1 = max(0, int(ys.min()) - 1), min(A.shape[0] - 1, int(ys.max()) + 1)
        m = sil[by0:by1 + 1, bx0:bx1 + 1]
        rgb = A[by0:by1 + 1, bx0:bx1 + 1].astype(np.uint8)
        # ---- 边缘抗锯齿: 4 倍上采样后用『上采样图的亮度』重新判定描边边界
        #   (比"模糊二值掩码"更准: 直接利用原图的灰度过渡, 得到真亚像素轮廓)
        m = ndimage.binary_opening(m, structure=S8, iterations=1)
        m = ndimage.binary_closing(m, structure=S8, iterations=1)
        up = 4
        big_rgb = np.dstack([ndimage.zoom(rgb[..., c].astype(np.float32), up, order=1)
                             for c in range(3)])
        big_sil = ndimage.zoom(m.astype(np.float32), up, order=1)
        # ★ 关键修复 (第22轮): 这里原本是
        #       ink4 = ndimage.binary_fill_holes(ink4) | (big_sil > 0.85)
        #   binary_fill_holes 会把"已被腔判据正确删掉的封闭浅色区"——
        #   呆毛与头发围成的圈、被发丝包住的缝 —— 又重新填回不透明,
        #   使前面所有腔清除工作全部被抵消, 表现为"每帧都有圈扣不掉"。
        #   改为只用掩码 m 自身兜底内部: m 里保留 -> 不透明; m 里已删 -> 保持透明。
        big_sil = ndimage.gaussian_filter(big_sil, 1.0)            # 亚像素: 边缘天然渐变
        ink4 = (big_rgb.min(axis=2) < 200) & (big_sil > 0.30)      # 上采样后的深色描边
        # 深色描边处拉满(描边保持清晰); 其余按掩码的平滑值 -> 得到真亚像素抗锯齿边
        soft4 = np.maximum(big_sil, ink4.astype(np.float32) * 0.9)
        soft4 = ndimage.gaussian_filter(soft4, 0.7)
        soft = np.clip((soft4 - 0.40) / 0.40, 0.0, 1.0)
        a2 = (np.clip(ndimage.zoom(soft, 1.0 / up, order=1), 0, 1) * 255).astype(np.uint8)
        a2 = ndimage.median_filter(a2, size=3)
        far = ndimage.distance_transform_edt(m) >= 2.0
        a2[far] = 255
        # ---- 细缝半透明残料清除 (不再做全图对比拉伸 —— 那会把抗锯齿边一起二值化,
        #   表现为"边缘硬切/毛刺"): 只对【近似底色 且 3x3 邻域里 >=5 个透明】的
        #   中低 alpha 像素归零 —— 细缝(1~2px)满足; 轮廓边缘只有 3~4 个透明邻居, 不满足,
        #   因此亚像素抗锯齿被完整保留。白袜/腿等细结构邻域多为不透明, 也安全。
        smn = rgb.min(axis=2).astype(np.int16)
        ssat = (rgb.max(axis=2).astype(np.int16) - smn)
        transp = (a2 == 0).astype(np.uint8)
        nb_trans = np.zeros_like(transp, np.int16)
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dy == 0 and dx == 0:
                    continue
                nb_trans += np.roll(np.roll(transp, dy, axis=0), dx, axis=1)
        a2[(a2 > 0) & (a2 < 250) & (smn >= 232) & (ssat <= 22) & (nb_trans >= 5)] = 0
        # 只在紧贴透明区的最外 1 圈, 把"近似底色"的不透明像素削掉 (统一处理, 不分区域)
        for _ in range(2):
            objm = a2 > 0
            edge = objm & ~ndimage.binary_erosion(objm, structure=S8, iterations=1)
            if not edge.any():
                break
            kill = edge & (smn >= 228) & (ssat <= 24)
            if not kill.any():
                break
            a2[kill] = 0
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
