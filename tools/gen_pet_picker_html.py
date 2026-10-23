# -*- coding: utf-8 -*-
"""2026-10-23: 生成「新素材选择器」交互 HTML (单文件, 数据全内嵌)。

读 assets/pet_new_20261023/manifest.json + thumbs/*.png (base64),
产出 docs/pet_picker_20261023.html:
  - 124 帧按 11 组展示, 棋盘格透明底预览
  - 勾选 + 分配到 7 个行为库 (idle/sleep/wake/drag/click/sidle/pat)
  - 场景栏显示各库已选帧 + 试播(按桌宠真实帧速)
  - 导出 pet_selection.json (下载 / 复制)
  - localStorage 记忆, 明暗双主题
"""
import base64
import json
import os
import sys

sys.dont_write_bytecode = True
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTDIR = os.path.join(BASE, "assets", "pet_new_20261023")
THUMB = os.path.join(OUTDIR, "thumbs")
HTML_OUT = os.path.join(BASE, "docs", "pet_picker_20261023.html")

SCENES = [
    ("idle",  "待机",     "默认帧停留 8~20s，其它帧偶尔插播 2~3s"),
    ("sleep", "睡觉",     "整段只播一帧不动，持续 90~240s"),
    ("wake",  "睡醒",     "醒来到待机的过渡，约 2s"),
    ("drag",  "拖拽",     "被拖拽时循环"),
    ("click", "点击互动", "点身体时的反馈"),
    ("sidle", "特殊待机", "小剧场，持续 15~60s"),
    ("pat",   "摸摸头",   "点头部 1/3 时的反馈"),
]

# 现有 v3r 库帧数 (供参考)
CURRENT_LIB = {"idle": 8, "sleep": 3, "wake": 2, "drag": 4, "click": 10, "sidle": 12, "pat": 6}


def main():
    man = json.load(open(os.path.join(OUTDIR, "manifest.json"), encoding="utf-8"))
    thumbs = {}
    for g in man["groups"]:
        for fr in g["frames"]:
            p = os.path.join(THUMB, fr["id"] + ".png")
            with open(p, "rb") as f:
                thumbs[fr["id"]] = "data:image/png;base64," + base64.b64encode(f.read()).decode()
    data = {
        "groups": [{"gid": g["gid"], "source": g["source"], "source_cn": g["source_cn"],
                    "note": g.get("note"),
                    "frames": [{"id": fr["id"], "w": fr["size"][0], "h": fr["size"][1],
                                "bodies": fr["selfcheck_bodies"], "hint": fr.get("hint"),
                                "note": fr.get("note")} for fr in g["frames"]]}
                   for g in man["groups"]],
        "thumbs": thumbs,
    }
    print("帧 %d, 缩略图 %d, 内嵌体积约 %.1f MB"
          % (man["total"], len(thumbs),
             sum(len(v) for v in thumbs.values()) / 1048576.0))

    scenes_json = json.dumps([{"key": k, "name": n, "desc": d} for k, n, d in SCENES], ensure_ascii=False)
    data_json = json.dumps(data, ensure_ascii=False)
    cur_json = json.dumps(CURRENT_LIB, ensure_ascii=False)

    # 苏企鹅的预分配 (浅浅猫的选择数据丢失后的兜底: 一键套用再微调)
    pre_path = os.path.join(BASE, "docs", "pet_preselect_20261023.json")
    preselect = {}
    if os.path.exists(pre_path):
        with open(pre_path, encoding="utf-8") as f:
            raw = json.load(f)
        valid = {f["id"] for g in data["groups"] for f in g["frames"]}
        for k, ids in raw.items():
            if k.startswith("_"):
                continue
            ids = [i for i in ids if i in valid]
            if ids:
                preselect[k] = ids
        n_pre = sum(len(v) for v in preselect.values())
        print("预选: %d 帧 %s" % (n_pre, {k: len(v) for k, v in preselect.items()}))
    pre_json = json.dumps(preselect, ensure_ascii=False)

    html = (TEMPLATE.replace("__SCENES__", scenes_json).replace("__DATA__", data_json)
            .replace("__CURLIB__", cur_json).replace("__PRESELECT__", pre_json))
    os.makedirs(os.path.dirname(HTML_OUT), exist_ok=True)
    with open(HTML_OUT, "w", encoding="utf-8") as f:
        f.write(html)
    print("saved:", HTML_OUT, "(%.1f MB)" % (len(html.encode("utf-8")) / 1048576.0))


TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>桌宠新素材选择器 · 2026-10-23</title>
<style>
:root{
  --bg:#0f1115; --panel:#171a21; --panel2:#1d212b; --line:#2a2f3a; --line2:#363c4a;
  --txt:#e8eaf0; --txt2:#a6adbb; --txt3:#6b7382; --acc:#5b8cff; --acc2:#8f6cff;
  --ok:#3ecf8e; --warn:#f0a35e; --card:#151820;
}
html[data-theme="light"]{
  --bg:#f2f4f8; --panel:#ffffff; --panel2:#f7f9fc; --line:#e2e6ee; --line2:#d0d6e2;
  --txt:#1c2030; --txt2:#5a6376; --txt3:#8b93a5; --acc:#3f6fe0; --acc2:#7a52e0;
  --ok:#1da26c; --warn:#d07f2e; --card:#ffffff;
}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--txt);font:15px/1.65 "Microsoft YaHei UI","PingFang SC",system-ui,sans-serif;min-height:100vh;padding:20px 16px 80px}
.wrap{max-width:1280px;margin:0 auto}
header{display:flex;flex-wrap:wrap;gap:12px;align-items:flex-start;justify-content:space-between;margin-bottom:18px}
h1{font-size:24px;font-weight:700;letter-spacing:.5px;display:flex;align-items:center;gap:10px}
.dot{width:10px;height:10px;border-radius:50%;background:var(--acc);box-shadow:0 0 10px var(--acc)}
.sub{color:var(--txt2);font-size:13.5px;margin-top:6px;max-width:760px}
.sub b{color:var(--txt)}
.hdr-right{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.btn{border:1px solid var(--line2);background:var(--panel);color:var(--txt);border-radius:10px;padding:8px 14px;font-size:14px;cursor:pointer;transition:.15s}
.btn:hover{border-color:var(--acc);color:var(--acc)}
.btn.primary{background:var(--acc);border-color:var(--acc);color:#fff;font-weight:600}
.btn.primary:hover{filter:brightness(1.1);color:#fff}
.btn.sm{padding:5px 10px;font-size:13px;border-radius:8px}
.chips{display:flex;flex-wrap:wrap;gap:8px;margin:14px 0}
.chip{border:1px solid var(--line);background:var(--panel);border-radius:999px;padding:6px 13px;font-size:13.5px;color:var(--txt2);cursor:pointer;user-select:none}
.chip:hover{border-color:var(--acc2)}
.chip.on{background:var(--acc);border-color:var(--acc);color:#fff;font-weight:600}
.chip .n{opacity:.75;font-size:12px;margin-left:4px}
.scenes{display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:10px;margin:16px 0 8px}
.scene{border:1px solid var(--line);background:var(--card);border-radius:12px;padding:12px;cursor:pointer;transition:.15s;position:relative}
.scene:hover{border-color:var(--acc2)}
.scene.active{border-color:var(--acc);box-shadow:0 0 0 1px var(--acc) inset}
.scene .sname{font-size:15px;font-weight:700;display:flex;align-items:center;gap:7px}
.scene .sdesc{font-size:12px;color:var(--txt3);margin-top:3px;line-height:1.5}
.scene .scount{margin-top:8px;font-size:13px;color:var(--txt2);display:flex;justify-content:space-between;align-items:center}
.scene .scount b{color:var(--acc);font-size:17px}
.scene .mini{display:flex;gap:4px;margin-top:8px;flex-wrap:wrap;min-height:26px}
.scene .mini img{width:24px;height:24px;object-fit:contain;background:var(--panel2);border-radius:5px;border:1px solid var(--line)}
.scene .play{position:absolute;top:10px;right:10px;font-size:12px;color:var(--txt3);border:1px solid var(--line);border-radius:6px;padding:2px 8px;background:var(--panel)}
.scene .play:hover{color:var(--acc);border-color:var(--acc)}
.bar{display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin:10px 0 18px;padding:12px 14px;border:1px solid var(--line);background:var(--panel);border-radius:12px}
.bar .lab{font-size:13px;color:var(--txt3)}
.group{margin:22px 0}
.ghead{display:flex;align-items:baseline;gap:10px;margin-bottom:10px;flex-wrap:wrap}
.ghead .gid{font-size:13px;font-weight:700;color:var(--acc);border:1px solid var(--acc);border-radius:6px;padding:1px 8px}
.ghead .gname{font-size:16.5px;font-weight:700}
.ghead .gnote{font-size:12.5px;color:var(--txt3)}
.ghead .gcount{font-size:12.5px;color:var(--txt2);margin-left:auto}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(148px,1fr));gap:12px}
.fcard{border:1px solid var(--line);background:var(--card);border-radius:12px;overflow:hidden;transition:.15s;position:relative}
.fcard:hover{border-color:var(--acc2);transform:translateY(-2px)}
.fcard.sel{border-color:var(--ok);box-shadow:0 0 0 1px var(--ok) inset}
.fprev{height:150px;display:flex;align-items:center;justify-content:center;cursor:pointer;
  background:repeating-conic-gradient(var(--panel2) 0% 25%, var(--panel) 0% 50%) 50% / 16px 16px}
.fprev img{max-width:100%;max-height:100%;object-fit:contain}
.fmeta{padding:8px 10px 10px}
.fid{font-size:13px;font-weight:700;display:flex;align-items:center;gap:6px}
.fhint{font-size:11.5px;color:var(--txt3);margin-top:1px}
.fsize{font-size:11.5px;color:var(--txt3);margin-top:2px}
.sels{display:flex;gap:4px;flex-wrap:wrap;padding:0 10px 10px}
.sbtn{font-size:11.5px;border:1px solid var(--line);background:var(--panel);color:var(--txt2);border-radius:6px;padding:2.5px 7px;cursor:pointer;transition:.12s}
.sbtn:hover{border-color:var(--acc2);color:var(--acc2)}
.sbtn.on{background:var(--ok);border-color:var(--ok);color:#04130c;font-weight:700}
.tick{position:absolute;top:8px;left:8px;width:22px;height:22px;border-radius:50%;border:2px solid var(--line2);background:var(--panel);display:flex;align-items:center;justify-content:center;font-size:13px;color:transparent;transition:.12s}
.fcard.sel .tick{background:var(--ok);border-color:var(--ok);color:#04130c}
.fcard .tag{position:absolute;top:8px;right:8px;font-size:11px;background:var(--acc);color:#fff;border-radius:6px;padding:1px 7px;font-weight:600}
.panel{border:1px solid var(--ok);background:var(--panel);border-radius:12px;padding:12px 14px;margin:12px 0}
.phead{display:flex;flex-wrap:wrap;gap:8px;align-items:center;font-size:14px}
.phint{font-size:12.5px;color:var(--txt3)}
#jsonBox{width:100%;height:190px;margin-top:10px;background:var(--bg);color:var(--txt);border:1px solid var(--line2);border-radius:8px;padding:10px;font:12px/1.55 Consolas,monospace;resize:vertical}
.modal{position:fixed;inset:0;background:rgba(0,0,0,.72);display:none;align-items:center;justify-content:center;z-index:50;padding:20px}
.modal.show{display:flex}
.mbox{background:var(--panel);border:1px solid var(--line2);border-radius:16px;padding:20px;max-width:520px;width:100%;max-height:86vh;overflow:auto}
.mbox h3{font-size:17px;margin-bottom:12px}
.stage{height:300px;display:flex;align-items:center;justify-content:center;background:repeating-conic-gradient(var(--panel2) 0% 25%, var(--panel) 0% 50%) 50% / 16px 16px;border-radius:12px;border:1px solid var(--line)}
.stage img{max-width:100%;max-height:100%;object-fit:contain}
.mrow{display:flex;gap:8px;margin-top:14px;flex-wrap:wrap;align-items:center}
.toast{position:fixed;left:50%;bottom:26px;transform:translateX(-50%);background:var(--panel);border:1px solid var(--ok);color:var(--txt);border-radius:10px;padding:10px 18px;font-size:14px;display:none;z-index:60;box-shadow:0 8px 30px rgba(0,0,0,.4)}
select{background:var(--panel);color:var(--txt);border:1px solid var(--line2);border-radius:8px;padding:7px 10px;font-size:13.5px}
.empty{color:var(--txt3);font-size:13px;padding:6px 0}
footer{margin-top:34px;color:var(--txt3);font-size:12.5px;line-height:1.8;border-top:1px solid var(--line);padding-top:14px}
@media (max-width:640px){ body{padding:14px 10px 60px} h1{font-size:20px} .grid{grid-template-columns:repeat(auto-fill,minmax(128px,1fr))} .fprev{height:120px} }
</style>
</head>
<body>
<div class="wrap">
<header>
  <div>
    <h1><span class="dot"></span>桌宠新素材选择器</h1>
    <div class="sub">2026-10-23 · 浅浅猫新制作 <b id="tTotal"></b> 帧动作素材（11 张源图，已统一连通域切分 + 单体质检）。
    <b>用法</b>：点帧卡片左上角勾选 → 点帧底部小按钮分配到行为库 → 全部选完后点右上角「导出选择」下载 JSON 发给我，我按结果入库。
    分配前建议先了解各库的播放语义（点场景卡片可试播已选帧）。</div>
  </div>
  <div class="hdr-right">
    <select id="libSel">
      <option value="pet_v3r">并入现有库 pet_v3r</option>
      <option value="pet_new_20261023">新建库（沿用现编号）</option>
    </select>
    <button class="btn" id="themeBtn">🌙 明/暗</button>
    <button class="btn" id="presetBtn" title="按动作语义预先分好 124 帧，套用后再微调">⚡ 载入预选</button>
    <button class="btn primary" id="copyBtn2">📋 复制选择 JSON（推荐）</button>
    <button class="btn" id="exportBtn" title="在 WorkBuddy 内置浏览器里下载可能被静默丢弃, 建议用复制">📥 存成文件</button>
  </div>
</header>

<div class="panel" id="jsonPanel" style="display:none">
  <div class="phead">
    <b>📋 你的选择（JSON 全文）</b>
    <span class="phint">点下面按钮全选复制，直接粘贴给苏企鹅即可；输入框里也可以粘贴 JSON 点「导入」恢复</span>
    <button class="btn sm" id="selJsonBtn" style="margin-left:auto">全选并复制</button>
    <button class="btn sm" id="importBtn">导入</button>
    <button class="btn sm" id="closePanel">收起</button>
  </div>
  <textarea id="jsonBox" spellcheck="false"></textarea>
</div>
<div class="panel" id="restoreTip" style="display:none">
  <div class="phead"><b>✅ 已恢复上次的选择</b><span class="phint" id="restoreN"></span>
    <button class="btn sm" id="showPanel" style="margin-left:auto">查看/复制 JSON</button></div>
</div>

<div class="chips" id="groupChips"></div>

<div class="scenes" id="sceneBar"></div>

<div class="bar">
  <span class="lab">显示</span>
  <span class="chip on" data-view="all">全部</span>
  <span class="chip" data-view="sel">仅已选 <span class="n" id="nSel">0</span></span>
  <span class="chip" data-view="unassigned">未分配</span>
  <span class="lab" style="margin-left:auto">操作</span>
  <button class="btn sm" id="selAllBtn">全选当前筛选</button>
  <button class="btn sm" id="clearBtn">清空选择</button>
  <button class="btn sm" id="copyBtn">复制 JSON</button>
</div>

<div id="groups"></div>

<footer>
  质检口径：每帧本体连通域数 = 1（无粘连/无误判）· 帧宽=本体宽（无标签残留）· 透明底零抠图，原始 alpha 未改动。<br>
  G02 源图原有 6 个蓝色分组标签（日常小动作/互动娱乐/应援动作/道具动作/活力动作/友好互动），已剔除，帧上的「分组」标注即来源于此。<br>
  G05 末尾两帧为接触相连的双角色，已按投影谷点拆分为两个独立角色。选择结果会记录帧 ID、来源、尺寸与质检信息。
</footer>
</div>

<div class="modal" id="playModal">
  <div class="mbox">
    <h3 id="playTitle">试播</h3>
    <div class="stage"><img id="playImg" alt=""></div>
    <div class="mrow">
      <span class="lab" id="playInfo"></span>
      <button class="btn sm" id="playClose" style="margin-left:auto">关闭</button>
    </div>
  </div>
</div>
<div class="toast" id="toast"></div>

<script>
var SCENES = __SCENES__;
var DATA = __DATA__;
var CURLIB = __CURLIB__;
var PRESELECT = __PRESELECT__;
var LS_KEY = "pet_picker_20261023";
var assign = {};      // fid -> scene key
var view = "all";
var groupFilter = "all";
var theme = "dark";

try { theme = localStorage.getItem("pet_picker_theme") || "dark"; } catch(e) {}
document.documentElement.setAttribute("data-theme", theme);

function load(){
  try {
    var s = localStorage.getItem(LS_KEY);
    if (s) { assign = JSON.parse(s) || {}; }
  } catch(e) { assign = {}; }
}
function save(){
  try { localStorage.setItem(LS_KEY, JSON.stringify(assign)); } catch(e) {}
}
function flatFrames(){
  var out = [];
  DATA.groups.forEach(function(g){ g.frames.forEach(function(f){ f._g = g; out.push(f); }); });
  return out;
}
function toast(msg){
  var t = document.getElementById("toast");
  t.textContent = msg; t.style.display = "block";
  clearTimeout(t._tm); t._tm = setTimeout(function(){ t.style.display = "none"; }, 2200);
}

/* ---------- 场景栏 ---------- */
function renderScenes(){
  var bar = document.getElementById("sceneBar");
  bar.innerHTML = "";
  SCENES.forEach(function(sc){
    var sel = flatFrames().filter(function(f){ return assign[f.id] === sc.key; });
    var div = document.createElement("div");
    div.className = "scene"; div.dataset.scene = sc.key;
    var mini = sel.slice(0, 8).map(function(f){
      return '<img src="' + DATA.thumbs[f.id] + '" title="' + f.id + '">';
    }).join("");
    div.innerHTML =
      '<div class="sname"><span class="dot" style="background:var(--acc2)"></span>' + sc.name +
      ' <span style="font-size:11px;color:var(--txt3);font-weight:400">' + sc.key + '</span></div>' +
      '<div class="sdesc">' + sc.desc + '</div>' +
      '<div class="scount"><span>已选 <b>' + sel.length + '</b> 帧 · 现库 ' + CURLIB[sc.key] + '</span>' +
      (sel.length ? '<span class="play" data-play="' + sc.key + '">▶ 试播</span>' : '') + '</div>' +
      '<div class="mini">' + (mini || '<span class="empty">未分配</span>') + '</div>';
    div.addEventListener("click", function(ev){
      if (ev.target.dataset && ev.target.dataset.play) { openPlay(sc.key); ev.stopPropagation(); return; }
      toast("已进入「' + sc.name + '」分配模式：点任意帧即纳入该库（再点一次取消）");
      div.classList.toggle("active");
    });
    bar.appendChild(div);
  });
}

/* ---------- 组筛选 chips ---------- */
function renderChips(){
  var box = document.getElementById("groupChips");
  box.innerHTML = "";
  var all = document.createElement("span");
  all.className = "chip" + (groupFilter === "all" ? " on" : "");
  all.innerHTML = "全部 <span class='n'>" + DATA.groups.reduce(function(s,g){return s+g.frames.length;},0) + "</span>";
  all.onclick = function(){ groupFilter = "all"; refresh(); };
  box.appendChild(all);
  DATA.groups.forEach(function(g){
    var c = document.createElement("span");
    c.className = "chip" + (groupFilter === g.gid ? " on" : "");
    c.innerHTML = g.gid + " " + g.source_cn + " <span class='n'>" + g.frames.length + "</span>";
    c.title = g.source;
    c.onclick = function(){ groupFilter = groupFilter === g.gid ? "all" : g.gid; refresh(); };
    box.appendChild(c);
  });
}

/* ---------- 帧网格 ---------- */
function renderGroups(){
  var box = document.getElementById("groups");
  box.innerHTML = "";
  DATA.groups.forEach(function(g){
    if (groupFilter !== "all" && groupFilter !== g.gid) return;
    var frames = g.frames.filter(function(f){
      if (view === "sel") return !!assign[f.id];
      if (view === "unassigned") return !assign[f.id];
      return true;
    });
    var sec = document.createElement("div");
    sec.className = "group";
    var note = g.note ? '<span class="gnote">' + g.note + '</span>' : "";
    sec.innerHTML = '<div class="ghead"><span class="gid">' + g.gid + '</span>' +
      '<span class="gname">' + g.source_cn + '</span>' + note +
      '<span class="gcount">' + frames.length + " / " + g.frames.length + ' 帧</span></div>';
    var grid = document.createElement("div");
    grid.className = "grid";
    if (!frames.length) {
      grid.innerHTML = '<div class="empty">当前筛选下本组无帧</div>';
    }
    frames.forEach(function(f){
      var sc = assign[f.id];
      var card = document.createElement("div");
      card.className = "fcard" + (sc ? " sel" : "");
      card.dataset.fid = f.id;
      var sbtns = SCENES.map(function(s){
        return '<span class="sbtn' + (sc === s.key ? " on" : "") + '" data-s="' + s.key + '" title="' + s.desc + '">' + s.name + '</span>';
      }).join("");
      card.innerHTML =
        '<div class="fprev"><img src="' + DATA.thumbs[f.id] + '" alt="' + f.id + '"></div>' +
        '<div class="tick">✓</div>' +
        (sc ? '<span class="tag">' + scName(sc) + '</span>' : "") +
        '<div class="fmeta"><div class="fid">' + f.id + '</div>' +
        (f.hint ? '<div class="fhint">分组：' + f.hint + '</div>' : "") +
        (f.note ? '<div class="fhint">' + f.note + '</div>' : "") +
        '<div class="fsize">' + f.w + "×" + f.h + " · 单体" + (f.bodies === 1 ? "✓" : "★" + f.bodies) + '</div></div>' +
        '<div class="sels">' + sbtns + '</div>';
      card.querySelector(".fprev").addEventListener("click", function(){
        if (sc) { delete assign[f.id]; } else { assign[f.id] = "idle"; }
        save(); refresh();
      });
      card.querySelectorAll(".sbtn").forEach(function(b){
        b.addEventListener("click", function(ev){
          ev.stopPropagation();
          var k = b.dataset.s;
          if (assign[f.id] === k) { delete assign[f.id]; }
          else { assign[f.id] = k; }
          save(); refresh();
        });
      });
      grid.appendChild(card);
    });
    sec.appendChild(grid);
    box.appendChild(sec);
  });
}

function scName(k){ var s = SCENES.find(function(x){return x.key===k;}); return s ? s.name : k; }

function refresh(){
  renderChips(); renderScenes(); renderGroups();
  var n = Object.keys(assign).length;
  document.getElementById("nSel").textContent = n;
  document.getElementById("tTotal").textContent = DATA.groups.reduce(function(s,g){return s+g.frames.length;},0);
  var jb = document.getElementById("jsonBox");
  if (jb) jb.value = JSON.stringify(buildJSON(), null, 1);
}

/* ---------- 视图切换 ---------- */
document.querySelectorAll(".chip[data-view]").forEach(function(c){
  c.addEventListener("click", function(){
    document.querySelectorAll(".chip[data-view]").forEach(function(x){x.classList.remove("on");});
    c.classList.add("on"); view = c.dataset.view; renderGroups();
  });
});

document.getElementById("selAllBtn").onclick = function(){
  var list = flatFrames().filter(function(f){
    if (groupFilter !== "all" && f._g.gid !== groupFilter) return false;
    if (view === "sel") return false;
    if (view === "unassigned") return !assign[f.id];
    return true;
  });
  list.forEach(function(f){ if (!assign[f.id]) assign[f.id] = "idle"; });
  save(); refresh(); toast("已勾选 " + list.length + " 帧（默认进待机库，请逐帧分配合适的行为）");
};
document.getElementById("clearBtn").onclick = function(){
  if (Object.keys(assign).length && !confirm("清空全部选择与分配？")) return;
  assign = {}; save(); refresh(); toast("已清空");
};
document.getElementById("themeBtn").onclick = function(){
  theme = theme === "dark" ? "light" : "dark";
  document.documentElement.setAttribute("data-theme", theme);
  try { localStorage.setItem("pet_picker_theme", theme); } catch(e) {}
};

/* ---------- 导出 ---------- */
function buildJSON(){
  var assignments = {};
  SCENES.forEach(function(s){ assignments[s.key] = []; });
  var meta = {};
  flatFrames().forEach(function(f){
    meta[f.id] = {source: f._g.source, source_cn: f._g.source_cn, gid: f._g.gid,
                  size: [f.w, f.h], bodies: f.bodies, hint: f.hint};
  });
  Object.keys(assign).forEach(function(fid){
    var k = assign[fid];
    if (!assignments[k]) assignments[k] = [];
    assignments[k].push(Object.assign({id: fid}, meta[fid] || {}));
  });
  return {
    v: 1, tool: "pet_picker_20261023",
    created: new Date().toISOString(),
    target_library: document.getElementById("libSel").value,
    stats: {total: flatFrames().length, selected: Object.keys(assign).length,
            assigned: Object.keys(assign).filter(function(k){return !!assign[k];}).length},
    assignments: assignments
  };
}
document.getElementById("exportBtn").onclick = function(){
  var j = buildJSON();
  var blob = new Blob([JSON.stringify(j, null, 1)], {type: "application/json"});
  var a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "pet_selection_20261023.json";
  a.click();
  URL.revokeObjectURL(a.href);
  toast("已导出 pet_selection_20261023.json，发给我即可入库");
};
document.getElementById("copyBtn").onclick = function(){
  var txt = JSON.stringify(buildJSON());
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(txt).then(function(){ toast("JSON 已复制到剪贴板"); },
      function(){ fallbackCopy(txt); });
  } else fallbackCopy(txt);
};
function fallbackCopy(txt){
  var ta = document.createElement("textarea");
  ta.value = txt; document.body.appendChild(ta); ta.select();
  try { document.execCommand("copy"); toast("JSON 已复制到剪贴板"); }
  catch(e){ toast("复制失败，请用导出按钮"); }
  document.body.removeChild(ta);
}

/* ---------- 试播 ---------- */
var playTm = null;
function openPlay(scKey){
  var sel = flatFrames().filter(function(f){ return assign[f.id] === scKey; });
  if (!sel.length) return;
  var ms = {idle:240, sleep:1500, wake:700, drag:140, click:300, sidle:600, pat:600}[scKey] || 240;
  var m = document.getElementById("playModal");
  document.getElementById("playTitle").textContent = "试播 · " + scName(scKey) + "（" + sel.length + " 帧，帧间隔 " + ms + "ms）";
  document.getElementById("playInfo").textContent = "实际行为语义：" + (SCENES.find(function(s){return s.key===scKey;}) || {}).desc;
  m.classList.add("show");
  var i = 0;
  var img = document.getElementById("playImg");
  function step(){
    img.src = DATA.thumbs[sel[i % sel.length].id];
    document.getElementById("playTitle").textContent =
      "试播 · " + scName(scKey) + "（" + (i % sel.length + 1) + "/" + sel.length + "，帧间隔 " + ms + "ms）";
    i++;
  }
  step();
  clearInterval(playTm);
  playTm = setInterval(step, ms);
}
document.getElementById("playClose").onclick = function(){
  clearInterval(playTm);
  document.getElementById("playModal").classList.remove("show");
};
document.getElementById("playModal").addEventListener("click", function(ev){
  if (ev.target === this) { clearInterval(playTm); this.classList.remove("show"); }
});

/* ---------- JSON 面板 (内置浏览器下载不可靠时的兜底通道) ---------- */
function showPanel(){
  var p = document.getElementById("jsonPanel");
  p.style.display = p.style.display === "none" ? "block" : "none";
  if (p.style.display === "block") document.getElementById("jsonBox").select();
}
document.getElementById("showPanel").onclick = showPanel;
document.getElementById("closePanel").onclick = function(){
  document.getElementById("jsonPanel").style.display = "none";
};
document.getElementById("selJsonBtn").onclick = function(){
  var ta = document.getElementById("jsonBox");
  ta.focus(); ta.select();
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(ta.value).then(
      function(){ toast("已复制 JSON，粘贴给苏企鹅即可"); },
      function(){ toast("请按 Ctrl+C 复制已选中的文本"); });
  } else {
    try { document.execCommand("copy"); toast("已复制 JSON"); }
    catch(e){ toast("请按 Ctrl+C 复制已选中的文本"); }
  }
};
document.getElementById("copyBtn2").onclick = function(){
  showPanel();
  document.getElementById("selJsonBtn").click();
};
document.getElementById("importBtn").onclick = function(){
  try {
    var j = JSON.parse(document.getElementById("jsonBox").value);
    var a = (j && j.assignments) || {};
    assign = {};
    Object.keys(a).forEach(function(k){
      (a[k] || []).forEach(function(it){ if (it && it.id) assign[it.id] = k; });
    });
    save(); refresh(); toast("已导入 " + Object.keys(assign).length + " 个选择");
  } catch(e){ toast("JSON 解析失败： " + e.message); }
};

document.getElementById("presetBtn").onclick = function(){
  var n = 0;
  Object.keys(PRESELECT || {}).forEach(function(k){
    (PRESELECT[k] || []).forEach(function(id){ assign[id] = k; n++; });
  });
  if (!n) { toast("没有预选数据"); return; }
  save(); refresh();
  toast("已载入预选 " + n + " 帧（按动作语义分的），你可以直接微调不对的");
};
load(); refresh();
/* 上次的选择会自动恢复(localStorage) —— 明确提示, 避免误以为白选了 */
if (Object.keys(assign).length) {
  var rt = document.getElementById("restoreTip");
  rt.style.display = "block";
  var byScene = {};
  Object.keys(assign).forEach(function(k){ byScene[assign[k]] = (byScene[assign[k]] || 0) + 1; });
  document.getElementById("restoreN").textContent =
    "共 " + Object.keys(assign).length + " 帧：" +
    SCENES.map(function(s){ return s.name + " " + (byScene[s.key] || 0); }).join(" · ");
}
</script>
</body>
</html>
"""

if __name__ == "__main__":
    main()
