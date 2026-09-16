# -*- coding: utf-8 -*-
"""观察 card_app.py 实例谱系随时间的变化 (定位"启动即双实例"的来源)。"""
import subprocess, sys, time, os

PS = ("Get-CimInstance Win32_Process -Filter \"Name='pythonw.exe'\" | "
      "Where-Object { $_.CommandLine -like '*card_app.py*' } | "
      "ForEach-Object { \"$($_.ProcessId)|$($_.ParentProcessId)|$($_.CreationDate.ToString('HH:mm:ss.fff'))|$($_.ExecutablePath)\" }")


def procs():
    r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", PS],
                       capture_output=True, text=True, errors="replace")
    out = []
    for line in r.stdout.splitlines():
        parts = [x.strip() for x in line.strip().split("|")]
        if len(parts) == 4 and parts[0].isdigit():
            out.append((int(parts[0]), int(parts[1]), parts[2], parts[3]))
    return out


def kill_all():
    for pid, _, _, _ in procs():
        subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True)


if __name__ == "__main__":
    kill_all()
    time.sleep(1.5)
    print("清理后剩余:", procs())
    D = 0x8 | 0x200 | 0x8000000
    py = r"C:\Users\a3564\.workbuddy\binaries\python\envs\pyside6\Scripts\pythonw.exe"
    sc = r"C:\Users\a3564\WorkBuddy\2026-08-25-04-20-35\token-stats\card_app.py"
    p = subprocess.Popen([py, sc], cwd=os.path.dirname(sc), creationflags=D,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print("本次启动 pid =", p.pid)
    for i in range(8):
        time.sleep(1.0)
        got = procs()
        print(f"  t={i+1:2d}s  进程数={len(got)}")
        for g in got:
            print(f"       pid={g[0]} ppid={g[1]} t={g[2]} exe={g[3]}")
