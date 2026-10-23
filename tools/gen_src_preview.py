# -*- coding: utf-8 -*-
"""生成 11 张带帧编号标注的源图总览 (供逐帧识别动作语义 -> 生成预分配)。"""
import os, sys
sys.dont_write_bytecode = True
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage

S8 = np.ones((3, 3), bool)
DL = os.path.join(os.path.expanduser("~"), "Downloads")
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(BASE, "assets", "pet_new_20261023", "_srcpreview")
os.makedirs(OUT, exist_ok=True)

SRC = [
    ("G01", "蓝发鲸鱼女仆日常贴纸合集.png"), ("G02", "桌宠新动作素材_4K透明.png"),
    ("G03", "蓝发鲸鱼少女表情贴纸合集.png"), ("G04", "桌宠新动作素材_无标签第三批_4K透明.png"),
    ("G05", "蓝鲸主题女仆少女贴纸表情集.png"), ("G06", "蓝鲸主题少女贴纸图鉴.png"),
    ("G07", "蓝发鲸鱼女仆十二格贴纸合集.png"), ("G08", "蓝发鲸鱼女仆日常贴纸集.png"),
    ("G09", "桌宠睡觉睡醒与日常动作_6x2_4K透明.png"), ("G10", "蓝色鲸鱼女仆的日常贴纸集.png"),
    ("G11", "蓝鲸少女的十二种日常姿态.png"),
]

def font(sz):
    for p in (r"C:/Windows/Fonts/msyh.ttc", r"C:/Windows/Fonts/msyhbd.ttc", r"C:/Windows/Fonts/arial.ttf"):
        try: return ImageFont.truetype(p, sz)
        except OSError: pass
    return ImageFont.load_default()

for gid, fn in SRC:
    A = np.asarray(Image.open(os.path.join(DL, fn)).convert("RGBA"))
    H, W = A.shape[:2]
    scale = max(W, H) / 1536.0
    bg = Image.new("RGBA", (W, H), (42, 46, 56, 255))
    bg.alpha_composite(Image.fromarray(A))
    r = 1100 / max(bg.size)
    im = bg.resize((int(bg.width * r), int(bg.height * r)), Image.LANCZOS).convert("RGB")
    d = ImageDraw.Draw(im)
    # 角色连通域 -> 行优先 = 帧编号 (与切分脚本同逻辑)
    fg = A[..., 3] > 128
    lbl, n = ndimage.label(fg, S8)
    szs = np.bincount(lbl.ravel())
    objs = ndimage.find_objects(lbl)
    chars = []
    for i in range(1, n + 1):
        sl = objs[i - 1]
        if sl is None or szs[i] < 20000 * scale * scale:
            continue
        bb = (sl[0].start, sl[0].stop - 1, sl[1].start, sl[1].stop - 1)
        h = bb[1] - bb[0] + 1; w = bb[3] - bb[2] + 1
        if szs[i] >= 3000 * scale * scale and h < 0.08 * H and w >= 1.5 * h:
            continue                       # 标签, 不算角色
        chars.append({"bb": bb, "yc": (bb[0] + bb[1]) / 2})
    chars.sort(key=lambda b: (b["bb"][0], b["bb"][2]))
    rows = []
    for b in chars:
        for rr in rows:
            if abs(rr["yc"] - b["yc"]) < 150 * scale:
                rr["items"].append(b); break
        else:
            rows.append({"yc": b["yc"], "items": [b]})
    rows.sort(key=lambda x: x["yc"])
    ordered = []
    for rr in rows:
        rr["items"].sort(key=lambda b: b["bb"][2])
        ordered += rr["items"]
    f = font(max(16, int(26 * r)))
    for k, b in enumerate(ordered, 1):
        x0 = int(b["bb"][2] * r); y0 = int(b["bb"][0] * r)
        x1 = int(b["bb"][3] * r); y1 = int(b["bb"][1] * r)
        d.rectangle([x0, y0, x1, y1], outline=(255, 90, 90), width=2)
        tag = "%s_%02d" % (gid, k)
        tw = d.textlength(tag, font=f)
        d.rectangle([x0, max(0, y0 - 30), x0 + tw + 12, y0 - 2], fill=(255, 90, 90))
        d.text((x0 + 6, max(0, y0 - 28)), tag, font=f, fill=(255, 255, 255))
    im.save(os.path.join(OUT, gid + ".png"))
    print(gid, len(ordered), "帧已标注")
