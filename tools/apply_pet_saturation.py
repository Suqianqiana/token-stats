# -*- coding: utf-8 -*-
"""把饱和度增强应用到主素材库（**只动 09-17 新素材那一批**）。

浅猫 2026-09-17 确认的档位：k=1.20 + 平滑提亮 a=0.16。

安全设计（每条都是防事故的）：
  1. **先整目录备份**到 `assets/pet_v3r_bak_preSat_<日期>/`，并逐个核对字节数与哈希；
  2. **幂等标记** `assets/pet_v3r/_saturation.json`：同参数重复执行直接跳过 ——
     否则每跑一次就再叠一层饱和度，连跑两次颜色就毁了；
     `--force` 重做时**从备份里取原图**再增强，绝不"在已增强的图上再增强"；
  3. **只处理 `installed_map.json` 里那批新素材**（23 帧），22 帧原素材一个字节都不碰
     —— 原素材是颜色基准，改了就不齐了；
  4. 每帧校验：尺寸一致、**alpha 通道逐像素一致**（只允许 RGB 变化）。

用法:
    python tools/apply_pet_saturation.py --k=1.2 --lift=0.16 --dry   # 预演
    python tools/apply_pet_saturation.py --k=1.2 --lift=0.16         # 正式应用
    python tools/apply_pet_saturation.py --k=1.2 --lift=0.16 --force # 重做(从备份取原图)
"""
import hashlib
import io
import json
import os
import shutil
import sys
import time

import numpy as np
from PIL import Image

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "tools"))
from enhance_pet_saturation import enhance_array  # noqa: E402

MAIN = os.path.join(BASE, "assets", "pet_v3r")
MARK = os.path.join(MAIN, "_saturation.json")
MAP_FILE = os.path.join(BASE, "assets", "pet_v3_add", "installed_map.json")


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def targets():
    with io.open(MAP_FILE, encoding="utf-8") as f:
        mp = json.load(f).get("map") or {}
    out = []
    for orig, rel in sorted(mp.items()):
        if not isinstance(rel, str):
            continue
        p = os.path.join(MAIN, *rel.split("/"))
        if os.path.exists(p):
            out.append((orig, rel, p))
    return out


def read_mark():
    try:
        with io.open(MARK, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def backup(tag):
    dst = os.path.join(BASE, "assets", "pet_v3r_bak_preSat_%s" % tag)
    if os.path.exists(dst):
        print("备份目录已存在, 复用它:", os.path.relpath(dst, BASE))
        return dst
    shutil.copytree(MAIN, dst)
    n = sum(1 for r, d, fs in os.walk(dst) for f in fs if f.endswith(".png"))
    print("已备份 %d 帧 → %s" % (n, os.path.relpath(dst, BASE)))
    return dst


def main():
    argv = sys.argv[1:]
    k, lift, dry, force = 1.2, 0.16, False, False
    for a in argv:
        if a.startswith("--k="):
            k = float(a.split("=", 1)[1])
        elif a.startswith("--lift="):
            lift = float(a.split("=", 1)[1])
        elif a == "--dry":
            dry = True
        elif a == "--force":
            force = True

    mark = read_mark()
    if mark and not force:
        same = abs(mark.get("k", 0) - k) < 1e-9 and abs(mark.get("lift", 0) - lift) < 1e-9
        print("主库已应用过饱和度增强: k=%s lift=%s (%s, %d 帧)"
              % (mark.get("k"), mark.get("lift"), mark.get("at", "?"), len(mark.get("frames", []))))
        if same:
            print("参数相同 → 跳过（幂等保护：重复执行会把饱和度叠两次）。如需重做加 --force。")
            return
        print("参数不同 → 需 --force 才能真正重做（会从备份取原图再增强）。")
        return

    tg = targets()
    print("目标帧: %d 帧（只替换 09-17 新素材, 原素材不碰）" % len(tg))
    if not tg:
        print("没有可处理的目标帧")
        return
    if dry:
        for orig, rel, p in tg[:5]:
            a = np.asarray(Image.open(p).convert("RGBA"))
            print("   [预演] %-22s %s  %dx%d" % (rel, orig, a.shape[1], a.shape[0]))
        print("   ... 共 %d 帧（预演, 未改动任何文件）" % len(tg))
        return

    # 备份（--force 时复用已有备份，从原始图重做）
    bdir = (mark or {}).get("backup_dir")
    if force and bdir and os.path.isdir(os.path.join(BASE, bdir)):
        bdir = os.path.join(BASE, bdir)
        print("复用已有备份（从原图重做）:", os.path.relpath(bdir, BASE))
    else:
        bdir = backup(time.strftime("%Y%m%d_%H%M"))
    rel_bdir = os.path.relpath(bdir, BASE)

    ok, bad = [], []
    for orig, rel, p in tg:
        src = os.path.join(bdir, *rel.split("/"))     # 永远从备份取原图
        if not os.path.exists(src):
            bad.append("%s(备份缺失)" % rel)
            continue
        a = np.asarray(Image.open(src).convert("RGBA"))
        out = enhance_array(a, k, 1.0, lift)
        if out.shape != a.shape or not np.array_equal(out[..., 3], a[..., 3]):
            bad.append("%s(alpha/尺寸被改动)" % rel)
            continue
        Image.fromarray(out, "RGBA").save(p)
        ok.append(rel)

    with io.open(MARK, "w", encoding="utf-8") as f:
        json.dump({"k": k, "lift": lift, "at": time.strftime("%Y-%m-%d %H:%M:%S"),
                   "tool": "tools/apply_pet_saturation.py", "backup_dir": rel_bdir,
                   "frames": ok, "failed": bad}, f, ensure_ascii=False, indent=1)

    print("已替换 %d 帧; 失败 %d 帧 %s" % (len(ok), len(bad), bad or ""))
    print("标记 → %s（备份 %s）" % (os.path.relpath(MARK, BASE), rel_bdir))


if __name__ == "__main__":
    main()
