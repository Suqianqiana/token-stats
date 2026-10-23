# -*- coding: utf-8 -*-
"""2026-10-23: 按浅浅猫在 HTML 里勾选的结果执行退休 (批量版 retire_pet_frames)。

退休 = 移动到 assets/pet_alt/<场景>/old_*.png (不删除), 剩余帧两步重排为连续编号,
写 pet_alt/index.json 记账。与 tools/retire_pet_frames.py 同纪律。

用法: python tools/apply_retire.py <retire.json> [--dry]
"""
import glob
import io
import json
import os
import shutil
import sys
import time

sys.dont_write_bytecode = True
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIB = os.path.join(BASE, "assets", "pet_v3r")
ALT = os.path.join(BASE, "assets", "pet_alt")


def retire_scene(sc, names, reason, dry=False):
    d = os.path.join(LIB, sc)
    if not os.path.isdir(d):
        print("  [%s] 目录不存在, 跳过" % sc)
        return 0
    frames = sorted(f for f in os.listdir(d) if f.lower().endswith(".png"))
    drop = ["%s.png" % n for n in names]
    keep = [f for f in frames if f not in drop]
    missing = [f for f in drop if f not in frames]
    if missing:
        print("  [%s] ★ 这些帧不存在: %s" % (sc, missing))
    if not [f for f in drop if f in frames]:
        return 0
    print("  [%s] 现有 %d -> 退休 %d, 保留 %d" % (sc, len(frames), len(drop) - len(missing), len(keep)))
    if dry:
        print("     (预演) 将退休:", [f for f in drop if f in frames])
        return 0
    altd = os.path.join(ALT, sc)
    os.makedirs(altd, exist_ok=True)
    for f in [x for x in drop if x in frames]:
        dst = os.path.join(altd, "old_" + f)
        # ⚠️ 防撞名 (2026-10-23 事故: 新退休的 wake_01/02 把入库时退役的旧 V3 wake_01/02
        #   同名覆盖了, 靠 preSelection 备份才恢复)。目标已存在时加 _rN 后缀。
        if os.path.exists(dst):
            k = 2
            while os.path.exists(os.path.join(altd, "old_%s_r%d.png" % (f[:-4], k))):
                k += 1
            dst = os.path.join(altd, "old_%s_r%d.png" % (f[:-4], k))
            print("     !! 目标已存在, 改用:", os.path.basename(dst))
        shutil.move(os.path.join(d, f), dst)
        print("     -> %s" % os.path.relpath(dst, BASE))
    # 两步重排 (避免撞名)
    for i, f in enumerate(keep, 1):
        new = "%s_%02d.png" % (sc, i)
        if new != f:
            os.rename(os.path.join(d, f), os.path.join(d, f + ".rtmp"))
    for i, f in enumerate(keep, 1):
        new = "%s_%02d.png" % (sc, i)
        if new != f:
            os.rename(os.path.join(d, f + ".rtmp"), os.path.join(d, new))
    return len([x for x in drop if x in frames])


def main():
    argv = sys.argv[1:]
    dry = "--dry" in argv
    paths = [a for a in argv if not a.startswith("--")]
    if not paths:
        print(__doc__)
        sys.exit(1)
    sel = json.load(io.open(paths[0], encoding="utf-8"))
    retire = sel.get("retire") or {}
    reason = "2026-10-23 浅浅猫在 V3 清单页勾选退休"
    print("=" * 70)
    print("执行退休 (dry=%s), 共 %d 个场景" % (dry, len(retire)))
    print("=" * 70)
    n = 0
    for sc, names in retire.items():
        n += retire_scene(sc, names, reason, dry)
    if not dry:
        idx_file = os.path.join(ALT, "index.json")
        try:
            idx = json.load(io.open(idx_file, encoding="utf-8"))
        except Exception:
            idx = {"v": 1, "note": "备选素材库: 从主库退役的帧原样保留在这里, 可随时取回", "items": []}
        for sc, names in retire.items():
            for nm in names:
                idx["items"].append({"scene": sc, "orig_name": nm + ".png",
                                     "file": "%s/old_%s.png" % (sc, nm),
                                     "was": "pet_v3r/%s/%s.png" % (sc, nm),
                                     "retired_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                                     "reason": reason})
        # 去掉"指向不存在文件"的条目 (防撞名改名后旧指向失效)
        idx["items"] = [it for it in idx["items"]
                        if os.path.exists(os.path.join(ALT, it["file"]))]
        json.dump(idx, io.open(idx_file, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("\n备选库索引已更新 (累计 %d 项)" % len(idx["items"]))
        total = sum(len(glob.glob(os.path.join(LIB, "*", "*.png"))) for _ in [0])
        per = {sc: len(glob.glob(os.path.join(LIB, sc, "*.png"))) for sc in
               ("idle", "sleep", "wake", "drag", "click", "sidle", "pat")}
        print("退休后库: %s = 共 %d 帧" % (per, sum(per.values())))
    print("退休 %d 帧%s" % (n, "  (预演, 未改动任何文件)" if dry else ""))


if __name__ == "__main__":
    main()
