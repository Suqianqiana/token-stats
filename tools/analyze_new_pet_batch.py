# -*- coding: utf-8 -*-
"""分析 Downloads 下 11 张新素材源图: 尺寸/透明度/行带/连通域角色数。"""
import os, sys, glob
sys.dont_write_bytecode = True
import numpy as np
from PIL import Image
from scipy import ndimage

S8 = np.ones((3, 3), bool)
DL = os.path.join(os.path.expanduser("~"), "Downloads")
FILES = [
    "蓝发鲸鱼女仆日常贴纸合集.png",
    "桌宠新动作素材_第二批_4K透明.png",
    "蓝发鲸鱼少女表情贴纸合集.png",
    "桌宠新动作素材_无标签第三批_4K透明.png",
    "蓝鲸主题女仆少女贴纸表情集.png",
    "蓝鲸主题少女贴纸图鉴.png",
    "蓝发鲸鱼女仆十二格贴纸合集.png",
    "蓝发鲸鱼女仆日常贴纸集.png",
    "桌宠睡觉睡醒与日常动作_6x2_4K透明.png",
    "蓝色鲸鱼女仆的日常贴纸集.png",
    "蓝鲸少女的十二种日常姿态.png",
]

for fn in FILES:
    p = os.path.join(DL, fn)
    if not os.path.exists(p):
        # 兼容 URL 编码文件名
        cands = glob.glob(os.path.join(DL, "*"))
        hit = [c for c in cands if os.path.basename(c).startswith(fn.split("_")[0][:4])]
        print("MISSING:", fn, "| 相似:", [os.path.basename(h) for h in hit[:3]])
        continue
    im = Image.open(p)
    A = np.asarray(im.convert("RGBA"))
    al = A[..., 3]
    H, W = al.shape
    trans_pct = float((al == 0).mean() * 100)
    fg = al > 128
    lbl, n = ndimage.label(fg, S8)
    szs = np.bincount(lbl.ravel())
    # 角色 = 面积 >= 20000
    big = [j for j in range(1, n) if j < len(szs) and szs[j] >= 20000]
    dec = [j for j in range(1, n) if j < len(szs) and 8 <= szs[j] < 20000]
    # 行带: 按 alpha 行投影
    rows = (fg.sum(axis=1) > 10)
    bands, s = [], None
    for i, x in enumerate(rows):
        if x and s is None: s = i
        if not x and s is not None:
            bands.append((s, i - 1)); s = None
    if s is not None: bands.append((s, H - 1))
    bands = [b for b in bands if b[1] - b[0] + 1 >= 100]
    # 角色按行带分组、行优先
    info = []
    for j in big:
        ys, xs = np.where(lbl == j)
        info.append(dict(id=j, area=int(szs[j]), x0=int(xs.min()), x1=int(xs.max()),
                         y0=int(ys.min()), y1=int(ys.max()), yc=float(ys.mean())))
    rows_g = []
    for c in info:
        for r in rows_g:
            if abs(r["yc"] - c["yc"]) < 150:
                r["items"].append(c); r["yc"] = float(np.mean([x["yc"] for x in r["items"]])); break
        else:
            rows_g.append({"yc": c["yc"], "items": [c]})
    rows_g.sort(key=lambda r: r["yc"])
    layout = " | ".join("行%d:%d个" % (i + 1, len(r["items"])) for i, r in enumerate(rows_g))
    print("%-46s %5dx%-5d 透明%5.1f%% 行带%s 角色%2d 装饰%2d  [%s]"
          % (fn[:46], W, H, trans_pct, bands, len(big), len(dec), layout))
