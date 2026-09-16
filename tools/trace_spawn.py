# -*- coding: utf-8 -*-
"""追踪 card_app 启动期间谁在拉起子进程 (给 subprocess.Popen 打补丁并打印调用栈)。"""
import os, sys, subprocess, traceback, runpy, tempfile

LOG = os.path.join(tempfile.gettempdir(), "cardapp_spawn_trace.log")
try:
    os.remove(LOG)
except OSError:
    pass

_orig = subprocess.Popen


def patched(*a, **k):
    with open(LOG, "a", encoding="utf-8") as f:
        f.write("=" * 60 + f"\nSPAWN args={a!r}\nkwargs={k!r}\n")
        traceback.print_stack(file=f)
    return _orig(*a, **k)


subprocess.Popen = patched

APP = r"C:\Users\a3564\WorkBuddy\2026-08-25-04-20-35\token-stats\card_app.py"
sys.argv = [APP]
sys.path.insert(0, os.path.dirname(APP))
os.environ["QT_QPA_PLATFORM"] = "offscreen"     # 无头运行, 不弹窗口

import threading


def _boom():
    import time
    time.sleep(12)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write("\n[trace] 12s 到, 结束观察\n")
    os._exit(0)


threading.Thread(target=_boom, daemon=True).start()

runpy.run_path(APP, run_name="__main__")
