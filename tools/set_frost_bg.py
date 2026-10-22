# -*- coding: utf-8 -*-
"""第97轮后半13: 把浅猫指定的图片做成毛玻璃静态底纹, 替换 assets/frost_bg.png。

处理链与程序内 `FrostTexture._process()` 完全一致(复用同一函数, 不是另写一套):
    读入 → 等比缩放长边 1400 → 真高斯模糊(QGraphicsBlurEffect) → 去饱和 35% → 存 PNG

用法:
    python -B tools/set_frost_bg.py <图片路径>
"""
import os, sys
sys.dont_write_bytecode = True
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QImage
import card_app as ca

src = sys.argv[1] if len(sys.argv) > 1 else (
    r"C:\Users\a3564\.workbuddy\clipboard-images\clipboard-2026-10-22T12-06-29-730Z-4ce1e60b.jpg")
if not os.path.exists(src):
    print("找不到源图:", src)
    sys.exit(1)

app = QApplication(sys.argv)
img = QImage(src)
if img.isNull():
    print("读图失败:", src)
    sys.exit(1)
print("源图:", src, img.width(), "x", img.height())

out = ca.FrostTexture._process(img)          # 复用程序内的真高斯 + 去饱和
dst = ca.FROST_TEX_DEFAULT                   # assets/frost_bg.png
if os.path.exists(dst):
    print("将覆盖:", dst, "(原文件在 git 里, 可用 git checkout 恢复)")
if not out.save(dst, "PNG"):
    print("保存失败")
    sys.exit(1)
print("已写入:", dst, out.width(), "x", out.height(), os.path.getsize(dst), "bytes")

# 清掉用户自定义纹理(若有), 让新内置底纹立即生效
for f in (ca.FROST_TEX_USER,):
    if os.path.exists(f):
        try:
            os.remove(f)
            print("已删除旧用户纹理:", f)
        except OSError as e:
            print("删除用户纹理失败(可忽略):", e)
print("DONE")
