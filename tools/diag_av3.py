# -*- coding: utf-8 -*-
"""确认: ①是哪款杀软在删我们的 pyc ②pycache 现状 ③桌宠实例是否还活着。"""
import os, subprocess, time, glob

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def run(cmd, t=60):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, errors="replace", timeout=t)
        return (r.stdout or "") + (r.stderr or "")
    except Exception as e:
        return "[失败] %s" % e


print("== 1. 已安装的安全软件 (注册表卸载项里找) ==")
KEYS = [r"HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
        r"HKLM\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"]
KW = ("火绒", "huorong", "360", "腾讯", "qqpcmgr", "管家", "qihoo", "kaspersky", "卡巴",
      "avast", "avg", "nod32", "eset", "bitdefender", "mcafee", "norton", "antivirus", "安全")
found = set()
for k in KEYS:
    out = run(["reg", "query", k, "/s", "/v", "DisplayName"])
    for line in out.splitlines():
        if "DisplayName" in line and "REG_SZ" in line:
            name = line.split("REG_SZ", 1)[1].strip()
            if any(w.lower() in name.lower() for w in KW):
                found.add(name)
for n in sorted(found):
    print("   -", n)

print("\n== 2. 可能的安全软件安装目录 ==")
for base in (r"C:\Program Files", r"C:\Program Files (x86)"):
    try:
        for d in sorted(os.listdir(base)):
            low = d.lower()
            if any(w in low for w in ("huorong", "火绒", "360", "tencent", "qqpcmgr", "qihoo",
                                      "kaspersky", "avast", "eset", "bitdefender", "mcafee",
                                      "norton", "windows defender", "antivirus", "安全")):
                print("   -", os.path.join(base, d))
    except OSError:
        pass

print("\n== 3. 相关进程 ==")
out = run(["wmic", "process", "get", "ProcessId,Name,ExecutablePath", "/format:csv"])
for line in out.splitlines():
    low = line.lower()
    if any(w in low for w in ("huorong", "hips", "usysdiag", "360", "qqpcmgr", "qihoo",
                              "msmpeng", "kav", "avast", "eset", "bdagent")):
        print("   ", line.strip()[:150])

print("\n== 4. 项目 __pycache__ 现状 ==")
for d in (os.path.join(ROOT, "__pycache__"), os.path.join(ROOT, "tools", "__pycache__")):
    print("   ", d, "存在" if os.path.isdir(d) else "不存在")
    if os.path.isdir(d):
        for f in sorted(os.listdir(d)):
            p = os.path.join(d, f)
            try:
                st = os.stat(p)
                print("      %-40s %8d B  %s" % (f, st.st_size,
                      time.strftime("%m-%d %H:%M:%S", time.localtime(st.st_mtime))))
            except OSError:
                pass

print("\n== 5. 桌宠实例是否还活着 ==")
out = run(["wmic", "process", "get", "ProcessId,ParentProcessId,ExecutablePath,CommandLine",
           "/format:list"])
cur, hits = {}, 0
for line in out.splitlines() + [""]:
    line = line.replace("\r", "")
    if not line.strip():
        if cur:
            if "card_app.py" in (cur.get("CommandLine") or ""):
                hits += 1
                print("   pid=%s ppid=%s" % (cur.get("ProcessId"), cur.get("ParentProcessId")))
            cur = {}
        continue
    if "=" in line:
        k, _, v = line.partition("=")
        cur[k.strip()] = v.strip()
print("   存活 card_app 进程数:", hits)
try:
    print("   ball.pid =", open(os.path.join(
        os.path.expanduser("~"), ".workbuddy", "plugins", "data", "token-usage-stats",
        "ball.pid")).read().strip())
except OSError:
    print("   ball.pid 读不到")
