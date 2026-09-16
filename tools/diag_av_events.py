# -*- coding: utf-8 -*-
"""Defender 检测/处理事件全量梳理: 时间、威胁名、被判定的对象, 以及是否命中我们的项目路径。"""
import re, subprocess, sys

Q = '*[System[(EventID=1116 or EventID=1117)]]'
r = subprocess.run(["wevtutil", "qe", "Microsoft-Windows-Windows Defender/Operational",
                    "/q:" + Q, "/c:60", "/rd:true", "/f:text"],
                   capture_output=True, text=True, errors="replace")
txt = r.stdout or ""

blocks = re.split(r"\r?\n(?=Event\[\d+\])", txt)
print("事件块数:", len(blocks))
KEY = ("token-stats", "card_app", "TokenStats", "launcher", "pythonw", "CODEBUDDY",
       "SAFE_DELETE", "msedge", "token_usage", "token-usage-stats")
for b in blocks:
    if not b.strip():
        continue
    date = re.search(r"Date:\s*(\S+)", b)
    eid = re.search(r"Event ID:\s*(\d+)", b)
    name = re.search(r"Name:\s*(\S+)", b)
    sev = re.search(r"Severity:\s*(\S+)", b)
    path = re.search(r"Path:\s*(.+)", b)
    hit = [k for k in KEY if k.lower() in b.lower()]
    print("-" * 66)
    print("  EID=%s  Date=%s" % (eid.group(1) if eid else "?", date.group(1) if date else "?"))
    print("  威胁=%s  等级=%s" % (name.group(1) if name else "?", sev.group(1) if sev else "?"))
    p = (path.group(1).strip() if path else "")
    print("  对象=%s" % (p[:150] if p else "(无 Path 字段)"))
    print("  命中我们的关键字: %s" % (", ".join(hit) if hit else "无"))
