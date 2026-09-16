# -*- coding: utf-8 -*-
"""补充取证: ASR / 受控文件夹访问拦截记录 + 我们进程当前存活情况 + 威胁全文。"""
import re, subprocess, json, os, hashlib


def run(cmd, timeout=90):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, errors="replace", timeout=timeout)
        return (r.stdout or "") + (("\n[stderr]" + r.stderr) if r.stderr.strip() else "")
    except Exception as e:
        return "[失败] %s: %s" % (type(e).__name__, e)


def ps(s, timeout=120):
    return run(["powershell", "-NoProfile", "-NonInteractive", "-Command", s], timeout)


print("== A. 09-14 那条 ClickFix 事件全文 (关键: 被点名的到底是什么) ==")
Q = '*[System[(EventID=1116 or EventID=1117)]]'
t = run(["wevtutil", "qe", "Microsoft-Windows-Windows Defender/Operational",
         "/q:" + Q, "/c:4", "/rd:true", "/f:text"])
t = t.replace("\x00", "")
for line in t.splitlines():
    if any(k in line for k in ("Event ID", "Name:", "ID:", "Severity", "Category", "Path:",
                               "Detection Origin", "Detection Type", "User:", "Process Name",
                               "Action:", "Date:")):
        print("   " + line.strip()[:200])

print("\n== B. ASR / 受控文件夹访问 拦截记录 (1121/1122/1123/1124/1125/1126) ==")
Q2 = '*[System[(EventID=1121 or EventID=1122 or EventID=1123 or EventID=1124 or EventID=1125 or EventID=1126)]]'
o = run(["wevtutil", "qe", "Microsoft-Windows-Windows Defender/Operational",
         "/q:" + Q2, "/c:20", "/rd:true", "/f:text"])
print(o.strip()[:1200] if o.strip() else "   (无 ASR/CFA 拦截记录)")

print("\n== C. Defender 的 PUA / 云保护 / 受控文件夹设置 ==")
print(ps("$ErrorActionPreference='SilentlyContinue';$p=Get-MpPreference;"
         "'PUAProtection=' + $p.PUAProtection;"
         "'CloudBlockLevel=' + $p.CloudBlockLevel;"
         "'EnableControlledFolderAccess=' + $p.EnableControlledFolderAccess;"
         "'MAPSReporting=' + $p.MAPSReporting;"
         "'DisableRealtimeMonitoring=' + $p.DisableRealtimeMonitoring").strip())

print("\n== D. 我们的关键文件是否还在 + 指纹 ==")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for rel in ("TokenStats.exe", "card_app.py", "launcher.py"):
    p = os.path.join(ROOT, rel)
    try:
        st = os.stat(p)
        h = hashlib.sha256(open(p, "rb").read()).hexdigest()[:16]
        print("   OK   %-16s %9d B  sha256=%s…" % (rel, st.st_size, h))
    except OSError as e:
        print("   缺失 %-16s  %s" % (rel, e))

print("\n== E. 我们自己的进程现在还在吗 ==")
PSP = ("Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*card_app.py*' } | "
       "ForEach-Object { \"$($_.ProcessId)|$($_.ParentProcessId)|$($_.ExecutablePath)\" }")
out = ps(PSP).strip()
print("   " + (out.replace("\n", "\n   ") if out else "(没有 card_app.py 进程在跑)"))

print("\n== F. 桌面/项目目录里 Defender 的隔离痕迹 ==")
for d in (r"C:\ProgramData\Microsoft\Windows Defender\Quarantine",
          os.path.join(os.path.expanduser("~"), "AppData", "Local", "Microsoft", "Windows",
                       "INetCache", "IE")):
    print("   %s -> %s" % (d, "存在" if os.path.exists(d) else "不存在"))
