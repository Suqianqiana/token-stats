# -*- coding: utf-8 -*-
"""生成 v2 桌宠素材检视页 (简单版): 每帧 = 原图区域 + 深底结果 + 浅底结果。"""
import numpy as np, os, io, base64, json
from PIL import Image

SRC = r"C:\Users\a3564\.workbuddy\clipboard-images\clipboard-2026-09-12T05-18-41-142Z-4fa99baf.jpg"
BASE = r"C:\Users\a3564\WorkBuddy\2026-08-25-04-20-35\token-stats"
ROOT = os.path.join(BASE, "assets", "pet_v2")
OUT = os.path.join(BASE, "docs", "pet_v2_review.html")

im = Image.open(SRC).convert("RGB")
W = json.load(open(os.path.join(BASE, "assets", "pet_v2_windows.json"), encoding="utf-8"))


def jpg(img, h):
    r = h / img.height
    t = img.resize((max(1, int(round(img.width * r))), h), Image.LANCZOS)
    buf = io.BytesIO()
    t.convert("RGB").save(buf, "JPEG", quality=86, optimize=True)
    return base64.b64encode(buf.getvalue()).decode()


GROUPS = [
    ("idle", "待机", "站立 / 眨眼 / 微笑 / 开心"),
    ("sleep", "睡觉", "躺睡 + 抱鲸鱼"),
    ("drag", "被拖拽", "被拎起的三个姿势"),
    ("click", "点击互动", "惊讶 / 开心"),
    ("special", "特殊动作", "鲸鱼互动"),
]

H = 430
data, tot = {}, 0
for g, _, _ in GROUPS:
    od = os.path.join(ROOT, g)
    for fn in sorted(os.listdir(od)):
        f = Image.open(os.path.join(od, fn)).convert("RGBA")
        box = W.get(f"{g}/{fn[:-4]}", {}).get("box", [0, 0, 0, 0])
        src = im.crop((box[0], box[2], box[1] + 1, box[3] + 1))
        dk = Image.new("RGBA", f.size, (30, 34, 42, 255)); dk.alpha_composite(f)
        lt = Image.new("RGBA", f.size, (255, 0, 255, 255)); lt.alpha_composite(f)   # 洋红底: 残留一望即知
        data[f"{g}/{fn[:-4]}"] = dict(name=fn[:-4], g=g, w=f.width, h=f.height,
                                      src=jpg(src, H), dark=jpg(dk, H), light=jpg(lt, H))
        tot += 1
print("frames:", tot)

GROUP_META = json.dumps([[g, n, d] for g, n, d in GROUPS], ensure_ascii=False)

html = """<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>桌宠 v2 素材检视</title><style>
:root{--bg:#0f1115;--card:#181b21;--line:#272b33;--tx:#e8eaee;--tx2:#a7aeb9;--tx3:#6f7885;--blue:#6aa6ff}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--tx);
font:14px/1.6 "Segoe UI","Microsoft YaHei",sans-serif}
.wrap{max-width:1480px;margin:0 auto;padding:28px 26px 60px}
h1{font-size:22px;margin:0 0 6px}.sub{color:var(--tx2);font-size:13px;margin-bottom:18px}
.bar{position:sticky;top:0;z-index:5;background:rgba(15,17,21,.94);backdrop-filter:blur(8px);
border-bottom:1px solid var(--line);padding:10px 0;margin-bottom:16px;display:flex;gap:12px;
align-items:center;flex-wrap:wrap}
.seg{display:flex;border:1px solid var(--line);border-radius:9px;overflow:hidden}
.seg button{background:transparent;border:0;color:var(--tx2);padding:6px 14px;font-size:12.5px;
cursor:pointer;font-family:inherit}
.seg button.on{background:#232833;color:var(--tx);font-weight:600}
.lbl{color:var(--tx3);font-size:12.5px}
.note{background:#14171d;border:1px solid var(--line);border-left:3px solid var(--blue);
border-radius:8px;padding:11px 15px;color:var(--tx2);font-size:12.5px;margin:0 0 20px}
h2{font-size:16px;margin:26px 0 10px}
h2 span{color:var(--tx3);font-size:12px;font-weight:400}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(420px,1fr));gap:14px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:11px 13px 13px}
.card .hd{display:flex;justify-content:space-between;margin-bottom:8px}
.card .nm{font-size:13px;font-weight:600}
.card .sz{color:var(--tx3);font-size:11.5px}
.shots{display:flex;gap:8px;align-items:flex-end;justify-content:center;
background:#0b0d11;border-radius:8px;padding:8px}
.shots figure{margin:0;display:flex;flex-direction:column;align-items:center;gap:5px}
.shots .cell{border-radius:6px;display:flex;align-items:flex-end;justify-content:center;overflow:hidden}
.shots .cell img{height:200px;display:block}
.shots figcaption{font-size:10.5px;color:var(--tx3)}
.c1{background:#2c313a}.c2{background:#1e222a}.c3{background:#ff00ff}
</style></head><body><div class="wrap">
<h1>桌宠 v2 素材检视（当前在用）</h1>
<div class="sub">按角色轮廓分割 · __TOT__ 帧（idle 4 / sleep 2 / drag 3 / click 2 / special 2）</div>
<div class="bar">
<span class="lbl">结果底色</span>
<div class="seg">
<button data-b="1" class="on">灰蓝</button>
<button data-b="2">深黑</button>
<button data-b="3">洋红(查残留)</button>
</div>
<span class="lbl">检查要点：① 发丝间隙是否还有残留底色 ② 白描边外缘是否毛糙 ③ 围裙/衣领白是否完整 ④ 装饰件是否齐全</span>
</div>
<div class="note">每帧三图：<b>原图区域</b>（素材排版里的原位）· <b>抠图结果·深底</b> · <b>抠图结果·浅底</b>。
切到「洋红(查残留)」：<b>洋红 = 已透明</b>，凡是仍显示白/浅色处就是没扣掉的残留，一眼可见。</div>
<div id="host"></div>
</div>
<script>
var DATA=__DATA__, GROUPS=__GROUPS__;
function cell(cls,img,cap){return '<figure><div class="cell '+cls+'"><img src="data:image/jpeg;base64,'+
 img+'" loading="lazy"></div><figcaption>'+cap+'</figcaption></figure>';}
var out=[];
GROUPS.forEach(function(gm){
 var keys=Object.keys(DATA).filter(function(k){return DATA[k].g===gm[0];});
 if(!keys.length)return;
 out.push('<h2>'+gm[1]+' <span>/'+gm[0]+'/ · '+keys.length+' 帧 · '+gm[2]+'</span></h2><div class="grid">');
 keys.forEach(function(k){var d=DATA[k];
  out.push('<div class="card"><div class="hd"><span class="nm">'+d.name+'</span>'+
   '<span class="sz">'+d.w+'×'+d.h+'</span></div><div class="shots">'+
   cell('c1',d.src,'原图区域')+cell('c2',d.dark,'结果·深底')+cell('c3',d.light,'结果·洋红底(查残留)')+
   '</div></div>');});
 out.push('</div>');
});
document.getElementById('host').innerHTML=out.join('');
document.querySelectorAll('.seg button').forEach(function(b){
 b.onclick=function(){
  document.querySelectorAll('.seg button').forEach(function(x){x.classList.remove('on');});
  b.classList.add('on');
  document.querySelectorAll('.shots .cell').forEach(function(c){
   c.className='cell c'+b.dataset.b;});
 };});
</script></body></html>"""
html = html.replace("__TOT__", str(tot)).replace("__DATA__",
                 json.dumps(data, ensure_ascii=False, separators=(",", ":"))).replace(
                 "__GROUPS__", GROUP_META)
open(OUT, "w", encoding="utf-8").write(html)
print("HTML ->", OUT, round(os.path.getsize(OUT) / 1024 / 1024, 2), "MB")
