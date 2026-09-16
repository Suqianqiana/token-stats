# -*- coding: utf-8 -*-
"""商汤刷新链路 UI 状态诊断: 失败/超时/连点 场景下 刷新按钮 与 同步面板 的状态。

只读诊断 — 不写任何配置文件 (monkeypatch 全部入口)。
"""
import os, sys, time, tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import card_app as ca
from PySide6.QtWidgets import QApplication

# 数据目录隔离: 诊断会触发保存/清除/归档凭据, 一律走临时目录, 绝不碰真实配置
_TMP = tempfile.mkdtemp(prefix="tstats_diag_")
ca.SN_AUTOSYNC_FILE = os.path.join(_TMP, "sn_autosync.json")
ca.SN_CRED_LOG = os.path.join(_TMP, "sn_cred.log")
ca.SN_USE_PLAYWRIGHT = False     # 不真拉浏览器

app = QApplication.instance() or QApplication([])

print("=" * 66)
print("商汤刷新链路 UI 状态诊断")
print("=" * 66)


def pump(sec):
    """驱动事件循环 sec 秒"""
    t0 = time.time()
    while time.time() - t0 < sec:
        app.processEvents()
        time.sleep(0.02)


def snap(w, tag):
    p = w.sn_page.sync_panel
    print(f"    {tag:<26} btn_refresh={('ON ' if w.btn_refresh.isEnabled() else 'OFF')}"
          f"  scanning={int(w._scanning)}  pending={int(w._pending_refresh)}"
          f"  panel_mode={p._status_mode:<8} msg={p._status_msg[:34]}")
    return w.btn_refresh.isEnabled()


w = ca.CardWindowWindow() if False else ca.CardWindow()
w.source = "sn"
w._auto_refresh_timer.stop()
print("\n[场景 A] 刷新成功")
ca.load_sn_stats = lambda force=False: {"source": "sn", "pools": [], "synced": True,
                                        "sync_src": "auto", "sync_time": "08:20",
                                        "autosync_error": None,
                                        "window_start": time.time(), "window_end": time.time() + 1}
w.refresh(force=True)
snap(w, "刚发起")
pump(1.5)
ok_a = snap(w, "完成后")

print("\n[场景 B] 刷新失败 (商汤拉取失败, autosync_error 有值)")
ca.load_sn_stats = lambda force=False: {"source": "sn", "pools": [], "synced": False,
                                        "sync_src": None, "sync_time": None,
                                        "autosync_error": "未捕获到积分数据",
                                        "window_start": time.time(), "window_end": time.time() + 1}
w.refresh(force=True)
snap(w, "刚发起")
pump(1.5)
ok_b = snap(w, "完成后")

print("\n[场景 C] 刷新抛异常")
def _boom(force=False):
    raise RuntimeError("模拟底层崩溃")
ca.load_sn_stats = _boom
w.refresh(force=True)
pump(1.5)
ok_c = snap(w, "完成后")

print("\n[场景 D] 扫描进行中点刷新按钮 (force 是否被吞)")
ca.load_sn_stats = lambda force=False: (time.sleep(2.5) or
                                        {"source": "sn", "pools": [], "synced": True, "sync_src": "auto",
                                         "sync_time": "08:21", "autosync_error": None,
                                         "window_start": time.time(), "window_end": time.time() + 1})
w.refresh(force=True)          # 长扫描, 进行中
pump(0.3)
snap(w, "扫描进行中")
w.refresh(force=True)          # 用户此刻点击按钮
print("    用户点击 ⟳ (force=True) 被丢弃 -> _pending_refresh=True")
pump(0.3)
print("    看门狗定时器 active =", w._scan_watchdog.isActive(), " 间隔ms =", w._scan_watchdog.interval())
pump(3.0)
ok_d = snap(w, "首轮完成后")
pump(3.5)
snap(w, "pending 补刷新完成后")

print("\n[场景 E] 慢扫描 + 连点 10 次 (模拟用户不耐烦狂点)")
w.stats = None
ca.load_sn_stats = lambda force=False: (time.sleep(6.0) or
                                        {"source": "sn", "pools": [], "synced": True, "sync_src": "auto",
                                         "sync_time": "08:22", "autosync_error": None,
                                         "window_start": time.time(), "window_end": time.time() + 1})
w.refresh(force=True)
for _ in range(10):
    pump(0.1)
    w.refresh(force=True)
pump(0.5)
snap(w, "连点后 0.5s")
pump(8.0)
ok_e = snap(w, "全部结束后")
print("    看门狗还在跑吗:", w._scan_watchdog.isActive())

print("\n[场景 F] 同步面板『保存并同步』失败 -> 按钮是否恢复")
p = w.sn_page.sync_panel
_orig_http = ca._http_json
ca._http_json = lambda req: (0, None, "DNS 解析失败 (模拟)")
p.curl_edit.setPlainText("curl 'https://api.example.com/x' -H 'Authorization: Bearer t'")
p._on_save()
snap(w, "保存发起后")
pump(1.5)
print("    btn_save.enabled =", p.btn_save.isEnabled(), " btn_clear.enabled =", p.btn_clear.isEnabled(),
      " err =", p.err_lbl.text()[:40])
ok_f = p.btn_save.isEnabled() and p.btn_clear.isEnabled()

print("\n[场景 G] 保存成功路径 (走真实 sn_autosync_fetch 慢路径会耗 13s+)")
ca._http_json = lambda req: (200, {"pools": [{"pool_type": "default", "name": "通用积分池",
                                              "window_5h": {"remaining": 100},
                                              "window_7d": {"remaining": 200}}]}, None)
_slow = ca.sn_autosync_fetch
ca.sn_autosync_fetch = lambda force=False: time.sleep(13.0)   # 模拟慢路径 13s
if hasattr(ca, "sn_page"): pass
t0 = time.time()
p._on_save()
pump(1.0)
print("    1.0s 后 btn_save.enabled =", p.btn_save.isEnabled(), " (慢路径等待中, 按钮灰着)")
pump(14.0)
print("    总耗时 %.1fs 后 btn_save.enabled = %s  err=%s" % (time.time() - t0, p.btn_save.isEnabled(),
                                                            p.err_lbl.text()[:40]))
ok_g = p.btn_save.isEnabled()
ca.sn_autosync_fetch = _slow
ca._http_json = _orig_http

print("\n" + "=" * 66)
print("结论:  A成功=%s  B失败=%s  C异常=%s  D连点=%s  E狂点=%s  F保存失败=%s  G慢保存=%s"
      % (ok_a, ok_b, ok_c, ok_d, ok_e, ok_f, ok_g))
print("=" * 66)
