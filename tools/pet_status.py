# -*- coding: utf-8 -*-
"""桌宠运行状态体检 (第101轮) —— 一条命令给出**确定**结论。

背景(浅浅猫指出的老毛病): 以前判断"桌宠有没有在跑 / 跑的是不是刚改完的代码"
全靠临时写 ctypes 枚举窗口、抓屏比对, 慢而且容易误判 —— 把"被火绒杀进程"
"孙进程逃逸""窗口被 WorkBuddy 遮挡"混成一团, 结论经常错。

现在的判据全部来自应用自己写的 `ball_status.json`(第101轮新增):
  · 里面记了 pid / 启动时间 / 代码文件的 mtime+size / 主题 / 帧数 / 窗口几何
  · 拿 `app_mtime` 和磁盘上 `card_app.py` 的 mtime 一比 → 是否跑的最新代码, 确定

用法: python -B tools/pet_status.py [-v]
退出码: 0 = 正常运行且是最新代码; 1 = 没跑或跑的是旧代码(需要重启)
"""
import os
import sys

sys.dont_write_bytecode = True
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import json
import subprocess

import card_app as ca

DATA = ca.scanner.PLUGIN_DATA_DIR
STATUS = ca.ball_status_path()
PIDFILE = os.path.join(DATA, "ball.pid")

PS_LIST = ("Get-CimInstance Win32_Process -Filter \"Name='pythonw.exe' OR Name='python.exe'\" | "
           "Where-Object { $_.CommandLine -like '*card_app.py*' } | "
           "ForEach-Object { \"$($_.ProcessId)|$($_.ExecutablePath)\" }")


def procs():
    """列出所有命令行含 card_app.py 的进程 [(pid, exe)]。"""
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", PS_LIST],
                           capture_output=True, text=True, errors="replace", timeout=30)
    except Exception:
        return None
    out = []
    for line in (r.stdout or "").splitlines():
        p = [x.strip() for x in line.strip().split("|")]
        if len(p) == 2 and p[0].isdigit():
            out.append((int(p[0]), p[1]))
    return out


def src_mtime():
    st = os.stat(os.path.join(ROOT, "card_app.py"))
    return round(st.st_mtime, 2), st.st_size


def main():
    verbose = "-v" in sys.argv
    mt, sz = src_mtime()
    print("源码 card_app.py : mtime=%s size=%d" % (mt, sz))
    print("状态文件       : %s" % STATUS)

    st = None
    if os.path.isfile(STATUS):
        try:
            with open(STATUS, encoding="utf-8") as f:
                st = json.load(f)
        except Exception as e:
            print("   (读取失败: %r)" % e)

    ps = procs()

    if st is None:
        print("\n结论: NOT_RUNNING  —— 没有状态文件(桌宠没起来, 或还没写状态)")
        print("      当前 card_app 进程: %s" % (ps if ps else "(查询失败或没有)"))
        return 1

    pid = int(st.get("pid", 0))
    print("状态里的 pid    : %d   启动于 %s" % (pid, st.get("launch", "?")))
    print("  build=%s  pet=%s theme=%s frames=%s seqs=%s window=%s" %
          (st.get("build"), st.get("pet"), st.get("pet_theme"),
           st.get("frames"), st.get("seqs"), st.get("window")))
    if verbose:
        print("  no_bytecode=%s  state=%s  rz_mode=%s" %
              (st.get("no_bytecode"), st.get("state"), st.get("rz_mode")))

    alive = [p for p in (ps or []) if p[0] == pid]
    if ps is None:
        print("  ⚠️ 进程列表查询失败, 无法确认存活")
    elif not alive:
        print("  ⚠️ 状态里的 pid 已不存在 —— 残留状态文件(进程已退出/被杀)")
        print("      现存 card_app 进程: %s" % (ps or "无"))
        print("\n结论: DEAD  —— 桌宠没在跑(状态文件是上次的残留)")
        return 1

    # 代码新旧
    st_mt = float(st.get("app_mtime", 0))
    st_sz = int(st.get("app_size", 0))
    if st_mt + 0.5 < mt or st_sz != sz:
        print("  ⚠️ 跑的是**旧代码**: 状态里 mtime=%.2f size=%d, 磁盘上 mtime=%.2f size=%d"
              % (st_mt, st_sz, mt, sz))
        print("\n结论: OUTDATED  —— 在跑, 但代码改过之后没重启 → 跑 `python -B tools/restart_app.py`")
        return 1

    print("  ✅ 进程存活, 且跑的正是当前这份代码(mtime 一致)")
    print("\n结论: RUNNING  —— 正常")
    return 0


if __name__ == "__main__":
    sys.exit(main())
