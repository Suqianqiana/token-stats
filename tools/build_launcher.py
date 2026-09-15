# -*- coding: utf-8 -*-
"""构建 / 安装「轻量启动器 exe」（带图标，约 8~10MB）。

为什么要它: 整包打包(PySide6)约 84MB 太大；改成只打包一个**纯启动器**，
           双击它即启动本工具（内部仍以 pythonw 跑 card_app.py），
           对外看起来就是一个正常软件，且开机自启 / 一键重启都指向它。

用法:
    python tools/build_launcher.py                # 打包 + 安装（覆盖已存在的）
    python tools/build_launcher.py --install-only # 只把 dist 里的产物装过去（不重新打包）

"安装"做了三件事:
    1. 把 dist\\TokenStats.exe 复制到项目根目录，命名 `Token统计.exe`
    2. 更新开机自启：启动文件夹 TokenAuditCard.vbs + 注册表 Run 键，都指向这个 exe
    3. 校验 exe 内确实嵌入了图标（RT_GROUP_ICON / RT_ICON 资源）
"""
import ctypes
import os
import shutil
import subprocess
import sys
import time

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LAUNCHER_SRC = os.path.join(BASE, "launcher.py")
ICON = os.path.join(BASE, "assets", "app_icon.ico")
BUILD_ROOT = r"D:\_launcher"                       # 构建目录放 D 盘，避免占用 C 盘
# ★ 每次打包都用**全新的构建目录**: 复用旧目录时 PyInstaller 会先清理它(删文件),
#   而受限环境里删除可能被拒 -> 直接报错。全新目录无需删任何东西, 最稳。
RUN = os.path.join(BUILD_ROOT, "run_" + time.strftime("%Y%m%d_%H%M%S"))
DIST = os.path.join(RUN, "dist")
OUT_NAME = "TokenStats.exe"   # ★ 用 ASCII 文件名: VBS/批处理按 ANSI 读取, 中文名会编码报错
OUT = os.path.join(BASE, OUT_NAME)
PY = sys.executable

VBS_PATH = os.path.join(os.environ.get("APPDATA", ""),
                        "Microsoft", "Windows", "Start Menu", "Programs",
                        "Startup", "TokenAuditCard.vbs")
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_NAME = "TokenAuditCard"


def build():
    env = dict(os.environ)
    tmp = os.path.join(RUN, "tmp")
    os.makedirs(tmp, exist_ok=True)
    env.update(TEMP=tmp, TMP=tmp, TMPDIR=tmp)
    cmd = [PY, "-m", "PyInstaller", "--noconfirm", "--onefile", "--windowed",
           "--name", "TokenStats", "--icon", ICON,
           "--exclude-module", "PySide6", "--exclude-module", "PyQt5",
           "--exclude-module", "tkinter", "--exclude-module", "numpy",
           "--exclude-module", "PIL",
           "--distpath", DIST,
           "--workpath", os.path.join(RUN, "build"),
           "--specpath", os.path.join(RUN, "spec"),
           LAUNCHER_SRC]
    print(f"构建目录: {RUN}")
    print("打包:", " ".join(cmd[:6]), "...")
    r = subprocess.run(cmd, env=env)
    if r.returncode != 0:
        print("★ 打包失败, 退出码", r.returncode)
        return False
    return True


def check_icon(path):
    """用 PE 资源目录检查 exe 里是否真的嵌入了图标。"""
    RT_ICON, RT_GROUP_ICON = 3, 14
    k32 = ctypes.windll.kernel32
    k32.LoadLibraryExW.restype = ctypes.c_void_p
    h = k32.LoadLibraryExW(path, None, 0x00000002)      # LOAD_LIBRARY_AS_DATAFILE
    if not h:
        return None
    found = {}

    def enum_cb(hmod, typ, name, lparam):
        try:
            t = int(typ) if (typ or 0) < 0x10000 else 0
        except TypeError:
            t = 0
        if t:
            found[t] = found.get(t, 0) + 1
        return True

    CB = ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p,
                            ctypes.c_void_p, ctypes.c_void_p)
    k32.EnumResourceNamesW(ctypes.c_void_p(h), 3, CB(enum_cb), None)   # RT_ICON
    k32.EnumResourceNamesW(ctypes.c_void_p(h), 14, CB(enum_cb), None)  # RT_GROUP_ICON
    k32.FreeLibrary(ctypes.c_void_p(h))
    return found


def find_newest_dist():
    """返回最近一次打包目录里的 exe（--install-only 时用；RUN 带时间戳，每次不同）。"""
    cand = os.path.join(DIST, "TokenStats.exe")
    if os.path.exists(cand):
        return cand
    import glob
    runs = sorted(glob.glob(os.path.join(BUILD_ROOT, "run_*", "dist", "TokenStats.exe")))
    return runs[-1] if runs else None


def install():
    src = find_newest_dist()
    if not src:
        print("★ 找不到产物（先不带 --install-only 跑一次以完成打包）")
        return False
    shutil.copy2(src, OUT)
    print(f"已安装: {src}\n    ->  {OUT}  ({os.path.getsize(OUT)/1048576:.1f} MB)")

    # 开机自启: 只写启动文件夹的 vbs（与主程序 set_autostart 的做法保持一致）,
    #   并**清掉注册表 Run 键** —— 两处都写会导致开机启动两次(第二个实例会把第一个顶掉)。
    cmd = f'"{OUT}"'
    try:
        content = 'CreateObject("WScript.Shell").Run "' + cmd.replace('"', '""') + '", 0, False\r\n'
        # ★ 该脚本由系统按 ANSI 读取 -> 必须用 mbcs(本地代码页) 写;
        #   否则路径里一旦含中文, ascii 编码会直接报 UnicodeEncodeError
        try:
            with open(VBS_PATH, "w", encoding="mbcs") as f:
                f.write(content)
        except (UnicodeEncodeError, LookupError):
            with open(VBS_PATH, "w", encoding="utf-8") as f:
                f.write(content)
        print(f"自启(启动文件夹) -> {VBS_PATH}")
    except OSError as e:
        print("★ 写启动文件夹失败:", e)
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0,
                            winreg.KEY_SET_VALUE) as k:
            winreg.DeleteValue(k, RUN_NAME)
        print(f"已清除重复的注册表自启项: {RUN_NAME}")
    except FileNotFoundError:
        pass
    except OSError as e:
        print("(注册表自启项无需清理或清理失败:", e, ")")

    ic = check_icon(OUT)
    print(f"exe 图标资源: {ic}  ({'OK' if ic else '★ 未嵌入'})")
    return True


def main():
    only_install = "--install-only" in sys.argv
    if not only_install:
        if not build():
            return 1
    return 0 if install() else 1


if __name__ == "__main__":
    sys.exit(main())
