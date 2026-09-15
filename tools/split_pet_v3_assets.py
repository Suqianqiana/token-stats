# -*- coding: utf-8 -*-
"""v3 素材抠图: 处理"2 行 x 5 列 + 蓝色圆角标签"的新版精灵图。
   流程(沿用 v2 已验收的抠图管线):
     1. 白底检测 -> 行带分割: 高带=角色行, 矮带=蓝色标签行(整条排除)
     2. 角色行内 ink 连通域 -> 面积>=15000 为角色; 小图标为装饰件 -> 归附最近角色
     3. 窗口裁剪(严格限制在角色行带内, 防止吃到标签) -> 白描边/背景泛洪去透明
     4. 封闭腔清除(第24轮原版: depth>28 深腔保护, 护眼白/衣白/皮肤; 腿部区不碰; 小腔高ink护栏)
     5. 贴装饰件 -> 削浅色边 -> 4x 超采样真亚像素 alpha -> 细缝残料清除
     6. 连通性清理 -> 边缘去背景污染(只换色不动 alpha)
   输出: assets/pet_v3/<set>/<set>_NN.png  (NN = 行优先 01..10)
"""
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage
import os, json
from collections import deque

BASE = r"C:\Users\a3564\WorkBuddy\2026-08-25-04-20-35\token-stats"
OUT = os.path.join(BASE, "assets", "pet_v3")
S8 = np.ones((3, 3), int)

SETS = [
    ("setA", r"C:\Users\a3564\.workbuddy\clipboard-images\clipboard-2026-09-13T21-46-03-551Z-a70b73fe.jpg"),
    ("setB", r"C:\Users\a3564\.workbuddy\clipboard-images\clipboard-2026-09-13T21-46-03-556Z-1fb214d8.jpg"),
]

os.makedirs(OUT, exist_ok=True)
info, qc = {}, {}


def denoise(mask, min_px=60):
    lbl, n = ndimage.label(mask, structure=S8)
    if not n:
        return mask
    szs = np.bincount(lbl.ravel())
    small = np.zeros(len(szs), bool); small[1:] = szs[1:] < min_px
    return mask & ~small[lbl]


def row_bands(mask, thr=10, min_h=4):
    rows = mask.sum(axis=1)
    on = rows > thr
    out, s = [], None
    for i, x in enumerate(on):
        if x and s is None:
            s = i
        if not x and s is not None:
            out.append((s, i - 1)); s = None
    if s is not None:
        out.append((s, len(on) - 1))
    return [b for b in out if b[1] - b[0] + 1 >= min_h]


for name, src in SETS:
    A = np.asarray(Image.open(src).convert("RGB")).astype(np.int16)
    H, W = A.shape[:2]
    mn_all = A.min(axis=2)
    sat_all = A.max(axis=2) - mn_all
    b_r = A[..., 2] - A[..., 0]

    ink = denoise(mn_all < 200)
    notbg = np.abs(A - np.array([255, 255, 255])).max(axis=2) > 16

    bands = row_bands(notbg, thr=10, min_h=4)
    char_bands = [b for b in bands if b[1] - b[0] + 1 >= 150]
    lab_bands = [b for b in bands if b[1] - b[0] + 1 < 150]
    print(f"[{name}] 行带 {bands} -> 角色带 {char_bands} / 标签带 {lab_bands}")

    # 角色组件: 只在角色带内的 ink 连通域
    comps = []
    for bi, (by0, by1) in enumerate(char_bands):
        band_mask = np.zeros_like(ink)
        band_mask[by0:by1 + 1, :] = True
        lb, nn = ndimage.label(ink & band_mask, structure=S8)
        szs = np.bincount(lb.ravel())
        for j in range(1, nn + 1):
            if szs[j] < 80:
                continue
            ys, xs = np.where(lb == j)
            comps.append(dict(band=bi, mask=(lb == j), x0=int(xs.min()), x1=int(xs.max()),
                              y0=int(ys.min()), y1=int(ys.max()), px=int(szs[j])))
    chars = [c for c in comps if c["px"] >= 15000]
    decors = [c for c in comps if c["px"] < 15000]
    # 行优先排序
    chars.sort(key=lambda c: (c["band"], (c["x0"] + c["x1"]) / 2.0))
    print(f"[{name}] 角色 {len(chars)} / 小图标装饰 {len(decors)}")

    od = os.path.join(OUT, name)
    os.makedirs(od, exist_ok=True)

    # 每个角色所在"行带"与"其下方标签带"(用于原图对照裁剪, 让用户看清动作名)
    def label_below(band_idx):
        by1 = char_bands[band_idx][1]
        best = None
        for (ly0, ly1) in lab_bands:
            if ly0 > by1 and (best is None or ly0 < best[0]):
                best = (ly0, ly1)
        return best

    # 每个小图标只归附"最近的那一个角色"(避免相邻角色串味/重复)
    decor_owner = {}
    for di, d in enumerate(decors):
        best, bd = -1, 1e9
        for ci, c in enumerate(chars):
            dx = max(c["x0"] - d["x1"], 0, d["x0"] - c["x1"])
            dy = max(c["y0"] - d["y1"], 0, d["y0"] - c["y1"])
            dist = (dx * dx + dy * dy) ** 0.5
            if dist < bd:
                bd, best = dist, ci
        if best >= 0 and bd <= 38:
            decor_owner[di] = best

    for i, c in enumerate(chars):
        f = c["mask"]
        bi = c["band"]
        by0, by1 = char_bands[bi]
        ys0, xs0 = np.where(f)
        # 窗口: 严格夹在角色行带内 (防吃标签)
        wx0 = max(0, int(xs0.min()) - 6); wx1 = min(W - 1, int(xs0.max()) + 6)
        wy0 = max(int(by0), int(ys0.min()) - 6); wy1 = min(int(by1), int(ys0.max()) + 6)
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
            for ny, nx in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)):
                if 0 <= ny < hh and 0 <= nx < ww and not rch[ny, nx] and passable[ny, nx]:
                    rch[ny, nx] = True; dq2.append((ny, nx))
        sil = ndimage.binary_fill_holes(f)
        sil[wy0:wy1 + 1, wx0:wx1 + 1] &= ~rch       # 白描边/背景 -> 透明
        # 调试用: 到"外部背景"的距离 (发丝围出的坑只隔薄发丝 -> 距离小; 衣服内部的画出来的白 -> 距离大)
        _rch_full = np.zeros(sil.shape, bool)
        _rch_full[wy0:wy1 + 1, wx0:wx1 + 1] = rch
        d_bg = ndimage.distance_transform_edt(~_rch_full)

        # ---- 封闭腔清除 (第24轮深腔保护 + 第30轮: 头发包围的深腔要删) ----
        #   深腔 = 角色内部特征(眼白/衣白/皮肤/围裙) -> 保护;
        #   但"环上偏暗且明显偏蓝(即被头发包围) 且 位于头发带(顶部/左右两侧)"的深腔,
        #   实际是【呆毛圈 / 长发尾端围出的背景】-> 必须删除。
        #   实测可分性: 头发环 ringMin 110~140 / ringB-R 41~71;
        #              合法衣白环 ringMin 210~218 / ringB-R 2~9  -> 阈值 185 / 25 干净切开。
        ink_core = ndimage.binary_erosion(f, structure=S8, iterations=2)
        dist_out = ndimage.distance_transform_edt(sil)
        _y, _x = np.where(sil)
        y_top, y_bot = int(_y.min()), int(_y.max())
        x_l, x_r = int(_x.min()), int(_x.max())
        leg_y = y_bot - int((y_bot - y_top) * 0.30)
        for _ in range(2):
            pockets = sil & ~f
            pl, pn = ndimage.label(pockets, structure=S8)
            if not pn:
                break
            psz = np.bincount(pl.ravel())
            cand = [j for j in range(1, pn + 1) if psz[j] >= 18
                    and float((f & (pl == j)).sum()) / psz[j] < 0.02
                    and float(A[pl == j].min(axis=1).mean()) >= 210
                    and float(b_r[pl == j].mean()) >= -2
                    and float(sat_all[pl == j].mean()) <= 32]
            biggest = max(cand, key=lambda j: psz[j]) if cand else None
            if os.environ.get("DBG_CAV") == "1":
                print(f"   [{name}_{i+1:02d}] pockets={pn} cand={len(cand)} biggest_psz={psz[biggest] if biggest else 0} sil={int(sil.sum())}")
            drop = np.zeros_like(sil)
            for j in cand:
                m = pl == j
                yy, xx = np.where(m)
                cy = int(yy.mean()); cx = int(xx.mean())
                yf = (cy - y_top) / max(1, (y_bot - y_top))
                xf = (cx - x_l) / max(1, (x_r - x_l))
                dep = float(np.median(dist_out[m]))
                # 环上颜色: 判定"包围它的是头发还是布料" —— 实测头发环 rbr(蓝度) 44~76 /
                #   rbmin(亮度) 97~143; 布料环(围裙/蕾丝/白袜) rbr 22~24 / rbmin 195~230。
                ring = ndimage.binary_dilation(m, structure=S8, iterations=4) & f
                if ring.sum():
                    rr = A[ring]
                    rbmin = float(rr.min(axis=1).mean())
                    rbr = float((rr[:, 2] - rr[:, 0]).mean())
                else:
                    rbmin, rbr = 255.0, 0.0
                is_hair_ring = (rbr >= 30) and (rbmin <= 190)
                # ★ 第34轮: "环蓝度偏弱"的腔 -> 一律保护(不删)。
                #   真·头发围出的背景坑, 其包围环几乎全是头发 -> rbr(蓝度) 实测 43~76;
                #   而"画出来的服装白"(衣服下摆/裙摆的白边)虽然也被蓝发/蓝裙围住, 但
                #   包围环里混入了衣物高光/皮肤等**非头发像素** -> 蓝度被稀释到 rbr<42。
                #   实测全帧 50 个候选中 rbr<42 的仅 5 个: 其中 2 个正是浅浅猫指认要保留的
                #   "衣服下摆白"(setA_07 cav#125 rbr=35 / setA_09 cav#118 rbr=32),
                #   另 3 个属已舍弃的帧(setA_04/setA_10) —— 因此这条护栏零回归。
                if is_hair_ring and rbr < 42:
                    if os.environ.get("DBG_CAV") == "1":
                        print(f" WEAK-BLUE keep (rbr={rbr:.0f})")
                    continue
                in_hairzone = (yf < 0.30) or (xf < 0.30) or (xf > 0.70)
                bright_ring = (rbmin >= 195)
                if os.environ.get("DBG_CAV") == "1":
                    _md = float(d_bg[m].min()); _mdm = float(np.median(d_bg[m]))
                    print(f"      cav#{j:>3} psz={psz[j]:>5} yf={yf:.2f} xf={xf:.2f} dep={dep:5.0f} "
                          f"dmin={_md:4.0f} dmed={_mdm:5.0f} "
                          f"rbmin={rbmin:5.0f} rbr={rbr:5.0f} hair={is_hair_ring} big={j == biggest} ->", end="")
                # ★ 围裙豁免修正: "最大腔=围裙"在第30轮被证伪 —— 呆毛圈常比围裙还大。
                #   仅当最大腔的环"不是头发环"(即真被布料包围)才豁免。
                if j == biggest and not is_hair_ring:
                    if os.environ.get("DBG_CAV") == "1":
                        print(" BIGGEST skip")
                    continue
                # ★ 头发包围的"背景" -> 删除 (呆毛圈 / 长发尾端围出的背景)。
                #   第32轮关键修正: 光"环上是头发"远远不够 —— 鲸鱼肚(抱抱)/白裙摆/书籍/
                #   发饰鲸鱼嘴的白色**同样是"被蓝色包围的白"**, 但它们是被**画出来的白**
                #   (有明暗渐变, 偏离面板纯白 11.8~13.6); 而发丝缝/呆毛圈里的背景几乎
                #   等于面板纯白(偏离仅 2.7~8.9)。因此必须再加"自身颜色≈面板纯白"一条。
                #   ★ 取腔内"最大的一片连通纯白"来算白度(与诊断口径一致):
                #     发丝缝/呆毛圈 = 整片纯白 -> 白度 3~9  -> 删
                #     鲸鱼肚/裙摆/书籍"画出来的白" -> 白度 12~14 -> 保留
                #     纯白主体太小(<60px, 如发饰小细节) -> 不当背景坑 -> 保留
                mw = m & (mn_all >= 240) & (sat_all <= 16)
                own_dev = 999.0
                if mw.any():
                    lw, nw = ndimage.label(mw, structure=S8)
                    if nw:
                        szw = np.bincount(lw.ravel()); szw[0] = 0
                        jw = int(szw.argmax())
                        if szw[jw] >= 60:
                            wcore = (lw == jw)
                            own_dev = float(np.abs(A[wcore] - np.array([255.0, 255.0, 255.0])).max(axis=1).mean())
                if is_hair_ring and in_hairzone and own_dev <= 10.0 and psz[j] >= 120:
                    if os.environ.get("DBG_CAV") == "1":
                        print(f" HAIR-RING DROP (own_dev={own_dev:.1f})")
                    drop |= m
                    continue
                if is_hair_ring and in_hairzone:
                    # 被头发包围、但自身是"画出来的白"(有明暗渐变) -> 保护, 不删
                    if os.environ.get("DBG_CAV") == "1":
                        print(f" PAINTED-WHITE keep (own_dev={own_dev:.1f})")
                    continue
                # 环上亮且中性 = 布料包围的角色白(围裙/蕾丝/白袜) -> 一律保护
                if bright_ring:
                    if os.environ.get("DBG_CAV") == "1":
                        print(" BRIGHT-RING keep")
                    continue
                if dep > 28:                                    # 深腔 = 角色内部特征
                    if os.environ.get("DBG_CAV") == "1":
                        print(" DEEP keep")
                    continue
                if cy > leg_y:                                  # 腿部区 -> 不碰
                    if os.environ.get("DBG_CAV") == "1":
                        print(" LEG skip")
                    continue
                if psz[j] < 120:
                    ring2 = ndimage.binary_dilation(m, structure=S8, iterations=3) & f
                    if float((ring2 & ink_core).sum()) / max(1, int(ring2.sum())) >= 0.30:
                        if os.environ.get("DBG_CAV") == "1":
                            print(" SMALL+ink skip")
                        continue
                if os.environ.get("DBG_CAV") == "1":
                    print(" DROP")
                drop |= m
            if drop.any():
                print(f"      [{name}_{i+1:02d}] 删腔 {int(drop.sum())}px")
            if not drop.any() or float(drop.sum()) > 0.25 * max(1.0, float(sil.sum())):
                break
            sil = sil & ~drop

        # ---- 小图标装饰件 -> 只贴归属于自己的那个 ----
        for di, d in enumerate(decors):
            if decor_owner.get(di) != i:
                continue
            dm = d["mask"]
            sl = ndimage.find_objects(dm.astype(int))[0]
            y0d, y1d = sl[0].start, sl[0].stop - 1
            x0d, x1d = sl[1].start, sl[1].stop - 1
            bbox = max(1, (y1d - y0d + 1) * (x1d - x0d + 1))
            if float(dm.sum()) / bbox >= 0.16:              # 实体装饰 -> 填洞
                dm = ndimage.binary_fill_holes(dm)
            sil |= dm

        # ---- 选择性削掉最外圈"近似底色的浅色"边界像素 ----
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
        bx0, bx1 = max(0, int(xs.min()) - 1), min(W - 1, int(xs.max()) + 1)
        by0b, by1b = max(0, int(ys.min()) - 1), min(H - 1, int(ys.max()) + 1)
        m = sil[by0b:by1b + 1, bx0:bx1 + 1]
        rgb = A[by0b:by1b + 1, bx0:bx1 + 1].astype(np.uint8)

        # ---- 4x 超采样 -> 真亚像素抗锯齿 ----
        # ★ 第30轮: 去掉 binary_opening —— 3x3 开运算会把 1px 宽的细发丝整条吃掉,
        #   正是"细发丝被扣断"的主因(实测发丝丢失 1177px)。只保留 closing。
        m = ndimage.binary_closing(m, structure=S8, iterations=1)
        up = 4
        big_rgb = np.dstack([ndimage.zoom(rgb[..., ch].astype(np.float32), up, order=1)
                             for ch in range(3)])
        big_sil = ndimage.zoom(m.astype(np.float32), up, order=1)
        big_sil = ndimage.gaussian_filter(big_sil, 1.2)
        ink4 = (big_rgb.min(axis=2) < 200) & (big_sil > 0.30)
        soft4 = np.maximum(big_sil, ink4.astype(np.float32) * 0.9)
        soft4 = ndimage.gaussian_filter(soft4, 0.7)
        soft = np.clip((soft4 - 0.30) / 0.45, 0.0, 1.0)
        a2 = (np.clip(ndimage.zoom(soft, 1.0 / up, order=1), 0, 1) * 255).astype(np.uint8)
        far = ndimage.distance_transform_edt(m) >= 1.6
        a2[far] = 255

        # ---- 细缝半透明残料清除(邻域透明>=6 才清, 保抗锯齿边) ----
        smn2 = rgb.min(axis=2).astype(np.int16)
        ssat2 = (rgb.max(axis=2).astype(np.int16) - smn2)
        transp = (a2 == 0).astype(np.uint8)
        nb_trans = np.zeros_like(transp, np.int16)
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dy == 0 and dx == 0:
                    continue
                nb_trans += np.roll(np.roll(transp, dy, axis=0), dx, axis=1)
        a2[(a2 > 0) & (a2 < 250) & (smn2 >= 230) & (ssat2 <= 24) & (nb_trans >= 6)] = 0

        # ---- 连通性清理(碎屑) ----
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

        # ---- 边缘去背景污染(只换色, 不动 alpha) ----
        bg_like = (rgb.min(axis=2) >= 226) & ((rgb.max(axis=2).astype(np.int16)
                                               - rgb.min(axis=2).astype(np.int16)) <= 28)
        core = (a2 >= 250) & (rgb.min(axis=2) < 210)
        if not core.any():
            core = (a2 >= 250) & ~bg_like
        if core.any():
            _, idx_core = ndimage.distance_transform_edt(~core, return_indices=True)
            near_core = rgb[idx_core[0], idx_core[1]]
            solid_sil = ndimage.binary_fill_holes(m)
            d_out = ndimage.distance_transform_edt(solid_sil)
            d_trans = ndimage.distance_transform_edt(a2 > 0)
            edge_band = (a2 > 0) & (d_out <= 1.5)
            near_trans = (a2 > 0) & (d_trans <= 2.5)
            fix = edge_band | (bg_like & near_trans)
            rgb[fix] = near_core[fix]

        # ---- 质检指标 ----
        silf = a2 > 40
        holes = int((ndimage.binary_fill_holes(silf) & ~silf).sum())
        semi = int(((a2 > 0) & (a2 < 250)).sum())
        white_near_trans = int(((a2 > 0) & (rgb.min(axis=2) >= 226)
                                & ((rgb.max(axis=2).astype(np.int16) - rgb.min(axis=2).astype(np.int16)) <= 28)
                                & (ndimage.distance_transform_edt(a2 > 0) <= 2.5)).sum())

        out = Image.fromarray(np.dstack([rgb, a2]), "RGBA")
        bb = out.getbbox()
        if bb:
            out = out.crop(bb)
        fn = f"{name}_{i+1:02d}.png"
        out.save(os.path.join(od, fn))
        qc[f"{name}_{i+1:02d}"] = dict(holes=holes, semi=semi, white_near_trans=white_near_trans,
                                       size=[out.width, out.height])
        # 原图对照裁剪(含下方标签, 便于辨认动作名)
        lb = label_below(bi)
        cy1 = (lb[1] + 10) if lb else (by1b + 8)
        sx0 = max(0, bx0 - 18); sx1 = min(W - 1, bx1 + 18)
        sy0 = max(0, by0b - 10); sy1 = min(H - 1, cy1)
        # fbox: 成品左上角在源图中的绝对坐标(用于像素级映射诊断)
        info[f"{name}/{name}_{i+1:02d}"] = dict(box=[sx0, sy0, sx1, sy1],
                                               cbox=[bx0, by0b, bx1, by1b],
                                               fbox=[bx0 + (bb[0] if bb else 0),
                                                     by0b + (bb[1] if bb else 0)])
        ndec = sum(1 for _di in decor_owner if decor_owner[_di] == i)
        print(f"   -> {fn} {out.width}x{out.height}  孔洞={holes} 半透明={semi} 贴透明浅色={white_near_trans} 图标={ndec}")

n = sum(len(os.listdir(os.path.join(OUT, g))) for g in os.listdir(OUT) if os.path.isdir(os.path.join(OUT, g)))
print("frames:", n)
json.dump(info, open(os.path.join(BASE, "assets", "pet_v3_windows.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
json.dump(qc, open(os.path.join(BASE, "assets", "pet_v3_qc.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)

# 深浅底 + 洋红底 自检拼图
for g in sorted(os.listdir(OUT)):
    gd = os.path.join(OUT, g)
    if not os.path.isdir(gd):
        continue
    files = sorted(os.listdir(gd))
    TH, pads, tiles = 250, 14, []
    for fn in files:
        f = Image.open(os.path.join(gd, fn)).convert("RGBA")
        r = TH / f.height
        tiles.append((fn[:-4], f.resize((max(1, int(f.width * r)), TH), Image.LANCZOS)))
    Wd = sum(t.width + pads for _, t in tiles) + pads
    sheet = Image.new("RGBA", (Wd, TH * 3 + 84), (52, 56, 64, 255))
    d = ImageDraw.Draw(sheet)
    x = pads
    for nm, t in tiles:
        dk = Image.new("RGBA", t.size, (30, 34, 42, 255)); dk.alpha_composite(t)
        lt = Image.new("RGBA", t.size, (246, 248, 252, 255)); lt.alpha_composite(t)
        mg = Image.new("RGBA", t.size, (255, 0, 255, 255)); mg.alpha_composite(t)
        sheet.alpha_composite(dk, (x, 26)); sheet.alpha_composite(lt, (x, TH + 42))
        sheet.alpha_composite(mg, (x, TH * 2 + 58))
        d.text((x + 2, 8), nm, fill=(255, 214, 110, 255))
        x += t.width + pads
    sheet.convert("RGB").save(os.path.join(BASE, "assets", "_v3_%s.png" % g))
print("self-check sheets saved")
