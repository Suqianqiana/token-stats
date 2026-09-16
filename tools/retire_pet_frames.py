# -*- coding: utf-8 -*-
"""把主素材库里不理想的帧「退役」到备选素材库, 并把剩余帧重排为连续编号。

用法:
    python tools/retire_pet_frames.py click 3 4                  # 退役 click_03 / click_04
    python tools/retire_pet_frames.py click 3 4 --reason "点击反馈不明显"
    python tools/retire_pet_frames.py click 3 4 --dry            # 只预演不改动

设计要点(都是踩过的坑):
  1. **退役 = 移动到备选库, 不是删除** —— 帧文件原样保留在 assets/pet_alt/<场景>/,
     名字带上原编号(old_click_03.png)以便溯源, 随时可以取回。
  2. **重排编号必须两步走** —— 先把剩余帧改成 .rtmp 临时名, 再改成目标名。
     直接原地改会撞名(click_05→click_03 时 click_03 可能还没让位)。
  3. 同步更新 assets/pet_v3_add/installed_map.json 里指向被重排文件的条目,
     否则映射表会指向不存在的文件, 以后没法追溯"某个姿势现在叫什么"。
  4. 不碰 card_app.py —— 加载是 glob + 文件名排序, 编号连续只是为了让
     「第 N 张」这种指认方式以后不再有歧义。
"""
import io
import json
import os
import shutil
import sys
import time

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAIN = os.path.join(BASE, "assets", "pet_v3r")
ALT = os.path.join(BASE, "assets", "pet_alt")
MAP_FILE = os.path.join(BASE, "assets", "pet_v3_add", "installed_map.json")


def list_frames(scene):
    d = os.path.join(MAIN, scene)
    if not os.path.isdir(d):
        return []
    return sorted(f for f in os.listdir(d) if f.lower().endswith(".png"))


def retire(scene, nums, reason="效果不理想", dry=False):
    frames = list_frames(scene)
    if not frames:
        print("场景不存在或没有帧:", scene)
        return False
    keep, drop = [], []
    for f in frames:
        try:
            n = int(os.path.splitext(f)[0].rsplit("_", 1)[1])
        except (IndexError, ValueError):
            keep.append(f)
            continue
        (drop if n in nums else keep).append(f)

    missing = [n for n in nums if not any(f.endswith("_%02d.png" % n) for f in drop)]
    if missing:
        print("这些编号不存在, 中止:", missing)
        return False

    print("场景 %s: 现有 %d 帧 → 退役 %d 帧, 保留 %d 帧" % (scene, len(frames), len(drop), len(keep)))
    print("  退役:", ", ".join(drop))
    print("  保留:", ", ".join(keep))

    # 旧编号 -> 新编号 的映射(供更新映射表用)
    rename = {}
    for i, f in enumerate(keep, 1):
        new = "%s_%02d.png" % (scene, i)
        if new != f:
            rename[f] = new
    if rename:
        print("  重排:", ", ".join("%s→%s" % (a, b) for a, b in rename.items()))
    else:
        print("  重排: 无需重排")

    if dry:
        print("(预演, 未改动任何文件)")
        return True

    # 1) 退役 → 备选素材库
    alt_dir = os.path.join(ALT, scene)
    os.makedirs(alt_dir, exist_ok=True)
    moved = []
    for f in drop:
        src = os.path.join(MAIN, scene, f)
        dst = os.path.join(alt_dir, "old_" + f)
        shutil.move(src, dst)
        moved.append(dst)
        print("  已退役 →", os.path.relpath(dst, BASE))

    # 2) 重排编号(两步走, 避免撞名)
    if rename:
        for old in rename:
            os.rename(os.path.join(MAIN, scene, old),
                      os.path.join(MAIN, scene, old + ".rtmp"))
        for old, new in rename.items():
            os.rename(os.path.join(MAIN, scene, old + ".rtmp"),
                      os.path.join(MAIN, scene, new))

    # 3) 记入备选库索引
    idx_file = os.path.join(ALT, "index.json")
    try:
        idx = json.load(io.open(idx_file, encoding="utf-8"))
    except Exception:
        idx = {"v": 1, "note": "备选素材库: 从主库退役的帧原样保留在这里, 可随时取回", "items": []}
    for f in drop:
        idx["items"].append({
            "scene": scene, "orig_name": f, "file": "%s/old_%s" % (scene, f),
            "was": "pet_v3r/%s/%s" % (scene, f),
            "retired_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "reason": reason,
        })
    with io.open(idx_file, "w", encoding="utf-8") as fp:
        json.dump(idx, fp, ensure_ascii=False, indent=1)
    print("  备选库索引 →", os.path.relpath(idx_file, BASE), "(累计 %d 项)" % len(idx["items"]))

    # 4) 同步新素材映射表
    if rename and os.path.exists(MAP_FILE):
        try:
            mp = json.load(io.open(MAP_FILE, encoding="utf-8"))
            changed = 0
            for key, val in list((mp.get("map") or {}).items()):
                if not isinstance(val, str) or "/" not in val:
                    continue
                sc, fn = val.split("/", 1)
                if sc == scene and fn in rename:
                    mp["map"][key] = "%s/%s" % (scene, rename[fn])
                    changed += 1
            if changed:
                mp.setdefault("renumber_log", []).append({
                    "at": time.strftime("%Y-%m-%d %H:%M:%S"), "scene": scene,
                    "retired": drop, "rename": rename,
                })
                with io.open(MAP_FILE, "w", encoding="utf-8") as fp:
                    json.dump(mp, fp, ensure_ascii=False, indent=1)
                print("  映射表已同步 %d 条 →" % changed, os.path.relpath(MAP_FILE, BASE))
        except Exception as e:
            print("  映射表同步失败(不影响帧文件):", e)

    left = list_frames(scene)
    print("  完成: %s 现有 %d 帧 → %s" % (scene, len(left), ", ".join(left)))
    return True


if __name__ == "__main__":
    argv = sys.argv[1:]
    dry = "--dry" in argv
    reason = "效果不理想"
    for a in argv:
        if a.startswith("--reason"):
            reason = a.split("=", 1)[1] if "=" in a else reason
    pos = [a for a in argv if not a.startswith("--") and not a.isdigit()]
    nums = [int(a) for a in argv if a.isdigit()]
    if not pos or not nums:
        print(__doc__)
        sys.exit(1)
    ok = retire(pos[0], nums, reason, dry)
    sys.exit(0 if ok else 1)
