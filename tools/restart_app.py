# -*- coding: utf-8 -*-
"""干净重启桌宠: 杀掉所有 card_app 实例 → 用启动器 exe 拉起 1 个 → 报告进程与凭据日志。

用法: python tools/restart_app.py [等待秒数]
注意: 单个实例在 Windows 上本来就是 2 个进程 —— venv 的 pythonw.exe 只是重定向 stub,
      真实解释器是它的子进程 (base pythonw.exe), 两者命令行相同。
"""
import os, subprocess, sys, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(os.path.expanduser("~"), ".workbuddy", "plugins", "data", "token-usage-stats")
LOG = os.path.join(DATA, "sn_cred.log")

PS = ("Get-CimInstance Win32_Process -Filter \"Name='pythonw.exe'\" | "
      "Where-Object { $_.CommandLine -like '*card_app.py*' } | "
      "ForEach-Object { \"$($_.ProcessId)|$($_.ExecutablePath)\" }")


def rows():
    r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", PS],
                       capture_output=True, text=True, errors="replace")
    out = []
    for line in r.stdout.splitlines():
        p = [x.strip() for x in line.strip().split("|")]
        if len(p) == 2 and p[0].isdigit():
            out.append((int(p[0]), p[1]))
    return out


def kill_all():
    for pid, _ in rows():
        subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True)


if __name__ == "__main__":
    wait = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    kill_all()
    time.sleep(1.2)
    print("清理后进程数:", len(rows()))
    try:
        os.remove(LOG)
    except OSError:
        pass
    D = 0x8 | 0x200 | 0x8000000
    exe = os.path.join(ROOT, "TokenStats.exe")
    p = subprocess.Popen([exe], cwd=ROOT, creationflags=D,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL)
    print("启动器 pid =", p.pid)
    time.sleep(wait)
    procs = rows()
    print("落定后进程数:", len(procs))
    for pid, exe_path in procs:
        print("   pid=%d  %s" % (pid, exe_path))
    try:
        print("ball.pid =", open(os.path.join(DATA, "ball.pid")).read().strip())
    except OSError:
        pass
    print("---- 凭据链路日志 ----")
    try:
        print(open(LOG, encoding="utf-8", errors="replace").read())
    except OSError:
        print("(无日志)")
