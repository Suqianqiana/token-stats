# -*- coding: utf-8 -*-
"""生成 v3 新素材检视页: 每帧 = 原图单元格(含动作标签) + 深底结果 + 洋红底(查残留)。"""
import numpy as np, os, io, base64, json
from PIL import Image

BASE = r"C:\Users\a3564\WorkBuddy\2026-08-25-04-20-35\token-stats"
ROOT = os.path.join(BASE, "assets", "pet_v3")
OUT = os.path.join(BASE, "docs", "pet_v3_review.html")

SETS = [
    ("setA", r"C:\Users\a3564\.workbuddy\clipboard-images\clipboard-2026-09-13T21-46-03-551Z-a70b73fe.jpg",
     "第一张（待机 / 点击·开心 / 点击·惊讶 / 睡觉 / 醒来 / 被拖拽 / 特动作·工作 / 抱抱 / 阅读 / 疑惑）"),
    ("setB", r"C:\Users\a3564\.workbuddy\clipboard-images\clipboard-2026-09-13T21-46-03-556Z-1fb214d8.jpg",
     "第二张（待机·眨眼 / 点击·开心 / 疑虑 / 生气 / 惊讶 / 拖拽·拉扯 / 飞起 / 睡觉 / 醒来 / 特殊·放烟花）"),
]

W = json.load(open(os.path.join(BASE, "assets", "pet_v3_windows.json"), encoding="utf-8"))
QC = json.load(open(os.path.join(BASE, "assets", "pet_v3_qc.json"), encoding="utf-8"))


def jpg(img, h):
    r = h / img.height
    t = img.resize((max(1, int(round(img.width * r))), h), Image.LANCZOS)
    buf = io.BytesIO()
    t.convert("RGB").save(buf, "JPEG", quality=88, optimize=True)
    return base64.b64encode(buf.getvalue()).decode()


H = 400
data, tot = {}, 0
for g, src_path, _desc in SETS:
    im = Image.open(src_path).convert("RGB")
    od = os.path.join(ROOT, g)
    for fn in sorted(os.listdir(od)):
        key = f"{g}/{fn[:-4]}"
        f = Image.open(os.path.join(od, fn)).convert("RGBA")
        box = W.get(key, {}).get("box", [0, 0, im.width - 1, im.height - 1])
        src = im.crop((box[0], box[1], box[2] + 1, box[3] + 1))
        dk = Image.new("RGBA", f.size, (30, 34, 42, 255)); dk.alpha_composite(f)
        mg = Image.new("RGBA", f.size, (255, 0, 255, 255)); mg.alpha_composite(f)
        q = QC.get(key, {})
        data[key] = dict(name=fn[:-4], g=g, w=f.width, h=f.height,
                         src=jpg(src, H), dark=jpg(dk, H), magenta=jpg(mg, H),
                         q=f"孔洞{q.get('holes','?')} · 半透明{q.get('semi','?')} · 白点{q.get('white_near_trans','?')}")
        tot += 1
print("frames:", tot)

META = json.dumps([[g, d] for g, _p, d in SETS], ensure_ascii=False)
html = """<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>桌宠 v3 新素材检视</title><style>
:root{--bg:#0f1115;--card:#181b21;--line:#272b33;--tx:#e8eaee;--tx2:#a7aeb9;--tx3:#6f7885;--blue:#6aa6ff;--grn:#5fd3a0}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--tx);
font:14px/1.6 "Segoe UI","Microsoft YaHei",sans-serif}
.wrap{max-width:1500px;margin:0 auto;padding:28px 26px 60px}
h1{font-size:22px;margin:0 0 6px}.sub{color:var(--tx2);font-size:13px;margin-bottom:16px}
.note{background:#14171d;border:1px solid var(--line);border-left:3px solid var(--grn);
border-radius:8px;padding:11px 15px;color:var(--tx2);font-size:12.5px;margin:0 0 20px}
.note b{color:var(--tx)}
h2{font-size:15.5px;margin:26px 0 6px}
h2 span{color:var(--tx3);font-size:12px;font-weight:400;display:block;margin-top:2px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(430px,1fr));gap:14px;margin-top:12px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:11px 13px 13px}
.card .hd{display:flex;justify-content:space-between;align-items:baseline;margin-bottom:8px}
.card .nm{font-size:13.5px;font-weight:700;color:#ffd66e}
.card .q{color:var(--tx3);font-size:11px}
.shots{display:flex;gap:8px;align-items:flex-end;justify-content:center;background:#0b0d11;border-radius:8px;padding:8px}
.shots figure{margin:0;display:flex;flex-direction:column;align-items:center;gap:5px}
.shots .cell{border-radius:6px;display:flex;align-items:flex-end;justify-content:center;overflow:hidden}
.shots .cell img{height:210px;display:block}
.shots figcaption{font-size:10.5px;color:var(--tx3)}
.c1{background:#fff}.c2{background:#1e222a}.c3{background:#ff00ff}
</style></head><body><div class="wrap">
<h1>桌宠 v3 新素材检视（__TOT__ 帧）</h1>
<div class="sub">白底 JPG 抠图结果 · 每帧三图对照</div>
<div class="note">每帧三图：<b>原图单元格（含动作标签，便于辨认）</b> · <b>结果·深底</b> · <b>结果·洋红底</b>。
洋红底上<b>洋红=已透明</b>：若仍能看到白色/浅色块就是没扣干净的残留。<br>
命名规则：<b>行优先</b>（第 1 行左→右 = 01~05，第 2 行左→右 = 06~10）。</div>
<div id="host"></div>
</div>
<script>
var DATA=__DATA__, META=__META__;
function cell(cls,img,cap){return '<figure><div class="cell '+cls+'"><img src="data:image/jpeg;base64,'+
 img+'" loading="lazy"></div><figcaption>'+cap+'</figcaption></figure>';}
var out=[];
META.forEach(function(gm){
 var keys=Object.keys(DATA).filter(function(k){return DATA[k].g===gm[0];});
 if(!keys.length)return;
 out.push('<h2>'+gm[0]+'<span>'+gm[1]+'</span></h2><div class="grid">');
 keys.forEach(function(k){var d=DATA[k];
  out.push('<div class="card"><div class="hd"><span class="nm">'+d.name+'</span>'+
   '<span class="q">'+d.w+'x'+d.h+' · '+d.q+'</span></div><div class="shots">'+
   cell('c1',d.src,'原图(含标签)')+cell('c2',d.dark,'结果·深底')+cell('c3',d.magenta,'结果·洋红底')+
   '</div></div>');});
 out.push('</div>');
});
document.getElementById('host').innerHTML=out.join('');
</script></body></html>"""
html = html.replace("__TOT__", str(tot)).replace("__DATA__",
      json.dumps(data, ensure_ascii=False, separators=(",", ":"))).replace("__META__", META)
open(OUT, "w", encoding="utf-8").write(html)
print("HTML ->", OUT, round(os.path.getsize(OUT) / 1024 / 1024, 2), "MB")
