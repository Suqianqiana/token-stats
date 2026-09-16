# -*- coding: utf-8 -*-
"""商汤凭据获取链路 分阶段耗时诊断 (只读, 不改任何配置)。

用法:
    python tools/diag_sn_cred.py            # 快路径 + 结构体检
    python tools/diag_sn_cred.py --slow     # 额外跑一次 Playwright 慢路径 (会拉起 Edge)
"""
import os, sys, json, time, base64, datetime, tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# --- 禁止生成 .pyc: 火绒把 __pycache__/card_app.cpython-313.pyc 误判为
#     Trojan/Python.ShellLoader.am 并删除+结束进程(实测 12 次)。不写字节码 = 不触发。
import sys as _sys
_sys.dont_write_bytecode = True
import card_app as ca

# cURL 凭据/日志走临时目录 (诊断不该改写真实配置)
_TMP = tempfile.mkdtemp(prefix="tstats_diag_")
ca.SN_AUTOSYNC_FILE = os.path.join(_TMP, "sn_autosync.json")
ca.SN_CRED_LOG = os.path.join(_TMP, "sn_cred.log")
_REAL_AUTOSYNC_BAK = None
try:
    with open(os.path.join(ca.scanner.PLUGIN_DATA_DIR, "sn_autosync.json"), encoding="utf-8") as f:
        _REAL_AUTOSYNC_BAK = f.read()
except Exception:
    pass
if _REAL_AUTOSYNC_BAK:
    with open(ca.SN_AUTOSYNC_FILE, "w", encoding="utf-8") as f:
        f.write(_REAL_AUTOSYNC_BAK)


def jwt_exp(tok):
    try:
        p = tok.split(".")[1]
        p += "=" * (-len(p) % 4)
        d = json.loads(base64.urlsafe_b64decode(p))
        return d.get("exp"), d.get("iat")
    except Exception:
        return None, None


def stage(label, fn):
    t0 = time.perf_counter()
    try:
        r = fn()
        err = None
    except Exception as e:
        r, err = None, f"{type(e).__name__}: {str(e)[:90]}"
    dt = time.perf_counter() - t0
    print(f"  [{dt:6.2f}s] {label}" + (f"  <-- {err}" if err else ""))
    return r, dt, err


print("=" * 62)
print("商汤凭据链路诊断  now =", time.strftime("%Y-%m-%d %H:%M:%S"))
print("=" * 62)

print("\n-- 1. 凭据来源体检 --")
print("  SN_USE_PLAYWRIGHT      =", ca.SN_USE_PLAYWRIGHT)
print("  _sn_playwright_ready() =", ca._sn_playwright_ready())
print("  login_state 存在       =", os.path.exists(ca.SN_LOGIN_STATE))
print("  token 缓存存在         =", os.path.exists(ca.SN_TOKEN_FILE))
print("  cURL 配置存在          =", os.path.exists(ca.SN_AUTOSYNC_FILE))

tok = ca._sn_load_token()
print("  _sn_load_token()       =", "OK(len=%d)" % len(tok) if tok else "None")
if tok:
    exp, iat = jwt_exp(tok)
    now = time.time()
    if exp:
        print("  JWT iat/exp            =", datetime.datetime.fromtimestamp(iat).strftime("%H:%M:%S"),
              "/", datetime.datetime.fromtimestamp(exp).strftime("%H:%M:%S"))
        print("  剩余有效期             = %.0f 分钟 (总寿命 %.0f 分钟)" % ((exp - now) / 60, (exp - iat) / 60))

cfg = ca.load_sn_autosync()
if cfg:
    print("  cURL 配置 url          =", cfg.get("url"))
    npaths = len(cfg.get("paths") or {})
    print("  cURL 配置 paths 数     =", npaths)
else:
    print("  cURL 配置              = 无 (或无效)")

print("\n-- 2. 快路径: token 直连 pool-usage --")
if tok:
    r, dt, err = stage("_sn_direct_fetch(token)", lambda: ca._sn_direct_fetch(tok))
    if isinstance(r, tuple):
        data, e2 = r
        print("       -> data=%s  err=%s" % ("dict(pools=%d)" % len(data.get("pools", []))
                                            if isinstance(data, dict) else data, e2))
        if isinstance(data, dict):
            v = ca._sn_parse_pool_data(data)
            print("       -> 解析 values 键:", sorted(v.keys()) if v else None)
else:
    print("  (无 token, 跳过)")

print("\n-- 3. 完整入口 sn_playwright_fetch() --")
r, dt, err = stage("sn_playwright_fetch()", ca.sn_playwright_fetch)
if isinstance(r, tuple):
    vals, e2 = r
    print("       -> values=%s  err=%s" % (sorted(vals.keys()) if vals else None, e2))

print("\n-- 4. cURL 回退路径 --")
r, dt, err = stage("sn_autosync_fetch(force=True)", lambda: ca.sn_autosync_fetch(force=True))
print("       -> values=%s" % (sorted(r.keys()) if r else None))
print("       -> _autosync_mem.error =", ca._autosync_mem["error"])

if "--slow" in sys.argv:
    print("\n-- 5. Playwright 慢路径分阶段 --")
    r, dt, err = stage("_sn_playwright_login_and_fetch()", ca._sn_playwright_login_and_fetch)
    if isinstance(r, tuple):
        print("       -> data=%s token=%s err=%s" % (bool(r[0]), bool(r[1]), r[2]))

print("\n完成。")
