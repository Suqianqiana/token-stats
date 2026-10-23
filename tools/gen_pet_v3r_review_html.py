# -*- coding: utf-8 -*-
"""2026-10-23: 生成「V3 现有素材库 · 新增前」高清清单页 (含退休勾选)。

- 45 帧全量高清预览 (450px 高, base64 内嵌)
- 每帧可勾选「退休」; 退休清单可复制成 JSON 发回给苏企鹅
- 每个场景显示: 播放语义 / 现有帧数 / 浅浅猫这次要新增的帧数 / 退休后总数
用法: python tools/gen_pet_v3r_review_html.py
"""
import base64
import io
import json
import os
import sys

sys.dont_write_bytecode = True
from PIL import Image

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIB = os.path.join(BASE, "assets", "pet_v3r")
SEL = os.path.join(BASE, "docs", "pet_selection_20261023.json")
OUT = os.path.join(BASE, "docs", "pet_v3r_review_20261023.html")
THUMB_H = 450

SCENES = [
    ("idle", "待机", "默认帧停留 10~20s，其它帧偶尔插播 5s"),
    ("sleep", "睡觉", "整段只播一帧不动，持续 90~240s"),
    ("wake", "睡醒", "睡醒过渡，约 4.2s；播完随机继续睡或回待机"),
    ("drag", "拖拽", "被拖拽时循环"),
    ("click", "点击互动", "点身体时的反馈"),
    ("sidle", "特殊待机", "小剧场，每 150~420s 触发、持续 30~60s"),
    ("pat", "摸摸头", "点头部 1/3 时的反馈"),
]


def main():
    sel = json.load(io.open(SEL, encoding="utf-8"))
    add_count = {k: len(v) for k, v in sel.get("assignments", {}).items()}
    frames = {}       # scene -> [(fname, w, h, b64)]
    for key, name, desc in SCENES:
        d = os.path.join(LIB, key)
        if not os.path.isdir(d):
            continue
        lst = []
        for fn in sorted(os.listdir(d)):
            if not fn.lower().endswith(".png"):
                continue
            p = os.path.join(d, fn)
            im = Image.open(p).convert("RGBA")
            if im.height > THUMB_H:
                r = THUMB_H / im.height
                im = im.resize((max(1, int(im.width * r)), THUMB_H), Image.LANCZOS)
            buf = io.BytesIO()
            im.save(buf, "PNG", optimize=True)
            b64 = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
            im0 = Image.open(p)
            lst.append((fn[:-4], im0.size[0], im0.size[1], b64))
        if lst:
            frames[key] = lst
    total = sum(len(v) for v in frames.values())
    data = {"scenes": [{"key": k, "name": n, "desc": d,
                        "add": add_count.get(k, 0),
                        "frames": [{"id": f[0], "w": f[1], "h": f[2], "src": f[3]} for f in frames.get(k, [])]}
                       for k, n, d in SCENES]}
    html = TEMPLATE.replace("__DATA__", json.dumps(data, ensure_ascii=False))
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(html)
    print("saved:", OUT, "(%.1f MB)" % (len(html.encode("utf-8")) / 1048576.0))
    for k, n, d in SCENES:
        if k in frames:
            print("  %-6s 现有 %2d + 新增 %2d -> %2d" % (k, len(frames[k]), add_count.get(k, 0),
                                                          len(frames[k]) + add_count.get(k, 0)))
    print("合计现有 %d 帧, 这次新增 %d 帧" % (total, sum(add_count.values())))


TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>V3 现有素材库 · 新增前清单（可勾选退休）</title>
<style>
:root{--bg:#0f1115;--panel:#171a21;--panel2:#1d212b;--line:#2a2f3a;--line2:#363c4a;
--txt:#e8eaf0;--txt2:#a6adbb;--txt3:#6b7382;--acc:#5b8cff;--acc2:#8f6cff;--ok:#3ecf8e;--bad:#f06a6a;--card:#151820}
html[data-theme="light"]{--bg:#f2f4f8;--panel:#fff;--panel2:#f7f9fc;--line:#e2e6ee;--line2:#d0d6e2;
--txt:#1c2030;--txt2:#5a6376;--txt3:#8b93a5;--acc:#3f6fe0;--acc2:#7a52e0;--ok:#1da26c;--bad:#d04545;--card:#fff}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--txt);font:15px/1.65 "Microsoft YaHei UI","PingFang SC",system-ui,sans-serif;padding:20px 16px 80px}
.wrap{max-width:1280px;margin:0 auto}
h1{font-size:24px;display:flex;align-items:center;gap:10px}
.dot{width:10px;height:10px;border-radius:50%;background:var(--acc);box-shadow:0 0 10px var(--acc)}
.sub{color:var(--txt2);font-size:13.5px;margin-top:6px;max-width:820px}
.sub b{color:var(--txt)}
.hdr{display:flex;flex-wrap:wrap;gap:10px;align-items:flex-start;justify-content:space-between}
.btn{border:1px solid var(--line2);background:var(--panel);color:var(--txt);border-radius:10px;padding:8px 14px;font-size:14px;cursor:pointer}
.btn:hover{border-color:var(--acc);color:var(--acc)}
.btn.primary{background:var(--acc);border-color:var(--acc);color:#fff;font-weight:600}
.btn.sm{padding:5px 10px;font-size:13px;border-radius:8px}
.bar{display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin:16px 0;padding:12px 14px;border:1px solid var(--line);background:var(--panel);border-radius:12px}
.chip{border:1px solid var(--line);background:var(--panel);border-radius:999px;padding:6px 13px;font-size:13.5px;color:var(--txt2);cursor:pointer}
.chip.on{background:var(--acc);border-color:var(--acc);color:#fff;font-weight:600}
.scene{margin:22px 0}
.shead{display:flex;align-items:baseline;gap:10px;flex-wrap:wrap;margin-bottom:6px}
.sname{font-size:16.5px;font-weight:700}
.skey{font-size:12px;color:var(--acc);border:1px solid var(--acc);border-radius:6px;padding:1px 8px}
.sdesc{font-size:12.5px;color:var(--txt3)}
.scount{font-size:13px;color:var(--txt2);margin-left:auto}
.scount b{color:var(--acc)}
.scount .add{color:var(--ok)}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:14px;margin-top:10px}
.fcard{border:1px solid var(--line);background:var(--card);border-radius:12px;overflow:hidden;position:relative;transition:.15s}
.fcard:hover{border-color:var(--acc2)}
.fcard.ret{border-color:var(--bad);opacity:.62}
.fcard.ret .fprev img{filter:grayscale(.8)}
.fprev{height:210px;display:flex;align-items:center;justify-content:center;cursor:pointer;
background:repeating-conic-gradient(var(--panel2) 0% 25%,var(--panel) 0% 50%) 50%/16px 16px}
.fprev img{max-width:100%;max-height:100%;object-fit:contain}
.fmeta{padding:8px 10px 10px;display:flex;align-items:center;gap:8px}
.fid{font-size:13px;font-weight:700}
.fsize{font-size:11.5px;color:var(--txt3);margin-left:auto}
.rtick{position:absolute;top:8px;right:8px;width:24px;height:24px;border-radius:50%;border:2px solid var(--line2);background:var(--panel);display:flex;align-items:center;justify-content:center;color:transparent;font-size:14px}
.fcard.ret .rtick{background:var(--bad);border-color:var(--bad);color:#fff}
.tag{position:absolute;top:8px;left:8px;font-size:11px;background:var(--bad);color:#fff;border-radius:6px;padding:1px 7px;font-weight:700;display:none}
.fcard.ret .tag{display:block}
textarea{width:100%;height:170px;background:var(--bg);color:var(--txt);border:1px solid var(--line2);border-radius:8px;padding:10px;font:12px/1.55 Consolas,monospace}
.toast{position:fixed;left:50%;bottom:26px;transform:translateX(-50%);background:var(--panel);border:1px solid var(--ok);border-radius:10px;padding:10px 18px;font-size:14px;display:none;z-index:60}
footer{margin-top:30px;color:var(--txt3);font-size:12.5px;line-height:1.8;border-top:1px solid var(--line);padding-top:14px}
@media(max-width:640px){body{padding:14px 10px 60px}h1{font-size:20px}.grid{grid-template-columns:repeat(auto-fill,minmax(150px,1fr))}.fprev{height:150px}}
</style>
</head>
<body>
<div class="wrap">
<div class="hdr">
  <div>
    <h1><span class="dot"></span>V3 现有素材库 · 新增前清单</h1>
    <div class="sub">这是 <b>assets/pet_v3r</b> 现有 <b id="tTotal"></b> 帧的<b>新增前</b>快照（高清预览）。
    这次浅浅猫要新增 95 帧，入库前想退休的旧素材在这里<b>勾选退休</b>：点帧卡右上角圆点即可。
    勾完点「复制退休清单」粘贴给我，我统一执行「退休 + 入库」。</div>
  </div>
  <div style="display:flex;gap:8px;flex-wrap:wrap">
    <button class="btn" id="themeBtn">🌙 明/暗</button>
    <button class="btn primary" id="copyBtn">📋 复制退休清单</button>
  </div>
</div>
<div class="bar">
  <span style="font-size:13px;color:var(--txt3)">显示</span>
  <span class="chip on" data-v="all">全部</span>
  <span class="chip" data-v="ret">已勾退休 <span class="n" id="nRet">0</span></span>
  <span style="font-size:13px;color:var(--txt3);margin-left:auto">操作</span>
  <button class="btn sm" id="clearBtn">清空勾选</button>
  <button class="btn sm" id="showJson">查看退休 JSON</button>
</div>
<div id="scenes"></div>
<div class="bar" id="jsonBar" style="display:none"><textarea id="jsonBox" spellcheck="false"></textarea></div>
<footer>
  退休 = 移动到 assets/pet_alt/&lt;场景&gt;/old_*.png（不删除，可随时取回），剩余帧自动重排为连续编号。<br>
  「+新增」列是浅浅猫这次在 HTML 里勾选的 95 帧分布；「退休后总数」= 现有 − 退休 + 新增。
</footer>
</div>
<div class="toast" id="toast"></div>
<script>
var DATA = __DATA__;
var LS = "pet_v3r_retire_20261023";
var retire = {};
try { retire = JSON.parse(localStorage.getItem(LS) || "{}"); } catch(e) {}
var view = "all";
try { if ((localStorage.getItem("theme") || "dark") === "light") document.documentElement.setAttribute("data-theme", "light"); } catch(e) {}
document.documentElement.setAttribute("data-theme", "dark");

function toast(m){ var t = document.getElementById("toast"); t.textContent = m; t.style.display = "block";
  clearTimeout(t._tm); t._tm = setTimeout(function(){ t.style.display = "none"; }, 2200); }
function save(){ try { localStorage.setItem(LS, JSON.stringify(retire)); } catch(e) {} }

function render(){
  var box = document.getElementById("scenes");
  box.innerHTML = "";
  var nRet = 0;
  DATA.scenes.forEach(function(sc){
    var frs = sc.frames.filter(function(f){
      if (view === "ret") return !!retire[sc.key + "/" + f.id];
      return true;
    });
    if (view === "ret" && !frs.length) return;
    var retN = sc.frames.filter(function(f){ return retire[sc.key + "/" + f.id]; }).length;
    nRet += retN;
    var sec = document.createElement("div");
    sec.className = "scene";
    sec.innerHTML = '<div class="shead"><span class="skey">' + sc.key + '</span>' +
      '<span class="sname">' + sc.name + '</span><span class="sdesc">' + sc.desc + '</span>' +
      '<span class="scount">现有 <b>' + sc.frames.length + '</b> · 勾休 <b style="color:var(--bad)">' + retN +
      '</b> · <span class="add">+新增 ' + sc.add + '</span> · 退休后总数 <b>' + (sc.frames.length - retN + sc.add) + '</b></span></div>';
    var grid = document.createElement("div");
    grid.className = "grid";
    if (!frs.length) grid.innerHTML = '<div style="color:var(--txt3);font-size:13px">当前筛选下无帧</div>';
    frs.forEach(function(f){
      var key = sc.key + "/" + f.id;
      var c = document.createElement("div");
      c.className = "fcard" + (retire[key] ? " ret" : "");
      c.innerHTML = '<div class="fprev"><img src="' + f.src + '" alt="' + f.id + '"></div>' +
        '<div class="rtick">✓</div><div class="tag">退休</div>' +
        '<div class="fmeta"><span class="fid">' + f.id + '</span><span class="fsize">' + f.w + "×" + f.h + '</span></div>';
      c.querySelector(".fprev").addEventListener("click", function(){
        if (retire[key]) delete retire[key]; else retire[key] = true;
        save(); render();
      });
      c.querySelector(".rtick").addEventListener("click", function(){
        if (retire[key]) delete retire[key]; else retire[key] = true;
        save(); render();
      });
      grid.appendChild(c);
    });
    sec.appendChild(grid);
    box.appendChild(sec);
  });
  document.getElementById("nRet").textContent = nRet;
  document.getElementById("tTotal").textContent = DATA.scenes.reduce(function(s, sc){ return s + sc.frames.length; }, 0);
}

function retireJSON(){
  var out = {};
  Object.keys(retire).forEach(function(k){
    var sc = k.split("/")[0];
    (out[sc] = out[sc] || []).push(k.split("/")[1]);
  });
  return JSON.stringify({v: 1, tool: "pet_v3r_retire_20261023",
    created: new Date().toISOString(),
    stats: {retiring: Object.keys(retire).length}, retire: out}, null, 1);
}
document.getElementById("copyBtn").onclick = function(){
  if (!Object.keys(retire).length) { toast("还没勾选任何帧"); return; }
  var txt = retireJSON();
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(txt).then(function(){ toast("退休清单已复制，粘贴给苏企鹅即可"); },
      function(){ showJsonBox(txt); });
  } else showJsonBox(txt);
};
function showJsonBox(txt){
  var b = document.getElementById("jsonBar");
  b.style.display = "block";
  document.getElementById("jsonBox").value = txt;
  document.getElementById("jsonBox").select();
  toast("请 Ctrl+C 复制已选中的文本");
}
document.getElementById("showJson").onclick = function(){
  if (!Object.keys(retire).length) { toast("还没勾选任何帧"); return; }
  showJsonBox(retireJSON());
};
document.getElementById("clearBtn").onclick = function(){
  if (Object.keys(retire).length && !confirm("清空所有退休勾选？")) return;
  retire = {}; save(); render(); toast("已清空");
};
document.getElementById("themeBtn").onclick = function(){
  var t = document.documentElement.getAttribute("data-theme") === "light" ? "dark" : "light";
  document.documentElement.setAttribute("data-theme", t);
  try { localStorage.setItem("theme", t); } catch(e) {}
};
document.querySelectorAll(".chip[data-v]").forEach(function(c){
  c.addEventListener("click", function(){
    document.querySelectorAll(".chip[data-v]").forEach(function(x){ x.classList.remove("on"); });
    c.classList.add("on"); view = c.dataset.v; render();
  });
});
render();
</script>
</body>
</html>
"""

if __name__ == "__main__":
    main()
