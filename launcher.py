# -*- coding: utf-8 -*-
"""Token 统计 —— 轻量启动器 (launcher)

作用: 做成一个**带图标的正式 exe**，双击即启动本工具（内部仍是 pythonw + card_app.py 运行，
      PySide6 不进这个 exe，所以体积只有 8~10MB，而不是整包 84MB）。
      开机自启 / 程序内"开机自启动" / 一键重启 都指向它。

行为:
  · 定位项目目录: ① exe 同级的 card_app.py ② exe 上一级(若放在 bin/ 里) ③ 兜底绝对路径
  · 定位解释器: 优先虚拟环境的 pythonw.exe（静默无控制台），找不到就弹窗报错
  · 以 DETACHED + CREATE_NO_WINDOW 方式拉起主程序后**立刻退出**（不留常驻进程、不闪黑框）
  · 每次启动写一行 launcher.log（便于排查自启为什么没生效）
"""
import os
import subprocess
import sys
import time

# ---- 可移植性兜底（exe 不在项目目录里时使用）----
FALLBACK_PROJECT = r"C:\Users\a3564\WorkBuddy\2026-08-25-04-20-35\token-stats"
PYTHONW_CANDIDATES = [
    r"C:\Users\a3564\.workbuddy\binaries\python\envs\pyside6\Scripts\pythonw.exe",
    r"C:\Users\a3564\.workbuddy\binaries\python\envs\default\Scripts\pythonw.exe",
]
DATA_DIR = os.path.join(os.path.expanduser("~"), ".workbuddy", "plugins", "data", "token-usage-stats")
LOG = os.path.join(DATA_DIR, "launcher.log")
APP_SCRIPT = "card_app.py"


def log(msg):
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')}  {msg}\n")
    except OSError:
        pass


def find_project():
    """返回含 card_app.py 的项目目录。"""
    here = os.path.dirname(os.path.abspath(sys.executable if getattr(sys, "frozen", False)
                                           else __file__))
    for cand in (here, os.path.dirname(here)):
        if os.path.exists(os.path.join(cand, APP_SCRIPT)):
            return cand
    return FALLBACK_PROJECT


def find_pythonw():
    for p in PYTHONW_CANDIDATES:
        if os.path.exists(p):
            return p
    # 退而求其次: exe 同级的 pythonw
    here = os.path.dirname(os.path.abspath(sys.executable if getattr(sys, "frozen", False)
                                           else __file__))
    p = os.path.join(here, "pythonw.exe")
    return p if os.path.exists(p) else None


def fatal(msg):
    log("ERROR " + msg)
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, msg, "Token 统计 · 启动失败", 0x10)
    except Exception:
        pass
    sys.exit(1)


def main():
    project = find_project()
    script = os.path.join(project, APP_SCRIPT)
    if not os.path.exists(script):
        fatal(f"找不到主程序：\n{script}\n\n"
              f"请确认 token-stats 目录还在原位置，或把本启动器放回该目录。")
    pythonw = find_pythonw()
    if not pythonw:
        fatal("找不到 Python 运行环境（pythonw.exe）。\n\n"
              "它属于本工具的依赖，路径为：\n" + "\n".join(PYTHONW_CANDIDATES))
    try:
        subprocess.Popen(
            [pythonw, script],
            cwd=project,
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=0x00000008 | 0x00000200 | 0x08000000,   # DETACHED|NEW_GROUP|NO_WINDOW
        )
        log(f"OK   launched '{pythonw}' '{script}'")
    except OSError as e:
        fatal(f"启动失败：{e}")


if __name__ == "__main__":
    main()
