# -*- coding: utf-8 -*-
"""杀毒软件取证: 看是谁在拦我们的程序、拦了什么、有没有留检测记录。

只读查询, 不做任何清除/修改。
"""
import json, os, subprocess, sys


def run(cmd, timeout=60):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, errors="replace", timeout=timeout)
        return (r.stdout or "") + (("\n[stderr] " + r.stderr) if r.stderr.strip() else "")
    except Exception as e:
        return f"[执行失败] {type(e).__name__}: {e}"


def ps(script, timeout=90):
    return run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script], timeout)


print("=" * 70)
print("杀毒软件取证")
print("=" * 70)

print("\n-- 1. 已注册的杀毒产品 (SecurityCenter2) --")
out = run(["wmic", "/namespace:\\\\root\\securitycenter2", "path", "antivirusproduct",
           "get", "displayName,productState,pathToSignedProductExe", "/format:list"])
print(out.strip() or "(无输出)")

print("\n-- 2. Defender 运行状态 --")
print(ps("Get-MpComputerStatus | Select-Object AMServiceEnabled,AntivirusEnabled,"
         "RealTimeProtectionEnabled,AntivirusSignatureLastUpdated | Format-List").strip() or "(无输出)")

print("\n-- 3. Defender 检测历史 (Get-MpThreatDetection, 最近 20) --")
js = ps("$ErrorActionPreference='SilentlyContinue';"
        "Get-MpThreatDetection | Sort-Object InitialDetectionTime -Descending | "
        "Select-Object -First 20 InitialDetectionTime,ThreatID,ThreatStatusID,Resources,ActionSuccess | "
        "ConvertTo-Json -Depth 4")
js = js.strip()
try:
    det = json.loads(js)
    if isinstance(det, dict):
        det = [det]
    for d in det:
        res = d.get("Resources")
        if isinstance(res, list):
            res = "; ".join(str(x) for x in res)[:220]
        print("  %s  ThreatID=%s  ActionOK=%s  %s"
              % (d.get("InitialDetectionTime"), d.get("ThreatID"), d.get("ActionSuccess"), res))
except Exception:
    print("(解析失败/无记录)", js[:600])

print("\n-- 4. Defender 威胁清单 (Get-MpThreat) --")
print(ps("$ErrorActionPreference='SilentlyContinue';"
         "Get-MpThreat | Select-Object ThreatName,SeverityID,ThreatID,Resources | ConvertTo-Json -Depth 4"
         ).strip()[:1500] or "(无记录)")

print("\n-- 5. Defender 排除项 --")
print(ps("$ErrorActionPreference='SilentlyContinue';"
         "(Get-MpPreference).ExclusionPath; '--- 进程排除 ---'; (Get-MpPreference).ExclusionProcess"
         ).strip() or "(无排除项)")

print("\n-- 6. Defender 操作日志 (EventID 1116 检测 / 1117 处理, 最近 15 条) --")
q = '*[System[(EventID=1116 or EventID=1117)]]'
print(run(["wevtutil", "qe", "Microsoft-Windows-Windows Defender/Operational",
           "/q:" + q, "/c:15", "/rd:true", "/f:text"], timeout=90).strip()[:3000] or "(无输出)")

print("\n-- 7. 隔离区目录 --")
qdir = r"C:\ProgramData\Microsoft\Windows Defender\Quarantine"
try:
    for root, dirs, files in os.walk(qdir):
        for f in files[:30]:
            p = os.path.join(root, f)
            try:
                print("  %8d  %s  %s" % (os.path.getsize(p), __import__("time").strftime(
                    "%Y-%m-%d %H:%M", __import__("time").localtime(os.path.getmtime(p))), p))
            except OSError:
                pass
        break
except Exception as e:
    print("  (无法读取:", e, ")")

print("\n-- 8. 我们自己的进程现在还在吗 --")
PS = ("Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*card_app.py*' "
      "-or $_.CommandLine -like '*TokenStats*' -or $_.CommandLine -like '*launcher.py*' } | "
      "ForEach-Object { \"$($_.ProcessId)|$($_.Name)|$($_.ExecutablePath)\" }")
print(ps(PS).strip() or "(当前没有我们的进程在跑 —— 可能已被结束)")

print("\n-- 9. 应用控制/勒索防护等可能拦程序的功能 --")
print(ps("$ErrorActionPreference='SilentlyContinue';"
         "$p=Get-MpPreference; "
         "'EnableControlledFolderAccess=' + $p.EnableControlledFolderAccess; "
         "'PUAProtection=' + $p.PUAProtection; "
         "'CloudBlockLevel=' + $p.CloudBlockLevel; "
         "'AttackSurfaceReductionRules_Ids=' + ($p.AttackSurfaceReductionRules_Ids -join ','); "
         "'ASR_Actions=' + ($p.AttackSurfaceReductionRules_Actions -join ',')").strip() or "(无输出)")

print("\n完成。")
