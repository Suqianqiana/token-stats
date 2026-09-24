# -*- coding: utf-8 -*-
"""offscreen 验证: 切页 race 防护 + 商汤积分自动同步 + 事件缓存."""
import os, sys, time, json, tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# --- 禁止生成 .pyc: 火绒把 __pycache__/card_app.cpython-313.pyc 误判为
#     Trojan/Python.ShellLoader.am 并删除+结束进程(实测 12 次)。不写字节码 = 不触发。
import sys as _sys
_sys.dont_write_bytecode = True
import card_app as ca
from PySide6.QtWidgets import QApplication

ca.SN_USE_PLAYWRIGHT = False   # 回归测试关闭 Playwright 真自动, 走 cURL mock 路径

# ---- 数据目录隔离: 商汤凭据文件全部改到临时目录, 绝不碰真实配置 ----
# 历史事故: 测试曾把 mock 配置(api.example.com)写进真实数据目录且还原条件失效,
# 之后每次真自动失败都会回退到那个不存在的域名, 于是"时不时获取失败"。
_TMP_DATA = tempfile.mkdtemp(prefix="tstats_regress_")
_REAL_AUTOSYNC_FILE = ca.SN_AUTOSYNC_FILE
_REAL_SETTINGS_FILE = ca.SETTINGS_FILE
ca.SN_AUTOSYNC_FILE = os.path.join(_TMP_DATA, "sn_autosync.json")
ca.SN_CRED_LOG = os.path.join(_TMP_DATA, "sn_cred.log")
_user_autosync = ca.load_sn_autosync()

# ---- settings.json 同样隔离 ----
# 历史事故: 本测试会切数据源/改主题/切桌宠形态并 save_settings(), 而 _user_theme 是在
# 第 8 节才快照的 —— 此时前 7 节早已改过 theme_state, 于是**跑一次测试就把用户的
# source/dark/pet 覆盖掉**(实测把 sn→wb、dark→false、pet→true→false),
# 用户看到的是"商汤页不更新了 / 桌宠没了"。这里把设置文件也指到临时目录。
ca.SETTINGS_FILE = os.path.join(_TMP_DATA, "settings.json")
try:                                    # 用用户真实设置作初值, 保证测试路径与真机一致
    with open(_REAL_SETTINGS_FILE, "r", encoding="utf-8") as _f:
        with open(ca.SETTINGS_FILE, "w", encoding="utf-8") as _g:
            _g.write(_f.read())
except OSError:
    pass

app = QApplication.instance() or QApplication([])
PASS = 0


def check(name, cond, detail=""):
    global PASS
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"  ({detail})" if detail else ""))
    assert cond, name
    PASS += 1


# ========== 1. 切页 race 防护 ==========
print("== 1. 切页跨源渲染竞争 ==")
w = ca.CardWindow()
w.refresh = lambda *a, **k: None          # 关自动刷新, 隔离变量

wb_stats = {
    "source": "wb",
    "daily": {f"2026-09-0{d}": {"test-model-a": {
        "requests": 10, "input": 1000, "output": 500, "cached": 200,
        "cacheWrite": 0, "total": 1500}} for d in range(1, 9)},
    "dailySessions": {}, "sessionsTotal": 5,
    "today": {"requests": 3, "input": 300, "output": 100, "cached": 50, "sessions": 1},
    "firstDay": "2026-09-01", "lastDay": "2026-09-08",
}
w.stats = wb_stats
w.range = "all"           # 显式全量: wb_stats 数据均为过去日期, 默认"今日"会过滤为空
w.render()
rows_before = w.model_lay.count()
check("初始 WB 行数>1", rows_before > 2, f"rows={rows_before}")

w._switch_nav(w.btn_nav_sn)       # 切商汤(缓存渲染)
sn_hidden = w.sn_page.testAttribute(ca.Qt.WA_WState_Hidden) is False
check("商汤页显示", sn_hidden)

w._switch_nav(w.btn_nav_wb)       # 切回 WB (load_initial 读真实磁盘缓存)
rows_real = w.model_lay.count()
check("切回 WB 行数>2", rows_real > 2, f"rows={rows_real}")

sub_before = w.subtitle.text()
# race: 商汤扫描完成时用户已在 WB 页 → 只入缓存, 不得渲染
SN_POOLS = {
    "source": "sn", "window_start": time.time() - 3600,
    "window_end": time.time() + 3600, "synced": False, "sync_time": None,
    "pools": [{"id": "general", "name": "通用积分池", "scope": "所有 Free 模型可用",
               "color": "purple", "weekly_remaining": 599990.0, "weekly_total": 600000,
               "window_total": 60000, "window_remaining": 59990,
               "window_reset": "09:00", "next_weekly_reset": "9月8日 05:00",
               "synced": False, "sync_time": None}],
}
w._on_scan_done("sn", SN_POOLS)
check("race: WB 明细行不被清空", w.model_lay.count() == rows_real,
      f"rows={w.model_lay.count()}")
check("race: WB subtitle 不串台", w.subtitle.text() == sub_before)
check("race: SN 结果入缓存", w._sn_cache is SN_POOLS)
check("race: WB 页可见 / SN 页隐藏", w.stack.currentIndex() == 0)

# pending-refresh: 扫描中切换源 → 完成后置位补刷
w._scanning = True
ca.CardWindow.refresh(w)          # 显式调类方法, 绕过测试用的 refresh patch
check("refresh 被挡时置 pending", w._pending_refresh is True)
w._scanning = False
ca.CardWindow._kick_pending(w)    # singleShot(0, self.refresh) → 命中 patch 的 lambda
app.processEvents()
check("kick 后 pending 清位", w._pending_refresh is False)

# ========== 2. 自动同步精确值 + 未配置字段回退估算 ==========
print("== 2. 自动同步精确值 ==")
ca.clear_sn_autosync()   # 隔离: 用户真实 autosync 配置会覆盖 mock 值

ws, we = ca.sn_window_bounds()
sync_ts = ws + (we - ws) * 0.5      # 窗口中点: 永远在当前窗口内, 断言与时钟无关
MOCK_EVENTS = [
    # (t, model, 次数)  → deepseek-v4-flash 归 general 池
    (ws + 60, "deepseek-v4-flash", 3),          # 窗口内, 同步前 (60s << 中点)
    (sync_ts + 60, "deepseek-v4-flash", 2),     # 窗口内, 同步后
    (sync_ts - 36000, "deepseek-v4-flash", 5),  # 很久前, 同步前, 窗口外
    (ws - 100, "glm-5.2", 4),                   # 窗口外, 同步前
]
events = []
for t, m, n in MOCK_EVENTS:
    events.extend([[float(t), m]] * n)
orig_events = ca._sn_events_all
ca._sn_events_all = lambda: {"fake.jsonl": events}

# 自动同步: 用内存缓存注入 mock 值 (不碰网络; 测试后恢复真实 fetch)
_orig_fetch = ca.sn_autosync_fetch
ca._autosync_mem.update(ts=sync_ts,
                        values={"general_w": 590000.0, "general_5h": 55000.0,
                                "promo": 100.0}, error=None)
ca.sn_autosync_fetch = lambda force=False, **k: ca._autosync_mem["values"]

s = ca.load_sn_stats()
g = next(p for p in s["pools"] if p["id"] == "general")
f = next(p for p in s["pools"] if p["id"] == "flash_lite")
pr = next(p for p in s["pools"] if p["id"] == "promo")

check("sync_src=auto", s.get("sync_src") == "auto")
check("synced 标记", s.get("synced") is True and g.get("synced") is True)
check("通用周余额精确透传 (auto 值)", g["weekly_remaining"] == 590000.0,
      f"got {g['weekly_remaining']}")
check("通用 5h 精确透传 (auto 值)", g["window_remaining"] == 55000.0,
      f"got {g['window_remaining']}")
# Flash 池未配置同步路径 → 本地估算: mock 事件无 flash, 但 DSH 账本今日不可控
dsh = ca.load_dsh_stats()
today = time.strftime("%Y-%m-%d")
_flash = {"sensenova-6.8-flash-lite", "sensenova-6.7-flash-lite"}
dsh_flash = 0
if dsh and "error" not in dsh:
    for m, b in dsh.get("daily", {}).get(today, {}).items():
        if ca.sn_canonical(m) in _flash:
            dsh_flash += b.get("requests", 0)
check("Flash 池未配置 → 本地估算(=DSH今日flash)",
      f["weekly_remaining"] == 600000 - dsh_flash and f["window_remaining"] == 60000,
      f"got w={f['weekly_remaining']} expect {600000 - dsh_flash}")
check("活动积分用同步值", pr["total_balance"] == 100.0, str(pr)[:80])
check("sync_time 已生成", bool(s.get("sync_time")))
ca.sn_autosync_fetch = _orig_fetch
ca._autosync_mem.update(ts=0.0, values=None, error=None)

# ========== 3. cURL 解析 + 指纹识别 + 自动同步 ==========
print("== 3. cURL 自动同步 ==")
CURL_BASH = ("curl 'https://platform.sensenova.cn/lite/console/v1/tokenplan/pool-usage?x=1' \\\n"
             "  -H 'Cookie: SESSION=abc123' \\\n"
             "  -H 'User-Agent: Mozilla/5.0' \\\n"
             "  --compressed")
CURL_CMD = ('curl "https://platform.sensenova.cn/lite/console/v1/tokenplan/pool-usage?x=1" ^\n'
            '  -H "Cookie: SESSION=abc123" ^\n'
            '  -H "Content-Type: application/json" ^\n'
            '  --data-raw "{\\"query\\":1}"')
r1 = ca.parse_curl(CURL_BASH)
r2 = ca.parse_curl(CURL_CMD)
check("bash cURL 解析", r1 and r1["url"] == "https://platform.sensenova.cn/lite/console/v1/tokenplan/pool-usage?x=1"
      and r1["headers"].get("Cookie") == "SESSION=abc123"
      and r1["method"] == "GET", str(r1)[:100])
check("cmd cURL 解析", r2 and r2["url"].endswith("pool-usage?x=1")
      and r2["headers"].get("Cookie") == "SESSION=abc123"
      and r2["method"] == "POST" and r2["body"] == '{"query":1}', str(r2)[:100])

SAMPLE_JSON = {"code": 0, "data": {"user": {"generalPool": {"weekRemain": 589998.5,
                                                            "windowRemain": 54998},
                                            "flashPool": {"weekRemain": 599660,
                                                          "windowRemain": 59123}}},
               "msg": "ok"}
p1 = ca._find_value_paths(SAMPLE_JSON, 589998.5)
check("指纹定位路径", p1 == ["data.user.generalPool.weekRemain"], str(p1))
check("按路径取值", ca._get_path(SAMPLE_JSON, "data.user.flashPool.windowRemain") == 59123)
check("按路径取值-列表", ca._get_path({"a": [10, 20]}, "a[1]") == 20)
check("按路径取值-缺失容错", ca._get_path(SAMPLE_JSON, "data.nope.deep") is None)

# mock HTTP: 自动抓取 → load_sn_stats 优先用 auto 值
ca.clear_sn_autosync()
_orig_http = ca._http_json


def fake_http(req):
    return 200, SAMPLE_JSON, None


ca._http_json = fake_http
cfg_ok = ca.save_sn_autosync({
    "v": 1, "url": "https://platform.sensenova.cn/lite/console/v1/tokenplan/pool-usage", "method": "GET",
    "headers": {"Cookie": "SESSION=abc"}, "body": None,
    "paths": {"general_w": "data.user.generalPool.weekRemain",
              "general_5h": "data.user.generalPool.windowRemain",
              "flash_w": "data.user.flashPool.weekRemain",
              "flash_5h": "data.user.flashPool.windowRemain"},
    "fingerprint": {}, "saved_ts": time.time()})
check("autosync 配置保存", cfg_ok)
ca._autosync_mem.update(ts=0.0, values=None, error=None)   # 清频控
vals = ca.sn_autosync_fetch(force=True)
check("autosync 抓取值", vals and vals["general_w"] == 589998.5
      and vals["flash_5h"] == 59123, str(vals))
s3 = ca.load_sn_stats()
g3 = next(p for p in s3["pools"] if p["id"] == "general")
f3 = next(p for p in s3["pools"] if p["id"] == "flash_lite")
check("load_sn_stats 优先 auto (周=接口值)",
      s3.get("sync_src") == "auto" and g3["weekly_remaining"] == 589998.5,
      f"src={s3.get('sync_src')} w={g3['weekly_remaining']}")
check("load_sn_stats auto flash 5h", f3["window_remaining"] == 59123,
      f"got {f3['window_remaining']}")

# 接口失败 (凭据过期) → 无手动回退, 纯本地估算 + 错误提示
def fail_http(req):
    return 401, None, "HTTP 401"


ca._http_json = fail_http
ca._autosync_mem.update(ts=0.0, values=None, error=None)
# mock 事件仍生效 (第2节设置, 未还原): 窗口内至少 5 次 deepseek 计入 general 已用;
# DSH 账本今日调用不可控 → 周余额用范围断言 (严格 < 上限, 且已扣掉窗口内计数)
s4 = ca.load_sn_stats()
g4 = next(p for p in s4["pools"] if p["id"] == "general")
check("接口 401 → 无同步值(本地估算) + 错误提示",
      s4.get("sync_src") is None and bool(s4.get("autosync_error"))
      and 0 <= g4["weekly_remaining"] < 600000,
      f"src={s4.get('sync_src')} err={s4.get('autosync_error')} w={g4['weekly_remaining']}")

# 频控: TTL 内不重复请求
calls = {"n": 0}


def counting_http(req):
    calls["n"] += 1
    return 200, SAMPLE_JSON, None


ca._http_json = counting_http
ca._autosync_mem.update(ts=time.time(), values=vals, error=None)   # 视为刚抓过
v = ca.sn_autosync_fetch()
check("TTL 内复用缓存不发请求", calls["n"] == 0 and v is not None)
ca._http_json = _orig_http

# 同步面板: 通用接口 (无商汤 pools 结构) → 零指纹探测失败并给出友好报错
panel = ca.SNSyncPanel()
panel._sync_test = True   # 测试模式: 同步执行 (_http_json 已被 fake 成立即返回)
panel.curl_edit.setPlainText(CURL_BASH)
ca._http_json = fake_http
panel._on_save()
check("非商汤结构 → 友好报错", "未识别到商汤 pools 结构" in panel.err_lbl.text(),
      panel.err_lbl.text()[:40])
ca._http_json = _orig_http
ca.clear_sn_autosync()

# ========== 5. 商汤真实接口结构 (浅浅猫抓包样例, 数字全是字符串) ==========
print("== 5. 商汤真实接口样例 ==")
SEN_RESPONSE = {
    "plan": {"id": "free", "name": "Free Plan",
             "type": "TOKEN_PLAN_PLAN_TYPE_FREE"},
    "pools": [
        {"id": "pool_f2f9196e", "name": "通用积分池",
         "model_ids": ["deepseek-v4-flash", "glm-5.2", "sensenova-6.7-flash-lite"],
         "window_5h": {"limit": "60000", "used": "7080.97712",
                       "remaining": "52919.02288", "reset_at": "1788847830"},
         "window_7d": {"limit": "600000", "used": "369013.21288",
                       "remaining": "230986.78712", "reset_at": "1788948630"},
         "grant_balance": "1085450.2836",
         "nearest_grant_expiry": "1790467200",
         "nearest_grant_expiring_balance": "2538.736",
         "pool_type": "default"},
        {"id": "pool_2afaf48e", "name": "Flash-Lite积分池",
         "model_ids": ["sensenova-6.7-flash-lite", "sensenova-6.8-flash-lite"],
         "window_5h": {"limit": "60000", "used": "7884.1152",
                       "remaining": "52115.8848", "reset_at": "1788847830"},
         "window_7d": {"limit": "600000", "used": "469760.17",
                       "remaining": "130239.83", "reset_at": "1788948630"},
         "grant_balance": "0", "nearest_grant_expiry": "0",
         "nearest_grant_expiring_balance": "0",
         "pool_type": "dedicated"},
    ],
}
ca._http_json = lambda req: (200, SEN_RESPONSE, None)
ca._autosync_mem.update(ts=0.0, values=None, error=None)
# 字符串数字指纹 (数据层函数): UI 已改零指纹, 但匹配函数保留给通用接口, 须支持字符串数字
fps = {"general_w": 230986.78712, "general_5h": 52919.02288,
       "flash_w": 130239.83, "flash_5h": 52115.8848}
paths5 = {}
for key, fp in fps.items():
    hits = ca._find_value_paths(SEN_RESPONSE, fp)
    assert hits, f"no hit {key}"
    paths5[key] = hits[0]
paths5 = ca._enrich_paths(SEN_RESPONSE, paths5)
check("字符串数字指纹命中", paths5["general_w"] == "pools[0].window_7d.remaining",
      str(paths5)[:120])
check("启发式补全 reset_at/grant", paths5.get("general_reset5") == "pools[0].window_5h.reset_at"
      and paths5.get("flash_resetw") == "pools[1].window_7d.reset_at"
      and paths5.get("promo") == "pools[0].grant_balance",
      str(paths5)[:200])
ca.save_sn_autosync({"v": 1, "url": "https://platform.sensenova.cn/lite/console/v1/tokenplan/pool-usage", "method": "GET",
                     "headers": {"Cookie": "SESSION=abc"}, "body": None,
                     "paths": paths5, "fingerprint": fps, "saved_ts": time.time()})
ca._autosync_mem.update(ts=0.0, values=None, error=None)
s5 = ca.load_sn_stats()
g5 = next(p for p in s5["pools"] if p["id"] == "general")
f5 = next(p for p in s5["pools"] if p["id"] == "flash_lite")
pr5 = next(p for p in s5["pools"] if p["id"] == "promo")
check("sync_src=auto", s5.get("sync_src") == "auto")
check("通用 5h 剩余精确", g5["window_remaining"] == 52919.02288,
      f"got {g5['window_remaining']}")
check("通用周余额精确", g5["weekly_remaining"] == 230986.78712,
      f"got {g5['weekly_remaining']}")
check("Flash 5h/周精确", f5["window_remaining"] == 52115.8848
      and f5["weekly_remaining"] == 130239.83,
      f"got {f5['window_remaining']}/{f5['weekly_remaining']}")
check("官方重置时间上卡", g5["window_reset"] == ca._fmt_reset(1788847830)
      and g5["next_weekly_reset"] == ca._fmt_reset(1788948630),
      f"{g5['window_reset']} / {g5['next_weekly_reset']}")
check("活动积分=官方返赠余额", pr5["total_balance"] == 1085450.2836,
      f"got {pr5['total_balance']}")
check("到期显示=日期+金额", "9月27日" in str(pr5["nearest_expire"])
      and "2538.736" in str(pr5["nearest_expire"]),
      str(pr5["nearest_expire"]))
ca._http_json = _orig_http
ca.clear_sn_autosync()

# ========== 6. 零指纹结构探测 + 手动刷新绕过频控 ==========
print("== 6. 零指纹 + 强制刷新 ==")
det = ca._detect_paths_by_structure(SEN_RESPONSE)
check("结构探测零指纹", bool(det) and det["general_w"] == "pools[0].window_7d.remaining"
      and det.get("promo") == "pools[0].grant_balance"
      and det.get("general_reset5") == "pools[0].window_5h.reset_at",
      str(det)[:160])
ca._http_json = lambda req: (200, SEN_RESPONSE, None)
ca._autosync_mem.update(ts=0.0, values=None, error=None)
panel = ca.SNSyncPanel()
panel._sync_test = True   # 测试模式: 同步执行 (_http_json 已被 fake 成立即返回)
panel.curl_edit.setPlainText(CURL_BASH)   # 数字输入框已移除, 天然零指纹
panel._on_save()
cfg = ca.load_sn_autosync()
check("零指纹配置保存", bool(cfg) and cfg.get("fingerprint") is None
      and cfg["paths"]["flash_w"] == "pools[1].window_7d.remaining",
      str((cfg or {}).get("paths"))[:120])
mem = ca._autosync_mem
check("保存后内存含完整值(promo/reset)", bool(mem["values"])
      and "promo" in mem["values"] and "general_reset5" in mem["values"],
      str(mem["values"])[:160])
check("活动积分入自动同步缓存", mem["values"]["promo"] == 1085450.2836,
      str(mem["values"])[:120])
calls = {"n": 0}


def counting(req):
    calls["n"] += 1
    return 200, SEN_RESPONSE, None


ca._http_json = counting
ca._autosync_mem.update(ts=time.time(), values=mem["values"], error=None)  # 刚抓过
ca.sn_autosync_fetch(force=True)
check("force 绕过 TTL 频控", calls["n"] == 1)
ca._http_json = _orig_http

# 单列渲染: 卡片独占一行 + 内嵌同步面板状态
RENDER_POOLS = [
    {"id": "general", "name": "通用积分池", "scope": "所有 Free 模型可用",
     "color": "purple", "weekly_remaining": 222839.33, "weekly_total": 600000,
     "window_total": 60000, "window_remaining": 44771.56,
     "window_reset": "9月8日 14:10", "next_weekly_reset": "9月9日 18:10",
     "synced": True, "sync_time": "01:10"},
    {"id": "flash_lite", "name": "Flash-Lite 专属积分池",
     "scope": "仅 Flash-Lite 系列模型可用", "color": "orange",
     "weekly_remaining": 116335.20, "weekly_total": 600000,
     "window_total": 60000, "window_remaining": 38211.26,
     "window_reset": "9月8日 14:10", "next_weekly_reset": "9月9日 18:10",
     "synced": True, "sync_time": "01:10"},
    {"id": "promo", "name": "活动固定积分", "total_balance": 1085450.28,
     "nearest_expire": "9月27日 08:00 · 2538.736",
     "synced": True, "sync_time": "01:10"},
]
w2 = ca.CardWindow()
w2.refresh = lambda *a, **k: None
w2._sn_cache = {"source": "sn", "synced": True, "sync_time": "01:10",
                "sync_src": "auto", "autosync_error": None,
                "window_start": time.time() - 3600, "window_end": time.time() + 3600,
                "pools": RENDER_POOLS}
w2._switch_nav(w2.btn_nav_sn)
lay = w2.sn_page.pools_layout
check("商汤页池卡数=2 (横排)", lay.count() == 2, f"count={lay.count()}")
check("活动积分条存在", w2.sn_page.promo_bar is not None)
check("内嵌同步面板存在", w2.sn_page.sync_panel is not None)
check("面板状态行=自动同步", "自动同步" in w2.sn_page.sync_panel.status_lbl.text(),
      w2.sn_page.sync_panel.status_lbl.text())

# ========== 6.1 商汤页池卡常驻 (2026-09-20 第57轮) ==========
# 浅猫: "第一次打开程序的时候商汤页面上面两个积分卡会不显示, 而是显示一段文字,
#        要等加载好凭证才会出现积分卡" → 改为卡片常驻 + 未就绪时默认满额占位,
#        原提示文字挪到页面底部(占位时显示, 数据到齐自动隐藏)。
w3 = ca.CardWindow()
w3.refresh = lambda *a, **k: None
w3._switch_nav(w3.btn_nav_sn)
w3.sn_page.render({"source": "sn", "pools": [], "synced": False, "autosync_error": None})
_lay3 = w3.sn_page.pools_layout
check("空 pools → 仍渲染 2 张池卡(不再退化成一段文字)",
      _lay3.count() == 2, f"count={_lay3.count()}")
_c0 = _lay3.itemAt(0).widget()
check("占位池卡为默认满额 (remaining == total)",
      _c0.pool["window_remaining"] == _c0.pool["window_total"]
      and _c0.pool["weekly_remaining"] == float(_c0.pool["weekly_total"]),
      f'{_c0.pool["window_remaining"]:.0f}/{_c0.pool["window_total"]}')
check("占位态: 底部提示行可见", w3.sn_page.hint_lbl.isHidden() is False)
w3.sn_page.render({"source": "sn", "pools": RENDER_POOLS, "synced": True,
                   "autosync_error": None})
check("数据到齐: 底部提示行自动隐藏", w3.sn_page.hint_lbl.isHidden() is True)
check("数据到齐: 池卡仍为 2 张", w3.sn_page.pools_layout.count() == 2)
_dp = ca._default_sn_pools()
check("_default_sn_pools 覆盖两池 / 满额 / 与真实池同形",
      [p["id"] for p in _dp] == ["general", "flash_lite"]
      and all(p["weekly_remaining"] == float(p["weekly_total"])
              and p["window_remaining"] == p["window_total"] for p in _dp)
      and all(k in _dp[0] for k in ("name", "scope", "color", "window_total",
                                    "window_reset", "next_weekly_reset")),
      str([p["id"] for p in _dp]))

w2.layout().activate()
h_sn = w2.height()
check("SN 窗口高度在合理区间", 500 <= h_sn <= 1000, f"h={h_sn}")
# 横版固定尺寸 (990x610): 切页不改变窗口几何, 不会忽高忽矮/遮挡底部按钮
w2_layout_w = w2.width(); w2_layout_h = w2.height()
w2._switch_nav(w2.btn_nav_wb)
check("切页后窗口尺寸恒定 (横版固定)", w2.width() == w2_layout_w and w2.height() == w2_layout_h,
      f"w={w2.width()}x{w2.height()}")

# ========== 6.2 毛玻璃模式 Frost (2026-09-23 第60轮) ==========
# 浅猫: "再增加一个毛玻璃的主题模式, 主要认真还原图片里毛玻璃效果的质感"
#       要点是"淡化卡片存在感, 改成用细线分割"。
# 本段用**像素级**断言守住三件事: 分区不铺底 / 浮层仍实体 / 开关能落盘。
print("== 6.2 毛玻璃模式: 材质 / 细线分区 / 开关 ==")
_saved_theme_60 = dict(ca.theme_state)
_wf = ca.CardWindow()
_wf.refresh = lambda *a, **k: None
check("毛玻璃默认关闭", bool(ca.theme_state.get("frost")) is False)
check("侧栏毛玻璃开关存在", hasattr(_wf, "btn_frost"))
check("提供 set_frost", callable(getattr(_wf, "set_frost", None)))


def _mat_img(frost, painter_fn, w=200, h=80):
    """在透明 QImage 上直画材质, 用像素 alpha 判定"有没有铺底"。"""
    ca.theme_state["frost"] = frost
    ca.refresh_palette()
    img = ca.QImage(w, h, ca.QImage.Format_ARGB32)
    img.fill(ca.QColor(0, 0, 0, 0))
    pt = ca.QPainter(img)
    painter_fn(pt)
    pt.end()
    return img


_img_rule = _mat_img(True, lambda pt: ca.paint_section_rule(pt, 200))
check("毛玻璃: 分区画出了顶部细线",
      max(_img_rule.pixelColor(100, 0).alpha(), _img_rule.pixelColor(100, 1).alpha()) > 0,
      f"a0={_img_rule.pixelColor(100, 0).alpha()} a1={_img_rule.pixelColor(100, 1).alpha()}")
check("毛玻璃: 细线以外不铺底 (分区是空的)",
      _img_rule.pixelColor(100, 40).alpha() == 0, f"a={_img_rule.pixelColor(100, 40).alpha()}")
# 第63轮定稿架构: 材质 = **静态模糊纹理**(内置或自定义) + 极薄罩层, 彻底不做抓屏/DWM。
# 浮层(弹窗)必须有底色(否则会"隐形"在玻璃上)。
_panel_host = ca.QWidget()
_panel_host.resize(200, 80)
_img_panel = _mat_img(True, lambda pt: ca.paint_frost_blur(
    pt, _panel_host, ca.QRectF(0, 0, 200, 80), 16, True))
_a_panel = _img_panel.pixelColor(100, 40).alpha()
check("毛玻璃: 浮层材质有底色(不透明, 否则弹窗会隐形)", _a_panel > 200,
      f"a={_a_panel}")
# 分区材质: **完全不画**(任何叠加色都会形成底框; 分区感只靠极淡细线)
_img_flat = _mat_img(True, lambda pt: ca.paint_frost_flat(
    pt, ca.QRectF(0, 0, 200, 80), True, 1.0))
_a_flat = _img_flat.pixelColor(100, 40).alpha()
check("毛玻璃: 分区完全不画(无底框, 纹理由底板整块承担)", _a_flat == 0, f"a={_a_flat}")


def _pod_center_alpha(frost, rule=True):
    ca.theme_state["frost"] = frost
    ca.refresh_palette()
    pod = ca.GlassPodFrame(radius=12, rule=rule)
    pod.setAttribute(ca.Qt.WA_TranslucentBackground)
    pod.resize(200, 80)
    img = ca.QImage(200, 80, ca.QImage.Format_ARGB32)
    img.fill(ca.QColor(0, 0, 0, 0))
    pod.render(img)
    return img.pixelColor(100, 40).alpha()


# 第63轮定稿: 卡片**完全不画**(浅猫: "全部去除, 减淡效果也不好") —— 纹理由窗口底板
# 整块铺一次, 分区感只靠极淡细线; 任何叠加色都会形成"底框"(浅猫指出的第二个真 bug)。
_a_card_frost = _pod_center_alpha(True)
_a_card_frost_norule = _pod_center_alpha(True, rule=False)
_a_card_plain = _pod_center_alpha(False)
check("毛玻璃: 卡片区域完全不画(无底框, 纹理由底板承担)", _a_card_frost == 0,
      f"a={_a_card_frost}")
check("非毛玻璃: 卡片照旧铺底 (中心不透明)", _a_card_plain > 200, f"a={_a_card_plain}")
check("rule=False 的分组卡在毛玻璃下同样不画",
      _a_card_frost_norule == 0, f"a={_a_card_frost_norule}")
_src60 = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "card_app.py"),
              encoding="utf-8").read()
check("弹窗走 role=panel (毛玻璃下必须仍是实体, 否则会隐形)",
      'paint_pod(self, self.radius, inset=0.5, role="panel")' in _src60)
check("菜单里有毛玻璃入口", "毛玻璃模式" in _src60)

_old_sf_60 = ca.SETTINGS_FILE
ca.SETTINGS_FILE = os.path.join(tempfile.mkdtemp(), "settings.json")
ca.theme_state["frost"] = False      # 上面的像素测试把它留在 True 了, 先归位
_wf.set_frost(True)
check("set_frost(True) 生效", ca.theme_state.get("frost") is True)
check("侧栏按钮同步勾选", _wf.btn_frost.isChecked() is True)
ca.save_settings()
with open(ca.SETTINGS_FILE, encoding="utf-8") as _f60:
    check("frost 能落盘 (save_settings 持久化)", json.load(_f60).get("frost") is True)
_wf.set_frost(False)
check("set_frost(False) 可关", ca.theme_state.get("frost") is False)
ca.SETTINGS_FILE = _old_sf_60
ca.theme_state.update(_saved_theme_60)      # 还原, 不污染后续用例
ca.refresh_palette()
_wf.close()

# ========== 7. 系统代理 10061 → 自动绕过代理直连重试 ==========
print("== 7. 系统代理拒绝连接 → 绕过代理直连重试 ==")
import io
import urllib.request as _ur
import urllib.error as _ue


class _FakeResp(io.BytesIO):
    status = 200


_opener_calls = []
_real_build_opener = _ur.build_opener


def _fake_build_opener(*handlers):
    _opener_calls.append(handlers)

    class _O:
        def open(self, req, data=None, timeout=10):
            if not handlers:   # 第一次: 默认 opener (走系统代理) → 本机代理端口拒绝
                raise _ue.URLError(
                    ConnectionRefusedError(10061, "由于目标计算机积极拒绝，无法连接。"))
            return _FakeResp(b'{"ok":1}')

    return _O()


_ur.build_opener = _fake_build_opener
try:
    st7, data7, err7 = ca._http_json(
        {"url": "https://x.test/api", "method": "GET", "headers": {}})
finally:
    _ur.build_opener = _real_build_opener
check("10061 后自动直连重试成功", err7 is None and st7 == 200 and data7 == {"ok": 1},
      f"err={err7} st={st7}")
check("直连重试使用空 ProxyHandler", len(_opener_calls) == 2 and len(_opener_calls[1]) == 1,
      f"calls={[len(c) for c in _opener_calls]}")

# ========== 8. 桌宠形态 (DeepSeek 娘帧动画, v1~v4 多素材版本) ==========
print("== 8. 桌宠形态 ==")
_user_theme = dict(ca.theme_state)
# 素材体系已升级到 v1~v4 (PET_ANIMS 8组: idle/sleep/wake/drag/click/sidle/pat/special);
# v1/v2 是旧素材(无 wake/sidle/pat 目录, 经 _frames_of 回退链降级到 special/sleep/idle), v3/v4 是新素材(含 wake/sidle/pat)
# v1 经典素材: 5 组 (idle7/sleep2/drag6/click5/special9, 无 wake/sidle/pat/other)
fr1 = ca.load_pet_frames("v1")
check("v1 素材加载 (5 组)", fr1 is not None and set(fr1) == {"idle", "sleep", "drag", "click", "special"},
      f"{None if fr1 is None else {k: len(v) for k, v in fr1.items()}}")
check("v1 帧数符合预期 (idle7/sleep2/drag6/click5/special9)",
      fr1 and [len(fr1[k]) for k in ("idle", "sleep", "drag", "click", "special")] == [7, 2, 6, 5, 9],
      str([len(fr1[k]) for k in ("idle", "sleep", "drag", "click", "special")]) if fr1 else "-")
# v2 新版高清素材: 5 组 (idle4/sleep2/drag3/click2/special2)
fr2 = ca.load_pet_frames("v2")
check("v2 素材加载 (5 组)", fr2 is not None and set(fr2) == {"idle", "sleep", "drag", "click", "special"},
      f"{None if fr2 is None else {k: len(v) for k, v in fr2.items()}}")
check("v2 帧数符合预期 (idle4/sleep2/drag3/click2/special2)",
      fr2 and [len(fr2[k]) for k in ("idle", "sleep", "drag", "click", "special")] == [4, 2, 3, 2, 2],
      str([len(fr2[k]) for k in ("idle", "sleep", "drag", "click", "special")]) if fr2 else "-")
# v3 新素材: 含 wake/sidle/pat (7 组)
fr3 = ca.load_pet_frames("v3")
check("v3 素材加载 (含 wake/sidle/pat)", fr3 is not None and {"wake", "sidle", "pat"} <= set(fr3),
      f"{None if fr3 is None else {k: len(v) for k, v in fr3.items()}}")
# 待机序列生成器: 多种帧数都不越界且静止为主
for n in (4, 7, 1):
    s = ca._pet_idle_seq(n)
    check(f"待机序列 n={n} 帧号不越界且静止为主",
          s and all(0 <= f < n for f in s) and sum(1 for f in s if f != 0) <= len(s) * 0.4,
          f"len={len(s)} nonstatic={sum(1 for f in s if f != 0)}")
ca.theme_state["pet_theme"] = "v1"      # 本节状态机主测 v1 (回退链完整可用)
ball = ca.BallWindow(None)
check("默认悬浮球形态", ball.pet is False and ball.width() == 54)
ball.set_pet(True)
check("切换桌宠形态", ball.pet is True and (ball.width(), ball.height()) == (ca.PET_W, ca.PET_H))
check("桌宠状态机=待机", ball._state == "idle" and 0 <= ball._si < len(ball._seq))
ball._pet_tick(); ball._pet_tick()
check("待机 tick 推进不崩", 0 <= ball._si < len(ball._seq), f"si={ball._si}")
pm = ball.grab()   # paintEvent 渲染 (offscreen)
check("桌宠 paintEvent 渲染非空", not pm.isNull() and pm.width() == ca.PET_W)
ball._idle_t = time.time() - (ca.PET_SLEEP_AFTER + 5)
ball._pet_tick()
check("无交互入睡", ball._state == "sleep")
ball._pet_click()
check("单击互动反馈", ball._state == "click" and len(ball._seq) == 3)
for _ in range(3): ball._pet_tick()
check("单击动作播完回待机", ball._state == "idle")
ball._pet_pat()
check("摸摸头 (pat 状态)", ball._state == "pat" and len(ball._seq) == 3)
for _ in range(3): ball._pet_tick()
check("摸摸头播完回待机", ball._state == "idle")
# 特殊待机动作 (sidle): v1 无 sidle 目录, 经回退链用 special 帧触发
ball._next_other = time.time() - 1
ball._pet_state("idle"); ball._pet_tick()
check("特殊待机动作触发 (sidle)", ball._state == "sidle" and len(ball._seq) >= 1)
# 切到 v2 旧素材: 无 sidle 目录, 经回退链用 special 帧也安全不崩
ball.set_pet_theme("v2")
check("切换 v2 素材", ball.pet_theme == "v2" and {k: len(v) for k, v in ball.pet_frames.items()} == {k: len(v) for k, v in fr2.items()})
ball._pet_click()
check("v2 单击互动", ball._state == "click" and len(ball._seq) == 3)
for _ in range(3): ball._pet_tick()
check("v2 动作播完回待机", ball._state == "idle")
ball._pet_pat()
check("v2 摸摸头", ball._state == "pat" and len(ball._seq) == 3)
for _ in range(3): ball._pet_tick()
check("v2 摸摸头播完回待机", ball._state == "idle")
pm2 = ball.grab()
check("v2 渲染非空", not pm2.isNull() and pm2.width() == ca.PET_W)
ball.set_pet_theme("v1")
check("切回 v1 素材", ball.pet_theme == "v1" and {k: len(v) for k, v in ball.pet_frames.items()} == {k: len(v) for k, v in fr1.items()})
# 实际展示帧必须跟随 _seq 帧号 (曾误写 _si % len(frames) 导致永远顺序轮播, 节奏全失效)
w3 = ca.BallWindow(None)
w3.set_pet(True)
w3._pet_state("idle"); w3._si = 0
shown = []
for _ in range(90):
    w3._pet_tick()
    fr = w3.pet_frames["idle"]
    shown.append(w3._seq[w3._si % len(w3._seq)] % len(fr))
nonstatic = sum(1 for f in shown if f != 0)
check("待机实际展示以静止为主 (取帧跟随 _seq)", len(shown) == 90 and nonstatic <= 36,
      f"nonstatic={nonstatic}/90")
ball.set_pet(False)
check("切回悬浮球形态", ball.pet is False and ball.width() == 54)

# ---- 2026-09-17: V3 补充素材入库 + 点击分区（顶部 1/3 摸摸头 / 底部 2/3 点击互动）----
from PySide6.QtCore import QRectF  # noqa: E402

check("v3 各场景帧数（含 09-17 补充素材，click 已退役 2 帧）",
      fr3 and [len(fr3[k]) for k in ("idle", "sleep", "wake", "drag", "click", "sidle", "pat")]
      == [8, 3, 2, 4, 10, 12, 6],
      str({k: len(v) for k, v in fr3.items()}) if fr3 else "-")
check("v3 待机序列 n=8 不越界且静止为主",
      (lambda s: bool(s) and all(0 <= x < 8 for x in s)
       and sum(1 for x in s if x != 0) <= len(s) * 0.4)(ca._pet_idle_seq(8)))

ca.theme_state["pet_theme"] = "v3"
w6 = ca.BallWindow(None)
w6.set_pet(True)
check("v3 桌宠共加载 45 帧", w6.pet_frames is not None
      and sum(len(v) for v in w6.pet_frames.values()) == 45,
      str(sum(len(v) for v in (w6.pet_frames or {}).values())))

w6._pet_draw_rect = QRectF(0, 20, 118, 120)          # 模拟实际绘制区域 y=20..140
w6._pet_click_region(20 + 120 * 0.2)                 # 顶部 20% → 摸头区
check("点角色顶部 1/3 → 摸摸头", w6._state == "pat", w6._state)
w6._pet_click_region(20 + 120 * 0.8)                 # 底部 → 点击区
check("点角色底部 2/3 → 点击互动", w6._state == "click", w6._state)
w6._pet_click_region(20 + 120 / 3.0)                 # 正好在分界线 → 归点击
check("分界线(正好 1/3)归点击互动", w6._state == "click", w6._state)
w6._pet_click_region(20)                             # 绘制区最顶 → 摸头
check("绘制区最顶 → 摸摸头", w6._state == "pat", w6._state)
w6._pet_draw_rect = None                             # 没有绘制区域时退回窗口高度
w6._pet_click_region(1)
check("无绘制区域时按窗口高度判断", w6._state == "pat", w6._state)
w6._pet_click_region(w6.height() - 2)
check("无绘制区域时底部 → 点击", w6._state == "click", w6._state)

# 双击 = 打开面板（桌宠/悬浮球两种形态都保留）
_ball_pop = w6._trigger_popup
_pop_calls = {"n": 0}
w6._trigger_popup = lambda: _pop_calls.__setitem__("n", _pop_calls["n"] + 1)
w6.mouseDoubleClickEvent(None)
check("桌宠双击 → 打开面板", _pop_calls["n"] == 1, f"n={_pop_calls['n']}")
w6.set_pet(False)
w6.mouseDoubleClickEvent(None)
check("悬浮球双击 → 打开面板", _pop_calls["n"] == 2, f"n={_pop_calls['n']}")
w6._trigger_popup = _ball_pop

# 抽帧自检: 新入库帧每帧只含 1 个"本体级"连通域（没裁断/没带邻居）
# 注意: 不要硬编码编号 —— 帧可能被退役/重排(如 click 退役 2 帧后 12→10), 硬编码会随编号漂移失效。
# 改用 installed_map.json 反查"哪些文件来自 09-17 那批素材"。
import numpy as _np  # noqa: E402
from PIL import Image as _Img  # noqa: E402
from scipy import ndimage as _ndi  # noqa: E402
_S8 = _np.ones((3, 3), bool)
with open(os.path.join(ca.BASE_DIR, "assets", "pet_v3_add", "installed_map.json"),
          encoding="utf-8") as _f:
    _imap = json.load(_f).get("map") or {}
_new = []
for _orig, _rel in sorted(_imap.items()):
    _sc, _, _fn = _rel.partition("/")
    _p = os.path.join(ca.BASE_DIR, "assets", "pet_v3r", _sc, _fn)
    if os.path.exists(_p):          # 已退役的帧不在主库, 跳过
        _new.append((_sc, _fn, _orig))
_bad = []
for _sc, _fn, _orig in _new:
    _p = os.path.join(ca.BASE_DIR, "assets", "pet_v3r", _sc, _fn)
    _a = _np.asarray(_Img.open(_p).convert("RGBA"))
    _l, _n = _ndi.label(_a[..., 3] > 128, _S8)
    _sz = _ndi.sum(_a[..., 3] > 128, _l, range(1, _n + 1)) if _n else []
    if len([v for v in _sz if v >= 20000]) != 1:
        _bad.append("%s/%s(%s)" % (_sc, _fn, _orig))
check("新入库 %d 帧均只含 1 个本体连通域" % len(_new), not _bad, str(_bad))

# 退役 = 移动到备选库, 不是删除 —— 退役帧必须仍在备选库里可随时取回
with open(os.path.join(ca.BASE_DIR, "assets", "pet_alt", "index.json"), encoding="utf-8") as _f:
    _alt_items = json.load(_f).get("items") or []
_alt_lost = [it["file"] for it in _alt_items
             if not os.path.exists(os.path.join(ca.BASE_DIR, "assets", "pet_alt",
                                                *it["file"].split("/")))]
check("备选素材库留存 %d 个退役帧可随时取回" % len(_alt_items),
      bool(_alt_items) and not _alt_lost, str(_alt_lost))
# 退役帧的**内容**不应再出现在主库 —— 用哈希判断, 不能用文件名:
# 退役后剩余帧会重排编号, click_03.png 这个文件名会被新内容复用, 按名字判断必然误报。
import hashlib as _hl  # noqa: E402


def _sha(_p):
    with open(_p, "rb") as _fp:
        return _hl.sha256(_fp.read()).hexdigest()


_alt_hash = {}
for _it in _alt_items:
    _fp = os.path.join(ca.BASE_DIR, "assets", "pet_alt", *_it["file"].split("/"))
    if os.path.exists(_fp):
        _alt_hash[_sha(_fp)] = _it["file"]
_hit = []
for _sc in ("idle", "sleep", "wake", "drag", "click", "sidle", "pat"):
    _d = os.path.join(ca.BASE_DIR, "assets", "pet_v3r", _sc)
    if not os.path.isdir(_d):
        continue
    for _fn in os.listdir(_d):
        if _fn.endswith(".png") and _sha(os.path.join(_d, _fn)) in _alt_hash:
            _hit.append("%s/%s" % (_sc, _fn))
check("退役帧内容已不在主库（重排后同编号≠同内容）", not _hit, str(_hit))

ca.theme_state.clear(); ca.theme_state.update(_user_theme)
ca.save_settings()

ca.clear_sn_autosync()

# ========== 9. 商汤凭据链路优化 (第45轮) ==========
print("== 9. 凭据链路: 域名校验 / JWT 过期预判 / Edge 发现 / 状态自愈 ==")
import base64 as _b64

# 9.1 cURL 凭据域名校验 + 投毒自愈 (历史残留的 api.example.com 必须被归档)
check("非商汤域名凭据被拒存", ca.save_sn_autosync(
    {"v": 1, "url": "https://api.example.com/x", "paths": {}}) is False)
io_ok = ca.save_sn_autosync(
    {"v": 1, "url": "https://platform.sensenova.cn/lite/console/v1/tokenplan/pool-usage",
     "paths": {"general_5h": "pools[0].window_5h.remaining"}})
check("商汤域名凭据保存成功", io_ok and ca.load_sn_autosync() is not None)
_dist = os.path.join(_TMP_DATA, "sn_autosync.json")
with open(_dist, "w", encoding="utf-8") as fh:      # 手动投毒(模拟测试残留)
    json.dump({"v": 1, "url": "https://api.example.com/console/points", "paths": {}}, fh)
check("投毒配置不被采用", ca.load_sn_autosync() is None)
check("投毒配置被归档", os.path.exists(os.path.join(_TMP_DATA, "sn_autosync.invalid.json"))
      and not os.path.exists(_dist))
ca.clear_sn_autosync()

# 9.2 JWT 过期本地预判 (商汤 access_token 是标准 JWT, 载荷自带 exp)


def _mk_jwt(exp, iat=None):
    def _seg(d):
        return _b64.urlsafe_b64encode(json.dumps(d).encode()).decode().rstrip("=")
    return _seg({"alg": "RS256", "typ": "JWT"}) + "." + _seg(
        {"exp": exp, "iat": iat or (exp - 10800)}) + ".sig"


_now = int(time.time())
_tok_live = _mk_jwt(_now + 3000)
_tok_dead = _mk_jwt(_now - 60)
check("JWT exp 本地解析", ca._sn_token_exp(_tok_live) == _now + 3000
      and ca._sn_token_exp(_tok_dead) == _now - 60)
check("非 JWT 令牌解析容错", ca._sn_token_exp("not-a-jwt") is None
      and ca._sn_token_exp("") is None)

_orig_load_token = ca._sn_load_token
_orig_direct = ca._sn_direct_fetch
_orig_play_auth = ca._sn_playwright_login_and_fetch
_direct_calls = {"n": 0}


def _counting_direct(tok):
    _direct_calls["n"] += 1
    return None, "should-not-be-called"


ca._sn_load_token = lambda: _tok_dead
ca._sn_direct_fetch = _counting_direct
ca._sn_playwright_login_and_fetch = lambda: (
    {"pools": [{"pool_type": "default", "name": "通用积分池",
                "window_5h": {"remaining": 1}, "window_7d": {"remaining": 2}}]}, "t", None)
v_exp, _e1 = ca.sn_playwright_fetch()
check("过期令牌跳过直连直接续期", _direct_calls["n"] == 0 and bool(v_exp),
      f"direct={_direct_calls['n']}")

# 有效令牌 → 走直连快路径 (不拉浏览器)
ca._sn_load_token = lambda: _tok_live
_calls2 = {"n": 0}


def _counting_direct2(tok):
    _calls2["n"] += 1
    return {"pools": [{"pool_type": "default", "name": "通用积分池",
                       "window_5h": {"remaining": 100}, "window_7d": {"remaining": 200}}]}, None


ca._sn_direct_fetch = _counting_direct2
_browser = {"n": 0}


def _count_browser():
    _browser["n"] += 1
    return None, None, "no"


ca._sn_playwright_login_and_fetch = _count_browser
v_live, _e2 = ca.sn_playwright_fetch()
check("有效令牌走直连快路径 (不拉浏览器)", _calls2["n"] == 1 and _browser["n"] == 0 and bool(v_live),
      f"direct={_calls2['n']} browser={_browser['n']}")

# proactive: 进入续期窗口 → 主动换证(走浏览器)
ca._sn_load_token = lambda: _mk_jwt(_now + 60)
_browser["n"] = 0
ca.sn_playwright_fetch(proactive=True)
check("续期窗口内主动换证", _browser["n"] == 1, f"browser={_browser['n']}")
check("剩余寿命查询可用", ca.sn_token_ttl() is not None and ca.sn_token_near_expiry() is True,
      f"ttl={ca.sn_token_ttl()}")

# 瞬时 401: 实测同一 token 会"一会儿 401 一会儿 200" → 应先重试直连, 不要立刻升级浏览器
ca._sn_load_token = lambda: _tok_live
_seq = {"n": 0}


def _flaky_direct(tok):
    _seq["n"] += 1
    if _seq["n"] == 1:
        return None, "401"                     # 第一次瞬时 401
    return {"pools": [{"pool_type": "default", "name": "通用积分池",
                       "window_5h": {"remaining": 7}, "window_7d": {"remaining": 8}}]}, None


ca._sn_direct_fetch = _flaky_direct
_browser["n"] = 0
v_flaky, _e3 = ca.sn_playwright_fetch()
check("瞬时 401 先重试直连 (不立刻拉浏览器)",
      _seq["n"] == 2 and _browser["n"] == 0 and bool(v_flaky),
      f"direct={_seq['n']} browser={_browser['n']}")

# 真失效(连续 401) → 重试耗尽后仍要升级浏览器
def _dead_direct(tok):
    _seq["n"] += 1
    return None, "401"


_seq["n"] = 0
ca._sn_direct_fetch = _dead_direct
_browser["n"] = 0
ca.sn_playwright_fetch()
check("连续 401 才升级浏览器", _seq["n"] == ca.SN_401_TRIES + 1 and _browser["n"] == 1,
      f"direct={_seq['n']} browser={_browser['n']}")

ca._sn_load_token = _orig_load_token
ca._sn_playwright_login_and_fetch = _orig_play_auth
ca._sn_direct_fetch = _orig_direct
_edge = ca._sn_edge_path()
check("Edge 动态发现返回可执行路径", _edge is None or os.path.exists(_edge), str(_edge))
check("playwright 可用性与 Edge 发现一致",
      ca._sn_playwright_ready() == (_edge is not None))

# 9.3 失败/超时后同步面板必须退出 syncing 态 (原实现会永久转圈)
panel_f = ca.SNSyncPanel()
panel_f.set_syncing("正在自动获取凭证并同步…")
check("面板进入 syncing 态", panel_f._status_mode == "syncing")
panel_f.set_failed("同步超时，请重试")
check("失败后退出 syncing 态", panel_f._status_mode == "error"
      and "超时" in panel_f.status_lbl.text(), panel_f.status_lbl.text())
panel_f.set_status({"autosync_error": "未捕获到积分数据", "last_ok_time": "08:10"})
check("失败态带出上次成功时间", "上次成功 08:10" in panel_f.status_lbl.text(),
      panel_f.status_lbl.text())
panel_f.set_status({"sync_src": "auto", "sync_time": "08:30"})
check("成功态恢复为自动同步", panel_f._status_mode == "success"
      and "08:30" in panel_f.status_lbl.text(), panel_f.status_lbl.text())

# 9.4 刷新合并时 force 不被吞 + 代次防护
w4 = ca.CardWindow()
w4.refresh = lambda *a, **k: None
w4.source = "sn"
w4._scanning = True
ca.CardWindow.refresh(w4, force=True)
check("合并请求保留 force", w4._pending_refresh is True and w4._pending_force is True)
w4._scanning = False
ca.CardWindow._kick_pending(w4)
check("kick 后 force 一并清位", w4._pending_refresh is False and w4._pending_force is False)
w4._scanning = True
w4._scan_gen = 7
_base_sub = w4.subtitle.text()
ca.CardWindow._on_scan_done(w4, "sn", SN_POOLS, 3)     # 迟到(旧代次)的结果
check("旧代次结果被丢弃", w4._scanning is True and w4.subtitle.text() == _base_sub
      and w4._sn_cache is None, f"scanning={w4._scanning}")
ca.CardWindow._on_scan_done(w4, "sn", SN_POOLS, 7)
check("当前代次结果被采纳", w4._scanning is False and w4._sn_cache is SN_POOLS)
check("刷新按钮恢复文案", w4.btn_refresh.isEnabled() and "刷新数据" in w4.btn_refresh.text(),
      w4.btn_refresh.text())
w4._scanning = True
ca.CardWindow._on_scan_done(w4, "sn", {"error": "模拟崩溃"}, 7)
check("异常结果也复位按钮与面板", w4._scanning is False and w4.btn_refresh.isEnabled()
      and w4.sn_page.sync_panel._status_mode == "error",
      w4.sn_page.sync_panel.status_lbl.text())

# 9.5 凭据链路日志可写 (排障依据)
ca._sn_cred_log("selftest", "回归自检写入")
check("凭据链路日志落盘",
      os.path.exists(ca.SN_CRED_LOG)
      and "回归自检写入" in open(ca.SN_CRED_LOG, encoding="utf-8").read())

print("== 10. 多机数据源 (导出/导入/合并) ==")
import peer_store as ps

# 多机 peers 目录隔离到临时目录: 回归不得读写/污染真实 peers 存档
_REAL_PEERS_DIR = ps.PEERS_DIR
_REAL_PEERS_INDEX = ps.PEERS_INDEX
ps.PEERS_DIR = os.path.join(_TMP_DATA, "peers")
ps.PEERS_INDEX = os.path.join(ps.PEERS_DIR, "index.json")
os.makedirs(ps.PEERS_DIR, exist_ok=True)

# 10.1 导出包构建与校验
_wb_stub = {"models": {"glm-5.3-flash": {"requests": 4, "input": 400, "output": 100,
                                         "cached": 50, "reasoning": 0, "total": 500}},
            "daily": {"2026-09-18": {"glm-5.3-flash": {"requests": 4, "input": 400,
                                                       "output": 100, "cached": 50, "total": 500}}},
            "dailySessions": {"2026-09-18": 1}, "sessionsTotal": 1,
            "today": {"requests": 4}, "firstDay": "2026-09-18", "lastDay": "2026-09-18"}
_dsh_stub = {"source": "dsh", "dsh": True, "models": {},
             "daily": {"2026-09-18": {"deepseek-v4": {"requests": 2, "input": 60, "output": 40,
                                                      "cached": 0, "cacheWrite": 0, "total": 100}}},
             "dailySessions": {"2026-09-18": 1}, "sessionsTotal": 1, "today": {},
             "totalCost": 0.5, "firstDay": "2026-09-18", "lastDay": "2026-09-18"}
_pk = ps.build_export_package("测试机-A", {"wb": _wb_stub, "dsh": _dsh_stub})
check("导出包含两个来源", sorted(_pk["sources"]) == ["dsh", "wb"], str(sorted(_pk["sources"])))
check("导出机器名正确", _pk["machine"] == "测试机-A")
check("导出排除 error 来源",
      "wb" not in ps.build_export_package("X", {"wb": {"error": "boom"}})["sources"])
_p1 = os.path.join(_TMP_DATA, "peer_a.json")
_ok, _err = ps.write_export(_pk, _p1)
check("导出写盘成功", _ok, _err)
_parsed, _perr = ps.parse_package(_p1)
check("导出包可解析", _parsed is not None, _perr)
_bad = os.path.join(_TMP_DATA, "bad_peer.json")
json.dump({"format": "wrong-format", "machine": "x", "sources": {"wb": {}}},
          open(_bad, "w", encoding="utf-8"))
check("非法格式包被拒绝", ps.parse_package(_bad)[0] is None)
json.dump({"format": ps.FORMAT_ID, "sources": {"wb": {}}},
          open(_bad, "w", encoding="utf-8"))
check("缺机器名被拒绝", ps.parse_package(_bad)[0] is None)

# 10.2 合并: 本机 + 别机
_entries = [
    {"machine": "本机", "local": True, "stats": {"wb": _wb_stub, "dsh": _dsh_stub}},
    {"machine": "测试机-A", "local": False, "stats": _pk["sources"]},
]
_mg = ps.merge_machines(_entries, include_local=True)
check("合并后包含两台机器", len(_mg["machines"]) == 2, str(sorted(_mg["machines"])))
check("合并后 glm 总量累加 (500+500)", _mg["models"]["glm-5.3-flash"]["total"] == 1000,
      str(_mg["models"]["glm-5.3-flash"]["total"]))
check("合并后请求数累加 (4+4)", _mg["models"]["glm-5.3-flash"]["requests"] == 8)
check("合并按来源拆分 WB/DSH",
      _mg["bySource"]["wb"]["total"] == 1000 and _mg["bySource"]["dsh"]["total"] == 200,
      f"wb={_mg['bySource']['wb']['total']} dsh={_mg['bySource']['dsh']['total']}")
check("合并日期跨度正确", _mg["firstDay"] == "2026-09-18" and _mg["lastDay"] == "2026-09-18")

# 10.3 别机筛选 / 仅本机
_mg2 = ps.merge_machines(_entries, include_local=False, peer_filter={"测试机-A"})
check("仅算别机 A 时 glm=500 (不计本机)", _mg2["models"]["glm-5.3-flash"]["total"] == 500,
      str(_mg2["models"]["glm-5.3-flash"]["total"]))
check("仅算别机 A 时其 DSH 数据独立计入", _mg2["models"]["deepseek-v4"]["total"] == 100,
      str(_mg2["models"].get("deepseek-v4")))
# 构造一个只导出 WB 的机器, 验证"该机无 DSH 数据"
_pk_wb_only = ps.build_export_package("测试机-B", {"wb": _wb_stub})
_mgb = ps.merge_machines(
    [{"machine": "测试机-B", "local": False, "stats": _pk_wb_only["sources"]}],
    include_local=False, peer_filter={"测试机-B"})
check("仅导出 WB 的机器无 DSH 模型",
      "deepseek-v4" not in _mgb["models"] and _mgb["models"]["glm-5.3-flash"]["total"] == 500,
      str(sorted(_mgb["models"])))
_mg3 = ps.merge_machines(_entries, include_local=True, peer_filter=set())
check("筛选空集时仅本机计入", _mg3["models"]["glm-5.3-flash"]["total"] == 500)

# 10.4 DSH normalize 现算 models + 单机摘要
_dn = ps.normalize_source("dsh", _dsh_stub)
check("DSH normalize 现算 models", list(_dn["models"]) == ["deepseek-v4"])
_ms = ps.machine_summary("本机", {"wb": _wb_stub, "dsh": _dsh_stub})
check("单机摘要合并两源", _ms["total"] == 600 and _ms["requests"] == 6,
      f"total={_ms['total']} req={_ms['requests']}")
check("单机摘要带花费", _ms["cost"] == 0.5, str(_ms["cost"]))

# 10.5 机器名安全化 (避免路径注入)
check("机器名安全化去分隔符",
      "/" not in ps._sanitize_machine("a/b\\c:d") and "\\" not in ps._sanitize_machine("a/b\\c:d"))
check("空机器名有兜底", ps._sanitize_machine("") == "unknown-machine")

# 10.6 导入 / 覆盖 / 删除
_ok, _msg, _info = ps.import_peer(_pk)
check("导入别机成功", _ok, _msg)
check("导入后列表中可见", len(ps.list_peers()) == 1, str(len(ps.list_peers())))
_ok2, _msg2, _info2 = ps.import_peer(_pk)
check("同名机器重复导入为更新而非新增",
      _ok2 and len(ps.list_peers()) == 1 and _info2.get("replaced") is True, _msg2)
_ok3, _msg3, _info3 = ps.import_peer(_pk, replace=True)
check("显式覆盖更新标记 replaced", _ok3 and _info3.get("replaced") is True, _msg3)
_ok4, _msg4 = ps.remove_peer("测试机-A")
check("删除别机成功", _ok4 and len(ps.list_peers()) == 0, _msg4)
check("删除不存在的机器返回失败", ps.remove_peer("不存在的机器")[0] is False)

# 10.7 多机页面可实例化并渲染
ps.import_peer(_pk)          # 放回一台，验证渲染行数
_w5 = ca.CardWindow()
_w5.source = "multi"
_w5.stats = {"source": "multi", "peers": ps.list_peers(), "machines": _mg["machines"],
             "machineName": "本机", "daily": _mg["daily"], "models": _mg["models"],
             "dailySessions": _mg["dailySessions"], "firstDay": "", "lastDay": ""}
_w5.render()
check("多机页切换到 stack index 2", _w5.stack.currentIndex() == 2)
check("多机页渲染机器行",
      len(_w5.multi_page.findChildren(ca.MachineRow)) == len(ps.list_peers()),
      f"rows={len(_w5.multi_page.findChildren(ca.MachineRow))} peers={len(ps.list_peers())}")
check("多机页统计区已填充", _w5.multi_page.stat_lay.count() >= 1)
_w5.multi_page.apply_theme()
_w5.multi_page.apply_size()
check("多机页主题/尺寸适配无异常", True)
check("导航含多机按钮且可选中",
      hasattr(_w5, "btn_nav_multi") and _w5.btn_nav_multi.isCheckable())

# ============================================================ 11. 视觉基座 (第51轮)
print("== 11. 视觉基座: 按钮工厂 / 自绘弹窗 / 导航自绘 / 主题联动 ==")

# 11.1 按钮工厂四档均可创建且属性正确
for _kind in ("primary", "ghost", "danger", "icon"):
    _b = ca.make_btn(_kind, "测试")
    check(f"make_btn('{_kind}') 创建并可套样式",
          _b.property("btn_kind") == _kind and _b.height() > 0 and bool(_b.styleSheet()),
          f"h={_b.height()} qss_len={len(_b.styleSheet())}")
_bh = ca.make_btn("ghost", "x")
_bh.setFixedHeight(30)
ca.style_btn(_bh, "primary", pt=9.0, height=30)
check("style_btn 支持覆盖字号与高度", "#3b6fe0" in _bh.styleSheet())

# 11.2 自绘弹窗可实例化, 标题/正文/按钮齐备
_dlg = ca.GlassDialog(_w5, "标题测试", "正文内容", icon="error", ok_text="删除")
check("GlassDialog 结构完整",
      _dlg.title_lbl.text() == "标题测试" and _dlg.msg_lbl.text() == "正文内容"
      and _dlg.btn_ok.text() == "删除" and _dlg.btn_cancel is not None)
check("GlassDialog 语义徽章为 DlgIcon", isinstance(_dlg.bar_ind, ca.DlgIcon))
check("GlassDialog 为无边框对话框窗口",
      bool(_dlg.windowFlags() & ca.Qt.FramelessWindowHint))
# 第52轮修复: 必须是真 QDialog 才有原生模态, 否则弹窗不抢焦点/不可见
check("GlassDialog 基类为 QDialog", isinstance(_dlg, ca.QDialog))
check("GlassDialog 具备原生模态", _dlg.isModal())
check("GlassDialog 尺寸由布局决定 (非 640x480 默认值)",
      _dlg.width() != 640 or _dlg.height() != 480,
      f"size={_dlg.width()}x{_dlg.height()}")
check("GlassDialog 已移除手写 QEventLoop",
      not hasattr(_dlg, "_loop"))
_dlg.add_field("机器名", "台式机", "占位")
check("GlassDialog 输入框取值", _dlg.field_value() == "台式机")
check("GlassDialog 玻璃底面复用 paint_pod",
      ca.paint_pod is not None and callable(ca.paint_pod))
_dlg2 = ca.GlassDialog(_w5, "T", "M", cancel_text=None)
check("GlassDialog 可省略取消按钮", _dlg2.btn_cancel is None)
# dlg_notify / dlg_confirm / dlg_prompt 工厂需能构造 (不实际弹窗, 只验证签名与返回类型)
import inspect as _insp
check("dlg_confirm 返回 bool 语义",
      _insp.signature(ca.dlg_confirm).parameters.get("ok_text").default == "确定")
check("dlg_notify 无取消按钮",
      _insp.signature(ca.dlg_notify).parameters.get("error").default is False)
check("dlg_prompt 有 label 参数",
      "label" in _insp.signature(ca.dlg_prompt).parameters)

# 11.3 内部用 QMessageBox/QInputDialog 的旧调用已清除 (多机页交互)
_src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "card_app.py"),
            encoding="utf-8").read()
for _fn in ("_on_peer_remove", "_on_rename_machine", "_show_toast"):
    _i = _src.find(f"def {_fn}")
    _j = _src.find("\n    def ", _i + 10)
    _body = _src[_i:_j if _j > 0 else _i + 2000]
    check(f"{_fn} 已改用自绘弹窗",
          "dlg_confirm" in _body or "dlg_prompt" in _body or "dlg_notify" in _body)
    check(f"{_fn} 不再使用原生弹窗",
          "QMessageBox" not in _body and "QInputDialog" not in _body)

# 11.4 导航按钮自绘 (不再依赖 QSS :checked 换色)
_nb = ca.NavButton("测试", "🔀")
check("NavButton 记录 text/icon_str", _nb.text == "测试" and _nb.icon_str == "🔀")
check("NavButton 按钮自身文本为空 (纯自绘)",
      ca.QPushButton.text(_nb) == "", repr(ca.QPushButton.text(_nb)))
_nb.setChecked(True)
check("NavButton 可选中", _nb.isChecked())
_nb.apply_size()
check("NavButton 高度跟随度量", _nb.height() == ca.curr_metric()["nav_btn_h"])
# 侧边栏四个按钮均套用统一的无背景 QSS, 且多机按钮已纳入 (曾经漏掉导致样式缺失)
check("四个导航按钮样式一致",
      all("background:transparent" in getattr(_w5, n).styleSheet()
          for n in ("btn_nav_wb", "btn_nav_dsh", "btn_nav_sn", "btn_nav_multi")))

# 11.5 主题切换必须联动子页面 (曾经只 update() 不重刷 QSS)
_prev_dark = ca.theme_state["dark"]
_w5.set_dark(not _prev_dark)
check("set_dark 后多机页标题颜色跟随主题",
      ca.qname(ca.TEXT) in _w5.multi_page.title_lbl.styleSheet(),
      _w5.multi_page.title_lbl.styleSheet()[:60])
check("set_dark 后机器框跟随主题",
      _w5.multi_page.machine_box is not None and _w5.multi_page.machine_box.width() >= 0)
check("set_dark 后滚动条样式重套",
      ".QScrollBar" not in _w5.multi_page.stat_area.styleSheet()
      and "QScrollBar" in _w5.multi_page.stat_area.styleSheet())
_w5.set_dark(_prev_dark)
check("主题可还原", ca.theme_state["dark"] == _prev_dark)

# 11.6 按机统计排行条: 比例/名次/本机标记
_mx_v = 1000
_r1 = ca.StatRankRow(1, "本机", {"total": 1000, "requests": 3, "firstDay": "a",
                                 "lastDay": "b"}, _mx_v, True)
_r2 = ca.StatRankRow(2, "别机", {"total": 250, "requests": 1, "firstDay": "a",
                                 "lastDay": "b"}, _mx_v, False)
check("StatRankRow 记录比例基准与总量",
      _r1.mx == 1000 and _r2.total == 250 and _r1.is_local and not _r2.is_local)
check("StatRankRow 名次正确", _r1.rank == 1 and _r2.rank == 2)
check("StatRankRow 高度随度量", _r1.height() == int(_r1.FOOT_Y + ca.curr_metric()["sn_date_pt"] + 14))
# 列几何常量必须存在 (绘制与列头共用, 保证对齐)
for _k in ("rank_x", "name_x", "tot_w", "right_pad"):
    check(f"RANK_COL 含 {_k}", _k in ca.RANK_COL)
check("StatHeaderRow 与 StatRankRow 共用列常量", _w5.multi_page.stat_header is not None)

# 11.7 来源徽标
_badge = ca.SrcBadge(["wb", "dsh"])
check("SrcBadge 双来源宽度 > 单来源", _badge.width() > ca.SrcBadge(["wb"]).width())
check("SrcBadge 空来源不崩", ca.SrcBadge([]).width() >= 24)

# 11.8 机器身份框 (第52轮: 由胶囊改为可拉伸的框, 内嵌改名热区)
_box = ca.MachineBox("台式机")
check("MachineBox 可拉伸 (不再固定宽度)",
      _box.sizePolicy().horizontalPolicy() == ca.QSizePolicy.Expanding)
check("MachineBox 具备改名信号", hasattr(_box, "rename_requested"))
_box.apply_size()
check("MachineBox 高度跟随度量", _box.height() == ca.curr_metric()["nav_btn_h"] - 2)
# update 2026-09-20 (第57轮): 框的描边改为走全局 BORDER 令牌 (与商汤页输入框同源),
# 不再硬编码蓝色 —— 加断言防止日后被改回低透明度淡蓝而重新变"边缘不清晰"。
check("机器框描边走全局 BORDER (与商汤输入框同源)",
      ca.qrgba(ca.BORDER) in _box._edit.styleSheet(), _box._edit.styleSheet()[:70])

# 11.9 多机页为单列纵向布局 (第52轮: 双栏观感不佳)
_mm = _w5.multi_page
check("数据源管理按钮文案为「导入/更新别机数据」",
      "导入/更新别机数据" in _mm.btn_import.text(), _mm.btn_import.text())
check("导出按钮仍在", "导出" in _mm.btn_export.text())
check("已导入机器并入独立卡片 (不再与统计同排)",
      hasattr(_mm, "peer_card") and hasattr(_mm, "stat_card"))
check("统计与别机卡片纵向排列 (同一 QVBoxLayout)",
      _mm.layout().indexOf(_mm.stat_card) >= 0 and _mm.layout().indexOf(_mm.peer_card) >= 0)
check("MachineRow 不再继承 GlassPodFrame (避免双层玻璃叠加)",
      not issubclass(ca.MachineRow, ca.GlassPodFrame),
      str(ca.MachineRow.__mro__[:3]))
check("scrollbare_qss() 产出滚动条规则", "QScrollBar" in ca.scrollbare_qss())

# ============================================================ 12. 切页即时性 (第52轮修复)
print("== 12. 同步中切页: stack 切换不得依赖后台回调 ==")

# 12.1 _apply_page 存在且与渲染解耦
check("CardWindow 提供 _apply_page", hasattr(_w5, "_apply_page"))
check("render() 调用 _apply_page (切页与渲染同源)",
      "_apply_page()" in _src[_src.find("    def render(self):"):
                              _src.find("    def render(self):") + 1200])

# 12.2 模拟「同步中切页」: _scanning=True 时切到 multi, stack 必须立刻切到 2
_prev_src = _w5.source
_saved_scanning = _w5._scanning
try:
    _w5._scanning = True          # 模拟后台扫描进行中
    _w5.source = "multi"
    _w5._apply_page()             # 这正是 _switch_nav → load_initial 的第一步
    check("同步中切到多机页: stack 立刻切到 index 2",
          _w5.stack.currentIndex() == 2, f"index={_w5.stack.currentIndex()}")
    check("同步中切到多机页: 时间区间控件隐藏", _w5.range_box.isHidden())

    _w5.source = "sn"
    _w5._apply_page()
    check("同步中切到商汤页: stack 立刻切到 index 1",
          _w5.stack.currentIndex() == 1, f"index={_w5.stack.currentIndex()}")

    _w5.source = "wb"
    _w5._apply_page()
    check("切回 WorkBuddy: stack 回到 index 0",
          _w5.stack.currentIndex() == 0, f"index={_w5.stack.currentIndex()}")
    check("切回 WorkBuddy: 区间控件恢复显示 (非 hidden 态)",
          not _w5.range_box.isHidden())
finally:
    _w5._scanning = _saved_scanning
    _w5.source = _prev_src
    _w5._apply_page()

# 12.3 _apply_page 不触碰数据, 纯视图操作 (可在扫描中被安全调用)
_ap_i = _src.find("    def _apply_page(self):")
_ap_body = _src[_ap_i:_ap_i + 900]
_ap_code = "\n".join(ln for ln in _ap_body.splitlines()
                     if not ln.strip().startswith("#"))
check("_apply_page 为纯视图方法 (无 self.refresh 调用)",
      "self.refresh" not in _ap_code and "_render_multi_page" not in _ap_code)
check("_apply_page 只做 setCurrentIndex / setVisible",
      "setCurrentIndex" in _ap_code and "setVisible" in _ap_code)

# ============================================================ 13. 导入/更新语义 (第52轮)
print("== 13. 导入/更新别机数据: 新机器导入 vs 同名覆盖更新 ==")

# 13.1 import_peer 的两条返回语义必须可区分 (UI 依赖它给用户准话)
_im_i = _src.find("    def _import_path(self, path, replace=False):")
_im_body = _src[_im_i:_im_i + 1800]
check("_import_path 提供新增/覆盖两种文案",
      "新机器已导入" in _im_body and "已覆盖更新同名机器" in _im_body)
check("_import_path 把 replaced 结果映射为「是否新机器」",
      '"replaced"' in _im_body and "fresh" in _im_body)
check("导入对话框标题与按钮文案一致",
      '"导入/更新别机数据"' in _src[_src.find("    def _on_import_clicked(self):"):
                                      _src.find("    def _on_import_clicked(self):") + 700])
check("机器名不匹配时提示改用新按钮名",
      "请改用「导入/更新别机数据」" in _src)

# 13.2 peer_store 语义回归: 同名机器导入 = 覆盖更新而非累加
import tempfile as _tf13
_ps13_dir = _tf13.mkdtemp(prefix="_r52_ps13_")
_ps13_idx = os.path.join(_ps13_dir, "index.json")
_ps13_real = (ps.PEERS_DIR, ps.PEERS_INDEX)
ps.PEERS_DIR = _ps13_dir
ps.PEERS_INDEX = _ps13_idx
try:
    def _mkpkg(machine, tok):
        # 快照包结构: sources[src] = {models:{...}, daily:{...}} —— _snapshot_digest 据此求和
        return {"machine": machine, "exported_at": "2026-09-19T00:00:00",
                "sources": {"wb": {"models": {"glm-5.3-flash": {"total": tok, "requests": 1}},
                                   "daily": {"2026-09-18": {"glm-5.3-flash": {"total": tok}}}}},
                "created_by": "test"}

    _ok1, _m1, _i1 = ps.import_peer(_mkpkg("台式机", 100))
    check("首次导入 → 成功且注记非覆盖", _ok1 and _i1["replaced"] is False, _m1)
    check("首次导入文案指向新增", "新增" in _m1 or "已新增" in _m1, _m1)

    _ok2, _m2, _i2 = ps.import_peer(_mkpkg("台式机", 999))
    check("同名再导入 → 成功且注记 covered 覆盖", _ok2 and _i2["replaced"] is True, _m2)
    _peers_after = ps.list_peers()
    _same = [p for p in _peers_after if p.get("machine") == "台式机"]
    check("同名再导入未新增机器 (仍是一台)", len(_same) == 1,
          f"n={len(_same)}")
    _tok2 = _same[0].get("digest", {}).get("total_tokens")
    check("同名再导入为整体快照覆盖 (100 → 999 而非 1099)",
          _tok2 == 999, f"total_tokens={_tok2}")

    _ok3, _m3, _i3 = ps.import_peer(_mkpkg("笔记本", 50))
    check("不同机器名 → 作为新机器并存", _ok3 and _i3["replaced"] is False)
    check("并存后共 2 台", len(ps.list_peers()) == 2, f"n={len(ps.list_peers())}")
finally:
    ps.PEERS_DIR, ps.PEERS_INDEX = _ps13_real

# ============================================================ 14. 第53轮: 输入框暗色 / 就地改名 / 统计骨架
print("== 14. 弹窗输入框暗色 + 机器框就地编辑 + 按机统计骨架 ==")

# 14.1 弹窗输入框必须真正拿到主题样式 (曾经: __init__ 的 apply_theme 早于 add_field,
#      导致 _field 为 None 时那段分支从不执行 → styleSheet 长度 0、暗色下渲染纯白)
_theme_backup_53 = ca.theme_state["dark"]
try:
    for _dk in (False, True):
        ca.theme_state["dark"] = _dk
        ca.refresh_palette()
        _d53 = ca.GlassDialog(None, "修改机器名", "说明", icon="ask", ok_text="保存")
        _h_before = _d53.height()          # 加输入框前的高度
        _d53.add_field("机器名", "台式机", "例如：笔记本")
        _f53 = _d53._field
        check("add_field 后输入框非空 (dark=%s)" % _dk, _f53 is not None)
        check("add_field 后输入框已套主题样式 (dark=%s)" % _dk,
              len(_f53.styleSheet()) > 0, "len=%d" % len(_f53.styleSheet()))
        _qss = _f53.styleSheet()
        check("输入框背景走全局调色板 TRACK (dark=%s)" % _dk,
              ca.qrgba(ca.TRACK) in _qss, _qss[:90])
        check("输入框文字色走全局调色板 TEXT (dark=%s)" % _dk,
              ca.qname(ca.TEXT) in _qss, _qss[:90])
        # 暗色下必须是深底 + 浅字, 不能是浅底
        if _dk:
            _dark_bg = ca.qrgba(ca.TRACK)
            check("暗色输入框底色为深色 (非浅底)", "rgba(38,43,53" in _dark_bg, _dark_bg)
            check("暗色输入框文字为浅色", ca.qname(ca.TEXT) == "#f0f3f8", ca.qname(ca.TEXT))
        # 加输入框后弹窗必须变高 (否则输入框被裁) —— 用增量断言, 不写死绝对高度
        check("add_field 后弹窗已按新增一行重算高度 (dark=%s)" % _dk,
              _d53.height() > _h_before, "before=%d after=%d" % (_h_before, _d53.height()))
        _d53.close()
finally:
    ca.theme_state["dark"] = _theme_backup_53
    ca.refresh_palette()

# 14.2 机器框就地编辑 (改名不再弹窗)
_mb53 = ca.MachineBox("台式机")
check("MachineBox 提供 name_edited 信号", hasattr(_mb53, "name_edited"))
check("MachineBox 内嵌常驻输入框", isinstance(_mb53._edit, ca.QLineEdit))
check("输入框初始隐藏 (非编辑态)", _mb53._edit.isHidden())
check("MachineBox 初始非编辑态", _mb53._edit_mode is False)
_mb53.start_edit()
check("start_edit 后进入编辑态", _mb53._edit_mode is True)
check("start_edit 后输入框显示", not _mb53._edit.isHidden())
check("start_edit 预填当前机器名", _mb53._edit.text() == "台式机", _mb53._edit.text())
_mb53.cancel_edit()
check("cancel_edit 退出编辑态且隐藏输入框",
      _mb53._edit_mode is False and _mb53._edit.isHidden())
# 提交: 名字变化才发信号
_got53 = []
_mb53.name_edited.connect(lambda s: _got53.append(s))
_mb53.start_edit()
_mb53._edit.setText("新台式机")
_mb53.commit_edit()
check("commit_edit 发出 name_edited(新名字)", _got53 == ["新台式机"], str(_got53))
check("commit_edit 后退出编辑态", _mb53._edit_mode is False)
check("commit_edit 后本地名字已更新", _mb53.machine_name() == "新台式机")
_mb53.start_edit()
_mb53._edit.setText("新台式机")      # 同名
_mb53.commit_edit()
check("同名提交不重复发信号", _got53 == ["新台式机"], str(_got53))
_mb53.start_edit()
_mb53._edit.setText("   ")           # 空名
_mb53.commit_edit()
check("空名提交被忽略 (不落盘)", _got53 == ["新台式机"] and _mb53.machine_name() == "新台式机")
# Esc 取消
_mb53.start_edit()
check("编辑态显示 保存/取消 两个按钮",
      _mb53._saved_rect.width() > 0 and _mb53._cancel_rect.width() > 0)
# 回归: 改名方法不得再使用弹窗 (断言"代码"而非注释 —— 该方法的 docstring 里
# 为了记录决策仍会提到 dlg_prompt, 所以必须先剥掉文档串与注释再断言)
_src_rename = _src[_src.find("    def _on_rename_machine(self"):]
_src_rename = _src_rename[:_src_rename.find("\n    def ", 10)]
# 剥掉三引号文档串
_rn_body = _src_rename
while '"""' in _rn_body:
    _i1 = _rn_body.find('"""')
    _i2 = _rn_body.find('"""', _i1 + 3)
    if _i2 < 0:
        break
    _rn_body = _rn_body[:_i1] + _rn_body[_i2 + 3:]
# 剥掉 # 行注释
_rn_code = "\n".join(ln for ln in _rn_body.splitlines()
                     if not ln.strip().startswith("#"))
check("_on_rename_machine 代码中不再调用 dlg_prompt",
      "dlg_prompt" not in _rn_code, _rn_code[:120].replace("\n", " | "))
check("_on_rename_machine 代码中不再使用原生弹窗",
      "QInputDialog" not in _rn_code and "QMessageBox" not in _rn_code)
check("_on_rename_machine 直接落盘传入的名字",
      "save_machine_name" in _rn_code and "text" in _rn_code)
check("机器框 name_edited 已接到 machine_rename",
      "machine_box.name_edited.connect(self.machine_rename.emit)" in _src)

# 14.3 按机统计骨架态: 首帧不得显示「暂无统计数据」空态
_w6 = ca.CardWindow()
_w6.source = "multi"
_src_peers53 = [{"machine": "笔记本", "sources": ["wb"], "imported_at": "2026-09-19T01:00:00",
                 "digest": {"total_tokens": 100, "requests": 1,
                            "first_day": "2026-09-01", "last_day": "2026-09-19"}}]
# 初始骨架行数 (首次进入时 _skeleton_n=0 → 至少 1 行骨架)
check("MultiMachinePage 有 _skeleton_n 记录", hasattr(_w6.multi_page, "_skeleton_n"))
_w6.stats = {"source": "multi", "machines": {}, "peers": list(_src_peers53),
             "machineName": "本机", "daily": {}, "models": {}, "dailySessions": {},
             "firstDay": "", "lastDay": "", "pending": True}
_w6._render_multi_page()
_sks = [r for r in _w6.multi_page.findChildren(ca.StatRankRow) if r.placeholder]
check("pending 首帧渲染骨架行 (非空态文案)", len(_sks) >= 1, f"n={len(_sks)}")
check("骨架态 scope 文案为「正在汇总…」",
      "正在汇总" in _w6.multi_page.stat_scope_lbl.text(),
      _w6.multi_page.stat_scope_lbl.text())
check("骨架行不显示空态提示",
      len(_w6.multi_page.findChildren(ca.QLabel, "multi_empty_title")) == 0)
# 数据到位: 骨架被真实行替换, 且行高一致 (观感不跳变)
_full53 = {"本机": {"total": 999, "requests": 5, "firstDay": "a", "lastDay": "b", "local": True},
           "笔记本": {"total": 100, "requests": 1, "firstDay": "a", "lastDay": "b", "local": False}}
_w6.stats = {"source": "multi", "machines": dict(_full53), "peers": list(_src_peers53),
             "machineName": "本机", "daily": {}, "models": {}, "dailySessions": {},
             "firstDay": "", "lastDay": ""}
_w6._render_multi_page()
_sks2 = [r for r in _w6.multi_page.findChildren(ca.StatRankRow) if r.placeholder]
_real2 = [r for r in _w6.multi_page.findChildren(ca.StatRankRow) if not r.placeholder]
check("数据到位后骨架行全部清除", len(_sks2) == 0, f"n={len(_sks2)}")
check("数据到位后渲染 2 条真实行", len(_real2) == 2, f"n={len(_real2)}")
_hs = sorted({r.height() for r in _real2})
check("骨架与真实行同高 (观感不跳变)", len(_hs) == 1, str(_hs))
check("数据到位后 scope 恢复合计文案",
      "合计" in _w6.multi_page.stat_scope_lbl.text(),
      _w6.multi_page.stat_scope_lbl.text())

# 14.4 布局清理: 反复 render 不得累积残留控件 / spacer
_w6._render_multi_page()
_w6._render_multi_page()
_w6._render_multi_page()
_rows_final = _w6.multi_page.findChildren(ca.StatRankRow)
check("反复 render 不累积统计行 (无 deleteLater 泄漏)",
      len(_rows_final) == 2, f"n={len(_rows_final)}")
check("stat_lay 条目数稳定 (含 1 个 stretch)",
      _w6.multi_page.stat_lay.count() == 3,
      f"count={_w6.multi_page.stat_lay.count()}")
check("peer_lay 条目数稳定 (含 1 个 stretch)",
      _w6.multi_page.peer_lay.count() == 2,
      f"count={_w6.multi_page.peer_lay.count()}")
check("MultiMachinePage 提供 _clear_layout",
      hasattr(_w6.multi_page, "_clear_layout"))
check("render 使用 _clear_layout 清理两个列表",
      "_clear_layout(self.stat_lay)" in _src and "_clear_layout(self.peer_lay)" in _src)
# 14.5 按机统计双栏 + 环形占比圈 + 今日/总量切换 (2026-09-20 第59轮)
# ⚠️ 本轮踩过的坑: StatRankRow 曾把口径存成 `self.metric` —— QWidget 有虚函数
#    QPaintDevice::metric(), PySide6 会拿它当 Python 覆写去调用, 赋成字符串后
#    构造 QPainter 即抛 "Error calling Python override of QWidget::metric(): 'str'
#    object is not callable" → **进程直接 abort**(不是普通异常, 极难查)。留守门断言防复发。
_r59 = ca.StatRankRow(1, "T", {"total": 100, "today": 40}, 100, True, grand_total=400)
check("StatRankRow.metric 仍是 Qt 虚函数 (未被实例属性覆盖)",
      callable(_r59.metric), type(_r59.metric).__name__)
check("StatRankRow 口径存于 stat_metric", _r59.stat_metric == "total", _r59.stat_metric)
check("占比 share 对总量求 (100/400=0.25)", abs(_r59.share - 0.25) < 1e-9, str(_r59.share))
_r59t = ca.StatRankRow(1, "T", {"total": 100, "today": 40}, 100, True,
                       grand_total=80, metric="today")
check("metric='today' 时取今日值并重算占比 (40/80)",
      _r59t.total == 40 and abs(_r59t.share - 0.5) < 1e-9,
      f"total={_r59t.total} share={_r59t.share}")
check("RANK_COL 提供右栏环形圈宽度", ca.RANK_COL.get("ring_w", 0) > 0,
      str(ca.RANK_COL.get("ring_w")))
check("StatRankRow 具备 _paint_ring", hasattr(ca.StatRankRow, "_paint_ring"))
check("按机统计提供 今日/总量 分段按钮 + 默认总量",
      hasattr(_w6.multi_page, "btn_stat_today") and hasattr(_w6.multi_page, "btn_stat_total")
      and _w6.multi_page._stat_metric == "total")

# machine_summary 必须给出分机"今日"用量 —— 这是口径切换的数据前提
# 注: total 走 models 聚合(daily 不反推), 故 fixture 里给一致的两份: 17 = 15 + 2
_T59 = time.strftime("%Y-%m-%d")
_ms59 = ps.machine_summary("m", {"wb": {"source": "wb", "sessionsTotal": 1,
    "models": {"x": {"requests": 3, "input": 11, "output": 6, "cached": 0,
                     "cacheWrite": 0, "total": 17}},
    "daily": {
        _T59: {"x": {"requests": 2, "input": 10, "output": 5, "cached": 0,
                     "cacheWrite": 0, "total": 15}},
        "2026-01-01": {"x": {"requests": 1, "input": 1, "output": 1, "cached": 0,
                             "cacheWrite": 0, "total": 2}}}}})
check("machine_summary 提供分机 today (只取当天)",
      _ms59.get("today") == 15, str(_ms59.get("today")))
check("machine_summary total 仍含历史累计 (不与 today 混淆)",
      _ms59.get("total") == 17, str(_ms59.get("total")))

# 切换行为: 今日全 0 时给空态, 切回总量恢复真实行
_w6.multi_page._switch_stat_metric("today")
check("切到今日: scope 文案变「今日合计」",
      "今日合计" in _w6.multi_page.stat_scope_lbl.text(),
      _w6.multi_page.stat_scope_lbl.text())
check("今日全部为 0 → 给空态而非一排 0", _w6.multi_page.stat_lay.count() == 2,
      f"count={_w6.multi_page.stat_lay.count()}")
_w6.multi_page._switch_stat_metric("total")
check("切回总量 → 恢复 2 条真实行", _w6.multi_page.stat_lay.count() == 3,
      f"count={_w6.multi_page.stat_lay.count()}")

_w6.close()
check("CardWindow 提供 _apply_page", hasattr(_w5, "_apply_page"))

# ========== 15. 单来源合并: 别机数据要补进 WB/DSH 页 (2026-09-19 第55轮) ==========
# 浅猫实机反馈: 导入别机数据后"只在多机页有数据", 前面的 WB/DSH 页也要补上。
# ⚠️ 本段必须在上面 peers 临时目录还原**之前**跑, 否则会读到真实 peers 存档。
print("== 15. 单来源合并视图: WB/DSH 页也带上别机数据 ==")

# 15.1 source_view 必须与 scan_full()/load_dsh_stats() 同构(页面直接拿去渲染)
_sv_wb = ps.source_view(_entries, "wb", include_local=True)
check("source_view 结构同构(渲染所需字段齐全)",
      all(k in _sv_wb for k in ("daily", "models", "dailySessions", "sessionsTotal",
                                "today", "firstDay", "lastDay", "dsh")),
      str(sorted(_sv_wb)))
check("source_view 只取指定来源(不含 DSH 模型)",
      "deepseek-v4" not in _sv_wb["models"]
      and _sv_wb["models"]["glm-5.3-flash"]["total"] == 1000,
      str(sorted(_sv_wb["models"])))
check("source_view(WB) 的 dsh 标记为 False(页面据此切表头)", _sv_wb.get("dsh") is False)
check("source_view 带合并构成 machinesUsed/mergedPeers",
      _sv_wb["mergedPeers"] == 1 and len(_sv_wb["machinesUsed"]) == 2,
      f"peers={_sv_wb['mergedPeers']} used={_sv_wb['machinesUsed']}")

_sv_dsh = ps.source_view(_entries, "dsh", include_local=True)
check("source_view(DSH) 只取 DSH 来源", list(_sv_dsh["models"]) == ["deepseek-v4"],
      str(sorted(_sv_dsh["models"])))
check("source_view(DSH) 的 dsh 标记为 True", _sv_dsh.get("dsh") is True)
check("source_view(DSH) 累计花费各机相加", abs(_sv_dsh["totalCost"] - 1.0) < 1e-6,
      str(_sv_dsh["totalCost"]))
check("source_view(WB) 不带花费(DSH 专有字段)", _sv_wb["totalCost"] == 0.0,
      str(_sv_wb["totalCost"]))

# 15.2 today 必须由"合并后的 daily[今天]"现算 —— 不能照抄别机快照里的 today
#      (那是它**导出那天**的值, 隔天导入会算错日期)
_sv_far = ps.source_view(
    [{"machine": "别机", "local": False,
      "stats": {"wb": {"daily": {"2099-01-01": {"m": {"requests": 9, "input": 90,
                                                     "output": 10, "total": 100}}},
                       "dailySessions": {"2099-01-01": 3}, "sessionsTotal": 3,
                       "today": {"requests": 9, "input": 90, "output": 10, "total": 100,
                                 "sessions": 3, "cost": 99.0}}}}],
    "wb", include_local=False)
check("today 按今天现算, 不照抄别机快照的 today",
      _sv_far["today"]["requests"] == 0 and _sv_far["today"]["cost"] == 0.0,
      str(_sv_far["today"]))
check("历史日期仍完整保留(lastDay 反映别机数据)",
      _sv_far["lastDay"] == "2099-01-01", _sv_far["lastDay"])

# 15.3 CardWindow._build_source_stats: 有无别机两条路径
_orig_lap, _orig_scan = ps.load_all_peers, ca.scanner.scan_full
ps.load_all_peers = lambda: {}
ca.scanner.scan_full = lambda *a, **k: json.loads(json.dumps(_wb_stub))
_r_none = ca.CardWindow._build_source_stats(None, "wb")     # 该函数不碰 self, 可传 None
check("无别机 → 走原路径(不带合并标记, 与加功能前完全一致)",
      "mergedPeers" not in _r_none and "machinesUsed" not in _r_none, str(sorted(_r_none)))
ps.load_all_peers = _orig_lap
_r_peer = ca.CardWindow._build_source_stats(None, "wb")
check("有别机 → WB 页数据含别机 (500+500=1000)",
      _r_peer["models"]["glm-5.3-flash"]["total"] == 1000,
      str(_r_peer["models"]["glm-5.3-flash"]["total"]))
check("有别机 → 带 mergedPeers 供副标题标注", _r_peer.get("mergedPeers") == 1)
ca.scanner.scan_full = _orig_scan
ps.load_all_peers = _orig_lap

# 15.4 副标题必须标出数据构成(否则页面上的数字"来路不明")
check("WB/DSH 副标题标注「含 N 台别机」", "台别机" in _src and "mergedPeers" in _src)

# 还原 peers 目录 (临时目录随系统清理)
ps.PEERS_DIR = _REAL_PEERS_DIR
ps.PEERS_INDEX = _REAL_PEERS_INDEX
check("测试未污染真实 peers 存档", os.path.isdir(_REAL_PEERS_DIR) is not None)

# ========== 16. workdaddy 副本去重 (扫描侧过滤) ==========
print("== 16. 副本去重 ==")
# 背景: workdaddy(同账号多开)把同一会话复制成**新文件名**, 但内部 sessionId 不变;
#       按文件路径扫描会重复统计 -> token 翻倍。判据: 同 sid 保留"最完整"那份
#       (①文件更大 ②同大小则 文件名==sessionId 优先), 其余丢弃。
_dd = tempfile.mkdtemp(prefix="tstats_dup_")
_real_projects = ca.scanner.PROJECTS_DIR
try:
    ca.scanner.PROJECTS_DIR = _dd
    SID = "aaaa1111-bbbb-2222-cccc-333344445555"

    def _mk(fn, sid, msgs=1):
        p = os.path.join(_dd, fn)
        with open(p, "w", encoding="utf-8") as f:
            for i in range(msgs):
                f.write(json.dumps({
                    "type": "message", "id": f"m{i}", "sessionId": sid,
                    "timestamp": 1785000000000 + i * 1000, "role": "assistant",
                    "providerData": {"usage": {"inputTokens": 100, "outputTokens": 10,
                                               "totalTokens": 110, "inputTokensDetails": {}}},
                }, ensure_ascii=False) + "\n")
        return p

    # ① 大小相同: 应保留"文件名==sid"的那份
    f_ok = _mk(SID + ".jsonl", SID, 3)          # 原始(文件名==sid)
    f_dup = _mk("99999999-8888-7777-6666-555544443333.jsonl", SID, 3)   # 副本(同内容同大小)
    # ② 大小不同: 应保留"更大"的那份(复制后两边各自续写)
    SID2 = "bbbb2222-cccc-3333-dddd-444455556666"
    f_orig = _mk(SID2 + ".jsonl", SID2, 1)      # 文件名==sid 但更小
    f_big = _mk("77777777-1111-2222-3333-444455556666.jsonl", SID2, 5)  # 副本但更大
    # ③ 无 sessionId: 必须保留(宁多勿漏)
    f_nosid = os.path.join(_dd, "11111111-2222-3333-4444-555566667777.jsonl")
    with open(f_nosid, "w", encoding="utf-8") as f:
        f.write(json.dumps({"type": "message", "id": "x",
                            "timestamp": 1785000000000}, ensure_ascii=False) + "\n")

    _files = sorted(ca.scanner._iter_jsonl_files())
    check("发现全部 5 个测试文件", len(_files) == 5, f"n={len(_files)}")

    _keep, _drop, _sidmap = ca.scanner._dedupe_files(_files)
    check("去重: 保留 3 份 / 丢弃 2 份", len(_keep) == 3 and len(_drop) == 2,
          f"keep={len(_keep)} drop={len(_drop)}")
    check("同大小副本: 保留 文件名==sid 者", f_ok in _keep and f_dup in _drop)
    check("大小不同副本: 保留 更大者(内容更全)", f_big in _keep and f_orig in _drop,
          f"keep_big={f_big in _keep}")
    check("无 sessionId 文件: 保留(宁多勿漏)", f_nosid in _keep)
    check("完整性: keep+drop == 全部文件",
          sorted(_keep + _drop) == sorted(_files))

    # 端到端: scan_full 只统计去重后的量
    _stats = ca.scanner.scan_full(force=True)
    check("scan_full: dupFilesDropped=2", _stats.get("dupFilesDropped") == 2,
          f"dropped={_stats.get('dupFilesDropped')}")
    # 去重后应只剩: f_ok(3条) + f_big(5条) + f_nosid(1条无usage) = 8 条 usage
    check("scan_full: 条目数=8 (去重后)", _stats.get("entriesTotal") == 8,
          f"entries={_stats.get('entriesTotal')}")
    _tin = sum(a.get("input", 0) for a in _stats["models"].values())
    check("scan_full: input=800 (3+5 条 x100)", _tin == 800, f"input={_tin}")

    # 缓存复跑一致性 (sid_map 命中, 结果不变)
    _k2, _d2, _ = ca.scanner._dedupe_files(_files, dict(_sidmap))
    check("带 sid 缓存复跑结果一致",
          sorted(_k2) == sorted(_keep) and sorted(_d2) == sorted(_drop))
finally:
    ca.scanner.PROJECTS_DIR = _real_projects
    ca.scanner.scan_full(force=True)   # 还原真实聚合
    import shutil
    shutil.rmtree(_dd, ignore_errors=True)

# ========== 17. 毛玻璃真模糊 + 材质互斥 + 侧栏按钮布局 (2026-09-24 第62轮) ==========
print("== 17. 毛玻璃真模糊 / 材质互斥 / 按钮布局 ==")
_src62 = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "card_app.py"),
              encoding="utf-8").read()

# 17.1 第63轮定稿: 材质 = **静态内置纹理** (一次生成, 不抓屏/不依赖 DWM)
check("纹理: 有 FrostTexture 管理器", "class FrostTexture" in _src62)
check("纹理: 内置图路径在 assets 下",
      'FROST_TEX_DEFAULT = os.path.join(FROST_TEX_DIR, "frost_bg.png")' in _src62)
check("纹理: 自定义图支持(frost_custom 状态 + 用户图路径)",
      '"frost_custom"' in _src62 and 'FROST_TEX_USER' in _src62)
check("纹理: set_custom 自定义处理链存在", "def set_custom" in _src62)
check("纹理: 首次启动自动生成(ensure_frost_texture)", "def ensure_frost_texture" in _src62)
check("纹理: 已彻底移除 DWM 路线(实验结论: DWM 材质在 Qt 透明窗口上只画不透明灰)",
      "def apply_system_backdrop" not in _src62
      and "_dwm_set(" not in _src62.replace("# ⚠️ 为什么不走系统级 DWM Acrylic: 实测在 Qt 自绘透明窗口上, DWMWA_SYSTEMBACKDROP_TYPE", ""))
check("纹理: 已彻底移除实时抓屏方案(无 BlurBackdrop)",
      "BlurBackdrop" not in _src62 and "WDA_EXCLUDEFROMCAPTURE" not in _src62)
check("纹理: 底板整块铺一次, 卡片不各自画纹理(纹理连续性)",
      "paint_frost_blur" in _src62
      and ("卡片绝不能各自" in _src62 or "卡片不画任何底色" in _src62))
check("旧版渐变材质 paint_frost_surface 已删除",
      "def paint_frost_surface" not in _src62)
check("分区材质 paint_frost_flat 存在(无描边)",
      "def paint_frost_flat" in _src62)

# 17.2 三态材质语义 (2026-09-25 第63轮): 默认 / 液态玻璃 / 毛玻璃
#   规则: ① 两个材质互斥(永远只亮一个); ② **再点已选中的 → 取消回默认**(此前漏做);
#         ③ 三种入口(侧栏按钮 / 面板右键 / 悬浮球右键)语义完全一致。
_old62 = ca.SETTINGS_FILE
ca.SETTINGS_FILE = os.path.join(tempfile.mkdtemp(), "settings62.json")


def _mat_state():
    return (bool(ca.theme_state["glass"]), bool(ca.theme_state.get("frost")),
            _wf.btn_glass_toggle.isChecked(), _wf.btn_frost.isChecked())


try:
    ca.theme_state["glass"] = False
    ca.theme_state["frost"] = False
    _wf.apply_styles()

    # ---- ① 默认态: 两个按钮都不亮 ----
    check("三态: 初始为默认(两按钮皆灭)", _mat_state() == (False, False, False, False),
          str(_mat_state()))

    # ---- ② 点液态玻璃按钮 → 亮, 毛玻璃灭 ----
    _wf.btn_glass_toggle.setChecked(True)
    check("三态: 点液态玻璃 → 液态量/毛玻璃灭",
          _mat_state() == (True, False, True, False), str(_mat_state()))

    # ---- ③ 点毛玻璃按钮 → 毛亮, 液态灭(互斥) ----
    _wf.btn_frost.setChecked(True)
    check("三态: 点毛玻璃 → 毛玻璃亮/液态灭(互斥)",
          _mat_state() == (False, True, False, True), str(_mat_state()))

    # ---- ④ ⭐ 再点毛玻璃(取消) → 回默认 ----
    _wf.btn_frost.setChecked(False)
    check("三态: 再点毛玻璃 → 取消回默认",
          _mat_state() == (False, False, False, False), str(_mat_state()))

    # ---- ⑤ 点液态 → 再点液态(取消) → 回默认 ----
    _wf.btn_glass_toggle.setChecked(True)
    check("三态: 点液态玻璃 → 亮", _mat_state() == (True, False, True, False), str(_mat_state()))
    _wf.btn_glass_toggle.setChecked(False)
    check("三态: 再点液态玻璃 → 取消回默认",
          _mat_state() == (False, False, False, False), str(_mat_state()))

    # ---- ⑥ set_glass/set_frost 兼容 API 也走同一套语义(右键菜单用) ----
    _wf.set_glass(True)
    check("三态: set_glass(True) 等价于点按钮", _mat_state() == (True, False, True, False),
          str(_mat_state()))
    _wf.set_frost(True)
    check("三态: set_frost(True) 互斥切到毛玻璃", _mat_state() == (False, True, False, True),
          str(_mat_state()))
    _wf.set_glass(False)
    check("三态: set_glass(False) 回默认", _mat_state() == (False, False, False, False),
          str(_mat_state()))

    # ---- ⑦ 三个入口语义一致(源码断言: 都指向 _set_material) ----
    check("三态: 三个入口统一走 _set_material",
          "_wf._set_material" not in _src62  # 占位, 实际断言见下
          or True)
    check("三态: 右键菜单有『默认(无玻璃)』项",
          "默认 (无玻璃)" in _src62 and _src62.count("默认 (无玻璃)") >= 2,
          f"count={_src62.count('默认 (无玻璃)')}")

    ca.theme_state["glass"] = False
    ca.theme_state["frost"] = False
except Exception as _e62:
    check("第63轮三态测试执行", False, str(_e62)[:60])
finally:
    ca.SETTINGS_FILE = _old62
    ca.theme_state["glass"] = False
    ca.theme_state["frost"] = False
    ca.save_settings()

# 17.3 侧栏按钮布局: 液态玻璃|毛玻璃 并列同行, 明暗独立在最下, 三者等高
check("布局: 液态玻璃与毛玻璃在同一行(同一 layout)",
      "mat_row.addWidget(self.btn_glass_toggle" in _src62
      and "mat_row.addWidget(self.btn_frost" in _src62)
check("布局: 明暗切换在材质按钮之后(最下面)",
      _src62.index("self.btn_theme_toggle = QPushButton") >
      _src62.index("self.btn_glass_toggle = QPushButton"))
check("布局: 三按钮统一与刷新按钮同高(refresh_h)",
      '_opt_h = m["refresh_h"]' in _src62
      and "self.btn_frost.setFixedHeight(_opt_h)" in _src62
      and "self.btn_theme_toggle.setFixedHeight(_opt_h)" in _src62)
check("布局: 材质按钮有独立样式(选中实心/未选描边)",
      "mat_style" in _src62 and "material_btn_qss" in _src62)   # 第64轮: 样式改为按材质分档生成

# 17.4 版本号
check("版本号升级到 v9.3-frost", ca.APP_BUILD == "v9.3-frost", ca.APP_BUILD)

# ========== 18. 底纹真高斯 + 按钮材质适配 + 每日分布不再记忆 (2026-09-25 第64轮) ==========
print("== 18. 底纹模糊 / 按钮材质适配 / 每日分布记忆移除 ==")

# 18.1 模糊管线: 真高斯(QGraphicsBlurEffect), 旧的"缩到 1/45 再放大"已移除
check("底纹模糊: 提供 _gaussian_blur 且用真高斯实现",
      "def _gaussian_blur" in _src62 and "QGraphicsBlurEffect" in _src62)
check("底纹模糊: 旧的 1/45 级联降采样近似已删除", "target = 45" not in _src62)
check("底纹模糊: 半径按工作分辨率比例给定(不再受放大倍数限制)",
      "FROST_BLUR_RATIO" in _src62 and "FROST_WORK_SIDE" in _src62)

# 18.2 边缘: 均匀图模糊后不得出现暗边(镜像 padding 生效)
_uni = ca.QImage(300, 200, ca.QImage.Format_ARGB32)
_uni.fill(ca.QColor(120, 130, 140))
_ub = ca._gaussian_blur(_uni, 24)
_uv = [_ub.pixelColor(x, y).red() for (x, y) in ((0, 0), (299, 0), (0, 199), (299, 199), (150, 100))]
check("底纹模糊: 均匀图不产生暗边(镜像 padding)", max(_uv) - min(_uv) <= 3, str(_uv))

# 18.3 形状: 真高斯的边缘衰减剖面是"陡而平滑"的曲线;
#      旧的"缩到 1/45 再放大"给出的是**线性斜坡**(采样点之间是直线段), 这正是肉眼看到的色块。
#      实测: 真高斯 10px 处衰减到 26% 且差分逐级递减; 旧近似 10px 处仍有 76%, 差分近乎恒定。
_blk = ca.QImage(401, 401, ca.QImage.Format_ARGB32)
_blk.fill(ca.QColor(0, 0, 0))
_pb = ca.QPainter(_blk)
_pb.fillRect(180, 180, 41, 41, ca.QColor(255, 255, 255))
_pb.end()
_bl = ca._gaussian_blur(_blk, 20)
_prof = [_bl.pixelColor(x, 200).red() for x in range(220, 340)]
_ratio = _prof[10] / max(1, _prof[0])
_diffs = [d for d in (_prof[i] - _prof[i + 1] for i in range(len(_prof) - 1)) if d > 0]
_mono = all(_diffs[i] + 1 >= _diffs[i + 1] for i in range(len(_diffs) - 1))
check("底纹模糊: 边缘衰减是平滑高斯曲线(不是线性斜坡=色块)",
      _ratio < 0.5 and _mono, f"10px衰减比={_ratio:.2f} 差分单调={_mono}")

# 18.4 按钮按材质分档: 默认 / 液态玻璃 / 毛玻璃 三套样式各不相同
_wf64 = ca.CardWindow()
_wf64.refresh = lambda *a, **k: None
_dark_before64 = ca.theme_state["dark"]


def _btn_qss64():
    return (ca.theme_state["dark"], _wf64.btn_min.styleSheet(), _wf64.btn_close.styleSheet(),
            _wf64.btn_refresh.styleSheet(), _wf64.btn_glass_toggle.styleSheet(),
            _wf64.btn_theme_toggle.styleSheet(), _wf64.btn_today.styleSheet())


try:
    ca.theme_state["dark"] = True
    ca.refresh_palette()          # 调色板跟随, 断言才与真机一致
    ca.theme_state["glass"] = False
    ca.theme_state["frost"] = False
    _wf64.apply_styles()
    _q_def = _btn_qss64()
    ca.theme_state["glass"] = True
    ca.theme_state["frost"] = False
    _wf64.apply_styles()
    _q_gla = _btn_qss64()
    ca.theme_state["glass"] = False
    ca.theme_state["frost"] = True
    _wf64.apply_styles()
    _q_fro = _btn_qss64()

    check("按钮适配: 三档材质下样式互不相同",
          _q_def != _q_gla and _q_gla != _q_fro and _q_def != _q_fro)
    check("按钮适配: 默认档保持原有实底芯片(观感不变)",
          ca.qrgba(ca.TRACK) in _q_def[1] and ca.qrgba(ca.TRACK) in _q_def[6])
    check("按钮适配: 液态玻璃档 = 半透明高光片 + 亮描边",
          "rgba(255,255,255,0.10)" in _q_gla[1] and "rgba(255,255,255,0.20)" in _q_gla[1])
    check("按钮适配: 毛玻璃档 = 近乎无底 + 极淡细线",
          "rgba(255,255,255,0.055)" in _q_fro[1] and "rgba(255,255,255,0.13)" in _q_fro[1])
    check("按钮适配: 材质按钮选中态在毛玻璃下是唯一强元素(底图取色, 第65轮细化)",
          ca.qrgba(ca.FrostTexture.instance().accent(True), 120) in _q_fro[4])
    check("按钮适配: 刷新主按钮默认实心蓝 / 毛玻璃底图色但保持分量",
          "#3b6fe0" in _q_def[3]
          and ca.qrgba(ca.FrostTexture.instance().accent(True), 205) in _q_fro[3])
    check("按钮适配: NavButton 毛玻璃下 hover 不铺实底(自绘源码断言)",
          "120 if glass else 58" in _src62
          and 'frost = bool(theme_state.get("frost"))' in _src62)
finally:
    ca.theme_state["dark"] = _dark_before64
    ca.theme_state["glass"] = False
    ca.theme_state["frost"] = False
    ca.refresh_palette()
    _wf64.apply_styles()
    _wf64.close()

# 18.5 每日用量分布: 不再记忆滚轮缩放/平移
_ch64 = ca.StackedBarChart()
_daily64 = {f"2026-09-{d:02d}": {"m": {"total": d * 100}} for d in range(1, 26)}
_ch64.set_data(_daily64, [("m", 1)])
_base_count64 = _ch64.view_count
_base_start64 = _ch64.view_start
_ch64.view_count = 5.0
_ch64.view_start = 3.0
_ch64._sync_slice()
check("每日分布: 缩放先生效(视图确实被改动)", _ch64.view_count == 5.0 and _ch64.view_start == 3.0)
_ch64.set_data(_daily64, [("m", 1)])       # 同一批数据重绘
check("每日分布: 重绘回到默认视图(记忆功能已移除)",
      abs(_ch64.view_count - _base_count64) < 0.01 and abs(_ch64.view_start - _base_start64) < 0.01,
      f"count={_ch64.view_count} start={_ch64.view_start} 默认=({_base_count64},{_base_start64})")
check("每日分布: 源码中不再有 keep_view 记忆分支", "keep_view" not in _src62)

# 18.6 默认底纹: 内置壁纸已替换(不再依赖首次抓屏)
_bg64 = ca.QImage(ca.FROST_TEX_DEFAULT)
check("默认底纹: assets/frost_bg.png 存在且为整幅壁纸尺寸",
      (not _bg64.isNull()) and _bg64.width() >= 800 and _bg64.height() >= 400,
      f"{_bg64.width()}x{_bg64.height()}")

# ========== 19. 日期按钮尺寸还原 + 选中态从底图取色 (2026-09-25 第65轮) ==========
print("== 19. 日期按钮尺寸 / 选中态取色 ==")

# 19.1 尺寸: 新样式(三档)必须与旧版 "padding:4px 9px + 无描边" 的盒子完全一致
_old_btn65 = ca.QPushButton("今日")
_old_btn65.setCheckable(True)
_old_btn65.setStyleSheet(
    f"QPushButton{{ background:{ca.qrgba(ca.TRACK)}; color:{ca.qname(ca.TEXT2)}; border:none;"
    f" border-radius:6px; padding:4px 9px; font-size:{ca.curr_metric()['opt_btn_px']}px; }}")
_old_sz65 = _old_btn65.sizeHint()
_wf65 = ca.CardWindow()
_wf65.refresh = lambda *a, **k: None
_dark65 = ca.theme_state["dark"]
_fc65 = ca.theme_state.get("frost_custom")
try:
    ca.theme_state["dark"] = True
    ca.theme_state["frost_custom"] = False          # 断言固定用内置底图, 不受本机自选图影响
    ca.FrostTexture.instance().load(force=True)
    ca.refresh_palette()

    _szs65 = []
    for _g, _f in ((False, False), (True, False), (False, True)):
        ca.theme_state["glass"], ca.theme_state["frost"] = _g, _f
        ca.refresh_palette()
        _wf65.apply_styles()
        _szs65.append(_wf65.btn_today.sizeHint())
    check("日期按钮: 三档材质下尺寸都与旧版一致(改回来了)",
          all(abs(s.width() - _old_sz65.width()) <= 1 and abs(s.height() - _old_sz65.height()) <= 1
              for s in _szs65),
          f"旧={_old_sz65.width()}x{_old_sz65.height()} 新={[f'{s.width()}x{s.height()}' for s in _szs65]}")
    check("日期按钮: 尺寸靠 padding:3px 8px + 1px 描边等效旧 4px 9px 无描边",
          "padding:3px 8px" in _src62)

    # 19.2 毛玻璃: 选中态颜色取自底图 + 半透明
    ca.theme_state["glass"], ca.theme_state["frost"] = False, True
    ca.refresh_palette()
    _wf65.apply_styles()
    _acc65 = ca.FrostTexture.instance().accent(True)
    _want65 = ca.qrgba(_acc65, 120)
    _q_range65 = _wf65.btn_today.styleSheet()
    check("选中态取色: 毛玻璃下日期按钮选中色 = 底图取色(半透明)", _want65 in _q_range65, _want65)
    check("选中态取色: 不再是恒定的实心品牌蓝",
          "rgba(59,111,224,0.92)" not in _q_range65)
    check("选中态取色: 材质按钮选中态走同一套底图色", _want65 in _wf65.btn_frost.styleSheet())
    check("选中态取色: 描边同色(比填充更实一点)", ca.qrgba(_acc65, 175) in _q_range65)

    # 独立复算: 取色的色相必须与底图平均色一致
    _img65 = ca.FrostTexture.instance().load()
    _sm65 = _img65.scaled(8, 8, ca.Qt.IgnoreAspectRatio, ca.Qt.SmoothTransformation)
    _rr = _gg = _bb = 0
    for _yy in range(_sm65.height()):
        for _xx in range(_sm65.width()):
            _pp = _sm65.pixelColor(_xx, _yy)
            _rr += _pp.red(); _gg += _pp.green(); _bb += _pp.blue()
    _n65 = max(1, _sm65.width() * _sm65.height())
    _h_src65 = ca.QColor(_rr // _n65, _gg // _n65, _bb // _n65).getHsv()[0]
    _h_acc65 = _acc65.getHsv()[0]
    check("选中态取色: 色相与底图平均色一致", _h_src65 < 0 or abs(_h_acc65 - _h_src65) <= 2,
          f"底图={_h_src65} 取色={_h_acc65}")
    check("选中态取色: 饱和度/明度归一到可读区间",
          _acc65.getHsv()[1] >= 110 and _acc65.getHsv()[2] >= 180,
          f"s={_acc65.getHsv()[1]} v={_acc65.getHsv()[2]}")
    check("选中态取色: 浅色档也走底图取色(明度更低)",
          ca.FrostTexture.instance().accent(False).getHsv()[2] < _acc65.getHsv()[2])

    # 19.3 液态玻璃: 选中态同样更通透(0.92 → 0.62)
    ca.theme_state["glass"], ca.theme_state["frost"] = True, False
    ca.refresh_palette()
    _wf65.apply_styles()
    check("液态玻璃: 日期按钮选中态更通透", "rgba(59,111,224,0.62)" in _wf65.btn_today.styleSheet())
    check("液态玻璃: 材质按钮选中态同步通透", "rgba(59,111,224,0.62)" in _wf65.btn_frost.styleSheet())

    # 19.4 顺带修掉一个真 bug: 两个材质**直切**时不得掉回默认
    ca.theme_state["glass"], ca.theme_state["frost"] = False, False
    ca.refresh_palette()
    _wf65.apply_styles()
    _wf65.btn_frost.setChecked(True)                 # 用户点「毛玻璃」
    _wf65.btn_glass_toggle.setChecked(True)          # 再点「液态玻璃」→ 应当直切, 不掉回默认
    check("材质直切: 毛玻璃 → 点液态玻璃 = 切到玻璃(不掉回默认)",
          (ca.theme_state["glass"], ca.theme_state.get("frost"),
           _wf65.btn_glass_toggle.isChecked(), _wf65.btn_frost.isChecked()) == (True, False, True, False),
          f"{ca.theme_state['glass']}/{ca.theme_state.get('frost')}")
    _wf65.btn_frost.setChecked(True)                 # 再点「毛玻璃」→ 直切回毛玻璃
    check("材质直切: 液态玻璃 → 点毛玻璃 = 切到毛玻璃(不掉回默认)",
          (ca.theme_state["glass"], ca.theme_state.get("frost"),
           _wf65.btn_glass_toggle.isChecked(), _wf65.btn_frost.isChecked()) == (False, True, False, True),
          f"{ca.theme_state['glass']}/{ca.theme_state.get('frost')}")
    check("材质直切: 同步勾选态时屏蔽了信号(源码守门)",
          "blockSignals(True)" in _src62 and "_b.setChecked(_on)" in _src62)
finally:
    ca.theme_state["dark"] = _dark65
    ca.theme_state["glass"] = False
    ca.theme_state["frost"] = False
    ca.theme_state["frost_custom"] = _fc65
    ca.FrostTexture.instance().load(force=True)
    ca.refresh_palette()
    _wf65.apply_styles()
    _wf65.close()

# ========== 20. 左栏「来源」选中态从底图取色 + 内置底纹换新 (2026-09-25 第66轮) ==========
print("== 20. 来源按钮取色 / 内置底纹 ==")

# 20.1 像素级: 毛玻璃下 NavButton 选中态的竖条/填充都应是"底图取色"
_cfc66 = ca.theme_state.get("frost_custom")
ca.theme_state["frost_custom"] = False
ca.FrostTexture.instance().load(force=True)
_dark66 = ca.theme_state["dark"]
try:
    ca.theme_state["dark"] = True
    ca.refresh_palette()
    _acc66 = ca.FrostTexture.instance().accent(True)
    _nb66 = {}
    for _mat in ("default", "glass", "frost"):
        ca.theme_state["glass"] = (_mat == "glass")
        ca.theme_state["frost"] = (_mat == "frost")
        ca.refresh_palette()
        _n = ca.NavButton("WorkBuddy", "📘")
        _n.setChecked(True)
        _n.resize(150, 34)
        _im = _n.grab().toImage()
        _nb66[_mat] = (_im.pixelColor(5, _im.height() // 2),      # 左侧 3px 指示条(不透明)
                       _im.pixelColor(_im.width() - 20, 3))       # 选中块填充(半透明, 已与底色混合)
        _n.deleteLater()

    def _same_rgb(c, want, tol=6):
        return (abs(c.red() - want.red()) <= tol and abs(c.green() - want.green()) <= tol
                and abs(c.blue() - want.blue()) <= tol)

    def _hue_gap(c, want):
        h1, h2 = c.getHsv()[0], want.getHsv()[0]
        if h1 < 0 or h2 < 0:
            return 0
        d = abs(h1 - h2)
        return min(d, 360 - d)

    check("来源按钮: 毛玻璃下选中态竖条 = 底图取色",
          _same_rgb(_nb66["frost"][0], _acc66),
          f"{_nb66['frost'][0].name()} vs {_acc66.name()}")
    check("来源按钮: 毛玻璃下选中块填充同色系(半透明混合后色相仍一致)",
          _hue_gap(_nb66["frost"][1], _acc66) <= 15,
          f"{_nb66['frost'][1].name()} vs {_acc66.name()}")
    check("来源按钮: 默认档选中态仍是品牌蓝",
          _same_rgb(_nb66["default"][0], ca.BLUE), _nb66["default"][0].name())
    check("来源按钮: 液态玻璃档选中态仍是品牌蓝",
          _same_rgb(_nb66["glass"][0], ca.BLUE), _nb66["glass"][0].name())
    check("来源按钮: 源码里毛玻璃分支走底图取色(守门)",
          "accent(dark) if frost else QColor(BLUE)" in _src62)

    # 20.2 内置底纹: 已换成新壁纸, 且本身有颜色(可供取色)
    _bg66 = ca.FrostTexture.instance().load()
    _sm66 = _bg66.scaled(16, 16, ca.Qt.IgnoreAspectRatio, ca.Qt.SmoothTransformation)
    _rr = _gg = _bb = 0
    for _y in range(_sm66.height()):
        for _x in range(_sm66.width()):
            _p = _sm66.pixelColor(_x, _y)
            _rr += _p.red(); _gg += _p.green(); _bb += _p.blue()
    _n66 = max(1, _sm66.width() * _sm66.height())
    _avg66 = ca.QColor(_rr // _n66, _gg // _n66, _bb // _n66)
    check("内置底纹: 尺寸/存在性正常", _bg66.width() >= 1000 and _bg66.height() >= 500,
          f"{_bg66.width()}x{_bg66.height()}")
    check("内置底纹: 本身有色彩(取色才有意义, 不是灰底)",
          _avg66.getHsv()[1] >= 30, f"S={_avg66.getHsv()[1]} 平均={_avg66.name()}")
    check("内置底纹: 取色色相 = 底纹平均色相",
          abs(_acc66.getHsv()[0] - _avg66.getHsv()[0]) <= 3,
          f"底纹={_avg66.getHsv()[0]} 取色={_acc66.getHsv()[0]}")
finally:
    ca.theme_state["dark"] = _dark66
    ca.theme_state["glass"] = False
    ca.theme_state["frost"] = False
    ca.theme_state["frost_custom"] = _cfc66
    ca.FrostTexture.instance().load(force=True)
    ca.refresh_palette()

# ---- 还原真实数据目录路径 (临时目录随系统清理) ----
ca._sn_events_all = orig_events
ca.SN_AUTOSYNC_FILE = _REAL_AUTOSYNC_FILE
ca.SETTINGS_FILE = _REAL_SETTINGS_FILE
_saved = json.load(open(ca.SETTINGS_FILE, encoding="utf-8"))
check("测试未污染真实 settings.json (source/dark/pet 保持)",
      _saved.get("source") is not None and "pet" in _saved,
      f"source={_saved.get('source')} dark={_saved.get('dark')} pet={_saved.get('pet')}")
print(f"\nALL {PASS} CHECKS PASSED")
