# -*- coding: utf-8 -*-
"""生成"新素材库(pet_v3r)按动作分组"的检视页: 深底 + 洋红底(查残留)。"""
import os, io, base64, json
from PIL import Image

BASE = r"C:\Users\a3564\WorkBuddy\2026-08-25-04-20-35\token-stats"
ROOT = os.path.join(BASE, "assets", "pet_v3r")
OUT = os.path.join(BASE, "docs", "pet_theme_v3_review.html")

POOLS = [
    ("idle", "普通待机", "原 v2 待机 4 帧 + setA_01（每帧停留 2~3s）"),
    ("sleep", "睡觉", "原 v2 睡觉 2 帧 + setB_08（时长随机 ≥90s）"),
    ("wake", "睡醒", "setB_09 / setA_05 随机取一个，播完回待机"),
    ("drag", "被拖拽", "原 v2 drag_01/02（drag_03 已舍弃）+ setB_06 + setA_06"),
    ("click", "点击互动", "原 v2 点击 2 帧 + setA_02/03 + setB_01~05"),
    ("sidle", "特殊待机动作", "setA_07 / setA_08 / setA_09，持续 15~60s"),
    ("pat", "摸摸头", "原 v2 special 2 帧 + setB_10（每次只随机播一个）"),
]


def jpg(img, h):
    r = h / img.height
    t = img.resize((max(1, int(round(img.width * r))), h), Image.LANCZOS)
    buf = io.BytesIO()
    t.convert("RGB").save(buf, "JPEG", quality=88, optimize=True)
    return base64.b64encode(buf.getvalue()).decode()


H = 200
data, tot = {}, 0
for key, _n, _d in POOLS:
    od = os.path.join(ROOT, key)
    if not os.path.isdir(od):
        continue
    items = []
    for fn in sorted(os.listdir(od)):
        if not fn.lower().endswith(".png"):
            continue
        f = Image.open(os.path.join(od, fn)).convert("RGBA")
        dk = Image.new("RGBA", f.size, (30, 34, 42, 255)); dk.alpha_composite(f)
        mg = Image.new("RGBA", f.size, (255, 0, 255, 255)); mg.alpha_composite(f)
        items.append(dict(n=fn[:-4], dark=jpg(dk, H), mg=jpg(mg, H)))
        tot += 1
    data[key] = items
print("frames:", tot)

META = json.dumps([[k, n, d] for k, n, d in POOLS], ensure_ascii=False)
html = """<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>桌宠新素材库 v3 · 动作分组</title><style>
:root{--bg:#0f1115;--card:#181b21;--line:#272b33;--tx:#e8eaee;--tx2:#a7aeb9;--tx3:#6f7885;--grn:#5fd3a0}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--tx);
font:14px/1.6 "Segoe UI","Microsoft YaHei",sans-serif}
.wrap{max-width:1520px;margin:0 auto;padding:28px 26px 60px}
h1{font-size:22px;margin:0 0 6px}.sub{color:var(--tx2);font-size:13px;margin-bottom:16px}
.note{background:#14171d;border:1px solid var(--line);border-left:3px solid var(--grn);
border-radius:8px;padding:11px 15px;color:var(--tx2);font-size:12.5px;margin:0 0 20px}
h2{font-size:15.5px;margin:26px 0 6px}
h2 span{color:var(--tx3);font-size:12px;font-weight:400;display:block;margin-top:3px}
.row{display:flex;gap:12px;flex-wrap:wrap;margin-top:12px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:9px 10px 10px}
.card .nm{font-size:12px;font-weight:700;color:#ffd66e;margin-bottom:6px;text-align:center}
.pair{display:flex;gap:7px;background:#0b0d11;border-radius:8px;padding:7px}
.cell{border-radius:6px;display:flex;align-items:flex-end;justify-content:center;overflow:hidden;
background:#1e222a}
.cell.mg{background:#ff00ff}
.cell img{height:170px;display:block}
</style></head><body><div class="wrap">
<h1>桌宠新素材库 v3（已接入 · __TOT__ 帧）</h1>
<div class="sub">assets/pet_v3r/ · 按动作分组</div>
<div class="note">每帧两图：<b>深底</b>（实际显示效果）· <b>洋红底</b>（洋红=已透明，用于查残留）。<br>
已舍弃入库的素材在 <code>assets/pet_v3_discard/</code>（setA_04 / setA_10 / setB_07 / 原 v2 drag_03）。</div>
<div id="host"></div></div>
<script>
var DATA=__DATA__, META=__META__;
function card(it){return '<div class="card"><div class="nm">'+it.n+'</div><div class="pair">'+
 '<div class="cell"><img src="data:image/jpeg;base64,'+it.dark+'" loading="lazy"></div>'+
 '<div class="cell mg"><img src="data:image/jpeg;base64,'+it.mg+'" loading="lazy"></div>'+
 '</div></div>';}
var out=[];
META.forEach(function(m){ if(!DATA[m[0]]) return;
 out.push('<h2>'+m[1]+' <span>'+m[0]+' · '+DATA[m[0]].length+' 帧 · '+m[2]+'</span></h2><div class="row">');
 DATA[m[0]].forEach(function(it){ out.push(card(it)); });
 out.push('</div>');});
document.getElementById('host').innerHTML=out.join('');
</script></body></html>"""
html = html.replace("__TOT__", str(tot)).replace("__DATA__",
        json.dumps(data, ensure_ascii=False, separators=(",", ":"))).replace("__META__", META)
open(OUT, "w", encoding="utf-8").write(html)
print("HTML ->", OUT, round(os.path.getsize(OUT) / 1024 / 1024, 2), "MB")
