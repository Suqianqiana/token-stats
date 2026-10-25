# -*- coding: utf-8 -*-
"""带日志启动 card_app (诊断用): 用 python.exe 拉起, stdout/stderr 落到文件, 便于看崩溃原因。
用法: python -B tools/launch_with_log.py [等待秒数]
"""
import os
import sys
import time
import subprocess

sys.dont_write_bytecode = True
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = r"C:\Users\a3564\.workbuddy\binaries\python\envs\pyside6\Scripts\python.exe"
LOG = os.path.join(ROOT, "docs", "_launch.log")


def main():
    wait = int(sys.argv[1]) if len(sys.argv) > 1 else 12
    if os.path.exists(LOG):
        os.remove(LOG)
    env = dict(os.environ)
    env["PYTHONUNBUFFERED"] = "1"
    with open(LOG, "wb") as f:
        p = subprocess.Popen([PY, "-B", "card_app.py"], cwd=ROOT,
                             stdout=f, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                             env=env)
    print("pid =", p.pid)
    time.sleep(wait)
    rc = p.poll()
    print("poll after %ds = %s" % (wait, ("still running" if rc is None else "EXIT rc=%s" % rc)))
    print("---- log ----")
    try:
        with open(LOG, encoding="utf-8", errors="replace") as f:
            print(f.read()[-6000:])
    except OSError as e:
        print("读日志失败:", e)


if __name__ == "__main__":
    main()
