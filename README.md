# Token 审计卡片（Token Audit Card）

> 常驻桌面的轻量 Token 用量审计浮窗：统计 WorkBuddy / DSH 会话的 Token 消耗，并实时查看商汤（SenseNova / 日日新）模型的积分额度。
> 桌面端 PySide6 程序，无后端依赖，数据全部来自本地 WorkBuddy 会话记录。

---

## 1. 项目简介

「Token 审计卡片」由两部分组成：

- **悬浮球**：屏幕右下角常驻（置顶、可拖动、位置记忆），单击弹出统计卡片，右键打开菜单。
- **卡片窗口**：无边框圆角、液态玻璃主题、可拖动；内置四个数据源 **WorkBuddy / DSH / 商汤积分 / 多机合并**，并支持深浅色切换。

核心能力一览：

| 模块 | 能力 |
|---|---|
| WB / DSH 用量 | 2×2 汇总卡、按模型明细、堆叠柱状图、GitHub 风活跃热力图；支持今日/近7天/近30天/全部 |
| 多机合并 | 导出本机数据（WB + DSH 全部记录）、导入别机数据（按机器名分别存放、不影响本机）、支持多台机器命名、覆盖更新某台机器旧数据；按机统计对比 |
| 商汤积分 | 通用积分池、Flash-Lite 专属积分池、活动固定积分（1:1 返赠）；支持 cURL 自动同步 |
| 交互 | 无边框置顶卡片、悬浮球、位置记忆、右键菜单、深浅色 / 玻璃主题；全程序统一自绘弹窗与按钮语言 |
| 桌宠形态 | DeepSeek 娘帧动画（待机/入睡/拖拽/点击互动/小剧场/摸摸头）；双素材版本（v1 经典 / v2 新版高清）右键菜单切换；双击打开统计面板 |

架构与实现细节、演进历程、Git 提交规范见根目录主协作文档 [`协作进度.md`](协作进度.md)。

---

## 2. 环境要求

- **操作系统**：Windows（已验证）；理论上 PySide6 跨平台，但启动脚本为 Windows 批处理
- **Python**：3.13（使用托管运行时，无需自行安装）
- **虚拟环境**：`~/.workbuddy/binaries/python/envs/pyside6`，已含 **PySide6 6.11.1**
- **第三方依赖**：仅 PySide6；扫描 / HTTP / JSON 均为标准库
- **数据来源**：`~/.workbuddy/projects/**/*.jsonl`（WorkBuddy 会话记录）
- **持久化目录**：`~/.workbuddy/plugins/data/token-usage-stats/`

> 无需 `pip install`，venv 已就绪。直接双击启动脚本即可。

---

## 3. 启动与使用

### 3.1 启动（推荐双击）

在文件资源管理器中进入本项目目录，双击以下任一启动器：

- **`start_card.bat`**（英文，规范入口）
- **`启动统计悬浮球.bat`**（中文别名，内容相同）
- **`启动统计悬浮球.vbs`**（静默启动，不弹控制台窗口，适合日常使用）

启动后：

1. 右下角出现悬浮球；
2. **单击悬浮球** → 弹出卡片窗口；
3. 卡片顶部标题栏可拖动；`–` 最小化、`✕` 隐藏（不退出，悬浮球仍在）；右键菜单可「打开 / 立即刷新 / 退出」。

### 3.2 开机自启

双击 `enable_autostart.bat`，会在「开始菜单 → 启动」创建快捷方式，下次开机自动运行。

### 3.3 数据源与界面

- 顶部第二行为 **数据源** 切换：`WorkBuddy` / `DSH` / `商汤` / `多机合并`；
- 顶部第一行为 **时间区间** 切换：`今日` / `近7天` / `近30天` / `全部`，以及 `⟳` 刷新、`–` 最小化、`✕` 隐藏；
- `商汤` 页底部为同步设置面板（见下节）；
- `多机合并` 页为多机数据源管理与按机统计（见第 5 节）。

---

## 4. 商汤积分自动同步配置

商汤官方未提供积分查询 API，本工具通过「抓取官网控制台接口」实现自动同步：

1. 浏览器打开商汤控制台「积分额度」页；
2. 按 **F12** → **Network（网络）**；
3. 刷新页面，找到响应中含有积分数字的请求（如 `tokenplan/pool-usage`）；
4. 在该请求上 **右键 → Copy → Copy as cURL**；
5. 回到工具「商汤」页底部的 **同步设置** 面板，粘贴 cURL，点击 **保存并测试**；
6. 字段由程序**零指纹自动识别**，无需手动填写任何数字。

> 说明：
> - 同步凭据（JWT）约 **3 小时**过期；过期后余额回退到**本地估算**并提示重新抓包。
> - 程序每 **5 分钟**自动更新一次；点卡片 `⟳` 可立即强制刷新。
> - **活动固定积分**仅来自接口返回；未配置同步时为占位状态。

如不再需要，点击「清除配置」即可回到本地估算模式。

---

## 5. 多机数据源合并

多台电脑的用量数据互相独立。本工具提供「导出 → 导入 → 合并展示」的闭环，用于把多台机器的数据汇总到一起查看。

> 单机统计仍以**本机实时扫描**为准；别机数据以**快照文件**形式常驻在本机，随时可删除或覆盖更新。导入**绝不会影响本机原有数据**。

### 5.1 为机器命名

首次使用先给本机起个名字（如「台式机」「笔记本」），导出时用于标识来源。在「多机合并」页点「改名」即可。

### 5.2 导出本机数据

在「多机合并」页点 **⬆ 导出本机数据** → 选择保存位置 → 生成一个 JSON 数据包（默认在桌面），其中**包含 WorkBuddy 与 DSH 两个来源的全部记录**。

### 5.3 导入别机数据

把数据包拷到另一台电脑，点 **⬇ 导入别机数据** 选择该文件即可。

- 数据按**机器名分别存放**（`peers/<机器名>.json`），互不干扰；
- 同一台机器重复导入会**更新为该机最新快照**（不会重复累加）；
- 「已导入的机器」列表中每行可 **覆盖更新**（重新选择该机的新数据包）或 **删除**。

### 5.4 查看合并结果

导入后，「多机合并」页的**按机统计**会列出每台机器（🖥 本机 / 💻 别机）的 token 总量、请求数与日期区间，按总量降序排列，顶部显示合计与机器数。

---

## 6. 视觉设计系统（面向维护者）

全程序走同一套「液态玻璃」语言，新增界面必须复用以下基座，不要另起样式。

### 6.1 按钮：四档统一工厂

所有按钮经 `make_btn(kind, text)` 创建、`style_btn(btn, ...)` 重刷：

| kind | 用途 | 外观 |
|---|---|---|
| `primary` | 每个面板的**主操作**（导出 / 保存 / 删除确认） | 实心蓝底白字，hover 加深 |
| `ghost` | 次要操作（改名 / 覆盖更新） | 透明底 + 描边，hover 转蓝 |
| `danger` | 破坏性操作（删除） | 同 ghost，hover 转红 |
| `icon` | 标题栏轻量开关 | 无边框，仅 hover 底色 |

改主题或字号后**必须重调 `style_btn`**，否则按钮颜色不跟随（QSS 不会自动重算）。

### 6.2 弹窗：一律自绘，禁用原生

`QMessageBox` / `QInputDialog` 的字体与圆角跟卡片语言完全不搭，**已全部替换**：

- `dlg_confirm(parent, title, msg, ok_text, icon)` → `bool`
- `dlg_notify(parent, title, msg, error)` → 单按钮通知
- `dlg_prompt(parent, title, msg, default, label)` → `(text, ok)`

底层是 `GlassDialog`（`GlassPodFrame` 子类）：同款圆角 + 菲涅尔描边 + `DlgIcon` 语义圆形徽章 + 可拖拽标题区 + `Esc` 取消 / `Enter` 确认。需要输入框时调 `add_field(label, text, placeholder)`。

### 6.3 侧边导航：纯自绘

`NavButton` 不套 QSS（否则与自绘叠加成双重背景），`paintEvent` 里画：

- 左侧 3px 竖条**选中指示器**（淡入 + 垂直居中）
- 固定 22px **图标槽**，图标居中 → 四个按钮的文字左边界严格对齐
- 选中态蓝色柔和填充 + 文字加粗变色；hover 态中性浅填充（与选中态可区分）

新增数据源时，**记得把新按钮加进 `apply_styles` 的所有 `for b in (...)` 循环**——历史上 `btn_nav_multi` 就漏过一次，导致它没有统一背景样式。

### 6.4 卡片与彩点标题

- 卡片底板用 `GlassPodFrame(radius=12)`，不要手写 `QSS` 背景。
- 每个面板头 = `BarIndicator(accent)` 小细条 + 加粗标题 + 右侧说明胶囊（`_panel_head()` 工厂）。
- 颜色语义：蓝=WorkBuddy/本机，紫=DSH/别机，绿=统计，橙=告警，红=错误。

### 6.5 主题联动（易踩坑）

`set_dark` / `set_glass` 只调 `update()` **不会重算 QSS**。子页面（`sn_page` / `multi_page`）必须经 `_refresh_subpages_theme()` 显式重刷，否则切暗色后页面保留旧主题的文字颜色。

**自绘控件从 `TEXT` / `TEXT2` / `TEXT3` 等全局调色板取值**，`refresh_palette()` 后会自动正确——不要缓存颜色到实例属性。

---

## 7. 贡献指南（面向维护者）

### 7.1 开发与调试

```bash
# 运行主程序（用 pyside6 venv 的 pythonw，无控制台窗口）
~/.workbuddy/binaries/python/envs/pyside6/Scripts/pythonw.exe card_app.py

# 单独调试扫描引擎（输出聚合摘要）
~/.workbuddy/binaries/python/envs/pyside6/Scripts/python.exe scanner.py --force

# 运行回归测试（必须在 offscreen 下，用 pyside6 venv）
QT_QPA_PLATFORM=offscreen \
  ~/.workbuddy/binaries/python/envs/pyside6/Scripts/python.exe test_switch_race.py

# 全项目语法检查
~/.workbuddy/binaries/python/envs/pyside6/Scripts/python.exe tools/syntax_check.py
```

> 测试覆盖：切页 race 防护、同步数学、cURL 解析、指纹/零指纹、真实接口样例、单列渲染、窗口位置统一、代理 10061 直连重试、多机数据源（导出/导入/合并/覆盖/命名）、视觉基座（按钮工厂/自绘弹窗/导航自绘/主题联动/排行条），共 **192 项断言**，需全过。

> **截图复核技巧**：`QT_QPA_PLATFORM=offscreen` 下 Qt 找不到系统字体，需手工 `QFontDatabase.addApplicationFont()` 注册 `C:\Windows\Fonts\msyh.ttc` 等，否则中文全是豆腐块。另外 `widget.grab()` 会把圆角外的透明区合成成 `#efefef` 灰，**不要据此误判卡片底色**——要看真实底色请 `grab()` 整个窗口并按坐标采样。

### 7.2 代码规范

- **语言**：Python；UI 用 PySide6；扫描/HTTP 仅用标准库（不引入第三方网络库，venv 无 requests）。
- **主题**：颜色一律走 `refresh_palette()` 全局调色板，经 `qrgba()` / `qname()` 输出样式表；禁止散落硬编码颜色。
- **布局**：卡片宽度锁定 664px；长数字卡片用**竖向堆叠**避免横向截断（参考 `SNPromoCard`）。
- **窄面板**：多机页等窄列场景优先**两行式**布局（上信息 / 下操作），不要硬塞横向多列——窄宽下必然互相挤压截断。
- **商汤同步**：优先扩展零指纹结构探测；改动 `pools[]` 字段映射务必同步更新测试 fixture。
- **Windows 安全**：托管 Python 严禁进入交互 REPL（用 `python -c` / `python script.py` / heredoc），避免拖垮客户端。
- **数据层**：多机导入/导出的格式与合并语义集中在 `peer_store.py`（纯标准库），UI 只负责调用；改动 `FORMAT_ID` 或字段名务必同步更新测试 fixture 与 §5 文档。

### 7.3 提交流程（Git · 本地仓库）

1. 在 `pyside6` venv 下 `python -m py_compile card_app.py scanner.py peer_store.py`；
2. 跑 `test_switch_race.py` 确认 192 项全绿；
3. **先更新根目录《协作进度.md》**（§二 演进历程 + §八 协作者备注登记本轮）；
4. 定点 `git add` 相关文件后提交，信息格式：`第N轮：<一句话说明>`；**勿用 `add -A`**；
5. 仓库仅本地管理，**不 `git push`**、不添加远程；回滚用 `git log --oneline` 查哈希。

---

## 8. 目录导航

```
token-stats/
├── card_app.py          # 主程序（UI + 商汤同步）
├── scanner.py           # 增量扫描聚合
├── peer_store.py        # 多机数据源：导出/导入/合并/命名
├── test_switch_race.py  # 回归测试（192 项）
├── 协作进度.md           # ★ 主协作文档（架构/演进/Git 规范/备注区）
├── start_card.bat       # 启动器（规范名）
├── 启动统计悬浮球.bat    # 启动器别名
├── 启动统计悬浮球.vbs    # 静默启动（日常主推）
├── enable_autostart.bat # 开机自启
├── legacy/              # 已弃用旧方案（app.py / panel.html，不入库）
└── docs/assets/previews/ # 界面预览图
```

- 协作与版本管理：[`协作进度.md`](协作进度.md)
- 外部数据/配置目录：`~/.workbuddy/plugins/data/token-usage-stats/`
- 别机数据源目录：`~/.workbuddy/plugins/data/token-usage-stats/peers/`

---

*本 README 面向使用者速览；《协作进度.md》为主协作文档，二者需同步维护。*
