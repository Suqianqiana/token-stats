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
    from ctypes.wintypes import DWORD, LONG, LPCVOID, ULONG, HWND, UINT

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
ACRYLIC_ALPHA_DARK = 0x8C       # 深色 tint (~55%, 压住壁纸色相)
ACRYLIC_ALPHA_LIGHT = 0x7A      # 浅色 tint (~48%, 第82轮浅猫指定)
# 第80轮(浅猫): "毛玻璃下背景比文字慢半拍" 的根因不是 tint 本身(单次下发实测 0.15ms),
# 而是 set_dark 里**先做了耗时的纹理重载/样式重刷**, 才去换 tint。
# → 修法: set_dark 里**先下发 tint**(见 CardWindow.set_dark), tint 仍按明暗给足分量。
# 第78轮(浅猫): 浅色要"纯奶白"。上一版 0x62(38%) 太透 → 桌面壁纸的色相渗上来,
# 她看到的是"纯薄荷绿"。现在: ① 提到 54%; ② tint 用**纯白**, 压住壁纸色相。
ACRYLIC_RGB_DARK = (0x14, 0x18, 0x1F)    # 深板岩色
ACRYLIC_RGB_LIGHT = (0xFF, 0xFF, 0xFF)   # 纯白(奶白的关键)


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
        self._set_pos = self.user32.SetWindowPos

        self._set_attr.restype = c_bool
        self._dwm_set.restype = LONG
        self._extend.restype = LONG
        self._set_pos.restype = c_bool

        self._set_attr.argtypes = [c_int, POINTER(WINDOWCOMPOSITIONATTRIBDATA)]
        self._dwm_set.argtypes = [c_int, DWORD, LPCVOID, DWORD]
        self._extend.argtypes = [c_int, POINTER(MARGINS)]
        # ⚠️⚠️ 第97轮后半的坑: SetWindowPos **必须**设 argtypes, 否则 64 位下 ctypes 按
        # 32 位 int 传 HWND → 句柄被截断 → 调用打到错误窗口/直接失败, 表现为
        # "开关置顶还是闪一下"(set_topmost 返回 False, 调用方回退到 setWindowFlags 老路)。
        # 这是上一轮修没生效的真凶, 不是 Qt 的问题。
        self._set_pos.argtypes = [HWND, HWND, c_int, c_int, c_int, c_int, UINT]

        self._policy = ACCENT_POLICY()
        self._data = WINDOWCOMPOSITIONATTRIBDATA()
        self._data.Attribute = WINDOWCOMPOSITIONATTRIB.WCA_ACCENT_POLICY
        self._data.SizeOfData = sizeof(self._policy)
        self._data.Data = pointer(self._policy)

    # ------------------------------------------------------------ 内部
    @staticmethod
    def _gradient(aarrggbb):
        """'AARRGGBB' → DWM 的 DWORD。

        ⚠️ DWM 的 `ACCENT_POLICY.GradientColor` 是 **AABBGGRR**(RGB 三通道反序),
        不是整串字节倒置。第79轮之前我按整串倒置(BBGGRRAA)写, 结果:
          · 浅色 8AFFFFFF → 读成 A=FF,R=8A,G=FF,B=FF = **不透明青色**(浅猫看到的"薄荷绿")
          · 深色 8C14181F → 读成 A=1F(仅 12% 不透明), RGB=8C1418 = 暗红
        正确做法: 只把 R 与 B 对调。
        """
        s = str(aarrggbb).replace("#", "")
        if len(s) != 8:
            raise ValueError("gradient color must be 8 hex chars (AARRGGBB)")
        return DWORD(int(s[0:2] + s[6:8] + s[4:6] + s[2:4], base=16))

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


def apply_acrylic(hwnd, dark, alpha=None, shadow=False, corner=False):
    """给窗口挂上 Acrylic。

    ⚠️ add_shadow(): DwmExtendFrameIntoClientArea(-1,-1,-1,-1) 会让 Windows 在最外圈画
    **原生实线边框**, 且切回其它模式不会自动消失 → **永远不要调用**(第81轮真凶之一)。

    ⚠️ set_corner(): DWMWA_WINDOW_CORNER_PREFERENCE 让 Win11 把窗口**裁成原生圆角**,
    但它也会带出 1px 描边, 曾经是"原生外框"的真凶。
      · **主窗口**: 绝不能调(那就是外框的来源);
      · **底层背板窗口**(第86轮双层架构): 却**必须**调 —— 浅猫在 demo v2 亲自投票选定
        "系统圆角背板 + 面板圆角14 + 内缩0" 为最佳观感: 背板自己是圆的, 就不会往面板的
        圆角缺口里溢出方形材质角, 直边也不需要内缩(没有未模糊带)。
    """
    fx = effect()
    if fx is None or not hwnd:
        return False
    try:
        ok = fx.set_acrylic(hwnd, acrylic_color(dark, alpha), enable_shadow=True)
        if ok:
            fx.set_dark_mode(hwnd, bool(dark))
            if corner:
                fx.set_corner(hwnd, 2)      # 仅背板使用
        return bool(ok)
    except Exception:
        return False


def reset_frame(hwnd):
    """把客户区框还原(MARGINS 0) —— 撤掉 add_shadow 留下的原生边框。

    离开毛玻璃/静态背景时必须调用: 否则那圈实线边框会一直挂在窗口最外层。
    """
    fx = effect()
    if fx is None or not hwnd:
        return False
    try:
        m = MARGINS(0, 0, 0, 0)
        return int(fx._extend(int(hwnd), byref(m))) == 0
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


# ================================================================ 区域模糊（第79轮）
# 为什么不再用 AccentPolicy：
#   实测（屏捕对比）—— `QWidget.setMask()`/窗口区域 一旦生效, Windows 会让
#   `SetWindowCompositionAttribute(AccentPolicy)` 的材质**失效**（窗口退回纯透明,
#   于是只能看到没模糊的壁纸, 浅猫那张"一片青色"就是这个）。
#   而 AccentPolicy 本身没有"只作用于某个区域"的参数, 它一定铺满整个窗口矩形,
#   于是圆角外那圈边距也带材质 → 就是她反复看到的"矩形框"。
#
# 正解: `DwmEnableBlurBehindWindow` + **模糊区域**(DWM_BB_BLURREGION)。
#   · 只模糊给定区域 → 圆角外那圈保持纯壁纸(没有材质, 没有矩形框), 圆角外框原样保留;
#   · 不改变窗口形状 → 命中测试/拖动完全不受影响;
#   · 它不含 tint → 底色由 Qt 自己画（我们本来就有完整的毛玻璃罩层）。
if _WIN:
    from ctypes.wintypes import HANDLE

    class DWM_BLURBEHIND(Structure):
        _fields_ = [("dwFlags", DWORD), ("fEnable", c_bool),
                    ("hRgnBlur", HANDLE), ("fTransitionOnMaximized", c_bool)]

    _DWM_BB_ENABLE = 0x1
    _DWM_BB_BLURREGION = 0x2


def set_blur_region(hwnd, x, y, w, h, radius=14):
    """在窗口的指定矩形区域(圆角)内开启实时模糊。失败返回 False。"""
    if not _WIN or not hwnd:
        return False
    try:
        gdi32 = WinDLL("gdi32")
        dwmapi = WinDLL("dwmapi")
        rgn = gdi32.CreateRoundRectRgn(int(x), int(y), int(x + w), int(y + h),
                                       int(radius * 2), int(radius * 2))
        if not rgn:
            return False
        bb = DWM_BLURBEHIND(_DWM_BB_ENABLE | _DWM_BB_BLURREGION, True, rgn, False)
        dwmapi.DwmEnableBlurBehindWindow.restype = LONG
        rc = dwmapi.DwmEnableBlurBehindWindow(int(hwnd), byref(bb))
        try:
            gdi32.DeleteObject(rgn)
        except Exception:
            pass
        return int(rc) == 0
    except Exception:
        return False


def clear_blur_region(hwnd):
    """关闭区域模糊。"""
    if not _WIN or not hwnd:
        return False
    try:
        dwmapi = WinDLL("dwmapi")
        bb = DWM_BLURBEHIND(_DWM_BB_ENABLE, False, None, False)
        dwmapi.DwmEnableBlurBehindWindow.restype = LONG
        rc = dwmapi.DwmEnableBlurBehindWindow(int(hwnd), byref(bb))
        return int(rc) == 0
    except Exception:
        return False



def reset_corner(hwnd):
    """把 DWM 圆角偏好还原成默认(0) —— 撤掉 set_corner 画的**原生小圆角 + 1px 边框**。

    第81轮: 这才是浅猫截图里那个偏矩形边框的真凶(第77~80 轮我误判成 add_shadow/边距)。
    DWMWA_WINDOW_CORNER_PREFERENCE 会让 Win11 给窗口画原生边框, 且**不会**被
    DwmExtendFrameIntoClientArea 还原 —— 离开毛玻璃时必须显式调它。
    """
    fx = effect()
    if fx is None or not hwnd:
        return False
    try:
        from ctypes.wintypes import c_int as _c
        v = _c(0)
        fx._dwm_set(int(hwnd), 33, byref(v), 4)
        return True
    except Exception:
        return False

def disable_shadow(hwnd):
    """关掉窗口的**投影**(DWMWA_NCRENDERING_POLICY = DWMNCRP_DISABLED)。

    为什么需要它: 背板是个顶层窗口, Windows 会给它画投影; 投影会落到主窗口的外圈 10px 上,
    那正是"外圈被材质覆盖"的观感来源(核验器数据也吻合: 下环 > 左右 > 上环, 是典型投影方向性)。
    Qt 的 Qt.NoDropShadowWindowHint 在 Windows 上**不生效**(实测窗口标志里没有它),
    所以只能走 DWM 的这条属性。
    """
    fx = effect()
    if fx is None or not hwnd:
        return False
    try:
        from ctypes.wintypes import c_int as _c
        v = _c(1)                      # DWMNCRP_DISABLED
        fx._dwm_set(int(hwnd), 2, byref(v), 4)   # DWMWA_NCRENDERING_POLICY = 2
        return True
    except Exception:
        return False


# ---------------------------------------------------------------- 置顶(不重显)
# SWP_NOACTIVATE | SWP_NOMOVE | SWP_NOSIZE = 0x0013
_SWP_NOACT_NOMOVE_NOSIZE = 0x0013
_HWND_TOPMOST = -1
_HWND_NOTOPMOST = -2


def set_topmost(hwnd, on):
    """用 Win32 SetWindowPos 改置顶态 —— **不重设 Qt flags、不重显窗口**。

    第97轮后半(浅猫: "开关窗口置顶还是闪一下, 没修好")补两个关键修正:
      ① **SetWindowPos 必须设 argtypes**(见 WindowsWindowEffect.__init__ 的 ⚠️)——
         64 位下 ctypes 默认按 32 位 int 传 HWND, 句柄被截断 → 调用失败 →
         上一版 set_topmost 返回 False, 调用方回退到 setWindowFlags 老路, 所以照样闪。
      ② 双窗口(主窗 + frost 背板)必须**先背板后主窗**依次调用:
         HWND_TOPMOST/NOTOPMOST 都会把目标移到同层顶部, 顺序反了会把背板提到主窗前面,
         玻璃板盖住面板(另一种"闪一下")。

    ⚠️ 只对**已显示**的窗口有效; 窗口还没 show 时改 Z 序没有意义(也没害处)。
    """
    fx = effect()
    if fx is None or not hwnd:
        return False
    try:
        hwnd = HWND(int(hwnd))
        after = HWND(_HWND_TOPMOST if on else _HWND_NOTOPMOST)
        return bool(fx._set_pos(hwnd, after, 0, 0, 0, 0, _SWP_NOACT_NOMOVE_NOSIZE))
    except Exception:
        return False
