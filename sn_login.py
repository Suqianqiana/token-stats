# -*- coding: utf-8 -*-
"""
商汤积分「真自动」全自动登录 (方案A · Playwright 持久化登录态)

自动完成: 打开 console → 跳登录页 → 点「账号密码登录」→ 填账号密码 →
          点「登录」→ 检测积分数据加载 → 保存登录态。

账号密码读取自本机数据目录 sn_account.json (不进 git)。
若登录出现验证码, 脚本会提示你手动完成。
"""
import os, sys, json, time
from playwright.sync_api import sync_playwright

EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
PLUGIN_DATA = os.path.expanduser("~/.workbuddy/plugins/data/token-usage-stats")
STATE_FILE = os.path.join(PLUGIN_DATA, "sn_login_state.json")
DATA_FILE = os.path.join(PLUGIN_DATA, "sn_login_dump.json")
ACCOUNT_FILE = os.path.join(PLUGIN_DATA, "sn_account.json")
CONSOLE_URL = "https://platform.sensenova.cn/console"


def load_account():
    try:
        with open(ACCOUNT_FILE, "r", encoding="utf-8-sig") as f:
            d = json.load(f)
        return d.get("username", ""), d.get("password", "")
    except Exception as e:
        print("[错误] 读取账号配置失败:", str(e)[:120])
        return "", ""


def main():
    os.makedirs(PLUGIN_DATA, exist_ok=True)
    username, password = load_account()
    if not username or not password:
        print("[错误] 未找到账号配置 sn_account.json")
        return 1
    print("=" * 50)
    print("  商汤积分 全自动登录")
    print("=" * 50)
    print("正在自动登录账号: %s ..." % username)
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=EDGE, headless=False)
        ctx = browser.new_context()
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

        # 若跳转到登录页, 自动登录
        if "/login" in page.url:
            print("[自动登录] 检测到登录页, 开始自动登录 ...")
            try:
                page.get_by_text("账号密码登录", exact=True).click(timeout=8000)
                page.wait_for_timeout(1500)
                page.get_by_placeholder("请设置用户名").fill(username)
                page.get_by_placeholder("请输入密码").fill(password)
                page.wait_for_timeout(500)
                page.get_by_role("button", name="登录", exact=True).click(timeout=8000)
                print("[自动登录] 已点击登录按钮")
            except Exception as e:
                print("[自动登录] 自动填写失败, 请手动完成登录:", str(e)[:150])

        # 等待登录成功 (积分数据捕获 + URL 离开 login)
        deadline = time.time() + 600
        while time.time() < deadline:
            time.sleep(2)
            url_ok = "/login" not in page.url
            if captured.get("data") and url_ok:
                print("")
                print("[成功] 登录完成 + 积分数据加载!")
                ctx.storage_state(path=STATE_FILE)
                with open(DATA_FILE, "w", encoding="utf-8") as f:
                    json.dump(captured["data"], f, ensure_ascii=False, indent=2)
                print("[成功] 登录态已保存:", STATE_FILE)
                print("[成功] 积分数据样本:", DATA_FILE)
                browser.close()
                return 0

        print("")
        print("[提示] 10 分钟内未完成登录")
        print("若出现验证码/滑块, 请手动完成; 若页面已显示积分额度, 说明检测有遗漏请联系")
        browser.close()
        return 1


if __name__ == "__main__":
    sys.exit(main())
