# -*- coding: utf-8 -*-
"""干净重启桌宠 —— 一条命令搞定, 跑完**自己退出**(不挂后台任务)。

第101轮重写(浅浅猫反馈: "每次你结束任务前, 重启程序的那个任务都会一直跑不停下"):
  旧做法是 `pythonw -B card_app.py` 挂在 Bash 后台任务里 —— 桌宠是常驻 GUI,
  那个后台任务**永远不会结束**, 一直显示 running。
  现在: 脚本用 DETACHED 方式把启动器踢出去(exe 是脚本的**孙进程**, 脱离进程树),
  然后轮询 ball_status.json, 等到"新 pid + 代码 mtime 匹配磁盘"就打印结论并退出。
  ⇒ 一条命令、几十秒内结束、结论确定(不再靠抓屏猜)。

用法: python -B tools/restart_app.py [最长等待秒数(默认45)]
退出码: 0 = 已重启且跑的是最新代码; 1 = 超时 / 没起来
"""
import os
import subprocess
import sys
import time

sys.dont_write_bytecode = True
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import json

import card_app as ca

DATA = ca.scanner.PLUGIN_DATA_DIR
STATUS = ca.ball_status_path()
PIDFILE = os.path.join(DATA, "ball.pid")

PS_LIST = ("Get-CimInstance Win32_Process -Filter \"Name='pythonw.exe' OR Name='python.exe'\" | "
           "Where-Object { $_.CommandLine -like '*card_app.py*' } | "
           "ForEach-Object { \"$($_.ProcessId)\" }")


def procs():
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", PS_LIST],
                           capture_output=True, text=True, errors="replace", timeout=30)
    except Exception:
        return None
    return [int(x) for x in (r.stdout or "").split() if x.strip().isdigit()]


def kill_all():
    ps = procs() or []
    for pid in ps:
        subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True)
    return ps


def clean_status():
    for p in (STATUS, PIDFILE):
        try:
            os.remove(p)
        except OSError:
            pass


def main():
    budget = int(sys.argv[1]) if len(sys.argv) > 1 else 45
    src = os.path.join(ROOT, "card_app.py")
    st0 = os.stat(src)
    mt, sz = round(st0.st_mtime, 2), st0.st_size
    print("目标代码 mtime=%.2f size=%d" % (mt, sz))

    old = kill_all()
    print("① 结束旧进程: %s" % (old or "无"))
    time.sleep(1.2)
    clean_status()
    print("② 清掉旧状态文件(免得拿上次的残留当结论)")

    exe = os.path.join(ROOT, "TokenStats.exe")
    if not os.path.exists(exe):
        print("!! 启动器不存在:", exe)
        return 1
    # ★ 第101轮实测: 前台 Bash 命令里 DETACHED Popen 出来的进程, **命令一结束就被
    #   递归回收**(脚本刚报告 OK, 过几十秒进程就没了)。改用 explorer.exe 拉起 ——
    #   explorer 是系统 shell, 由它启动的进程属于 explorer 的进程树, 与 WorkBuddy
    #   的工具进程树无关, 不会被回收(等价于她自己双击, 也是自启链路的同一条路)。
    how = "explorer"
    try:
        subprocess.Popen(["explorer.exe", os.path.normpath(exe)], cwd=ROOT)
    except Exception:
        how = "detached(回退)"
        subprocess.Popen([exe], cwd=ROOT, creationflags=0x8 | 0x200 | 0x8000000,
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)
    print("③ 已拉起启动器 TokenStats.exe [%s] → explorer 进程树, 不会被回收" % how)

    t0 = time.time()
    seen = None
    while time.time() - t0 < budget:
        time.sleep(1.5)
        if not os.path.isfile(STATUS):
            continue
        try:
            with open(STATUS, encoding="utf-8") as f:
                st = json.load(f)
        except Exception:
            continue
        if float(st.get("app_mtime", 0)) + 0.5 < mt or int(st.get("app_size", 0)) != sz:
            continue                       # 还是旧状态
        seen = st
        break

    print("④ 等待 %.1fs" % (time.time() - t0))
    if seen is None:
        print("\n结论: FAIL  —— 超时没见到新状态文件, 桌宠可能没起来")
        print("  现存 card_app 进程:", procs())
        print("  ---- 启动器日志 tail ----")
        try:
            print(open(os.path.join(DATA, "launcher.log"), encoding="utf-8",
                       errors="replace").read()[-900:])
        except OSError:
            print("   (无日志)")
        return 1

    print("\n结论: OK  —— 桌宠已重启")
    print("  pid=%s  启动于 %s  build=%s" %
          (seen.get("pid"), seen.get("launch"), seen.get("build")))
    print("  pet=%s theme=%s frames=%s window=%s" %
          (seen.get("pet"), seen.get("pet_theme"), seen.get("frames"), seen.get("window")))
    print("  代码 mtime 与磁盘一致 ✅   进程: %s" % procs())
    return 0


if __name__ == "__main__":
    sys.exit(main())
