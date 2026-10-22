# -*- coding: utf-8 -*-
"""第97轮: 生成 README 用的界面预览图 —— 全部使用**合成匿名数据**, 不含真实用量。

隔离策略: 在 import card_app **之前**把 USERPROFILE/HOME 指到临时目录,
`~/.workbuddy/...` 全部落到临时区, 绝不会碰到真实数据目录。

⚠️ 必须在**真实屏幕**上跑(毛玻璃的 DWM 材质 offscreen 没有; 且毛玻璃模式下
控件透明, 控件自绘抓图会变成白底 —— 必须抓真实屏幕的合成结果)。
运行时窗口会在屏幕上闪现几秒, 属正常。

用法: pyside6_python -B tools/shot_readme.py
输出: docs/assets/previews/*.png
"""
import os, sys, json, random, tempfile, datetime

# ---- ① 数据隔离(必须在 import card_app 之前) ----
_TMP = tempfile.mkdtemp(prefix="shotreadme_")
_HOME = os.path.join(_TMP, "home")
os.makedirs(_HOME, exist_ok=True)
os.environ["USERPROFILE"] = _HOME
os.environ["HOME"] = _HOME

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.dont_write_bytecode = True

DATA = os.path.join(_HOME, ".workbuddy", "plugins", "data", "token-usage-stats")
os.makedirs(DATA, exist_ok=True)

# ---- ② 合成匿名数据(固定种子 → 截图可复现) ----
MODELS = [("deepseek-v4.1-flash", 0.34), ("hy4-preview", 0.28),
          ("step-5-preview", 0.18), ("hy3", 0.12), ("deepseek-v4-flash", 0.08)]
rnd = random.Random(20261021)
DAYS = 35
# ⚠️ 最后一天必须是**真实今天** —— 界面默认就是「今日」口径, 数据停在昨天会让
# 今日概览/模型明细/合计全部显示 0(第97轮实测: 热力图有数据、其余全 0)。
end = datetime.date.today()
days = [(end - datetime.timedelta(days=i)).isoformat() for i in range(DAYS)][::-1]

daily, daily_sessions, models = {}, {}, {m: dict(requests=0, input=0, output=0,
                                                 total=0, cached=0, reasoning=0)
                                         for m, _ in MODELS}
for d in days:
    per = {}
    base = rnd.randint(18_000_000, 320_000_000)
    for m, share in MODELS:
        v = int(base * share * rnd.uniform(0.35, 1.5))
        if v <= 0:
            continue
        inp = int(v * rnd.uniform(0.94, 0.99))
        out = v - inp
        e = dict(requests=rnd.randint(60, 900), input=inp, output=out, total=v,
                 cached=int(inp * rnd.uniform(0.55, 0.85)), reasoning=int(out * 0.3))
        per[m] = e
        for k in models[m]:
            models[m][k] += e[k]
    daily[d] = per
    daily_sessions[d] = rnd.randint(1, 14)

today = daily[days[-1]]
STATS = {
    "generatedAt": "2026-10-22T11:00:00", "scanSeconds": 0.4,
    "filesTracked": 128, "filesRescanned": 3, "entriesTotal": 5120,
    "models": models, "daily": daily,
    "sessionsTotal": 96, "dailySessions": daily_sessions,
    "today": dict(requests=sum(e["requests"] for e in today.values()),
                  input=sum(e["input"] for e in today.values()),
                  output=sum(e["output"] for e in today.values()),
                  cached=sum(e["cached"] for e in today.values()),
                  sessions=daily_sessions[days[-1]]),
    "firstDay": days[0], "lastDay": days[-1],
    "dupFilesDropped": 0, "dupFilesTotal": 128,
}
with open(os.path.join(DATA, "stats.json"), "w", encoding="utf-8") as f:
    json.dump(STATS, f, ensure_ascii=False)

# 合成 jsonl 会话文件 —— 扫描器扫的就是这个, 走**真实链路**出数据
# (否则后台扫描空目录会用空结果覆盖 load_initial 的渲染, 界面全变 0)
PROJECTS = os.path.join(_HOME, ".workbuddy", "projects", "demo-project")
os.makedirs(PROJECTS, exist_ok=True)
rid = [0]
lines = []
for d in days:
    ts0 = int(datetime.datetime.fromisoformat(d + "T09:00:00").timestamp() * 1000)
    for k in range(rnd.randint(6, 16)):
        m = rnd.choice([mm for mm, _ in MODELS])
        inp = rnd.randint(2000, 60000)
        out = rnd.randint(100, 5000)
        rid[0] += 1
        lines.append(json.dumps({
            "id": "demo-msg-%06d" % rid[0],
            "timestamp": ts0 + k * 60000,
            "type": "message",
            "sessionId": "demo-session",
            "providerData": {
                "model": m, "requestModelId": m, "requestModelName": m,
                "usage": {"requests": 1, "inputTokens": inp, "outputTokens": out,
                          "totalTokens": inp + out,
                          "inputTokensDetails": [{"cached_tokens": int(inp * 0.7)}],
                          "outputTokensDetails": [{"reasoning_tokens": int(out * 0.3)}]}}},
            ensure_ascii=False))
with open(os.path.join(PROJECTS, "demo-session.jsonl"), "w", encoding="utf-8") as f:
    f.write("\n".join(lines))

# 目标主题状态直接写进 settings.json —— CardWindow 构造时 load_settings 会读它,
# 不会被"文件不存在→默认浅色"覆盖。
THEME = {"dark": True, "glass": False, "frost": True, "frost_static": False,
         "source": "wb", "window_size": "default", "pet": False, "pet_theme": "v3",
         "glass_transparency": "balanced", "frost_custom": False, "always_top": True}
with open(os.path.join(DATA, "settings.json"), "w", encoding="utf-8") as f:
    json.dump(THEME, f, ensure_ascii=False)

from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QGuiApplication, QPixmap, QPainter, QColor
from PySide6.QtTest import QTest
import card_app as ca

OUT = os.path.join(ROOT, "docs", "assets", "previews")
os.makedirs(OUT, exist_ok=True)

app = QApplication(sys.argv)
scr = QGuiApplication.primaryScreen()

# ⚠️ card_app 有单实例互杀机制 —— 跑本脚本前**必须先清掉所有运行中的 card_app 实例**
# (否则新实例与她的主程序互杀, 扫描线程直接死掉, 界面停在"正在扫描"全 0)。
# 清理由外部(Agent)用 PowerShell 工具按命令行精确过滤执行;
# 脚本里不做——粗暴 tasklist+taskkill 会误杀她的其它 pythonw 程序(桌面猫/代理等)。
ca.theme_state.update(THEME)
ca.refresh_palette()


def new_win():
    """新开一个窗口: 数据来自合成 stats.json(隔离目录), 主题来自合成 settings.json。"""
    w = ca.CardWindow()
    w.apply_styles()
    w.apply_size_mode("default", save=False)
    w.move(180, 90)
    w.show()
    QTest.qWait(500)
    w.bridge.done.connect(lambda src, s, gen: print(
        "  [dbg] bridge.done src=%s gen=%s models=%d err=%r"
        % (src, gen, len((s or {}).get("models") or {}), (s or {}).get("error")), flush=True))
    w.load_initial()
    QTest.qWait(5000)          # 等后台扫描完成(合成 jsonl 会触发真实扫描链路)
    # 调试输出: 确认数据链路哪一步断了
    try:
        _m = (w.stats or {}).get("models") or {}
        print("  [dbg] stats.models=%d  scanning=%s  subtitle=%r"
              % (len(_m), getattr(w, "_scanning", None), w.subtitle.text()[:40]), flush=True)
    except Exception as e:
        print("  [dbg] 取状态失败:", repr(e), flush=True)
    return w


def shot(w, name, use_grab=False):
    """默认: 真实屏幕抓屏(合成 DWM 毛玻璃材质) + 按窗口几何裁剪。
    use_grab=True: 直接抓控件自绘 —— 用于**静态底纹**等"内容不透明"的场景:
    半透明窗口的桌面合成不可靠(第97轮实测: 撤销 Acrylic 后抓屏仍是透出的旧帧,
    等 1.7s 也一样; 而 w.grab() 完全正确)。抓完补一圈深色边, 与抓屏版观感一致。

    ⚠️ 必须先等 `_scanning` 结束: 后台扫描的回调(bridge.done)有时比固定等待
    晚到几秒, 不等就拍会拍到"正在扫描…"的空态(第97轮实测踩过)。
    """
    for _ in range(200):                 # 最多等 20s
        if not getattr(w, "_scanning", False):
            break
        QTest.qWait(100)
    # DWM 合成延迟: 撤销 Acrylic 后, 桌面合成器要几帧才把窗口从"实时模糊"切到
    # "正常 alpha 合成" —— 抓太早会抓到旧帧(第97轮实测: 静态主题截图全是毛玻璃)。
    QTest.qWait(1400)
    ca.ChartTip.instance().hide_tip()
    QTest.qWait(300)
    p = os.path.join(OUT, name)
    if use_grab:
        # 等指标区缓存率就绪再抓(合成数据偶发中间态, 抓到会显示 "/%")
        for _ in range(60):
            try:
                if getattr(w.metrics, "rate", 0) > 0:
                    break
            except Exception:
                pass
            QTest.qWait(100)
        # ⚠️ 记忆里的老坑: processEvents() 默认**不处理 DeferredDelete** ——
        # render() 换下来的旧 ModelRow 还挂在原位绘制, 不显式发送就会抓到旧帧
        # (第97轮实测: 静态两张表的缓存率列显示 "/%")。
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        # render() 重建控件后布局要重算, 否则缓存率列按旧 x 画、被新宽度裁掉
        # (第97轮实测: "70%" 只剩 "/%")。
        try:
            w.layout().activate()
            w.model_host.layout().activate()
        except Exception:
            pass
        try:
            w._update_all()
        except Exception:
            pass
        QTest.qWait(450)
        pad = 8
        base = QPixmap(w.width() + pad * 2, w.height() + pad * 2)
        base.fill(QColor(18, 20, 26))
        gp = QPainter(base)
        gp.drawPixmap(pad, pad, w.grab())
        gp.end()
        base.save(p)
        print("saved(grab)", p, base.width(), "x", base.height(), flush=True)
        return
    img = scr.grabWindow(0).toImage()
    r = img.width() / float(scr.geometry().width())
    g = w.geometry()
    pad = 8
    crop = img.copy(int((g.x() - pad) * r), int((g.y() - pad) * r),
                    int((g.width() + pad * 2) * r), int((g.height() + pad * 2) * r))
    crop.save(p)
    print("saved", p, crop.width(), "x", crop.height(), flush=True)


# ---- ③ WorkBuddy 页: 深色毛玻璃(主图) / 浅色毛玻璃 / 深色液态 / 浅色液态 ----
w = new_win()
shot(w, "01-workbuddy.png")                 # 深色 + 毛玻璃 ★主图

w.set_dark(False)
shot(w, "10-frost-wb-light.png")            # 浅色 + 毛玻璃

w.set_dark(True)
w._set_material("glass")
shot(w, "05-dark-theme.png")                # 深色 + 液态玻璃

w._set_material("frost")
w.set_dark(False)
shot(w, "11-glass-wb-light.png")            # 浅色 + 液态玻璃

# 默认主题(无玻璃材质) —— 深色 / 浅色各一张
w._set_material(None)
w.set_dark(True)
shot(w, "14-default-dark.png")
w.set_dark(False)
shot(w, "15-default-light.png")

# ⚠️ 「静态图片主题」不在此脚本里拍: 现场从毛玻璃切到静态时, DWM 撤销 Acrylic 是
# 异步的, 抓屏会抓到还没切换完的旧帧(实测等 1.7s 仍是透出的); 而"启动即静态"
# 拍出来的图又丢了深色适配(浅猫: 程序是好的, 是我截图方式不对)。
# 需要该图时, 正确做法是**在她机器上手动切到静态、等切换稳定后单独抓一次** ——
# 不改程序、不用启动态 hack。README 用文字说明 + 设置页截图(含「静态」按钮)展示。

# ---- ④ 设置页(第97轮重做后的新样式) ----
w = new_win()
w.btn_nav_set.click()
QTest.qWait(500)
shot(w, "12-settings-dark.png")
w.set_dark(False)
shot(w, "13-settings-light.png")
w.close()

# ---- ⑤ DSH 本地页(合成账本数据, 走 _build_source_stats 的真实渲染) ----
w = new_win()
_orig_build = ca.CardWindow._build_source_stats
ca.CardWindow._build_source_stats = lambda self, k: dict(STATS, source="dsh",
                                                        totalCost=128.6,
                                                        dailyCost={d: round(rnd.uniform(0.2, 4.8), 2)
                                                                   for d in days})
w.source = "dsh"
w._apply_page()
w.load_initial()
QTest.qWait(900)
shot(w, "02-dsh.png")
ca.CardWindow._build_source_stats = _orig_build
w.close()

# ---- ⑥ 商汤额度页(合成占位池) ----
w = new_win()
w._sn_cache = {"source": "sn", "pools": ca._default_sn_pools()}
w.source = "sn"
w._apply_page()
w.load_initial()
QTest.qWait(500)
shot(w, "03-sensenova.png")
w.close()

# ---- ⑥ 多机合并页(合成两台别机, 同源数据) ----
w = new_win()
peers = {"办公机-ThinkPad": STATS, "家里-台式机": STATS}
ca.peer_store.load_all_peers = lambda: peers
ca.peer_store.load_machine_name = lambda: "本机"
w.source = "multi"
w._apply_page()
w.load_initial()
QTest.qWait(900)
shot(w, "04-multi-machine.png")
w.close()

print("DONE")
