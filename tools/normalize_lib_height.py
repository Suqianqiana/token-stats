# -*- coding: utf-8 -*-
"""第101轮: 把 V5 库所有帧的高度**统一**到基准高(等比缩放, 含放大)。

为什么: 第99轮定下的纪律是"同场景统一画布" —— 混入 140 帧新素材后, 各帧高度
参差(333~360, 因为落地脚本只缩不放), 会破坏回归里"V5 站姿组/躺姿组画布一致"
这条断言。而 paintEvent 是逐帧算缩放比的, 高度不齐确实有大小跳动的隐患。
统一成同一高度后: 显示时高度恒定, 宽度随角色自然变化 —— 既规范又安全。

用法: python -B tools/normalize_lib_height.py pet_v5 [基准高(不给=取库中位数)]
"""
import glob
import os
import shutil
import sys
import time

sys.dont_write_bytecode = True
from PIL import Image

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    lib = sys.argv[1] if len(sys.argv) > 1 else "pet_v5"
    lib_dir = os.path.join(BASE, "assets", lib)
    if not os.path.isdir(lib_dir):
        print("!! 没有这个库:", lib_dir)
        return 1
    files = sorted(glob.glob(os.path.join(lib_dir, "*", "*.png")))
    if not files:
        print("!! 库是空的")
        return 1
    if len(sys.argv) > 2:
        th = int(sys.argv[2])
    else:
        hs = sorted(Image.open(p).height for p in files)
        th = hs[len(hs) // 2]
    print("库: assets/%s   帧 %d   基准高 %dpx" % (lib, len(files), th))

    tag = time.strftime("%Y%m%d_%H%M")
    bak = os.path.join(BASE, "assets", "%s_bak_preNormalize_%s" % (lib, tag))
    shutil.copytree(lib_dir, bak)
    print("已备份 -> %s" % os.path.relpath(bak, BASE))

    changed = 0
    for p in files:
        im = Image.open(p).convert("RGBA")
        if im.height == th:
            continue
        r = th / im.height
        im.resize((max(1, int(round(im.width * r))), th), Image.LANCZOS).save(p, optimize=True)
        changed += 1
    print("调整 %d 帧, 其余 %d 帧已是 %d 高" % (changed, len(files) - changed, th))

    hs = sorted(Image.open(p).height for p in sorted(glob.glob(os.path.join(lib_dir, "*", "*.png"))))
    print("复核: 帧高集合 =", sorted(set(hs)), "→", "统一 ✓" if len(set(hs)) == 1 else "仍不齐 ★")
    return 0


if __name__ == "__main__":
    sys.exit(main())
