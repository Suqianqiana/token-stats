# -*- coding: utf-8 -*-
"""Windows DWM 实时毛玻璃（Acrylic）—— 纯标准库 ctypes 实现，零第三方依赖。

2026-10-19 第76轮 · 移植自浅浅猫的调研结论
（《PySide6毛玻璃调研/07-本机实测-最终结论.md》）：
  · **Acrylic 可用**：Qt 透明窗口 + AccentPolicy=19 → 保留率 95.1%、归一化 HF 降 39% = 真模糊，
    由 DWM 在 GPU 上每帧合成，Python 进程 CPU 占用 0（背景随窗口移动实时重采样）。
  · **Mica 不可用**：实测保留率 39.7%，与不透明窗口完全相同（会被盖成实心板）—— 第63轮判对了。
  · 第63轮之所以判错 Acrylic，是实验只设了 `DwmSetWindowAttribute(38)`，
    没走 `SetWindowCompositionAttribute`(AccentPolicy) 这条通路。

⚠️ 三个必须遵守的坑（调研 05/08 号文档）：
  1. `GradientColor` 内存布局是 **BB GG RR AA**（与书写的 AARRGGBB 相反）→ 必须反转字节；
  2. 必须在 **show() 之后** 用 `int(winId())` 应用；最小化恢复 / 跨屏 DPI 变化后要重应用；
  3. tint 基色必须**随深浅主题切换**（同一 alpha 下深浅 tint 亮度差可达 39），
     否则浅色 UI 会被深 tint 压脏。

不用 Mica、不引 PyQt-Frameless-Window（规避 GPL-3.0 传染）。
"""

import sys

_WIN = (sys.platform == "win32")

# ---------------------------------------------------------------- 结构体 / 枚举
if _WIN:
    from ctypes import (POINTER, Structure, byref, c_bool, c_int,
                        pointer, sizeof, WinDLL)
    from ctypes.wintypes import DWORD, LONG, LPCVOID, ULONG

    class ACCENT_STATE:
        ACCENT_DISABLED = 0
        ACCENT_ENABLE_GRADIENT = 1
        ACCENT_ENABLE_TRANSPARENTGRADIENT = 2
        ACCENT_ENABLE_BLURBEHIND = 3            # Aero
        ACCENT_ENABLE_ACRYLICBLURBEHIND = 4     # Acrylic ★
        ACCENT_ENABLE_HOSTBACKDROP = 5          # Mica（实测不可用）
        ACCENT_INVALID_STATE = 6

    class WINDOWCOMPOSITIONATTRIB:
        WCA_ACCENT_POLICY = 19

    class ACCENT_POLICY(Structure):
        _fields_ = [("AccentState", DWORD), ("AccentFlags", DWORD),
                    ("GradientColor", DWORD), ("AnimationId", DWORD)]

    class WINDOWCOMPOSITIONATTRIBDATA(Structure):
        _fields_ = [("Attribute", DWORD), ("Data", POINTER(ACCENT_POLICY)),
                    ("SizeOfData", ULONG)]

    class MARGINS(Structure):
        _fields_ = [("cxLeftWidth", c_int), ("cxRightWidth", c_int),
                    ("cyTopHeight", c_int), ("cyBottomHeight", c_int)]

    class DWMWINDOWATTRIBUTE:
        DWMWA_USE_IMMERSIVE_DARK_MODE = 20
        DWMWA_WINDOW_CORNER_PREFERENCE = 33


# ---------------------------------------------------------------- tint 常量
# 调研 08 号：深色用深基色、浅色用浅基色。下面两个数字可直接微调观感。
ACRYLIC_ALPHA_DARK = 0x8C        # 深色 tint 不透明度 (~55%)
ACRYLIC_ALPHA_LIGHT = 0x62       # 浅色 tint 不透明度 (~38%)
# 第77轮(浅猫截图): 原先浅色 0xAA(67% 近白)会把背后模糊整个盖死,
# 反馈是"亮色完全没有实现毛玻璃" → 降到 0x62, 模糊立起来。
ACRYLIC_RGB_DARK = (0x14, 0x18, 0x1F)    # 深板岩色
ACRYLIC_RGB_LIGHT = (0xF2, 0xF5, 0xFA)   # 近白


def acrylic_color(dark, alpha=None):
    """返回 DWM 需要的 'AARRGGBB' 字符串（调用方再反转字节）。"""
    r, g, b = ACRYLIC_RGB_DARK if dark else ACRYLIC_RGB_LIGHT
    if alpha is None:
        alpha = ACRYLIC_ALPHA_DARK if dark else ACRYLIC_ALPHA_LIGHT
    return "%02X%02X%02X%02X" % (alpha, r, g, b)


class WindowsWindowEffect:
    """Windows 窗口效果封装（Acrylic / 阴影 / 圆角 / 深色标题栏）。"""

    def __init__(self):
        self.user32 = WinDLL("user32")
        self.dwmapi = WinDLL("dwmapi")

        self._set_attr = self.user32.SetWindowCompositionAttribute
        self._dwm_set = self.dwmapi.DwmSetWindowAttribute
        self._extend = self.dwmapi.DwmExtendFrameIntoClientArea

        self._set_attr.restype = c_bool
        self._dwm_set.restype = LONG
        self._extend.restype = LONG

        self._set_attr.argtypes = [c_int, POINTER(WINDOWCOMPOSITIONATTRIBDATA)]
        self._dwm_set.argtypes = [c_int, DWORD, LPCVOID, DWORD]
        self._extend.argtypes = [c_int, POINTER(MARGINS)]

        self._policy = ACCENT_POLICY()
        self._data = WINDOWCOMPOSITIONATTRIBDATA()
        self._data.Attribute = WINDOWCOMPOSITIONATTRIB.WCA_ACCENT_POLICY
        self._data.SizeOfData = sizeof(self._policy)
        self._data.Data = pointer(self._policy)

    # ------------------------------------------------------------ 内部
    @staticmethod
    def _gradient(aarrggbb):
        """'AARRGGBB' → DWM 的 DWORD。⚠️ 内存布局是 BB GG RR AA，必须反转字节。"""
        s = str(aarrggbb).replace("#", "")
        if len(s) != 8:
            raise ValueError("gradient color must be 8 hex chars (AARRGGBB)")
        return DWORD(int(''.join(s[i:i + 2] for i in range(6, -1, -2)), base=16))

    def _apply(self, hwnd):
        hwnd = int(hwnd)
        self._data.Attribute = WINDOWCOMPOSITIONATTRIB.WCA_ACCENT_POLICY
        self._data.SizeOfData = sizeof(self._policy)
        self._data.Data = pointer(self._policy)
        return bool(self._set_attr(hwnd, pointer(self._data)))

    # ------------------------------------------------------------ 对外
    def set_acrylic(self, hwnd, aarrggbb="F2F2F299", enable_shadow=True):
        """Acrylic 亚克力毛玻璃（Win10 1607+）。"""
        self._policy.AccentState = ACCENT_STATE.ACCENT_ENABLE_ACRYLICBLURBEHIND
        self._policy.GradientColor = self._gradient(aarrggbb)
        # 0x20|0x40|0x80|0x100 = 480：保留 DWM 阴影等
        self._policy.AccentFlags = DWORD(0x20 | 0x40 | 0x80 | 0x100) if enable_shadow else DWORD(0)
        self._policy.AnimationId = DWORD(0)
        return self._apply(hwnd)

    def remove(self, hwnd):
        """移除背景效果（切回默认/液态玻璃时必须调用）。"""
        self._policy.AccentState = ACCENT_STATE.ACCENT_DISABLED
        self._policy.GradientColor = DWORD(0)
        self._policy.AccentFlags = DWORD(0)
        self._policy.AnimationId = DWORD(0)
        return self._apply(hwnd)

    def add_shadow(self, hwnd):
        m = MARGINS(-1, -1, -1, -1)
        self._extend(int(hwnd), byref(m))

    def set_dark_mode(self, hwnd, dark=True):
        if sys.getwindowsversion().build < 22000:
            return
        v = c_int(1 if dark else 0)
        self._dwm_set(int(hwnd), DWMWINDOWATTRIBUTE.DWMWA_USE_IMMERSIVE_DARK_MODE,
                      byref(v), 4)

    def set_corner(self, hwnd, mode=3):
        """圆角：2=不圆 3=圆角 4=小圆角（Win11 22000+）。"""
        if sys.getwindowsversion().build < 22000:
            return
        v = c_int(mode)
        self._dwm_set(int(hwnd), DWMWINDOWATTRIBUTE.DWMWA_WINDOW_CORNER_PREFERENCE,
                      byref(v), 4)


_EFFECT = None
_SUPPORTED = None


def effect():
    """懒加载（非 Windows 返回 None）。"""
    global _EFFECT
    if not _WIN:
        return None
    if _EFFECT is None:
        try:
            _EFFECT = WindowsWindowEffect()
        except Exception:
            _EFFECT = None
    return _EFFECT


def supported():
    """Acrylic 是否可用（只探测一次）。失败 → 调用方应回落静态底纹。"""
    global _SUPPORTED
    if _SUPPORTED is None:
        _SUPPORTED = bool(_WIN) and (effect() is not None)
    return _SUPPORTED


def apply_acrylic(hwnd, dark, alpha=None):
    """给窗口挂上 Acrylic（含阴影/圆角）。失败返回 False。"""
    fx = effect()
    if fx is None or not hwnd:
        return False
    try:
        fx.add_shadow(hwnd)
        ok = fx.set_acrylic(hwnd, acrylic_color(dark, alpha), enable_shadow=True)
        if ok:
            fx.set_dark_mode(hwnd, bool(dark))
            fx.set_corner(hwnd, 3)
        return bool(ok)
    except Exception:
        return False


def remove_acrylic(hwnd):
    """移除 Acrylic（离开毛玻璃模式时必须调用，否则会留一层灰）。"""
    fx = effect()
    if fx is None or not hwnd:
        return False
    try:
        return bool(fx.remove(hwnd))
    except Exception:
        return False
