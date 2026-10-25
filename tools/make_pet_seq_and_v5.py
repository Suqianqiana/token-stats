# -*- coding: utf-8 -*-
"""① 睡觉完整动作帧（A 套 8 帧）-> assets/pet_v3r/seq/sleep/A/
   ② V5 素材（贴纸包 7 切片）-> assets/pet_v5/

设计要点（第99轮）:
  * 睡觉序列: 8 帧用**并集 alpha bbox 统一裁切**再整体缩放 —— 各帧画布一致,
    内容相对位置保持原样, 播放时不会有"抖动/位移"。
  * V5: 7 个切片共用**同一个全局缩放系数**, 保持贴纸包内的原始相对大小;
    同场景(站姿 idle+click / 躺姿 sleep)用**统一画布**居中底部对齐,
    避免逐帧尺寸差异导致绘制时缩放比变化(=大小跳动)。

用法: python -B tools/make_pet_seq_and_v5.py
"""
import sys
sys.dont_write_bytecode = True
import os
import json
import numpy as np
from PIL import Image

ROOT = r"C:\Users\a3564\WorkBuddy\2026-08-25-04-20-35\token-stats"
SEQ_SRC = (r"C:\Users\a3564\Downloads\%E6%A1%8C%E5%AE%A0%E7%9D%A1%E8%A7%89%E5%8A%A8%E4%BD%9C"
           r"%E5%B8%A7_%E4%B8%A4%E5%A5%978%E5%B8%A7_2K%E9%80%8F%E6%98%8EPNG")
SEQ_GROUP = "A_枕头与鲸鱼花纹被子"
SEQ_DST = os.path.join(ROOT, "assets", "pet_v3r", "seq", "sleep", "A")
PARTS = os.path.join(ROOT, "assets", "_v5_parts")
V5_DST = os.path.join(ROOT, "assets", "pet_v5")
DOCS = os.path.join(ROOT, "docs")

SEQ_TARGET_H = 359      # 与库内其它帧同量级(高分辨率), 绘制时再统一缩放
V5_SCALE = 0.7495       # 全局缩放: 待机角色高 470~480px -> 352~360px
SEQ_MS = 1000           # 睡觉动画单帧停留(ms): 8 帧一轮 8s


def bbox_union(paths, thr=8):
    x0 = y0 = 10 ** 9
    x1 = y1 = -1
    for p in paths:
        a = np.asarray(Image.open(p).convert("RGBA"))[:, :, 3]
        ys, xs = np.where(a > thr)
        x0 = min(x0, int(xs.min())); y0 = min(y0, int(ys.min()))
        x1 = max(x1, int(xs.max()) + 1); y1 = max(y1, int(ys.max()) + 1)
    return x0, y0, x1, y1


def do_sleep_seq():
    src = os.path.join(SEQ_SRC, SEQ_GROUP)
    files = sorted(f for f in os.listdir(src) if f.lower().endswith(".png"))
    paths = [os.path.join(src, f) for f in files]
    print("[睡觉序列] %s -> %d 帧" % (SEQ_GROUP, len(paths)))
    bb = bbox_union(paths)
    cw, ch = bb[2] - bb[0], bb[3] - bb[1]
    scale = SEQ_TARGET_H / float(ch)
    tw, th = max(1, int(round(cw * scale))), SEQ_TARGET_H
    print("  并集 bbox=%s (%dx%d) -> 画布 %dx%d" % (bb, cw, ch, tw, th))
    os.makedirs(SEQ_DST, exist_ok=True)
    # 清掉旧的 01..08, 防止重跑堆积
    for f in os.listdir(SEQ_DST):
        if f.lower().endswith(".png"):
            os.remove(os.path.join(SEQ_DST, f))
    for i, p in enumerate(paths, start=1):
        im = Image.open(p).convert("RGBA").crop(bb)
        im = im.resize((tw, th), Image.LANCZOS)
        out = os.path.join(SEQ_DST, "%02d.png" % i)
        im.save(out, optimize=True)
        print("  %s -> %s (%dx%d, %d B)" % (os.path.basename(p), os.path.basename(out),
                                            im.width, im.height, os.path.getsize(out)))
    with open(os.path.join(SEQ_DST, "seq.json"), "w", encoding="utf-8") as f:
        json.dump({"ms": SEQ_MS,
                   "note": "睡觉完整动作帧 A 套（枕头与鲸鱼花纹被子）8 帧循环"},
                  f, ensure_ascii=False, indent=1)
    # 预览: 8 帧并排
    tiles = [Image.open(os.path.join(SEQ_DST, "%02d.png" % i)) for i in range(1, len(paths) + 1)]
    sheet = Image.new("RGB", (sum(t.width for t in tiles) + 8 * (len(tiles) + 1), th + 16),
                      (250, 250, 252))
    x = 8
    for t in tiles:
        sheet.paste(t, (x, 8), t)
        x += t.width + 8
    sp = os.path.join(DOCS, "_sleep_seq_sheet.png")
    sheet.save(sp)
    print("  预览 ->", sp)


def do_v5():
    meta = json.load(open(os.path.join(PARTS, "parts.json"), encoding="utf-8"))
    by = {m["name"]: m for m in meta}

    def load(n):
        return Image.open(os.path.join(PARTS, n + ".png")).convert("RGBA")

    groups = {
        # 组名 -> (输出子目录, 成员)
        "stand": [("idle", "idle_01"), ("idle", "idle_02"), ("idle", "idle_03"), ("idle", "idle_04")],
    }
    # ---- 站姿组: idle x4 + click x1 共用画布 ----
    stand = [("idle", "idle_01"), ("idle", "idle_02"), ("idle", "idle_03"), ("idle", "idle_04"),
             ("click", "click_01")]
    scaled = []
    for scene, name in stand:
        im = load(name)
        w = max(1, int(round(im.width * V5_SCALE)))
        h = max(1, int(round(im.height * V5_SCALE)))
        scaled.append((scene, name, im.resize((w, h), Image.LANCZOS)))
    cw = max(im.width for _, _, im in scaled)
    ch = max(im.height for _, _, im in scaled)
    print("[V5] 站姿画布 %dx%d" % (cw, ch))

    # ---- 躺姿组: sleep x2 共用画布 ----
    lie = [("sleep", "sleep_01"), ("sleep", "sleep_02")]
    scaled_lie = []
    for scene, name in lie:
        im = load(name)
        w = max(1, int(round(im.width * V5_SCALE)))
        h = max(1, int(round(im.height * V5_SCALE)))
        scaled_lie.append((scene, name, im.resize((w, h), Image.LANCZOS)))
    cw2 = max(im.width for _, _, im in scaled_lie)
    ch2 = max(im.height for _, _, im in scaled_lie)
    print("[V5] 躺姿画布 %dx%d" % (cw2, ch2))

    def fit(im, w, h):
        """底部对齐 + 水平居中放进统一画布 —— 保证同组帧尺寸完全一致(绘制缩放比不跳)。"""
        canvas = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        canvas.paste(im, ((w - im.width) // 2, h - im.height), im)
        return canvas

    plan = []          # (scene, outname, image)
    canvas_map = {}
    for scene, name, im in scaled:
        c = fit(im, cw, ch)
        canvas_map[name] = c.copy()
        plan.append((scene, name, c))
    for scene, name, im in scaled_lie:
        plan.append((scene, name, fit(im, cw2, ch2)))

    # ---- 派生: drag = idle_01 (被拖动时保持站姿) / wake = idle_04 (闭眼+动作线, 像刚醒) ----
    #   ⚠️ 必须套同一张站姿画布, 否则这两张尺寸与 idle 不同 -> 拖拽/睡醒瞬间角色大小跳变。
    plan.append(("drag", "drag_01", canvas_map["idle_01"]))
    plan.append(("wake", "wake_01", canvas_map["idle_04"]))

    # 写出 (先清空目标目录里的 png, 支持重跑)
    for scene in set(s for s, _, _ in plan):
        d = os.path.join(V5_DST, scene)
        os.makedirs(d, exist_ok=True)
        for f in os.listdir(d):
            if f.lower().endswith(".png"):
                os.remove(os.path.join(d, f))
    for scene, name, im in plan:
        p = os.path.join(V5_DST, scene, name + ".png")
        im.save(p, optimize=True)
        print("  %-9s %-12s %dx%d  %d B" % (scene, name, im.width, im.height,
                                            os.path.getsize(p)))

    # 预览: 按场景分组并排
    order = ["idle", "click", "sleep", "wake", "drag"]
    tiles = []
    for scene in order:
        d = os.path.join(V5_DST, scene)
        for f in sorted(x for x in os.listdir(d) if x.endswith(".png")):
            tiles.append((scene + "/" + f, Image.open(os.path.join(d, f)).convert("RGBA")))
    from PIL import ImageDraw
    pad = 10
    W = sum(t.width for _, t in tiles) + pad * (len(tiles) + 1)
    H = max(t.height for _, t in tiles) + 34
    sheet = Image.new("RGB", (W, H), (250, 250, 252))
    dr = ImageDraw.Draw(sheet)
    x = pad
    for name, t in tiles:
        sheet.paste(t, (x, 28), t)
        dr.text((x + 1, 10), name, fill=(20, 20, 20))
        x += t.width + pad
    p = os.path.join(DOCS, "_v5_final_sheet.png")
    sheet.save(p)
    print("  预览 ->", p, sheet.size)


if __name__ == "__main__":
    do_sleep_seq()
    print()
    do_v5()
