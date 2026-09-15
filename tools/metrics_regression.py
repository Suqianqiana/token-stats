# -*- coding: utf-8 -*-
"""回归指标: 每帧统计 4 类像素, 写 JSON。用于 before/after 对比, 验证后处理不伤
   合法白衣(围裙/皮肤/白袜)。"""
import numpy as np, json
from PIL import Image
import os

OUT = r"C:\Users\a3564\WorkBuddy\2026-08-25-04-20-35\token-stats\assets\pet_v2"


def metrics(fn):
    im = np.asarray(Image.open(fn).convert("RGBA")).astype(np.int16)
    a = im[..., 3]; rgb = im[..., :3]
    mn = rgb.min(axis=2); mx = rgb.max(axis=2); sat = mx - mn
    br = rgb[..., 2] - rgb[..., 0]
    op = a >= 250
    cool = op & (mn >= 210) & (sat <= 40) & (br >= -2)
    warm = op & (br < -4)
    ys, _ = np.where(op)
    H = a.shape[0]
    yb0, yb1 = int(ys.min()), int(ys.max())
    leg_y = yb1 - int((yb1 - yb0) * 0.30)
    leg_mask = np.zeros(a.shape, bool); leg_mask[int(leg_y):, :] = True
    return dict(
        cool_total=int(cool.sum()),
        warm_total=int(warm.sum()),
        leg_white=int((cool & leg_mask).sum()),
        total_light=int((op & (mn >= 210) & (sat <= 40)).sum()),
    )


res = {}
for g in ["idle", "sleep", "drag", "click", "special"]:
    od = os.path.join(OUT, g)
    for fn in sorted(os.listdir(od)):
        if fn.endswith(".png"):
            res[fn[:-4]] = metrics(os.path.join(od, fn))
print(json.dumps(res, ensure_ascii=False))
