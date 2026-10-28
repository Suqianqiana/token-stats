# -*- coding: utf-8 -*-
"""第102轮: 扫描素材目录, 做**精确 + 感知**双重去重, 输出"唯一源图清单"。

浅浅猫: "注意可能会有重复的图片, 记得辨别一下" —— 她的下载目录里同一张图
经常有多个副本(名字带 (1)/(2)、大小一样), 也可能是同一张的不同导出(压缩/尺寸
不同但内容一样)。所以:
  1) md5 精确去重
  2) 感知去重: 缩到 64x64, 用 alpha 加权灰度比平均绝对差(阈值 0.97)

用法: python -B tools/scan_sources.py "<目录>" [--out 清单json]
"""
import glob
import hashlib
import json
import os
import sys

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")
sys.dont_write_bytecode = True

import numpy as np
from PIL import Image


def md5(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sig(path, n=64):
    """感知签名: alpha 加权灰度(透明处为 0), 归一化到 0..1。"""
    im = Image.open(path).convert("RGBA").resize((n, n), Image.LANCZOS)
    a = np.asarray(im, dtype=np.float64)
    al = a[..., 3] / 255.0
    gray = (0.299 * a[..., 0] + 0.587 * a[..., 1] + 0.114 * a[..., 2]) * al
    return gray / 255.0


def sim(a, b):
    return 1.0 - float(np.abs(a - b).mean())


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return 1
    d = args[0]
    out = None
    for a in args[1:]:
        if a.startswith("--out="):
            out = a.split("=", 1)[1]
    files = [p for p in glob.glob(os.path.join(d, "*.png"))]
    files.sort(key=os.path.getmtime)
    print("目录:", d)
    print("png 数量:", len(files))

    # ---- 1) md5 精确去重 ----
    by_md5 = {}
    for p in files:
        by_md5.setdefault(md5(p), []).append(p)
    exact_dups = {k: v for k, v in by_md5.items() if len(v) > 1}
    uniq_files = sorted((v[0] for v in by_md5.values()), key=os.path.getmtime)
    print("\n[md5 精确重复] %d 组, 去重后 %d 张" % (len(exact_dups), len(uniq_files)))
    for k, v in exact_dups.items():
        print("  同 %s: %s" % (k[:8], " | ".join(os.path.basename(x) for x in v)))

    # ---- 2) 感知去重 ----
    print("\n[感知签名] 计算中 …")
    sigs = {}
    for p in uniq_files:
        try:
            sigs[p] = sig(p)
        except OSError as e:
            print("  !! 读不了", os.path.basename(p), e)
    groups = []                    # [(代表, [成员])]
    used = set()
    for p in uniq_files:
        if p in used or p not in sigs:
            continue
        members = [p]
        for q in uniq_files:
            if q in used or q == p or q not in sigs:
                continue
            s = sim(sigs[p], sigs[q])
            if s >= 0.97:
                members.append(q)
                used.add(q)
        used.add(p)
        if len(members) > 1:
            # ★ 重复组里要留**分辨率最高**的那张(同一内容常有 1536 小图 + 3840 的
            #   4K 版两个导出, 按时间取会留下小图, 白白丢了高清细节)。
            members.sort(key=lambda x: -Image.open(x).size[0] * Image.open(x).size[1])
            print("  %.4f 相似: %s  → 保留 %s"
                  % (sim(sigs[p], sigs[members[-1]]),
                     " | ".join(os.path.basename(x) for x in members),
                     os.path.basename(members[0])))
        groups.append((members[0], members))

    keep = [rep for rep, _m in groups]
    print("\n最终唯一源图 %d 张 (原始 %d)" % (len(keep), len(files)))
    for i, p in enumerate(keep, 1):
        im = Image.open(p)
        print("  %2d  %-44s %s" % (i, os.path.basename(p)[:42], "%dx%d" % im.size))

    if out:
        data = {"dir": d, "total": len(files), "unique": len(keep),
                "exact_dups": [{"md5": k[:12],
                                "files": [os.path.basename(x) for x in v]}
                               for k, v in exact_dups.items()],
                "perceptual_dups": [{"keep": os.path.basename(rep),
                                     "files": [os.path.basename(x) for x in m]}
                                    for rep, m in groups if len(m) > 1],
                "keep": [{"path": p, "name": os.path.basename(p),
                          "size": list(Image.open(p).size)} for p in keep]}
        with open(out, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
        print("\n清单 ->", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
