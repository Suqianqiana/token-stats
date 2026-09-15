# -*- coding: utf-8 -*-
"""用"透明背景 PNG 原图"切出的 v5 素材, 重建桌宠素材库 assets/pet_v3r/ (原地升级)。

为什么换成 v5 源:
  之前用的是剪贴板转存的 **JPG**(白底压平 + JPEG 噪声), 必须"抠图", 于是产生
  呆毛没扣/下发没扣/细发丝被吃/下摆白被误删 等一系列判断错误。
  v5 源是 ChatGPT 直出的 **1536x1024 RGBA PNG**, 背景 alpha=0 真透明 -> 零抠图,
  只做行带分离 + DP 竖向切分 + 裁剪, 保留原始 alpha 羽化。

动作池映射(与第33轮定稿一致, 仅把来自 setA/setB 的帧换成 v5 版本):
  idle  = v2 idle 4帧 + setA_01
  sleep = v2 sleep 2帧 + setB_08
  wake  = setB_09 / setA_05
  drag  = v2 drag_01/02 + setB_06 + setA_06
  click = v2 click 2帧 + setA_02 + setA_03
  sidle = setA_07 setA_08 setA_09
  pat   = v2 special 2帧 + setB_10
setC(12 帧, 07_20_09 那张新图) 尚未安排 -> 暂不进入素材库。
"""
import os, shutil

BASE = r"C:\Users\a3564\WorkBuddy\2026-08-25-04-20-35\token-stats"
DST = os.path.join(BASE, "assets", "pet_v3r")
DISC = os.path.join(BASE, "assets", "pet_v3_discard")

PLAN = [
    ("idle",  ["pet_v2/idle/idle_01.png", "pet_v2/idle/idle_02.png",
               "pet_v2/idle/idle_03.png", "pet_v2/idle/idle_04.png",
               "pet_v5/setA/setA_01.png"]),
    ("sleep", ["pet_v2/sleep/sleep_01.png", "pet_v2/sleep/sleep_02.png",
               "pet_v5/setB/setB_08.png"]),
    ("wake",  ["pet_v5/setB/setB_09.png", "pet_v5/setA/setA_05.png"]),
    ("drag",  ["pet_v2/drag/drag_01.png", "pet_v2/drag/drag_02.png",
               "pet_v5/setB/setB_06.png", "pet_v5/setA/setA_06.png"]),
    ("click", ["pet_v2/click/click_01.png", "pet_v2/click/click_02.png",
               "pet_v5/setA/setA_02.png", "pet_v5/setA/setA_03.png"]),
    ("sidle", ["pet_v5/setA/setA_07.png", "pet_v5/setA/setA_08.png",
               "pet_v5/setA/setA_09.png"]),
    ("pat",   ["pet_v2/special/special_01.png", "pet_v2/special/special_02.png",
               "pet_v5/setB/setB_10.png"]),
]
DISCARD = ["pet_v5/setB/setB_07.png", "pet_v5/setA/setA_04.png",
           "pet_v5/setA/setA_10.png", "pet_v2/drag/drag_03.png"]

os.makedirs(DST, exist_ok=True)
os.makedirs(DISC, exist_ok=True)
for anim, srcs in PLAN:
    od = os.path.join(DST, anim)
    os.makedirs(od, exist_ok=True)
    for i, s in enumerate(srcs, 1):
        sp = os.path.join(BASE, "assets", s.replace("/", os.sep))
        assert os.path.exists(sp), f"缺少素材: {sp}"
        shutil.copy2(sp, os.path.join(od, f"{anim}_{i:02d}.png"))
for s in DISCARD:
    sp = os.path.join(BASE, "assets", s.replace("/", os.sep))
    if os.path.exists(sp):
        nm = os.path.basename(s)
        shutil.copy2(sp, os.path.join(DISC, nm if nm.startswith("set") else f"pet_v2_{nm}"))

# 动作池里"不在计划内"的残留 -> 移入废弃库(沙箱禁用删除, 用 move)
moved = []
for anim, srcs in PLAN:
    od = os.path.join(DST, anim)
    keep = {f"{anim}_{i:02d}.png" for i in range(1, len(srcs) + 1)}
    for fn in sorted(os.listdir(od)):
        if fn.lower().endswith(".png") and fn not in keep:
            shutil.move(os.path.join(od, fn), os.path.join(DISC, f"dropped_{fn}"))
            moved.append(f"{anim}/{fn}")
if moved:
    print("  已移入废弃库:", ", ".join(moved))

for anim, srcs in PLAN:
    print(f"  {anim:6} {len(srcs)} 帧")
print("合计:", sum(len(s) for _a, s in PLAN), "帧 ->", DST)
