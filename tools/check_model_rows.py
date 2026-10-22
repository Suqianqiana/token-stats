# -*- coding: utf-8 -*-
"""第97轮后半16: 模型列表满时切页"行距先变小再正常"的回归。

bug: model_area 是 QScrollArea + setWidgetResizable(True) —— 重建 ModelRow 的
瞬间 model_host 的 sizeHint 还没重算, QScrollArea 把内容压到 viewport 内(行被
压扁), 下一帧才弹回。模型越多(全部时间口径)越明显。
修法: 渲染完把已渲染控件真实高度累加写进 minimumHeight + activate 布局。

本脚本用**满模型列表**(30 个) + 切页(wb→dsh→wb)复现路径, 验证:
  ① 渲染后 model_host.minimumHeight 覆盖全部内容(不会被压扁);
  ② 切页后立刻抓图, 首行位置/高度稳定(不出现压扁帧);
  ③ 行数少时(今日口径)不回归——内容仍能被 stretch 正常吸收。
"""
import os, sys, tempfile
sys.dont_write_bytecode = True
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
import card_app as ca

ca.SETTINGS_FILE = os.path.join(tempfile.mkdtemp(), "s.json")
ca.theme_state.update({"dark": True, "glass": False, "frost": False, "source": "wb",
                       "window_size": "default", "pet": False, "pet_theme": "v3",
                       "glass_transparency": "balanced", "always_top": True})
ca.refresh_palette()
app = QApplication(sys.argv)

fails = []
def check(name, ok, extra=""):
    print(("PASS " if ok else "FAIL ") + name + (("  " + extra) if extra else ""), flush=True)
    if not ok:
        fails.append(name)

N_MODELS = 30
models = {}
for i in range(N_MODELS):
    k = "model-%02d" % i
    inp = 5_000_000 + i * 137_000
    out = 40_000 + i * 900
    models[k] = dict(requests=200 + i, input=inp, output=out, total=inp + out,
                     cached=int(inp * 0.7), reasoning=int(out * 0.3))
daily = {"2026-10-23": {m: dict(v) for m, v in models.items()},
         "2026-10-22": {m: dict(v) for m, v in models.items()}}
STATS = {"source": "wb", "models": models, "daily": daily,
         "dailySessions": {"2026-10-23": 3, "2026-10-22": 3},
         "today": dict(requests=sum(v["requests"] for v in models.values()),
                       input=sum(v["input"] for v in models.values()),
                       output=sum(v["output"] for v in models.values()),
                       cached=sum(v["cached"] for v in models.values()),
                       sessions=3),
         "sessionsTotal": 6, "firstDay": "2026-10-22", "lastDay": "2026-10-23"}

w = ca.CardWindow()
w.refresh = lambda *a, **k: None
w.apply_styles()
w.show()
QTest.qWait(400)
w.stats = STATS
# 直接走渲染(不依赖扫描): 模拟"数据到位"的那一帧
import json
_orig = ca.scanner.STATS_FILE
tmpf = os.path.join(tempfile.mkdtemp(), "stats.json")
json.dump(STATS, open(tmpf, "w", encoding="utf-8"), ensure_ascii=False)
ca.scanner.STATS_FILE = tmpf
w.load_initial()
QTest.qWait(300)

rows = [r for r in w.model_host.findChildren(ca.ModelRow)]
check("渲染出满列表(30 行)", len(rows) == N_MODELS, "实际 %d" % len(rows))

# ① minimumHeight 必须覆盖全部内容(表头 + 30 行)
content_h = 0
for i in range(w.model_lay.count()):
    it = w.model_lay.itemAt(i)
    wd = it.widget() if it is not None else None
    if wd is not None:
        content_h += wd.height()
check("minimumHeight 覆盖全部内容(不被压扁)",
      w.model_host.minimumHeight() >= content_h,
      "minH=%d 内容=%d" % (w.model_host.minimumHeight(), content_h))

# ② 切页(wb → dsh → wb)后, 首帧行距仍稳定
w.btn_nav_dsh.click()
QTest.qWait(250)
w.btn_nav_wb.click()
QTest.qWait(60)          # 故意只等一帧: 旧 bug 在这一帧行距最小
rows2 = [r for r in w.model_host.findChildren(ca.ModelRow)]
heights = sorted({r.height() for r in rows2})
check("切页后一帧内行高仍统一(无压扁帧)", heights == [ca.curr_metric()["row_h"]],
      "高度集合=%s" % heights)

# ③ 行数少时不应被 minimumHeight 撑爆: 换成 2 个模型重渲染, minimumHeight 应随之变小
small = {m: v for m, v in list(models.items())[:2]}
# render() 是从 daily 聚合的(不是 stats["models"]) → daily 也要一起换成 2 个模型
STATS2 = dict(STATS, models=small,
              daily={"2026-10-23": dict(small), "2026-10-22": dict(small)})
w.stats = STATS2
w.render()
QTest.qWait(250)
rows3 = [r for r in w.model_host.findChildren(ca.ModelRow)]
check("行数变少后行数正确(2 行)", len(rows3) == 2, "实际 %d" % len(rows3))
c3 = 0
for i in range(w.model_lay.count()):
    it = w.model_lay.itemAt(i)
    wd = it.widget() if it is not None else None
    if wd is not None:
        c3 += wd.height()
check("minimumHeight 随行数收缩", w.model_host.minimumHeight() < content_h,
      "minH=%d < %d" % (w.model_host.minimumHeight(), content_h))

ca.scanner.STATS_FILE = _orig
print()
print("DONE fails=%d" % len(fails))
sys.exit(1 if fails else 0)
