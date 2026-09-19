# Token 审计卡片（Token Audit Card）

> 常驻桌面的轻量 Token 用量审计浮窗：统计 WorkBuddy / DSH 会话的 Token 消耗，实时查看商汤（SenseNova / 日日新）模型积分额度，并支持多台机器用量合并。
> 桌面端 PySide6 程序，无后端依赖，数据全部来自本地 WorkBuddy 会话记录与本地运行数据目录。
> 当前版本 **v9.1-pet-v4**。

> 代码托管在 GitHub：**https://github.com/Suqianqiana/token-stats**（默认分支 `main`；当前为公开仓库，可见性可在仓库 Settings → Danger Zone 中调整）。

---

## 1. 项目简介

「Token 审计卡片」由两部分组成：

- **悬浮球**：屏幕右下角常驻（置顶、可拖动、位置记忆），单击弹出统计卡片，右键打开菜单。
- **卡片窗口**：无边框圆角、液态玻璃主题、可拖动；内置四个数据源 **WorkBuddy / DSH 本地 / 商汤额度 / 多机合并**，并支持深浅色切换。

核心能力一览：

| 模块 | 能力 |
|---|---|
| WB / DSH 用量 | 2×2 汇总卡、按模型明细、堆叠柱状图、GitHub 风活跃热力图；支持今日/近7天/近30天/全部 |
| 多机合并 | 单列纵向三段（数据源管理 / 按机统计 / 已导入机器）；导出本机数据（WB + DSH 全部记录）、**导入/更新别机数据**（新机器导入、同名机器覆盖更新）；机器框内嵌改名热区 |
| 商汤额度 | 通用积分池、Flash-Lite 专属积分池、活动固定积分（1:1 返赠）；支持 cURL 零指纹自动同步 |
| 交互 | 无边框置顶卡片、悬浮球、位置记忆、右键菜单、深浅色 / 玻璃主题；全程序统一自绘弹窗与按钮语言 |
| 桌宠形态 | DeepSeek 娘帧动画（待机/入睡/拖拽/点击互动/摸摸头）；四个素材主题（v1 经典 / v2 高清 / v3 最新合并 / v4 deepseek娘V4Pro）右键菜单切换；双击打开统计面板 |

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

- 顶部第二行为 **数据源** 切换：`WorkBuddy` / `DSH 本地` / `商汤额度` / `多机合并`；
- 顶部第一行为 **时间区间** 切换：`今日` / `近7天` / `近30天` / `全部`，以及 `⟳` 刷新、`–` 最小化、`✕` 隐藏；
- `商汤额度` 页底部为同步设置面板（见第 4 节）；
- `多机合并` 页为多机数据源管理与按机统计（见第 5 节）。

---

## 4. 商汤积分自动同步配置

商汤官方未提供积分查询 API，本工具通过「抓取官网控制台接口」实现自动同步：

1. 浏览器打开商汤控制台「积分额度」页；
2. 按 **F12** → **Network（网络）**；
3. 刷新页面，找到响应中含有积分数字的请求（如 `tokenplan/pool-usage`）；
4. 在该请求上 **右键 → Copy → Copy as cURL**；
5. 回到工具「商汤额度」页底部的 **同步设置** 面板，粘贴 cURL，点击 **保存并测试**；
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

首次使用先给本机起个名字（如「台式机」「笔记本」），导出时用于标识来源。

**点名字框即可就地改名，不再弹窗**：点一下机器名区域进入编辑态，输入框已预填当前名字并全选，改完后：

| 操作 | 结果 |
|---|---|
| 按 `Enter` / 点「保存」/ 点输入框外任意处 | **提交**新名字 |
| 按 `Esc` / 点「取消」 | **放弃**修改，恢复原名字 |

名字为空或与原名相同时不会落盘、不触发任何写入。改动会立刻写进本机配置，下次导出即用新名字标识。

### 5.2 导出本机数据

在「多机合并」页点 **⬆ 导出本机数据** → 选择保存位置 → 生成一个 JSON 数据包（默认在桌面），其中**包含 WorkBuddy 与 DSH 两个来源的全部记录**。

### 5.3 导入 / 更新别机数据

把数据包拷到另一台电脑，点 **⬇ 导入/更新别机数据** 选择该文件即可。这一个按钮覆盖两种情形：

| 情形 | 行为 |
|---|---|
| 包内机器名**从未出现过** | 作为**一台新机器**加入统计（提示「新机器已导入」） |
| 包内机器名**已存在** | 视为同一台机器的新快照，**覆盖其旧数据**（提示「已覆盖更新同名机器」，不是累加） |

- 数据按**机器名分别存放**（`peers/<机器名>.json`），互不干扰；
- 导入**绝不会影响本机数据**，也不会影响其他机器的快照；
- 「已导入的机器」列表中每行可 **覆盖更新**（重新选择该机的新数据包，会校验机器名是否匹配）或 **删除**。

### 5.4 查看合并结果

导入后，「多机合并」页按**单列纵向三段**组织：

1. **数据源管理** —— 左侧是本机机器框（含「改名」热区），右侧是「导出本机数据」与「导入/更新别机数据」两个按钮；
2. **按机统计** —— 通栏列出每台机器（🖥 本机 / 💻 别机）的 token 总量、请求数与日期区间，按总量降序排列，顶部显示合计与机器数；
3. **已导入的机器** —— 通栏列出全部别机快照及其导入时间、来源徽标。

---

## 6. 桌宠形态

桌宠随卡片呼吸动画呈现，**双击**悬浮球或右键菜单「打开面板」进入统计面板；右键菜单可在四个素材主题间切换：

| 主题 | 名称 | 素材目录 |
|---|---|---|
| `v1` | 经典素材（旧版） | `assets/pet` |
| `v2` | 新版素材（高清） | `assets/pet_v2` |
| `v3` | 最新素材（与原版合并） | `assets/pet_v3r` |
| `v4` | deepseek娘V4Pro | `assets/pet_v4` |

互动姿态：待机、入睡（随机）、拖拽（随机姿势）、点击互动（角色**顶部 1/3 为摸摸头、底部 2/3 为点击**，分区以 `paintEvent` 记录的「实际绘制区」`_pet_draw_rect` 的 1/3 为准，不按窗口算）。退役帧存档在 `assets/pet_alt/`、补充帧源在 `assets/pet_v3_add/`，二者被回归测试读取，**勿动**。

---

## 7. GitHub 协作与跨机同步

代码托管在 **https://github.com/Suqianqiana/token-stats**，默认分支 **`main`**。两位协作者通过 `git clone` / `pull` / `push` 协同开发（第 56 轮接入）。

### 7.1 首次接入（另一台机器）

```bash
git clone https://github.com/Suqianqiana/token-stats.git
cd token-stats
# 提交身份（让提交关联到 GitHub 账号，且不暴露真实邮箱）
git config user.email "318013379+Suqianqiana@users.noreply.github.com"
git config user.name  "浅浅猫"
```

推送 / 拉取需要 GitHub 凭据：本机可双击 **`推送到GitHub.bat`**（走浏览器授权，凭据进 Windows 凭据管理器，只需一次）；或使用 Personal Access Token（fine-grained PAT 需开启 `Contents: Read and write` 权限）。

### 7.2 日常节奏

**开工先 `git pull`，收工 `git push`**；只在 `main` 上协作。

### 7.3 三条硬规矩

1. **禁止 `rebase` / `amend` 已推送的提交。** 一旦重写历史，另一台机器的 commit hash 会全部对不上（第 54 轮正是靠「同一 commit 即同源」确认两边一致）。
2. **`_archive/` 永远不随 git 同步**（在 `.gitignore` 里）—— 归档区是「本机磁盘整理」的产物，换机器需要时得单独拷贝。
3. **本机运行期数据不在仓库里**（`~/.workbuddy/plugins/data/token-usage-stats/`）。跨机共享用量走程序内「导出 / 导入别机数据」，别把数据塞进仓库。

---

## 8. 视觉设计系统（面向维护者）

全程序走同一套「液态玻璃」语言，新增界面必须复用以下基座，不要另起样式。

### 8.1 按钮：四档统一工厂

所有按钮经 `make_btn(kind, text)` 创建、`style_btn(btn, ...)` 重刷：

| kind | 用途 | 外观 |
|---|---|---|
| `primary` | 每个面板的**主操作**（导出 / 保存 / 删除确认） | 实心蓝底白字，hover 加深 |
| `ghost` | 次要操作（改名 / 覆盖更新） | 透明底 + 描边，hover 转蓝 |
| `danger` | 破坏性操作（删除） | 同 ghost，hover 转红 |
| `icon` | 标题栏轻量开关 | 无边框，仅 hover 底色 |

改主题或字号后**必须重调 `style_btn`**，否则按钮颜色不跟随（QSS 不会自动重算）。

### 8.2 弹窗：一律自绘，禁用原生

`QMessageBox` / `QInputDialog` 的字体与圆角跟卡片语言不搭，**已全部替换**为 `GlassDialog`（`QDialog` 子类，玻璃底面 + 菲涅尔描边 + `DlgIcon` 语义圆形徽章 + 可拖拽标题区 + `Esc` 取消 / `Enter` 确认）。需要输入框时调 `add_field(label, text, placeholder)`；建好 `QLineEdit` 后必须补一次 `apply_theme()`，并逐层 `invalidate()` 重算高度（否则输入框会被裁或渲染成纯白）。

### 8.3 侧边导航 / 卡片 / 主题联动

- `NavButton` 纯自绘（左侧 3px 选中竖条 + 固定 22px 图标槽），新增数据源要把新按钮加进 `apply_styles` 的**所有** `for b in (...)` 循环。
- 卡片底板用 `GlassPodFrame(radius=12)`；面板头 = `BarIndicator(accent)` 小细条 + 加粗标题 + 右侧说明胶囊（`_panel_head()` 工厂）。
- `set_dark` / `set_glass` 只调 `update()` **不会重算 QSS**；子页面必须经 `_refresh_subpages_theme()` 显式重刷。局部 `setStyleSheet` 会「顶掉」全局 QSS，滚动条样式必须打包重设（`style_scroll_area()`）。
- 自绘控件颜色一律走全局调色板（`TEXT` / `TEXT2` / `TEXT3`…），不要缓存到实例属性。

更多视觉坑（双层玻璃叠加、列表重绘必须清空 spacer、骨架占位行、切页不依赖后台回调）记录在 [`协作进度.md`](协作进度.md) 对应轮次。

---

## 9. 开发、调试与发布

### 9.1 常用命令

```bash
# 运行主程序（用 pyside6 venv 的 pythonw，无控制台窗口）
~/.workbuddy/binaries/python/envs/pyside6/Scripts/pythonw.exe card_app.py

# 单独调试扫描引擎（输出聚合摘要）
~/.workbuddy/binaries/python/envs/pyside6/Scripts/python.exe scanner.py --force

# 全量语法检查（内存编译，不写 .pyc —— 避免火绒误杀字节码）
~/.workbuddy/binaries/python/envs/pyside6/Scripts/python.exe tools/syntax_check.py

# 回归测试（必须在 offscreen 下，用 pyside6 venv）
QT_QPA_PLATFORM=offscreen \
  ~/.workbuddy/binaries/python/envs/pyside6/Scripts/python.exe test_switch_race.py
```

> **回归覆盖**：切页 race 防护、同步数学、cURL 解析、指纹/零指纹、真实接口样例、单列渲染、窗口位置统一、代理 10061 直连重试、多机数据源（导出/导入/合并/覆盖/命名）、导入语义（新增 vs 覆盖）、视觉基座（按钮工厂/自绘弹窗/导航自绘/主题联动/排行条）、暗色输入框、内联改名、骨架占位行 —— **200+ 项断言**，需全过。
>
> **截图复核技巧**：`QT_QPA_PLATFORM=offscreen` 下 Qt 找不到系统字体，需手工 `QFontDatabase.addApplicationFont()` 注册 `C:\Windows\Fonts\msyh.ttc` 等，否则中文全是豆腐块。另外 `widget.grab()` 会把圆角外的透明区合成成 `#efefef` 灰，**不要据此误判卡片底色**——要看真实底色请 `grab()` 整个窗口并按坐标采样。

### 9.2 代码规范

- **语言**：Python；UI 用 PySide6；扫描/HTTP 仅用标准库（不引入第三方网络库，venv 无 requests）。
- **主题**：颜色一律走 `refresh_palette()` 全局调色板，经 `qrgba()` / `qname()` 输出样式表；禁止散落硬编码颜色。
- **布局**：卡片宽度锁定 664px；长数字卡片用**竖向堆叠**避免横向截断（参考 `SNPromoCard`）。窄面板优先**两行式**布局（上信息 / 下操作），不要硬塞横向多列。
- **商汤同步**：优先扩展零指纹结构探测；改动 `pools[]` 字段映射务必同步更新测试 fixture。
- **Windows 安全**：托管 Python 严禁进入交互 REPL；语法检查走 `tools/syntax_check.py`（不写 `.pyc`，规避火绒误杀）。
- **数据层**：多机导入/导出的格式与合并语义集中在 `peer_store.py`（纯标准库），UI 只负责调用；改动 `FORMAT_ID` 或字段名务必同步更新测试 fixture 与 §5 文档。

### 9.3 提交与推送流程（Git · GitHub）

1. 跑 `tools/syntax_check.py` 确认无语法错误；
2. `QT_QPA_PLATFORM=offscreen python test_switch_race.py` 确认 200+ 项全绿；
3. **先更新根目录《协作进度.md》**（§二 演进历程 + §八 协作者备注登记本轮）；
4. 定点 `git add` 相关文件后提交，信息格式：`第N轮：<一句话说明>`；**勿用 `add -A`**；
5. `git push` 推到 `origin/main`（首次授权见 §7.1；凭据已存则直接推）。

---

## 10. 目录导航

```
token-stats/
├── card_app.py          # 主程序（UI + 商汤同步 + 桌宠），当前 v9.1-pet-v4
├── scanner.py           # 增量扫描聚合
├── peer_store.py        # 多机数据源：导出/导入/合并/命名（纯标准库）
├── launcher.py          # 轻启动器源码（不含 PySide6）
├── sn_login.py          # 商汤登录
├── sn_autologin_fetch.py# 商汤积分抓取
├── test_switch_race.py  # offscreen 回归测试（200+ 项断言）
├── 协作进度.md           # ★ 主协作文档（架构/演进/Git 规范/备注区）
├── README.md            # 本文件
├── .gitignore           # 版本库排除规则
├── TokenStats.exe       # 编译产物（launcher.py 的 PyInstaller onefile）
├── start_card.bat           # 启动器（规范名）
├── 启动统计悬浮球.bat       # 启动器别名
├── 启动统计悬浮球.vbs       # 静默启动（日常主推）
├── enable_autostart.bat     # 开机自启
├── 推送到GitHub.bat         # GitHub 首次授权 + 推送（双击即用）
├── 桌面图标指向exe.bat      # 桌面快捷方式
├── 商汤自动登录.bat         # 商汤登录入口
├── 重新打包exe.bat          # 重新打包 exe
├── assets/              # 现役素材
│   ├── pet/             #   v1 经典素材
│   ├── pet_v2/          #   v2 新版素材（高清）
│   ├── pet_v3r/         #   v3 最新素材（与原版合并）
│   ├── pet_v4/          #   v4 deepseek娘V4Pro
│   ├── pet_alt/         #   退役帧存档（测试依赖，勿动）
│   ├── pet_v3_add/      #   补充帧（测试依赖，勿动）
│   ├── app_icon.{ico,png}
│   └── *_qc.json / *_windows.json   # 各版本 QC 质检参考文件
├── docs/                # 文档与预览
│   ├── 素材饱和度优化.md
│   ├── V3补充素材清单.md
│   └── assets/previews/ #   界面预览图
├── tools/               # 现役脚本
│   ├── syntax_check.py      # 全量语法检查（内存编译，不写 pyc）
│   ├── restart_app.py       # 重启卡片应用
│   ├── build_exe.py         # 打包主程序 exe
│   ├── build_launcher.py    # 打包轻启动器
│   ├── make_app_icon.py     # 生成应用图标
│   └── metrics_regression.py# 指标回归
└── _archive/            # 归档区（不入库，见 _archive/README.md）
    ├── assets-debug/        #   根级调试截图
    ├── assets-pet-legacy/   #   桌宠历史版本
    ├── docs-reviews/        #   历史审查页
    ├── root-legacy/         #   根目录历史物
    └── tools-once/          #   一次性诊断脚本
```

**归档约定**（第 53 轮建立）：一切**历史备份、调试中间产物、一次性脚本、已废弃的审查页**统一放进 `_archive/` 对应分类，不进版本库；项目内只保留「跑起来必需 + 当前在维护」的东西。归档清单与取回方法见 [`_archive/README.md`](_archive/README.md)。

- 协作与版本管理：[`协作进度.md`](协作进度.md)
- 归档说明：[`_archive/README.md`](_archive/README.md)
- 外部数据/配置目录：`~/.workbuddy/plugins/data/token-usage-stats/`
- 别机数据源目录：`~/.workbuddy/plugins/data/token-usage-stats/peers/`

---

*本 README 面向使用者速览；《协作进度.md》为主协作文档，二者需同步维护。*
