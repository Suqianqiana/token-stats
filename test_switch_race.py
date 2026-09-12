# -*- coding: utf-8 -*-
"""offscreen 验证: 切页 race 防护 + 商汤积分自动同步 + 事件缓存."""
import os, sys, time, json

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import card_app as ca
from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])
PASS = 0

# ---- 备份用户真实自动同步配置 (测试过程会读写/清除这些文件, 结束后恢复) ----
_user_autosync = ca.load_sn_autosync()


def check(name, cond, detail=""):
    global PASS
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"  ({detail})" if detail else ""))
    assert cond, name
    PASS += 1


# ========== 1. 切页 race 防护 ==========
print("== 1. 切页跨源渲染竞争 ==")
w = ca.CardWindow()
w.refresh = lambda: None          # 关自动刷新, 隔离变量

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
w.render()
rows_before = w.model_lay.count()
check("初始 WB 行数>1", rows_before > 2, f"rows={rows_before}")

w._switch_source(w.src_sn)        # 切商汤(缓存渲染)
sn_hidden = w.sn_page.testAttribute(ca.Qt.WA_WState_Hidden) is False
check("商汤页显示", sn_hidden)

w._switch_source(w.src_wb)        # 切回 WB (load_initial 读真实磁盘缓存)
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
check("race: WB 页可见 / SN 页隐藏",
      not w.content_old.testAttribute(ca.Qt.WA_WState_Hidden)
      and w.sn_page.testAttribute(ca.Qt.WA_WState_Hidden))

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
ca.sn_autosync_fetch = lambda force=False: ca._autosync_mem["values"]

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
CURL_BASH = ("curl 'https://api.example.com/console/points?x=1' \\\n"
             "  -H 'Cookie: SESSION=abc123' \\\n"
             "  -H 'User-Agent: Mozilla/5.0' \\\n"
             "  --compressed")
CURL_CMD = ('curl "https://api.example.com/console/points?x=1" ^\n'
            '  -H "Cookie: SESSION=abc123" ^\n'
            '  -H "Content-Type: application/json" ^\n'
            '  --data-raw "{\\"query\\":1}"')
r1 = ca.parse_curl(CURL_BASH)
r2 = ca.parse_curl(CURL_CMD)
check("bash cURL 解析", r1 and r1["url"] == "https://api.example.com/console/points?x=1"
      and r1["headers"].get("Cookie") == "SESSION=abc123"
      and r1["method"] == "GET", str(r1)[:100])
check("cmd cURL 解析", r2 and r2["url"].endswith("/points?x=1")
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
    "v": 1, "url": "https://api.example.com/x", "method": "GET",
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
check("非商汤结构 → 友好报错", "识别失败" in panel.err_lbl.text(),
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
ca.save_sn_autosync({"v": 1, "url": "https://api.example.com/x", "method": "GET",
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
w2.refresh = lambda: None
w2._sn_cache = {"source": "sn", "synced": True, "sync_time": "01:10",
                "sync_src": "auto", "autosync_error": None,
                "window_start": time.time() - 3600, "window_end": time.time() + 3600,
                "pools": RENDER_POOLS}
w2._switch_source(w2.src_sn)
lay = w2.sn_page.cards_lay
check("商汤页卡片数=3 (单列)", lay.count() == 3, f"count={lay.count()}")
check("内嵌同步面板存在", w2.sn_page.sync_panel is not None)
check("面板状态行=自动同步", "自动同步" in w2.sn_page.sync_panel.status_lbl.text(),
      w2.sn_page.sync_panel.status_lbl.text())
w2.layout().activate()
h_sn = w2.height()
check("SN 窗口高度在合理区间", 500 <= h_sn <= 1000, f"h={h_sn}")
# 顶部定位统一: WB/商汤页 place_right 后 y 一致 (基准高度 880, 不随页高漂移)
w2.resize(664, 880)
w2.place_right()
y_wb = w2.y()
w2._switch_source(w2.src_sn)
w2.place_right()
check("切页后窗口顶部位置统一", w2.y() == y_wb, f"y_wb={y_wb} y_sn={w2.y()}")

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

# ========== 8. 桌宠形态 (DeepSeek 娘帧动画, 双素材版本) ==========
print("== 8. 桌宠形态 ==")
_user_theme = dict(ca.theme_state)
# v1 经典素材: 6 组 (idle7/sleep2/drag6/click5/other12/special9)
fr1 = ca.load_pet_frames("v1")
check("v1 素材加载 (6 组)", fr1 is not None and set(fr1) == set(ca.PET_ANIMS),
      f"{None if fr1 is None else {k: len(v) for k, v in fr1.items()}}")
check("v1 帧数符合预期 (idle7/sleep2/drag6/click5/other12/special9)",
      fr1 and [len(fr1[a]) for a in ca.PET_ANIMS] == [7, 2, 6, 5, 12, 9],
      str([len(fr1[a]) for a in ca.PET_ANIMS]) if fr1 else "-")
# v2 新版高清素材: 5 组 (idle4/sleep2/drag3/click2/special2, 无 other)
fr2 = ca.load_pet_frames("v2")
exp2 = {"idle": 4, "sleep": 2, "drag": 3, "click": 2, "special": 2}
check("v2 素材加载 (5 组, 无 other)", fr2 is not None and set(fr2) == set(exp2),
      f"{None if fr2 is None else {k: len(v) for k, v in fr2.items()}}")
check("v2 帧数符合预期 (idle4/sleep2/drag3/click2/special2)",
      fr2 and all(len(fr2[k]) == v for k, v in exp2.items()),
      str({k: len(fr2[k]) for k in exp2}) if fr2 else "-")
# 待机序列生成器: 两种帧数都不越界且静止为主
for n in (4, 7, 1):
    s = ca._pet_idle_seq(n)
    check(f"待机序列 n={n} 帧号不越界且静止为主",
          s and all(0 <= f < n for f in s) and sum(1 for f in s if f != 0) <= len(s) * 0.2,
          f"len={len(s)} nonstatic={sum(1 for f in s if f != 0)}")
ca.theme_state["pet_theme"] = "v1"      # 本节先测 v1, 后面再切 v2
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
ball._idle_t = time.time()
ball._next_other = time.time() - 1
ball._pet_state("idle"); ball._pet_tick()
check("v1 小剧场触发", ball._state == "other" and len(ball._seq) == 3)
ball._pet_special()
check("摸摸头 (特殊状态)", ball._state == "special" and len(ball._seq) == 3)
ball._pet_tick(); ball._pet_tick(); ball._pet_tick(); ball._pet_tick()
check("一次性动作播完回待机", ball._state == "idle")
# 切到 v2 新素材: 无 other 组也不崩, 小剧场直接跳过
ball.set_pet_theme("v2")
check("切换 v2 素材", ball.pet_theme == "v2" and {k: len(v) for k, v in ball.pet_frames.items()} == {k: len(v) for k, v in fr2.items()})
ball._next_other = time.time() - 1
ball._pet_state("idle"); ball._pet_tick()
check("v2 无 other 组 -> 跳过小剧场不崩", ball._state == "idle")
ball._pet_click()
check("v2 单击互动", ball._state == "click" and len(ball._seq) == 3)
ball._pet_special()
check("v2 摸摸头", ball._state == "special" and len(ball._seq) == 3)
ball._pet_tick(); ball._pet_tick(); ball._pet_tick(); ball._pet_tick()
check("v2 动作播完回待机", ball._state == "idle")
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
check("待机实际展示以静止为主 (取帧跟随 _seq)", len(shown) == 90 and nonstatic <= 12,
      f"nonstatic={nonstatic}/90")
ball.set_pet(False)
check("切回悬浮球形态", ball.pet is False and ball.width() == 54)
ca.theme_state.clear(); ca.theme_state.update(_user_theme)
ca.save_settings()

ca.clear_sn_autosync()

# ---- 恢复用户真实自动同步配置 (测试前备份的) ----
if _user_autosync:
    ca.save_sn_autosync(_user_autosync)

ca._sn_events_all = orig_events
print(f"\nALL {PASS} CHECKS PASSED")
