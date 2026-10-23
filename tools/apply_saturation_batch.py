# -*- coding: utf-8 -*-
"""2026-10-23: 新批次 95 帧饱和度 + 平滑提亮全量应用 (浅浅猫确认 k=1.06/lift=0.10)。

公式与 docs/素材饱和度优化.md 完全一致:
    S' = S * k                     (饱和度)
    V' = V + a*V*(1-V)             (平滑提亮: 中间调提亮多, 高光/暗部几乎不动)
    alpha 通道一个字节都不动

防事故纪律 (每条都是历史踩坑):
  1. 先整目录备份当前库 -> assets/pet_v3r_bak_preSat_<时间戳>/ (与 09-17 同规矩)
  2. **幂等**: assets/pet_v3r/_saturation.json 记批次; 同 batch 同参数重复执行直接跳过
  3. **只碰 2026-10-23 这批新入库的 95 帧** —— 帧名从 selection JSON + 入库前备份
     (pet_v3r_bak_preSelection_*) 的原有帧数重放编号推出, 老素材一字节不碰
  4. 每帧校验: 尺寸一致 + alpha 逐像素一致, 只允许 RGB 变

用法:
    python tools/apply_saturation_batch.py --dry
    python tools/apply_saturation_batch.py --k=1.06 --lift=0.10
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

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIB = os.path.join(BASE, "assets", "pet_v3r")
SEL = os.path.join(BASE, "docs", "pet_selection_20261023.json")
MARK = os.path.join(LIB, "_saturation.json")
SCENES = ("idle", "sleep", "wake", "drag", "click", "sidle", "pat")
K, LIFT = 1.06, 0.10


def enhance_array(a, k, lift):
    """RGBA ndarray -> 只改 S/V, alpha 原样 (与 09-17 同公式)"""
    im = Image.fromarray(a, "RGBA")
    hsv = np.asarray(im.convert("HSV")).astype(np.float64)
    H, S, V = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    S2 = np.clip(S * k, 0, 255)
    V2 = np.clip(V + lift * V * (1.0 - V / 255.0), 0, 255)
    out_hsv = np.dstack([H, S2, V2]).astype(np.uint8)
    out = np.asarray(Image.fromarray(out_hsv, "HSV").convert("RGBA")).copy()
    out[..., 3] = a[..., 3]
    return out


def new_frame_names():
    """重放入库时的编号: selection ids 顺序 + 各场景原有帧数 -> 新帧在库里的文件名。
    ⚠️ wake 特殊: 入库时旧 wake 帧**先全部退役**再写入新帧, 所以新 wake 从 _01 起,
       不是 base_n+1 (2026-10-23 实测踩过: 按 base_n 算成 wake_03 起, 漏增强 wake_01/02)。"""
    sel = json.load(io.open(SEL, encoding="utf-8"))
    baks = sorted(glob.glob(os.path.join(BASE, "assets", "pet_v3r_bak_preSelection_*")))
    if not baks:
        print("!! 找不到入库前备份, 无法推算新帧编号")
        sys.exit(1)
    bak = baks[-1]
    out = {}
    for sc in SCENES:
        old_dir = os.path.join(bak, sc)
        base_n = len(os.listdir(old_dir)) if os.path.isdir(old_dir) else 0
        if sc == "wake":
            base_n = 0          # 旧 wake 入库时已退役, 新帧从 01 起
        ids = sel.get("assignments", {}).get(sc) or []
        for i, fid in enumerate(ids, 1):
            out["%s/%s_%02d.png" % (sc, sc, base_n + i)] = fid
    return out


def read_mark():
    try:
        with io.open(MARK, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def main():
    argv = sys.argv[1:]
    dry = "--dry" in argv
    k, lift = K, LIFT
    for a in argv:
        if a.startswith("--k="):
            k = float(a.split("=", 1)[1])
        elif a.startswith("--lift="):
            lift = float(a.split("=", 1)[1])
    batch = "2026-10-23"

    mark = read_mark()
    applied = []
    if mark:
        # 兼容两种格式: 旧 {k,lift,...} 单条 与 新 {applied:[...]}
        if "applied" in mark:
            applied = mark["applied"]
        else:
            applied = [{"batch": "2026-09-17", "k": mark.get("k"), "lift": mark.get("lift"),
                        "at": mark.get("at"), "frames": mark.get("frames", [])}]
    for ap in applied:
        if ap.get("batch") == batch and abs(ap.get("k", 0) - k) < 1e-9 and abs(ap.get("lift", 0) - lift) < 1e-9:
            print("本批次已应用过 k=%s lift=%s (%s, %d 帧) -> 跳过 (幂等保护)"
                  % (ap.get("k"), ap.get("lift"), ap.get("at"), len(ap.get("frames", []))))
            return

    targets = new_frame_names()
    print("=" * 76)
    print("饱和度 + 平滑提亮: k=%.2f  lift=%.2f   目标 %d 帧 (仅 2026-10-23 新批次)" % (k, lift, len(targets)))
    print("=" * 76)
    if dry:
        for rel in list(targets)[:5]:
            print("   [预演]", rel, "<-", targets[rel])
        print("   ... 共 %d 帧 (预演, 未改动任何文件)" % len(targets))
        return

    tag = time.strftime("%Y%m%d_%H%M")
    bak = os.path.join(BASE, "assets", "pet_v3r_bak_preSat_%s" % tag)
    shutil.copytree(LIB, bak)
    n_bak = sum(1 for r, d, fs in os.walk(bak) for f in fs if f.endswith(".png"))
    print("已备份当前库 %d 帧 -> %s" % (n_bak, os.path.relpath(bak, BASE)))

    ok, bad = [], []
    for rel, fid in targets.items():
        p = os.path.join(LIB, *rel.split("/"))
        src = os.path.join(bak, *rel.split("/"))          # 永远从备份取原图
        if not os.path.exists(src):
            bad.append("%s(备份缺失)" % rel)
            continue
        a = np.asarray(Image.open(src).convert("RGBA"))
        out = enhance_array(a, k, lift)
        if out.shape != a.shape or not np.array_equal(out[..., 3], a[..., 3]):
            bad.append("%s(alpha/尺寸被改动)" % rel)
            continue
        Image.fromarray(out, "RGBA").save(p, optimize=True)
        ok.append(rel)

    applied.append({"batch": batch, "k": k, "lift": lift,
                    "at": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "tool": "tools/apply_saturation_batch.py",
                    "backup_dir": os.path.relpath(bak, BASE),
                    "frames": ok, "failed": bad})
    with io.open(MARK, "w", encoding="utf-8") as f:
        json.dump({"applied": applied}, f, ensure_ascii=False, indent=1)
    print("已增强 %d 帧; 失败 %d 帧 %s" % (len(ok), len(bad), bad or ""))
    print("幂等标记 -> %s (含历史 %d 个批次)" % (os.path.relpath(MARK, BASE), len(applied)))


if __name__ == "__main__":
    main()
