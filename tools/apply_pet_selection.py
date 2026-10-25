# -*- coding: utf-8 -*-
"""2026-10-23: 按浅浅猫在 HTML 里的勾选结果, 把新素材并入桌宠行为库。

用法:
    python tools/apply_pet_selection.py <selection.json> [--dry] [--no-scale]

设计要点(防事故, 沿用历史纪律):
  1. **先整目录备份**目标库 -> assets/<lib>_bak_preSelection_<时间戳>/
  2. **wake 场景特殊处理** (浅浅猫要求): 现有 V3 睡醒帧全部**退役**到 assets/pet_alt/wake/old_*,
     只用这次选的新帧; 其余场景保留现有帧, 新帧追加编号接在后面。
  3. **尺寸对齐**: 4K 源切出的帧(如 692x860)远比现有库帧(200~365 宽)大, 默认按
     现有库帧的**中位高度**等比缩放, 保持与老素材同量级(绘制时本来就只显示 138px 高)。
     原始大图始终留在 assets/pet_new_20261023/ 不动, 可随时重来; `--no-scale` 关闭缩放。
  4. 逐帧校验: 源帧存在 + 本体连通域=1 + alpha 保留 -> 才写入。
  5. 退役 = 移动不删除(与 retire_pet_frames.py 同纪律), 写 pet_alt/index.json 记账。

输出: 目标库 <scene>/<scene>_NN.png, 并打印入库前后各场景帧数。
"""
import glob
import io
import json
import os
import shutil
import sys
import time

sys.dont_write_bytecode = True
import numpy as np
from PIL import Image
from scipy import ndimage

S8 = np.ones((3, 3), bool)
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# 2026-10-26 (第101轮): 批次由 --batch 指定(默认 20261023 保持旧用法兼容)。
#   浅浅猫选材在 HTML 里做, 每批一个 assets/pet_new_<批次>/
BATCH = "20261023"
for _a in sys.argv[1:]:
    if _a.startswith("--batch="):
        BATCH = _a.split("=", 1)[1]
NEW = os.path.join(BASE, "assets", "pet_new_%s" % BATCH)
ALT = os.path.join(BASE, "assets", "pet_alt")
SCENES = ("idle", "sleep", "wake", "drag", "click", "sidle", "pat")


def qc_ok(path):
    """成品帧质检: 本体连通域 = 1"""
    a = np.asarray(Image.open(path).convert("RGBA"))[..., 3]
    l, n = ndimage.label(a > 128, S8)
    if not n:
        return False
    sz = ndimage.sum(a > 128, l, range(1, n + 1))
    return sum(1 for v in sz if v >= 20000) == 1


def target_height(lib_dir):
    """取现有库帧的中位高度作为缩放基准"""
    hs = []
    for p in glob.glob(os.path.join(lib_dir, "*", "*.png")):
        try:
            hs.append(Image.open(p).size[1])
        except OSError:
            pass
    if not hs:
        return 347          # v3r 原素材基准
    hs.sort()
    return hs[len(hs) // 2]


def main():
    argv = sys.argv[1:]
    dry = "--dry" in argv
    no_scale = "--no-scale" in argv
    paths = [a for a in argv if not a.startswith("--")]
    if not paths:
        print(__doc__)
        sys.exit(1)
    sel = json.load(io.open(paths[0], encoding="utf-8"))
    lib = sel.get("target_library", "pet_v3r")
    lib_dir = os.path.join(BASE, "assets", lib)
    os.makedirs(lib_dir, exist_ok=True)
    th = target_height(lib_dir)
    print("=" * 78)
    print("入库目标: assets/%s   (dry=%s, scale=%s, 基准高=%dpx)" % (lib, dry, not no_scale, th))
    print("=" * 78)

    # 1) 备份
    tag = time.strftime("%Y%m%d_%H%M")
    bak = os.path.join(BASE, "assets", "%s_bak_preSelection_%s" % (lib, tag))
    if not dry and not os.path.exists(bak):
        shutil.copytree(lib_dir, bak)
        n = sum(1 for r, d, fs in os.walk(bak) for f in fs if f.endswith(".png"))
        print("已备份 %d 帧 -> %s" % (n, os.path.relpath(bak, BASE)))
    else:
        print("备份已存在或预演:", os.path.relpath(bak, BASE))

    # 2) wake: 退役现有帧 —— 仅在显式 --retire-wake 时执行。
    #    2026-10-23 那次是浅浅猫明确要求"睡醒素材弃用、只用新的"; 第101轮她没这么说,
    #    默认**保留**旧的再追加(否则会把刚验收过的 wake 帧白白挪走)。
    wake_new = ((sel.get("assignments") or {}).get("wake") or []) if "--retire-wake" in argv else []
    if wake_new:
        wd = os.path.join(lib_dir, "wake")
        olds = sorted(glob.glob(os.path.join(wd, "*.png"))) if os.path.isdir(wd) else []
        if olds:
            print("\n[wake] 退役 %d 帧旧睡醒素材 (浅浅猫要求: 只用新的)" % len(olds))
            altd = os.path.join(ALT, "wake")
            if not dry:
                os.makedirs(altd, exist_ok=True)
            for p in olds:
                dst = os.path.join(altd, "old_" + os.path.basename(p))
                print("   %s -> %s" % (os.path.basename(p), os.path.relpath(dst, BASE)))
                if not dry:
                    shutil.move(p, dst)
            idx_file = os.path.join(ALT, "index.json")
            try:
                idx = json.load(io.open(idx_file, encoding="utf-8"))
            except Exception:
                idx = {"v": 1, "note": "备选素材库", "items": []}
            for p in olds:
                idx["items"].append({"scene": "wake", "orig_name": os.path.basename(p),
                                     "file": "wake/old_" + os.path.basename(p),
                                     "was": "%s/wake/%s" % (lib, os.path.basename(p)),
                                     "retired_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                                     "reason": "2026-10-23 浅浅猫: 睡醒换用新素材"})
            if not dry:
                json.dump(idx, io.open(idx_file, "w", encoding="utf-8"),
                          ensure_ascii=False, indent=1)

    # 3) 逐场景写入
    print("\n各场景入库:")
    total = 0
    for sc in SCENES:
        items = (sel.get("assignments") or {}).get(sc) or []
        if not items:
            print("  %-6s  未选择, 保持原样" % sc)
            continue
        od = os.path.join(lib_dir, sc)
        exist = sorted(f for f in os.listdir(od) if f.lower().endswith(".png")) if os.path.isdir(od) else []
        base_n = len(exist)
        if not dry:
            os.makedirs(od, exist_ok=True)
        written = []
        for i, it in enumerate(items, 1):
            fid = it["id"] if isinstance(it, dict) else it      # 兼容 {id:...} 与纯 id 字符串
            src = os.path.join(NEW, fid + ".png")
            if not os.path.exists(src):
                print("    ★ 缺源帧 %s, 跳过" % src)
                continue
            if not qc_ok(src):
                print("    ★ 质检未过(本体数≠1) %s, 跳过" % fid)
                continue
            im = Image.open(src).convert("RGBA")
            if not no_scale and im.height > th:
                r = th / im.height
                im = im.resize((max(1, int(im.width * r)), th), Image.LANCZOS)
            name = "%s_%02d.png" % (sc, base_n + len(written) + 1)
            if not dry:
                im.save(os.path.join(od, name), optimize=True)
            written.append(name)
        total += len(written)
        print("  %-6s  现有 %d + 新增 %d -> %d 帧  %s"
              % (sc, base_n, len(written), base_n + len(written),
                 ", ".join(written) if written else ""))

    print("\n合计新增 %d 帧%s" % (total, "  (预演, 未改动任何文件)" if dry else ""))
    if not dry:
        print("备份: %s" % os.path.relpath(bak, BASE))
        print("提示: 素材需**重启桌宠进程**才会加载")


if __name__ == "__main__":
    main()
