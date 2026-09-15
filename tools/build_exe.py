# -*- coding: utf-8 -*-
"""把 card_app.py 打包成单文件 exe（自带图标 + 在用素材）。

用法（在 token-stats 目录下）:
    python tools/build_exe.py             # 单文件 exe（默认）
    python tools/build_exe.py --onedir    # 目录模式（不是单文件，但启动更快）

产物:
    <构建目录>/dist/TokenStats.exe        # 主产物
    桌面/Token统计.exe                     # 同时复制一份到桌面，双击即用

设计要点:
  1. **只打包"在用"的素材** —— assets/pet(v1)、pet_v2、pet_v3r、pet_v4 与 app_icon；
     备份目录(pet_v2_green / *_bak_* / pet_v5 等)不进包，否则体积会白白翻几倍。
  2. 构建临时目录优先放 **D 盘**（通过 TMP/TEMP 传给 PyInstaller 子进程），
     避免把 C 盘塞满导致打包失败。
  3. 图标只有一个来源 `assets/app_icon.ico`：exe 图标(--icon) / 任务栏(setWindowIcon)
     / 托盘(QSystemTrayIcon) 三处统一。
  4. exe 启动时会**优先读取 exe 同级的 assets/**，所以把 assets 放在 exe 旁边
     就能直接替换素材，无需重新打包。
"""
import argparse
import os
import shutil
import subprocess
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = sys.executable
ENTRY = os.path.join(BASE, "card_app.py")
ICON = os.path.join(BASE, "assets", "app_icon.ico")
APP_EXE = "TokenStats.exe"
DESKTOP_NAME = "Token统计.exe"

# 打进包里的素材（只含在用的）
BUNDLE_ASSETS = ["assets/pet", "assets/pet_v2", "assets/pet_v3r", "assets/pet_v4"]
BUNDLE_FILES = ["assets/app_icon.ico", "assets/app_icon.png"]


def work_root():
    """构建目录根：优先 D 盘（空间大），否则退回用户临时目录。"""
    for cand in (r"D:\_pybuild", os.path.join(os.environ.get("TEMP", BASE), "_pybuild")):
        drive = os.path.splitdrive(cand)[0]
        if not drive or os.path.isdir(drive + os.sep):
            return cand
    return os.path.join(BASE, "_pybuild")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--onedir", action="store_true", help="目录模式(非单文件, 启动更快)")
    args = ap.parse_args()

    root = work_root()
    tmp = os.path.join(root, "tmp")
    dist = os.path.join(root, "dist")
    work = os.path.join(root, "build")
    spec = os.path.join(root, "spec")
    for d in (tmp, dist, work, spec):
        os.makedirs(d, exist_ok=True)

    env = dict(os.environ)
    env.update(TEMP=tmp, TMP=tmp, TMPDIR=tmp)      # 交给子进程, 别占 C 盘
    print(f"构建目录: {root}")
    if not os.path.exists(ICON):
        print(f"!! 缺图标 {ICON}，先跑 tools/make_app_icon.py")
        return 1

    cmd = [PY, "-m", "PyInstaller", "--noconfirm", "--clean",
           "--onedir" if args.onedir else "--onefile",
           "--windowed", "--name", "TokenStats", "--icon", ICON]
    # ⚠️ --add-data 的源路径必须用**绝对路径**：一旦指定了 --specpath，
    #    PyInstaller 会以 spec 目录为基准解析相对路径（实测会报
    #    "Unable to find 'D:\_pybuild\spec\assets\pet'"）。
    for d in BUNDLE_ASSETS:
        cmd += ["--add-data", f"{os.path.join(BASE, d)};{d}"]
    for f in BUNDLE_FILES:
        cmd += ["--add-data", f"{os.path.join(BASE, f)};assets"]
    cmd += ["--distpath", dist, "--workpath", work, "--specpath", spec, ENTRY]

    print("执行:", " ".join(cmd[:8]), "...")
    r = subprocess.run(cmd, env=env, cwd=BASE)
    if r.returncode != 0:
        print(f"!! 打包失败 (exit {r.returncode})")
        return r.returncode

    exe = os.path.join(dist, APP_EXE)
    if not os.path.exists(exe):
        print(f"!! 未找到产物 {exe}")
        return 1
    size_mb = os.path.getsize(exe) / 1048576
    print(f"OK  产物: {exe}  ({size_mb:.1f} MB)")

    desktop = os.path.join(os.environ.get("USERPROFILE", ""), "Desktop")
    if os.path.isdir(desktop):
        dst = os.path.join(desktop, DESKTOP_NAME)
        try:
            shutil.copy2(exe, dst)
            print(f"OK  已复制到桌面: {dst}")
        except Exception as e:
            print(f"(复制到桌面失败: {e})")
    print("\n提示: 把 assets 目录放在 exe 旁边即可直接替换素材, 无需重新打包。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
