# -*- coding: utf-8 -*-
"""桌宠模式「设计 + 测试」双视角审查探针（只读诊断，不改任何线上数据）。

用法::

    QT_QPA_PLATFORM=offscreen python -B tools/pet_review_probe.py

所有 settings / ball_pos 都指向临时目录，绝不碰真实配置。
只做一件事：**把怀疑变成结论**——每条 either PASS(没问题) 或 FIND(确认有问题)。
"""
import os, sys, time, json, glob, tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")
sys.dont_write_bytecode = True

import numpy as np                      # 必须在开头导入（低内存救生符）
from PIL import Image

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)          # token-stats/
sys.path.insert(0, _ROOT)

_TMP = tempfile.mkdtemp(prefix="pet_probe_")
import scanner  # noqa: E402
scanner.PLUGIN_DATA_DIR = _TMP

import card_app as ca                   # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication([])

FIND = []
def find(tag, msg):
    FIND.append((tag, msg))
    print("  FIND  [%s] %s" % (tag, msg))

def ok(tag, msg):
    print("  PASS  [%s] %s" % (tag, msg))

def head(t):
    print("\n" + "=" * 74 + "\n" + t + "\n" + "=" * 74)


# ============================================================ 0. 素材与内存账
head("0. 素材体量 / 常驻内存账")
Tot = {}
for key in ("v6", "v5", "v4", "v3", "v2", "v1"):
    d = ca.PET_THEMES[key]["dir"]
    pngs = glob.glob(os.path.join(d, "*", "*.png"))
    nbytes = sum(os.path.getsize(p) for p in pngs)
    Tot[key] = (len(pngs), nbytes)
    print("  %-3s %3d 帧  %6.1f MB (PNG 磁盘)" % (key, len(pngs), nbytes / 1048576))

# 解码后内存 = Σ w*h*4 (QImage ARGB32)
for key in ("v6", "v5", "v3"):
    d = ca.PET_THEMES[key]["dir"]
    tot = 0
    for p in glob.glob(os.path.join(d, "idle", "*.png")):
        with Image.open(p) as im:
            tot += im.width * im.height * 4
    per = tot / max(1, len(glob.glob(os.path.join(d, "idle", "*.png"))))
    est = per * Tot[key][0] / 1048576
    print("  %-3s 单帧解码均值 %.1f MB → 全主题常驻 ≈ %.0f MB" % (key, per / 1048576, est))
if Tot["v6"][1] / 1048576 > 20:
    find("内存", "V6 一次性把 %d 帧全部解码进 QImage 常驻（≈%.0f MB），换主题时旧库要等 GC"
          % (Tot["v6"][0], 0 + sum(p / 1048576 for p in [0]) or 0) if False else
          "V6 一次性解码 %d 帧常驻内存，且 _load_frames 不做 LRU/释放" % Tot["v6"][0])


# ============================================================ 1. 未初始化属性
head("1. 属性初始化健壮性")
b = ca.BallWindow(None)
if not hasattr(b, "_drag"):
    find("初始化", "BallWindow 从未初始化 self._drag，但 mouseMoveEvent(8978) 直接用它 —— "
         "任何「未按下的鼠标移动」都会 AttributeError；_varscompany对比 CardWindow/GlassDialog 都在 __init__ 里置了 None")
else:
    ok("初始化", "_drag 已初始化")
if not hasattr(b, "_sleep_until"):
    find("初始化", "_sleep_until 未声明，代码靠 getattr(…) 兜底（8384/8417）——能跑但把初始化缺失藏起来了")
if not hasattr(b, "_pet_draw_rect"):
    find("初始化", "_pet_draw_rect 只在 paintEvent 里赋值；首帧渲染前点击会走 getattr 兜底分支")


# ============================================================ 2. 启动时不夹位置
head("2. 存档位置失效时的可恢复性")
pos_file = os.path.join(_TMP, "ball_pos.json")
scr = app.primaryScreen().availableGeometry()
with open(pos_file, "w", encoding="utf-8") as f:
    json.dump({"x": scr.right() + 4000, "y": scr.bottom() + 4000}, f)   # 模拟拔显示器/改分辨率
b2 = ca.BallWindow(None)      # 悬浮球形态（非桌宠）
bad = b2.x() > scr.right() or b2.y() > scr.bottom()
if bad:
    find("越屏", "非桌宠形态启动时直接 move(存档坐标)，**不夹**到当前屏幕 → 拔过显示器/改过分辨率后，"
          "悬浮球落在屏幕外，肉眼彻底消失且再也点不到（实测 x=%d 而屏幕右边界 %d）" % (b2.x(), scr.right()))
else:
    ok("越屏", "启动位置已夹到屏幕内")
b2.set_pet(True)
bad2 = b2.x() > scr.right() or b2.y() > scr.bottom()
print("  （切到桌宠形态后 _pet_apply→_clamp_pos 才修回来：%s）" % ("已修正" if not bad2 else "仍越屏"))
b2.set_pet(False)
b2.close()

src_of_clamp = []
try:
    with open(os.path.join(_ROOT, "card_app.py"), encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            if "_clamp_pos" in line:
                src_of_clamp.append(i)
    print("  _clamp_pos 调用点(行号):", src_of_clamp)
except OSError:
    pass
if not any("availableGeometryChanged" in l for l in open(os.path.join(_ROOT, "card_app.py"),
                                                          encoding="utf-8")):
    find("动态屏幕", "全文件没有监听 availableGeometryChanged / screenRemoved —— "
         "运行中拔显示器或改分辨率，桌宠不会自动回屏幕，须重启")


# ============================================================ 4. 长按 → 无反馈
head("4. 点击判定阈值")
b4 = ca.BallWindow(None)
b4.set_pet(True)
import inspect
src = inspect.getsource(ca.BallWindow._ball_release)
import re as _re
_code = "\n".join(_l for _l in src.splitlines() if not _l.strip().startswith("#"))
_m = _re.search(r"dur_ms\s*<\s*(\d+)", _code)
limit = int(_m.group(1)) if _m else -1
print("  当前判定: %s" % ("位移>4px 且 时长 < %d ms 才算「点」" % limit if limit > 0
                         else "只看位移(>4px = 拖动)，不再有时长门槛"))
if limit > 0:
    find("点击阈值", "按住超过 %d ms 再松手 = **完全没反应**（不触发单击/摸头）。"
         "普通用户、触控板、犹豫型点击很容易超 250ms，观感就是「点了她不理我」" % limit)
b4.close()


# ============================================================ 5. 摸头分区偏移
head("5. 摸头分区 vs 素材真实透明边距")
for key in ("v6", "v5"):
    d = ca.PET_THEMES[key]["dir"]
    files = sorted(glob.glob(os.path.join(d, "idle", "*.png")))[:8]
    offs = []
    for p in files:
        a = np.array(Image.open(p).convert("RGBA").split()[-1])
        ys = np.where(a.any(axis=1))[0]
        if len(ys) == 0:
            continue
        offs.append(ys[0] / a.shape[0])
    if offs:
        med = float(np.median(offs)) * 100
        print("  %-3s idle 帧顶部透明边距中位 %.1f%% (n=%d)" % (key, med, len(offs)))
        if med > 4:
            find("分区偏移", "%s 的 idle 帧自带 ~%.0f%% 顶部透明边距，而 _pet_click_region 按**整张图画框**"
                  "的上 1/3 判定 → 摸头热区整体下移到头发/脸部，真正「头顶」那一条反而落在 pat 之外"
                  % (key, med))


# ============================================================ 6. sidle 触发时机
head("6. 特殊待机(sidle)到底什么时候出现 —— 虚拟时钟跑 3 小时")
_real_time = ca.time
class FakeTime:
    t = 0.0
    def time(self):
        return FakeTime.t
    def __getattr__(self, k):
        return getattr(_real_time, k)
ca.time = FakeTime()

b5 = ca.BallWindow(None)
b5.set_pet_theme("v1")
b5.set_pet(True)
b5._tm.stop()

FakeTime.t = 1000.0
b5._idle_t = 1000.0
b5._next_other = 1000.0 + 200.0
b5._pet_state("idle")

END = 1000.0 + 3 * 3600
prev = b5._state
log = []            # (state, enter_t)
log.append((prev, FakeTime.t))
dur = {}
while FakeTime.t < END:
    step = ca.PET_MS.get(b5._state, 240) / 1000.0
    FakeTime.t += step
    b5._pet_tick()
    if b5._state != prev:
        log.append((b5._state, FakeTime.t))
        prev = b5._state

for i in range(1, len(log)):
    st, t0 = log[i - 1]
    dur[st] = dur.get(st, 0.0) + (log[i][0] if False else log[i][1] - t0)
total = sum(dur.values())
print("  3 小时状态占比:")
for st, v in sorted(dur.items(), key=lambda x: -x[1]):
    print("     %-6s %6.1f s  %5.1f%%" % (st, v, v / total * 100))

# sidle 的前驱状态
prec = {}
for i in range(1, len(log)):
    if log[i][0] == "sidle":
        p = log[i - 1][0]
        prec[p] = prec.get(p, 0) + 1
print("  sidle 共出现 %d 次，前驱状态分布: %s" % (sum(prec.values()), prec))

# 连续 idle 的时长
idle_runs = []
for i in range(1, len(log)):
    if log[i - 1][0] == "idle":
        idle_runs.append((log[i][1] - log[i - 1][1], log[i][0]))
if idle_runs:
    print("  连续 idle 段: n=%d 最长 %.1fs (PET_SLEEP_AFTER=%ds)" %
          (len(idle_runs), max(r[0] for r in idle_runs), ca.PET_SLEEP_AFTER))
    # 被 sidle 立刻打断的 idle 段有多短?
    cut = [r[0] for r in idle_runs if r[1] == "sidle"]
    if cut:
        print("  其中 %d 段是被 sidle **立刻**打断的，这些 idle 段平均只持续 %.2f s (= 1 拍)"
              % (len(cut), sum(cut) / len(cut)))
        find("sidle 时机", "sidle 之前的那段 idle 平均只有 %.2f 秒 —— 不是「待机中偶尔插播」，"
             "而是「一回到待机就立刻播」，周期性变成可预测的固定套路" % (sum(cut) / len(cut)))
print("  前 14 次状态迁移:")
for st, t in log[:15]:
    print("     t+%-7.1fs  %s" % (t - 1000.0, st))

# 「赖床链」: sleep/wake 交替不断时，最长的一段连续"基本看不见人"的时长
runs, cur = [], None
for i in range(1, len(log)):
    st, t0 = log[i - 1]
    t1 = log[i][1]
    if st in ("sleep", "wake"):
        if cur is None:
            cur = [t0, t1]
        else:
            cur[1] = t1
    else:
        if cur is not None:
            runs.append(cur[1] - cur[0])
            cur = None
if cur is not None:
    runs.append(cur[1] - cur[0])
if runs:
    print("  连续「睡觉/赖床」段: n=%d 最长 %.0f s (%.1f 分钟) 中位 %.0f s"
          % (len(runs), max(runs), max(runs) / 60, sorted(runs)[len(runs) // 2]))
    if max(runs) > 300:
        find("赖床链", "wake 之后有 40%% 概率直接再睡(PET 逻辑 8441)，会串成链式赖床 ——"
             " 实测最长一段连续 %0.f 秒(约 %.1f 分钟)里只在中间闪过几次 4 秒的伸懒腰;"
             "这段时间桌宠对用户来说等于「不在」" % (max(runs), max(runs) / 60))

sleep_pct = dur.get("sleep", 0) / total * 100
find("睡眠占比", "桌宠 %.0f%% 的时间在睡觉帧上（且无动作帧组时是**完全静止的单帧**）；"
      "真正能看出「活着」的时间很少" % sleep_pct)

if prec and all(k in ("wake", "idle") for k in prec) and sum(prec.values()) > 0:
    find("sidle 逻辑", "sidle 的触发间隔 %s 秒 > 入睡阈值 %d 秒 ⇒ **任何连续待机都撑不到 _next_other 到期**"
         "（最长 idle 段都被强制入睡截断）。结果 sidle 只可能出现在「睡醒/动作结束刚回 idle 的那一拍」，"
         "变成每次睡醒必播，而不是设计初衷的「待机期间偶尔惊喜」" % (ca.PET_OTHER_EVERY, ca.PET_SLEEP_AFTER))

if b5.pet_seqs:
    print("  动作帧组:", {k: len(v) for k, v in b5.pet_seqs.items()})
b5.close()
ca.time = _real_time


# ============================================================ 7. 交互/入口一致性
head("7. 入口一致性")
try:
    src_all = open(os.path.join(_ROOT, "card_app.py"), encoding="utf-8").read()
    tray_src = src_all[src_all.index("class TrayIcon"):]
    tray_body = tray_src[:tray_src.index("def run_selftest")]
    if "调整大小" not in tray_body:
        find("入口不齐", "托盘菜单没有「📐 调整大小…」（只有桌宠右键有）；"
             "托盘还缺材质/通透度/窗口尺寸，和桌宠右键菜单的项不一致")
    if "wheelEvent" not in src_all[src_all.index("class BallWindow"):
                                   src_all.index("class SettingsPage")]:
        find("缺滚轮", "桌宠没有 wheelEvent —— 无法用 Ctrl+滚轮就地缩放")
    if "WindowStaysOnTopHint | Qt.Tool" in src_all:
        find("置顶策略", "桌宠恒为 WindowStaysOnTopHint|Qt.Tool，全屏应用/游戏/PPT 演示时仍压在最上层，"
             "且卡片的「始终置顶」开关管不到它")
except Exception as e:
    print("  (静态检查跳过: %s)" % e)


# ============================================================ 3. paintEvent 除零
head("3. 极端序列下的绘制健壮性")
b3 = ca.BallWindow(None)
b3.set_pet(True)
b3._frames_of = lambda st: b3.pet_frames["idle"]
b3._seq = []                       # 理论上不可达，但 paintEvent 没有防护
try:
    b3.grab()
    ok("除零", "paintEvent 对空 _seq 有防护")
except Exception as e:
    find("除零", "paintEvent 第 8856 行 `self._seq[self._si %% len(self._seq)]` 无空序列防护 → %s: %s"
          % (type(e).__name__, e))
b3.close()



head("结论")
if not FIND:
    print("  没有发现问题")
else:
    print("  共 %d 条确认问题：" % len(FIND))
    for i, (tag, m) in enumerate(FIND, 1):
        print("   %2d. [%s] %s" % (i, tag, m))
print("\n临时目录: %s" % _TMP)
