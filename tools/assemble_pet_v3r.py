# -*- coding: utf-8 -*-
"""按浅浅猫的安排把 v2 原版帧 + 新抠好的 v3 帧组装成新素材库 assets/pet_v3r/,
   并同步舍弃库 assets/pet_v3_discard/。

   动作池映射(用户 2026-09-14 指定):
     idle  = v2 idle 4帧 + setA_01                    (idle_01 为默认待机, 每帧停 2~3s)
     sleep = v2 sleep 2帧 + setB_08                    (每次只取一帧, 时长随机 >=90s)
     wake  = setB_09 / setA_05                         (随机取一个)
     drag  = v2 drag_01/02 (舍弃原 drag_03) + setB_06 + setA_06
     click = v2 click 2帧 + setA_02 setA_03
             (原第 5~9 号 = setB_01~05 于 2026-09-14 追加弃用 -> 废弃库)
     sidle = setA_07 setA_08 setA_09                   (特殊待机, 持续 15~60s)
     pat   = v2 special 2帧 + setB_10                  (每次只随机播一个)
"""
import os, shutil

BASE = r"C:\Users\a3564\WorkBuddy\2026-08-25-04-20-35\token-stats"
V2 = os.path.join(BASE, "assets", "pet_v2")
V3 = os.path.join(BASE, "assets", "pet_v3")
DST = os.path.join(BASE, "assets", "pet_v3r")
DISC = os.path.join(BASE, "assets", "pet_v3_discard")

# (目标动作, [源文件相对路径...])  顺序即 01..NN 编号
PLAN = [
    ("idle",  ["pet_v2/idle/idle_01.png", "pet_v2/idle/idle_02.png",
               "pet_v2/idle/idle_03.png", "pet_v2/idle/idle_04.png",
               "pet_v3/setA/setA_01.png"]),
    ("sleep", ["pet_v2/sleep/sleep_01.png", "pet_v2/sleep/sleep_02.png",
               "pet_v3/setB/setB_08.png"]),
    ("wake",  ["pet_v3/setB/setB_09.png", "pet_v3/setA/setA_05.png"]),
    ("drag",  ["pet_v2/drag/drag_01.png", "pet_v2/drag/drag_02.png",
               "pet_v3/setB/setB_06.png", "pet_v3/setA/setA_06.png"]),
    ("click", ["pet_v2/click/click_01.png", "pet_v2/click/click_02.png",
               "pet_v3/setA/setA_02.png", "pet_v3/setA/setA_03.png"]),
    ("sidle", ["pet_v3/setA/setA_07.png", "pet_v3/setA/setA_08.png",
               "pet_v3/setA/setA_09.png"]),
    ("pat",   ["pet_v2/special/special_01.png", "pet_v2/special/special_02.png",
               "pet_v3/setB/setB_10.png"]),
]
DISCARD = ["pet_v3/setB/setB_07.png", "pet_v3/setA/setA_04.png",
           "pet_v3/setA/setA_10.png", "pet_v2/drag/drag_03.png"]

for d in (DST, DISC):
    # 注意: 沙箱禁用 rmtree(回收站不可用->fail-closed), 改为直接覆盖同名文件
    os.makedirs(d, exist_ok=True)
for anim, srcs in PLAN:
    od = os.path.join(DST, anim)
    os.makedirs(od, exist_ok=True)
    for i, s in enumerate(srcs, 1):
        sp = os.path.join(BASE, "assets", s.replace("/", os.sep))
        assert os.path.exists(sp), f"缺少素材: {sp}"
        shutil.copy2(sp, os.path.join(od, f"{anim}_{i:02d}.png"))
for i, s in enumerate(DISCARD, 1):
    sp = os.path.join(BASE, "assets", s.replace("/", os.sep))
    assert os.path.exists(sp), f"缺少素材: {sp}"
    shutil.copy2(sp, os.path.join(DISC, os.path.basename(s).replace("set", "discard_set")
                                  if s.startswith("pet_v2") else os.path.basename(s)))

# 清理: 动作池里"不在计划内"的残留(上次组装留下的) -> **移入废弃库**
#   注意: 沙箱禁用删除(回收站不可用->fail-closed), 故用 shutil.move 而不是 os.remove;
#   这一步同时保证"弃用的帧不会残留在素材库里被桌宠读到"。
moved = []
for anim, srcs in PLAN:
    od = os.path.join(DST, anim)
    keep = {f"{anim}_{i:02d}.png" for i in range(1, len(srcs) + 1)}
    for fn in sorted(os.listdir(od)):
        if fn.lower().endswith(".png") and fn not in keep:
            dst = os.path.join(DISC, f"dropped_{fn}")
            shutil.move(os.path.join(od, fn), dst)
            moved.append(f"{anim}/{fn}")
if moved:
    print("  已移入废弃库:", ", ".join(moved))

for anim, srcs in PLAN:
    print(f"  {anim:6} {len(srcs)} 帧")
print("舍弃库:", sorted(os.listdir(DISC)))
print("合计:", sum(len(s) for _a, s in PLAN), "帧 ->", DST)
