# -*- coding: utf-8 -*-
"""回归校验: 修复版(fixed) vs 问题版(broken) 成品帧像素对比。
   量化目标:
     · 面部/眼睛白区(fixed 应 >= broken, 即眼白被恢复)
     · 身体/衣服白区(fixed 应 >= broken, 即衣服白被恢复)
     · 腿部白区(fixed 应 == broken, 无回归)
     · 围裙大白块(fixed 应 == broken)
     · 发丝区白残留(fixed 应 <= broken, 即发丝坑仍被清)
"""
import numpy as np
from PIL import Image
import os

BASE = r"C:\Users\a3564\WorkBuddy\2026-08-25-04-20-35\token-stats"
FIX = os.path.join(BASE, "assets", "pet_v2")
BRK = os.path.join(BASE, "assets", "pet_v2_broken_bak")

def white_mask(rgba):
    rgb = rgba[..., :3].astype(np.int16)
    a = rgba[..., 3]
    mn = rgb.min(axis=2); mx = rgb.max(axis=2)
    return (mn >= 235) & (mx - mn <= 18) & (a > 200)

def zone_count(wm, y0r, y1r, x0r, x1r):
    h, w = wm.shape
    y0, y1 = int(h*y0r), int(h*y1r)
    x0, x1 = int(w*x0r), int(w*x1r)
    return int(wm[y0:y1, x0:x1].sum())

groups = ["idle", "sleep", "drag", "click", "special"]
tot = dict(face=0, body=0, leg=0, apron=0, hair=0)
tot_b = dict(face=0, body=0, leg=0, apron=0, hair=0)
print(f"{'frame':12} {'face_f':>7} {'face_b':>7} {'body_f':>7} {'body_b':>7} {'leg_f':>6} {'leg_b':>6} {'hair_f':>7} {'hair_b':>7}")
for g in groups:
    for fn in sorted(os.listdir(os.path.join(FIX, g))):
        f = np.asarray(Image.open(os.path.join(FIX, g, fn)).convert("RGBA"))
        b = np.asarray(Image.open(os.path.join(BRK, g, fn)).convert("RGBA"))
        wf, wb = white_mask(f), white_mask(b)
        face_f = zone_count(wf, 0.20, 0.46, 0.22, 0.78)
        face_b = zone_count(wb, 0.20, 0.46, 0.22, 0.78)
        body_f = zone_count(wf, 0.50, 0.86, 0.15, 0.85)
        body_b = zone_count(wb, 0.50, 0.86, 0.15, 0.85)
        leg_f = zone_count(wf, 0.80, 1.00, 0.10, 0.90)
        leg_b = zone_count(wb, 0.80, 1.00, 0.10, 0.90)
        hair_f = zone_count(wf, 0.10, 0.30, 0.05, 0.95)
        hair_b = zone_count(wb, 0.10, 0.30, 0.05, 0.95)
        print(f"{g+'_'+fn[-6:-4]:12} {face_f:>7} {face_b:>7} {body_f:>7} {body_b:>7} {leg_f:>6} {leg_b:>6} {hair_f:>7} {hair_b:>7}")
        tot["face"]+=face_f; tot_b["face"]+=face_b
        tot["body"]+=body_f; tot_b["body"]+=body_b
        tot["leg"]+=leg_f; tot_b["leg"]+=leg_b
        tot["hair"]+=hair_f; tot_b["hair"]+=hair_b
print("-"*80)
print(f"{'TOTAL':12} {tot['face']:>7} {tot_b['face']:>7} {tot['body']:>7} {tot_b['body']:>7} {tot['leg']:>6} {tot_b['leg']:>6} {tot['hair']:>7} {tot_b['hair']:>7}")
print()
print("判读: face/body 修复版应 >= 问题版(眼/衣白恢复); leg 应相等(无回归);")
print("      hair 修复版应 <= 问题版(发丝坑仍清, 不应反弹)。")
