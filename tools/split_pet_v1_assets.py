# -*- coding: utf-8 -*-
"""v24 拆帧 (定稿方案):
  1. 列投影定位每帧(帧数正确) -> 窗口 = 投影窗口 + 固定余量 (左右 9px / 上 9px / 下 4px)
     —— 余量固定可控, 不会像自适应外扩那样一路吃到区块边框
  2. 去底: 中性色泛洪(亮度>=205 且 饱和度<=8) -> 清小噪点/边框线/贴底编号 -> 小孔填回(<700px)
  3. 边缘: 轮廓 2 圈内按亮度渐变 alpha (深底无白晕, 内部白色不受影响)
"""
import numpy as np
import json
import json
from PIL import Image
from scipy import ndimage
from collections import deque
import os, shutil

SRC = r"C:\Users\a3564\.workbuddy\clipboard-images\clipboard-2026-09-09T20-00-45-903Z-a9db0f76.jpg"
ROOT = r"C:\Users\a3564\WorkBuddy\2026-08-25-04-20-35\token-stats\assets\pet"
im = Image.open(SRC).convert("RGB")
A = np.asarray(im).astype(np.int16)
S8 = np.ones((3, 3), int)

MN_BG, SAT_BG = 205, 8
CAVITY_FILL_MAX = 700
PAD_LR = 9
# 每行输出的 y 边界 (由人物实体实际范围推出, 精确避开上方标题栏与下方编号托盘)
ROW_Y = {
    "idle":    (210, 347),
    "sleep":   (234, 366),
    "drag":    (476, 628),
    "click":   (461, 600),
    "other":   (700, 813),
    "special": (882, 963),
}

core2 = ndimage.binary_erosion((A < 228).any(axis=2), iterations=2)
SEED_ROWS = [
    ("idle",    218, 344, [(24, 640)], 6, 3, None),
    ("sleep",   240, 366, [(656, 1180)], 6, 3, None),
    ("drag",    470, 590, [(24, 640)], 6, 3, None),
    ("click",   470, 590, [(656, 1180)], 6, 3, None),
    ("other",   698, 812, [(24, 1180)], 6, 3, None),
    ("special", 884, 962, None, 3, 2,
     [(30, 104), (114, 224), (234, 324), (334, 414), (424, 504),
      (514, 624), (634, 724), (734, 824), (834, 932), (932, 968)]),
]


def split_row(x0, x1, y0, y1, thresh, min_gap):
    counts = core2[y0:y1, x0:x1].sum(axis=0)
    segs, s, gap = [], None, 0
    for i, v in enumerate(counts):
        if v > thresh:
            if s is None:
                s = i
            gap = 0
        else:
            if s is not None:
                gap += 1
                if gap >= min_gap:
                    segs.append((s, i - gap + 1))
                    s, gap = None, 0
    if s is not None:
        segs.append((s, len(counts)))
    return [(x0 + p - 3, x0 + q + 3) for p, q in segs if q - p >= 28]


SEEDS = {}
for name, y0, y1, xr, th, mg, fixed in SEED_ROWS:
    segs = list(fixed) if fixed else []
    if not fixed:
        for x0, x1 in xr:
            segs += split_row(x0, x1, y0, y1, th, mg)
    SEEDS[name] = [(int(a), int(b), y0, y1) for a, b in segs]

EXPECT = {"idle": 7, "sleep": 6, "drag": 6, "click": 6, "other": 12, "special": 10}


def flood_bg(sub):
    mn = sub.min(axis=2)
    sat = sub.max(axis=2) - mn
    neutral = (mn >= MN_BG) & (sat <= SAT_BG)
    h, w = neutral.shape
    reach = np.zeros((h, w), bool)
    dq = deque()
    for x in range(w):
        for y in (0, h - 1):
            if neutral[y, x] and not reach[y, x]:
                reach[y, x] = True; dq.append((y, x))
    for y in range(h):
        for x in (0, w - 1):
            if neutral[y, x] and not reach[y, x]:
                reach[y, x] = True; dq.append((y, x))
    while dq:
        y, x = dq.popleft()
        for ny, nx in ((y-1, x), (y+1, x), (y, x-1), (y, x+1)):
            if 0 <= ny < h and 0 <= nx < w and not reach[ny, nx] and neutral[ny, nx]:
                reach[ny, nx] = True; dq.append((ny, nx))
    return ~reach


def clean_objs(obj):
    h, w = obj.shape
    lbl, n = ndimage.label(obj, structure=S8)
    for i in range(1, n + 1):
        m = lbl == i
        cnt = int(m.sum())
        ys, xs = np.where(m)
        y0, y1, x0, x1 = ys.min(), ys.max(), xs.min(), xs.max()
        hh, ww = y1 - y0 + 1, x1 - x0 + 1
        fill = cnt / float(hh * ww)
        if cnt < 30:
            obj[m] = False; continue
        sticky = (x0 <= 2) or (x1 >= w - 3) or (y0 <= 2)
        if sticky and min(hh, ww) <= 8:                                # 贴边细长条 = 区块边框线
            obj[m] = False; continue
        if sticky and min(hh, ww) <= 12 and fill < 0.55:               # 贴边低填充细线
            obj[m] = False; continue
        if y1 >= h - 3 and hh <= 32 and ww >= hh * 0.8:                # 贴底文字块 = 编号标签
            obj[m] = False; continue
    return obj


def dewhite(sub):
    obj = clean_objs(flood_bg(sub).copy())
    filled = ndimage.binary_fill_holes(obj)
    holes = filled & ~obj
    cavity = np.zeros_like(obj)          # 大封闭腔 = 手臂环抱出的背景, 保持透明
    hl, hn = ndimage.label(holes, structure=S8)
    if hn:
        hsz = np.bincount(hl.ravel())
        for i in range(1, hn + 1):
            if hsz[i] < CAVITY_FILL_MAX:
                obj |= (hl == i)          # 小孔 = 渗入/内部残留 -> 填回
            else:
                cavity |= (hl == i)
    alpha = np.where(obj, 255, 0).astype(np.uint8)

    # ---- 边缘: ① 形态学平滑去掉 JPEG 锯齿/碎点  ② 4 倍超采样 + 高斯 -> 柔和抗锯齿边 ----
    M = ndimage.binary_opening(obj, structure=S8, iterations=1)     # 去 1px 毛刺
    M = ndimage.binary_closing(M, structure=S8, iterations=1)       # 补 1px 缺口
    if not M.any():
        M = obj
    up = 4
    big = ndimage.zoom(M.astype(np.float32), up, order=1)
    big = ndimage.gaussian_filter(big, 1.1)
    soft = np.clip((big - 0.34) / 0.30, 0.0, 1.0)
    a_soft = np.clip(ndimage.zoom(soft, 1.0 / up, order=1), 0.0, 1.0)
    a2 = (a_soft * 255.0).astype(np.uint8)
    # 距透明区 >=2px 的内部强制不透明 (防止把内部白色磨淡)
    far = ndimage.distance_transform_edt(M) >= 2.0
    a2[far] = 255
    # 大封闭腔 (手臂环抱出的背景) 仍保持透明
    a2[cavity] = 0
    return a2






if os.path.isdir(ROOT):
    shutil.rmtree(ROOT)
info = {}
for name in ("idle", "sleep", "drag", "click", "other", "special"):
    od = os.path.join(ROOT, name)
    os.makedirs(od, exist_ok=True)
    cs = [((a + b) / 2.0) for a, b, _, _ in SEEDS[name]]
    for i, (sx0, sx1, sy0, sy1) in enumerate(SEEDS[name]):
        lim_l = 0 if i == 0 else int((cs[i - 1] + cs[i]) / 2)
        lim_r = A.shape[1] - 1 if i == len(cs) - 1 else int((cs[i] + cs[i + 1]) / 2)
        x0 = max(lim_l, sx0 - PAD_LR); x1 = min(lim_r, sx1 + PAD_LR)
        y0, y1 = ROW_Y[name]
        sub = A[y0:y1 + 1, x0:x1 + 1]
        a2 = dewhite(sub)
        out = Image.fromarray(np.dstack([sub.astype(np.uint8), a2]), "RGBA")
        bb = out.getbbox()
        if bb:
            out = out.crop(bb)
        out.save(os.path.join(od, f"{name}_{i + 1:02d}.png"))
        key = f"{name}_{i + 1:02d}"
        info[key] = dict(win=[x0, x1, y0, y1],
                         box=[x0 + bb[0], x0 + bb[2], y0 + bb[1], y0 + bb[3]],
                         size=[out.width, out.height])
    print(f"{name:8s} {len(SEEDS[name])} 帧")

for rel in ("click/click_01.png", "special/special_10.png",
            "sleep/sleep_03.png", "sleep/sleep_04.png", "sleep/sleep_05.png", "sleep/sleep_06.png"):
    p = os.path.join(ROOT, rel)
    if os.path.exists(p):
        os.remove(p)
n = sum(len(os.listdir(os.path.join(ROOT, g))) for g in os.listdir(ROOT))
print("frames:", n)
with open(os.path.join(os.path.dirname(ROOT), "pet_windows.json"), "w", encoding="utf-8") as fp:
    json.dump({k: v for k, v in info.items()
               if os.path.exists(os.path.join(ROOT, k.split("_")[0], k + ".png"))},
              fp, ensure_ascii=False, indent=1)
print("windows json saved")

from PIL import ImageDraw
for g in ("idle", "sleep", "drag", "click", "other", "special"):
    od = os.path.join(ROOT, g)
    files = sorted(os.listdir(od))
    TH, pads, tiles = 250, 14, []
    for fn in files:
        f = Image.open(os.path.join(od, fn)).convert("RGBA")
        r = TH / f.height
        tiles.append((fn[:-4], f.resize((max(1, int(f.width * r)), TH), Image.LANCZOS)))
    W = sum(t.width + pads for _, t in tiles) + pads
    sheet = Image.new("RGBA", (W, TH * 2 + 60), (52, 56, 64, 255))
    d = ImageDraw.Draw(sheet)
    x = pads
    for nm, t in tiles:
        dk = Image.new("RGBA", t.size, (38, 42, 50, 255)); dk.alpha_composite(t)
        lt = Image.new("RGBA", t.size, (244, 246, 250, 255)); lt.alpha_composite(t)
        sheet.alpha_composite(dk, (x, 26)); sheet.alpha_composite(lt, (x, TH + 42))
        d.text((x + 2, 8), nm, fill=(255, 214, 110, 255))
        x += t.width + pads
    sheet.convert("RGB").save(os.path.join(os.path.dirname(ROOT), "_v24_%s.png" % g))
print("self-check sheets saved")
