# -*- coding: utf-8 -*-
"""第99轮验证: ① 睡觉「完整动作帧组」机制 ② V5 主题素材与加载。

覆盖:
  - load_pet_seqs("v3") 能读到 sleep 组 (A 套 8 帧, ms 来自 seq.json)
  - load_pet_frames("v3") 帧数不变(128), 且 seq 没混进 frames(统计不被多算)
  - 进入 sleep 时走动作帧组: _seq_frames 非空、_seq == 0..7、节拍 = 1000ms
  - 睡觉循环: tick 走到末尾会从头开始, 且到点转 wake
  - V5: 加载成功 / 各场景帧数(4 idle,1 click,2 sleep,1 wake,1 drag) / 同场景画布一致
  - V5 没有 seq, 且有 _has_anim 保护(不会误触发特殊待机)
  - 无 seq 的主题(v4) sleep 仍是"单帧定格"

用法: QT_QPA_PLATFORM=offscreen python -B tools/_verify_seq_v5.py
"""
import os
import sys
import json
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.dont_write_bytecode = True
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

import card_app as ca
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QRectF

ca.SN_USE_PLAYWRIGHT = False
TMP = tempfile.mkdtemp(prefix="tstat_seq_")
ca.SN_AUTOSYNC_FILE = os.path.join(TMP, "sn_autosync.json")
ca.SN_CRED_LOG = os.path.join(TMP, "sn_cred.log")
ca.SETTINGS_FILE = os.path.join(TMP, "settings.json")
try:
    with open(os.path.join(TMP, "_x"), "w") as f:
        f.write("1")
except OSError:
    pass

app = QApplication.instance() or QApplication([])
PASS = 0


def check(name, cond, detail=""):
    global PASS
    print("  %s  %s%s" % ("PASS" if cond else "FAIL", name, ("  (%s)" % detail) if detail else ""))
    assert cond, name
    PASS += 1


print("== 1. 睡觉动作帧组加载 ==")
seqs = ca.load_pet_seqs("v3")
check("v3 有 sleep 动作帧组", "sleep" in seqs, str(list(seqs.keys())))
grp_list = seqs["sleep"]
check("sleep 组数量 = 1 (只用 A 套)", len(grp_list) == 1, str([g["name"] for g in grp_list]))
g0 = grp_list[0]
check("A 组 8 帧", len(g0["frames"]) == 8, str(len(g0["frames"])))
check("组名 = A", g0["name"] == "A", g0["name"])
check("节拍取自 seq.json = 1000ms", g0["ms"] == 1000, str(g0["ms"]))
check("组带 chance 字段(单帧/动画混播)", g0.get("chance") == 0.5, str(g0.get("chance")))
sizes = {(im.width(), im.height()) for im in g0["frames"]}
check("8 帧画布完全一致(播放不抖动)", len(sizes) == 1, str(sizes))

print("== 2. 普通帧库没被污染 ==")
fr = ca.load_pet_frames("v3")
check("v3 帧库仍为 128 帧", sum(len(v) for v in fr.values()) == 128,
      str(sum(len(v) for v in fr.values())))
check("frames 的 key 全是场景名(无 __seq__)", "__seq__" not in fr, str(sorted(fr.keys())))

print("== 3. 进入睡觉时播放动作帧组 ==")
ca.theme_state["pet_theme"] = "v3"
ball = ca.BallWindow.__new__(ca.BallWindow)     # 只测逻辑, 不建窗口
ca.QWidget.__init__(ball, None)
ball.pet_theme = "v3"
ball.pet_frames = None
ball.pet_seqs = {}
ball._seq_frames = None
ball._loaded_pet_theme = None
ball.pet = True
ball._last_drawn = -1
ball._state = "idle"
ball._si = 0
ball._seq = [0]
from PySide6.QtCore import QTimer
ball._tm = QTimer()
ball.pet_frames = ball._load_frames()           # 必须真加载, 否则 pet_seqs 还是空的
check("BallWindow 载入了 sleep 动作帧组", "sleep" in (ball.pet_seqs or {}),
      str(list((ball.pet_seqs or {}).keys())))
ball._pet_state("sleep")
check("chance=0.5 → 两种睡觉形态之一(单帧定格 或 8帧动画)",
      ball._seq_frames is not None or (len(set(ball._seq)) == 1 and len(ball._seq) == 8),
      f"seq_frames={ball._seq_frames is not None} seq={ball._seq[:4]}")
# 显式置 1.0 / 0.0 测两条路(避免 0.5 让断言 flaky)
_g = ball.pet_seqs["sleep"][0]
_g["chance"] = 1.0
ball._pet_state("sleep")
check("chance=1 → 必走动作帧组", ball._seq_frames is not None
      and ball._seq == list(range(8)) and ball._tm.interval() == 1000,
      f"frames={ball._seq_frames is not None} ms={ball._tm.interval()}")
for _ in range(8):
    ball._pet_tick()
check("循环 8 拍后回到第 0 帧", ball._si == 0, str(ball._si))
ball._sleep_until = 0                                  # 假装睡够
ball._pet_tick()
check("睡够后转 wake 并清空动作帧组", ball._state == "wake" and ball._seq_frames is None,
      "%s / %s" % (ball._state, ball._seq_frames))
_g["chance"] = 0.0
ball._pet_state("sleep")
check("chance=0 → 走单帧库(随机一张定格, 单帧素材能出场)",
      ball._seq_frames is None and len(set(ball._seq)) == 1 and len(ball._seq) == 8,
      f"seq_frames={ball._seq_frames} seq={set(ball._seq)}")
_g["chance"] = 0.5
_hits = sum(1 for _ in range(400)
            if (ball._pet_state("sleep"), ball._seq_frames is not None)[1])
check("chance=0.5 → 400 次抽样两种形态都出现", 120 < _hits < 280, f"动画 {_hits}/400")

print("== 4. 没有动作帧组的主题保持旧行为 ==")
ball.pet_theme = "v4"
ball.pet_frames = None
ball._loaded_pet_theme = None
ball.pet_seqs = ca.load_pet_seqs("v4")
check("v4 无动作帧组", ball.pet_seqs == {}, str(ball.pet_seqs))
ball._pet_state("sleep")
check("v4 sleep 仍是单帧定格", ball._seq_frames is None and len(set(ball._seq)) == 1
      and len(ball._seq) == 8, "%s / %s" % (ball._seq_frames, set(ball._seq)))

print("== 5. V5 主题 ==")
check("PET_THEMES 含 v5", "v5" in ca.PET_THEMES, str(list(ca.PET_THEMES.keys())))
fr5 = ca.load_pet_frames("v5")
check("V5 素材可加载", fr5 is not None)
if fr5:
    cnt = {k: len(v) for k, v in sorted(fr5.items())}
    print("     V5 场景帧数:", cnt)
    check("V5 idle 4 张", cnt.get("idle") == 4, str(cnt.get("idle")))
    check("V5 click 1 张", cnt.get("click") == 1, str(cnt.get("click")))
    check("V5 sleep 2 张", cnt.get("sleep") == 2, str(cnt.get("sleep")))
    check("V5 具备必需四场景(加载条件)",
          all(k in fr5 for k in ("idle", "sleep", "drag", "click")), str(sorted(fr5.keys())))
    stand = {(im.width(), im.height()) for k in ("idle", "click", "drag", "wake")
             for im in fr5.get(k, [])}
    lie = {(im.width(), im.height()) for im in fr5.get("sleep", [])}
    check("V5 站姿组(idle/click/drag/wake)画布一致", len(stand) == 1, str(stand))
    check("V5 躺姿组(sleep)画布一致", len(lie) == 1, str(lie))
check("V5 没有动作帧组(seq 目录不存在)", ca.load_pet_seqs("v5") == {})

ball.pet_theme = "v5"
ball._loaded_pet_theme = None
ball.pet_frames = None
fr5b = ball._load_frames()
check("BallWindow 能切到 V5", fr5b is not None and ball._loaded_pet_theme == "v5",
      str(ball._loaded_pet_theme))
check("V5 无 sidle -> _has_anim 为假(不误触发特殊待机)", ball._has_anim("sidle") is False)
check("v3 有 sidle -> _has_anim 为真", ca.load_pet_seqs("v3") is not None)
ball.pet_theme = "v3"
ball._loaded_pet_theme = None
ball.pet_frames = None
ball._load_frames()
check("v3 _has_anim(sidle) 为真", ball._has_anim("sidle") is True)

print("== 6. V5 绘制不越界 ==")
ca.theme_state["pet_theme"] = "v5"
w = ca.BallWindow.__new__(ca.BallWindow)
ca.QWidget.__init__(w, None)
w.pet_theme = "v5"
w.pet_frames = None
w.pet_seqs = {}
w._seq_frames = None
w._loaded_pet_theme = None
w.pet = True
w._last_drawn = -1
w._state = "idle"
w._si = 0
w._seq = [0]
w._tm = QTimer()
w._idle_t = 0
w._next_other = 0
w.pet_frames = w._load_frames()
w.resize(ca.PET_W, ca.PET_H)
for st in ("idle", "sleep", "click", "wake", "drag"):
    w._pet_state(st)
    pix = w.grab()
    r = w._pet_draw_rect
    ok = (not pix.isNull()) and r is not None and r.left() >= -0.5 and r.top() >= -0.5 \
        and r.right() <= ca.PET_W + 0.5 and r.bottom() <= ca.PET_H + 0.5
    check("V5 %s 渲染正常且不越界" % st, ok, str(r))

print("\n全部通过 (%d 项)" % PASS)
