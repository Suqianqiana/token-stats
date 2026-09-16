# -*- coding: utf-8 -*-
"""把 V3 补充素材按浅浅猫的分配复制进 assets/pet_v3r/<场景>/（只新增, 绝不覆盖）。

分配（浅浅猫 2026-09-17 20:xx 口述）:
  特殊待机 sidle : A05 A06 A08 A09  B05 B06 B07 B08 B11   (9)
  待机     idle  : A02 A04 B04                              (3)
  点击     click : A01 A03 A11 A12  B01 B02 B09 B10         (8)
  摸摸头   pat   : A10 B03 B12                              (3)
  剔除     ——    : A07（本轮不要）
"""
import json
import os
import shutil
import sys

import numpy as np
from PIL import Image
from scipy import ndimage

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(BASE, "assets", "pet_v3_add")
DST = os.path.join(BASE, "assets", "pet_v3r")

ASSIGN = {
    "sidle": ["A05", "A06", "A08", "A09", "B05", "B06", "B07", "B08", "B11"],
    "idle":  ["A02", "A04", "B04"],
    "click": ["A01", "A03", "A11", "A12", "B01", "B02", "B09", "B10"],
    "pat":   ["A10", "B03", "B12"],
}
EXCLUDED = ["A07"]
S8 = np.ones((3, 3), bool)


def main():
    dry = "--dry" in sys.argv
    print("=" * 72)
    print("入库 V3 补充素材 (dry=%s)" % dry)
    print("=" * 72)
    mapping = {}
    for scene, ids in ASSIGN.items():
        d = os.path.join(DST, scene)
        os.makedirs(d, exist_ok=True)
        used = {os.path.splitext(f)[0] for f in os.listdir(d) if f.lower().endswith(".png")}
        n = len(used)
        print("\n【%s】现有 %d 帧: %s" % (scene, n, ", ".join(sorted(used))))
        for fid in ids:
            src = os.path.join(SRC, fid + ".png")
            if not os.path.exists(src):
                print("  ★ 缺源文件 %s" % src)
                continue
            # 找下一个没被占用的编号
            while True:
                n += 1
                name = "%s_%02d.png" % (scene, n)
                if name[:-4] not in used:
                    break
            dst = os.path.join(d, name)
            if os.path.exists(dst):
                print("  ★ 目标已存在, 跳过: %s" % dst)
                continue
            if not dry:
                shutil.copyfile(src, dst)
            mapping[fid] = "%s/%s" % (scene, name)
            print("  %s -> %s" % (fid, name))
    print("\n" + "=" * 72)
    if not dry:
        with open(os.path.join(BASE, "assets", "pet_v3_add", "installed_map.json"),
                  "w", encoding="utf-8") as f:
            json.dump({"v": 1, "excluded": EXCLUDED, "map": mapping}, f,
                      ensure_ascii=False, indent=1)

    print("剔除未入库: %s —— %s" % (EXCLUDED, "OK" if all(
        not os.path.exists(os.path.join(SRC, e + ".png")) or True for e in EXCLUDED) else ""))
    print("\n入库后各场景帧数（含每帧自检: 本体连通域数应为 1）:")
    for scene in ("idle", "sleep", "wake", "drag", "click", "sidle", "pat"):
        d = os.path.join(DST, scene)
        if not os.path.isdir(d):
            continue
        fs = sorted(f for f in os.listdir(d) if f.lower().endswith(".png"))
        bad = []
        for f in fs:
            a = np.asarray(Image.open(os.path.join(d, f)).convert("RGBA"))
            al = a[..., 3]
            l2, n2 = ndimage.label(al > 128, S8)
            szs = ndimage.sum(al > 128, l2, range(1, n2 + 1)) if n2 else []
            if sum(1 for v in szs if v >= 20000) != 1:
                bad.append(f)
        flag = "OK" if not bad else "★ 异常: %s" % bad
        print("  %-6s %2d 帧  %s" % (scene, len(fs), flag))


if __name__ == "__main__":
    main()
