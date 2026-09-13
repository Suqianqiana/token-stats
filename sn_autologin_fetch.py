# -*- coding: utf-8 -*-
"""
商汤积分「真自动」抓取 (方案A · Playwright 持久化登录态)

加载 sn_login_state.json → 无头 Edge → 打开 console 页 →
监听页面自动发出的 /lite/console/v1/metered/models 响应, 捕获真实积分数据。
(不手动拼 Authorization, 让页面 JS 自己带 token, 零逆向)

可独立运行, 也可被 card_app 的 sn_autologin_fetch() 调用。
"""
import os, json, sys
from playwright.sync_api import sync_playwright

EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
PLUGIN_DATA = os.path.expanduser("~/.workbuddy/plugins/data/token-usage-stats")
STATE_FILE = os.path.join(PLUGIN_DATA, "sn_login_state.json")
CONSOLE_URL = "https://platform.sensenova.cn/console"


def sn_autologin_fetch(headless=True, timeout_ms=25000):
    """用持久登录态抓取积分数据, 返回 (dict_json, error)"""
    if not os.path.exists(STATE_FILE):
        return None, "未找到登录态 sn_login_state.json, 请先运行 sn_login.py 手动登录一次"
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path=EDGE, headless=headless)
            ctx = browser.new_context(storage_state=STATE_FILE)
            page = ctx.new_page()

            captured = {}

            def on_response(resp):
                u = resp.url
                if "/lite/console/v1/metered/models" in u and resp.status == 200:
                    try:
                        d = json.loads(resp.text())
                    except Exception:
                        return
                    if isinstance(d, dict) and (d.get("models") or d.get("data") or d.get("pools")):
                        captured["data"] = d
            
            page.on("response", on_response)
            page.goto(CONSOLE_URL, timeout=30000)
            page.wait_for_timeout(4000)
            browser.close()

            if captured.get("data"):
                return captured["data"], None
            return None, "未捕获到积分数据 — 登录态可能已过期, 请重新运行 sn_login.py"
    except Exception as e:
        return None, str(e)[:200]


if __name__ == "__main__":
    data, err = sn_autologin_fetch(headless=True)
    if err:
        print("[抓取失败]", err)
        sys.exit(1)
    print("[抓取成功] 积分数据:")
    print(json.dumps(data, ensure_ascii=False, indent=2)[:3000])