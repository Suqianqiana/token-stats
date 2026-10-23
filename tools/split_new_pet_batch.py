# -*- coding: utf-8 -*-
"""2026-10-23: 统一切分浅浅猫新制作的 11 张桌宠动作素材 (零抠图 + alpha 连通域)。

沿用 v3_add/v4 已验收的管线:
  1. alpha>128 连通域 -> 面积 >= BG_AREA(按图幅自适应) = 角色本体; 小件 = 装饰
  2. 装饰件归附 bbox 距离最近的角色(<= DEC_DIST), 不清 label==0(本角色自己的抗锯齿边缘)
  3. 行带分组 -> 行优先编号 G<组>_<NN>
  4. QC: 成品本体连通域数(应=1) / 尺寸 / 面积 / 半透明像素 / 透明占比
输出: assets/pet_new_20261023/
  G01_01.png ... (单帧, 保留原始 alpha, bbox 紧贴)
  thumbs/G01_01.png (高 150px 缩略图, HTML 预览用)
  manifest.json (全部元数据 + QC)
"""
import json
import os
import sys

sys.dont_write_bytecode = True
import numpy as np
from PIL import Image
from scipy import ndimage

S8 = np.ones((3, 3), bool)
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(BASE, "assets", "pet_new_20261023")
THUMB = os.path.join(OUT, "thumbs")
DL = os.path.join(os.path.expanduser("~"), "Downloads")

# (组号, 源文件名, 中文简称)
SOURCES = [
    ("G01", "蓝发鲸鱼女仆日常贴纸合集.png", "女仆日常贴纸合集"),
    ("G02", "桌宠新动作素材_4K透明.png", "新动作素材·第二批"),
    ("G03", "蓝发鲸鱼少女表情贴纸合集.png", "少女表情贴纸合集"),
    ("G04", "桌宠新动作素材_无标签第三批_4K透明.png", "无标签第三批"),
    ("G05", "蓝鲸主题女仆少女贴纸表情集.png", "女仆少女表情集"),
    ("G06", "蓝鲸主题少女贴纸图鉴.png", "少女贴纸图鉴"),
    ("G07", "蓝发鲸鱼女仆十二格贴纸合集.png", "女仆十二格合集"),
    ("G08", "蓝发鲸鱼女仆日常贴纸集.png", "女仆日常贴纸集"),
    ("G09", "桌宠睡觉睡醒与日常动作_6x2_4K透明.png", "睡觉睡醒与日常"),
    ("G10", "蓝色鲸鱼女仆的日常贴纸集.png", "蓝色女仆日常集"),
    ("G11", "蓝鲸少女的十二种日常姿态.png", "十二种日常姿态"),
]

DEC_MIN = 8
THUMB_H = 150


def bbox_dist(a, b):
    """bbox=(y0,y1,x0,x1) 最短距离"""
    dy = max(0, max(a[0], b[0]) - min(a[1], b[1]))
    dx = max(0, max(a[2], b[2]) - min(a[3], b[3]))
    return (dy * dy + dx * dx) ** 0.5


def process(gid, fname, cname):
    p = os.path.join(DL, fname)
    if not os.path.exists(p):
        print("!! 缺源图:", fname)
        return None
    im = Image.open(p).convert("RGBA")
    A = np.asarray(im).copy()
    al = A[..., 3]
    H, W = al.shape
    # 阈值按图幅自适应 (基准 1536x1024)
    scale = max(W, H) / 1536.0
    bg_area = int(20000 * scale * scale)
    dec_dist = 90 * scale
    fg = al > 128
    lbl, n = ndimage.label(fg, S8)
    areas = ndimage.sum(fg, lbl, range(1, n + 1)) if n else []
    objs = ndimage.find_objects(lbl)

    bigs, smalls = [], []
    # 2026-10-23 (浅浅猫报告): 标签剔除口径 —— 面积>=3000*scale^2 且 高<8%图高 且 宽>=1.5高。
    #   G02 大标签(~730x150, 面积8万) 与 G01/G03 小胶囊(~150x44, 面积5k~8k) 都靠这条挡住;
    #   第一版口径(面积>=30000)漏掉了小胶囊, 被当装饰归附进角色帧(帧宽被撑大)。
    lab_min = int(3000 * scale * scale)
    for i in range(1, n + 1):
        sl = objs[i - 1]
        if sl is None:
            continue
        bb = (sl[0].start, sl[0].stop - 1, sl[1].start, sl[1].stop - 1)
        hh = bb[1] - bb[0] + 1
        ww = bb[3] - bb[2] + 1
        if areas[i - 1] >= lab_min and hh < 0.08 * H and ww >= 1.5 * hh:
            continue                      # 标签: 不参与角色/装饰归附
        if areas[i - 1] >= bg_area:
            bigs.append({"id": i, "bb": bb, "area": int(areas[i - 1])})
        elif areas[i - 1] >= DEC_MIN:
            smalls.append({"id": i, "bb": bb, "area": int(areas[i - 1])})

    for s in smalls:
        best, bd = None, 1e9
        for b in bigs:
            d = bbox_dist(s["bb"], b["bb"])
            if d < bd:
                best, bd = b, d
        if best is not None and bd <= dec_dist:
            best.setdefault("decs", []).append(s["id"])
        else:
            s["dropped"] = True

    # 行带分组 -> 行优先
    bigs.sort(key=lambda b: (b["bb"][0], b["bb"][2]))
    rows_g = []
    for b in bigs:
        yc = (b["bb"][0] + b["bb"][1]) / 2.0
        for r in rows_g:
            if abs(r["yc"] - yc) < 150 * scale:
                r["items"].append(b)
                r["yc"] = float(np.mean([(x["bb"][0] + x["bb"][1]) / 2.0 for x in r["items"]]))
                break
        else:
            rows_g.append({"yc": yc, "items": [b]})
    rows_g.sort(key=lambda r: r["yc"])
    ordered = []
    for r in rows_g:
        r["items"].sort(key=lambda b: b["bb"][2])
        ordered += r["items"]

    frames = []
    for k, b in enumerate(ordered, 1):
        keep = [b["id"]] + b.get("decs", [])
        decs_bb = [next(s["bb"] for s in smalls if s["id"] == i) for i in b.get("decs", [])]
        y0 = min([b["bb"][0]] + [d[0] for d in decs_bb])
        y1 = max([b["bb"][1]] + [d[1] for d in decs_bb])
        x0 = min([b["bb"][2]] + [d[2] for d in decs_bb])
        x1 = max([b["bb"][3]] + [d[3] for d in decs_bb])
        sub = A[y0:y1 + 1, x0:x1 + 1].copy()
        sub_lbl = lbl[y0:y1 + 1, x0:x1 + 1]
        # 只清"属于其它角色/已归附其它角色的装饰件"的像素; label==0 是自己的抗锯齿边
        foreign = (sub_lbl != 0) & ~np.isin(sub_lbl, keep)
        sub[foreign, 3] = 0

        name = "%s_%02d.png" % (gid, k)
        out = Image.fromarray(sub)
        out.save(os.path.join(OUT, name), optimize=True)
        # 缩略图 (保透明)
        th = out.copy()
        r = THUMB_H / th.height
        th = th.resize((max(1, int(th.width * r)), THUMB_H), Image.LANCZOS)
        th.save(os.path.join(THUMB, name), optimize=True)

        # QC: 成品本体连通域数
        al2 = sub[..., 3]
        l2, n2 = ndimage.label(al2 > 128, S8)
        a2 = ndimage.sum(al2 > 128, l2, range(1, n2 + 1)) if n2 else []
        nbody = int(sum(1 for v in a2 if v >= bg_area))
        semi = int(((al2 > 0) & (al2 <= 128)).sum())
        trans = float((al2 == 0).mean() * 100)
        hh, ww = sub.shape[0], sub.shape[1]
        frames.append(dict(
            id=name[:-4], source=fname, source_cn=cname,
            size=[ww, hh], body_area=b["area"],
            decorations=len(b.get("decs", [])),
            selfcheck_bodies=nbody, semi=semi, trans_pct=round(trans, 1),
        ))
        flag = "" if nbody == 1 else "  ★本体数=%d(粘连?)" % nbody
        print("  %s  %4dx%-4d 面积%7d 装饰%2d 半透明%6d%s" % (name, ww, hh, b["area"], len(b.get("decs", [])), semi, flag))
    return dict(gid=gid, source=fname, source_cn=cname, src_size=[W, H], frames=frames)


def main():
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(THUMB, exist_ok=True)
    groups = []
    for gid, fname, cname in SOURCES:
        print("== %s %s" % (gid, fname))
        g = process(gid, fname, cname)
        if g:
            groups.append(g)
    manifest = dict(v=1, generated="2026-10-23", groups=groups,
                    total=sum(len(g["frames"]) for g in groups))
    with open(os.path.join(OUT, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)
    bad = [(g["gid"], fr["id"]) for g in groups for fr in g["frames"] if fr["selfcheck_bodies"] != 1]
    print("\n合计 %d 帧 / %d 组" % (manifest["total"], len(groups)))
    print("本体数异常(粘连或误判):", bad if bad else "无 ✓")


if __name__ == "__main__":
    main()
