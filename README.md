# Token 审计卡片（Token Audit Card）

> 常驻桌面的轻量 Token 用量审计浮窗：统计 WorkBuddy / DSH 会话的 Token 消耗，并实时查看商汤（SenseNova / 日日新）模型的积分额度。
> 桌面端 PySide6 程序，无后端依赖，数据全部来自本地 WorkBuddy 会话记录。

---

## 1. 项目简介

「Token 审计卡片」由两部分组成：

- **悬浮球**：屏幕右下角常驻（置顶、可拖动、位置记忆），单击弹出统计卡片，右键打开菜单。
- **卡片窗口**：无边框圆角、液态玻璃主题、可拖动；内置三个数据源 **WorkBuddy / DSH / 商汤积分**，并支持深浅色切换。

核心能力一览：

| 模块 | 能力 |
|---|---|
| WB / DSH 用量 | 2×2 汇总卡、按模型明细、堆叠柱状图、GitHub 风活跃热力图；支持今日/近7天/近30天/全部 |
| 商汤积分 | 通用积分池、Flash-Lite 专属积分池、活动固定积分（1:1 返赠）；支持 cURL 自动同步 |
| 交互 | 无边框置顶卡片、悬浮球、位置记忆、右键菜单、深浅色 / 玻璃主题 |
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

- 顶部第二行为 **数据源** 切换：`WorkBuddy` / `DSH` / `商汤`；
- 顶部第一行为 **时间区间** 切换：`今日` / `近7天` / `近30天` / `全部`，以及 `⟳` 刷新、`–` 最小化、`✕` 隐藏；
- `商汤` 页底部为同步设置面板（见下节）。

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

## 5. 贡献指南（面向维护者）

### 5.1 开发与调试

```bash
# 运行主程序（用 pyside6 venv 的 pythonw，无控制台窗口）
~/.workbuddy/binaries/python/envs/pyside6/Scripts/pythonw.exe card_app.py

# 单独调试扫描引擎（输出聚合摘要）
~/.workbuddy/binaries/python/envs/pyside6/Scripts/python.exe scanner.py --force

# 运行回归测试（必须在 offscreen 下，用 pyside6 venv）
QT_QPA_PLATFORM=offscreen \
  ~/.workbuddy/binaries/python/envs/pyside6/Scripts/python.exe test_switch_race.py
```

> 测试覆盖：切页 race 防护、同步数学、cURL 解析、指纹/零指纹、真实接口样例、单列渲染、窗口位置统一、代理 10061 直连重试，共 **67 项断言**，需全过。

### 5.2 代码规范

- **语言**：Python；UI 用 PySide6；扫描/HTTP 仅用标准库（不引入第三方网络库，venv 无 requests）。
- **主题**：颜色一律走 `refresh_palette()` 全局调色板，经 `qrgba()` / `qname()` 输出样式表；禁止散落硬编码颜色。
- **布局**：卡片宽度锁定 664px；长数字卡片用**竖向堆叠**避免横向截断（参考 `SNPromoCard`）。
- **商汤同步**：优先扩展零指纹结构探测；改动 `pools[]` 字段映射务必同步更新测试 fixture。
- **Windows 安全**：托管 Python 严禁进入交互 REPL（用 `python -c` / `python script.py` / heredoc），避免拖垮客户端。

### 5.3 提交流程（Git · 本地仓库）

1. 在 `pyside6` venv 下 `python -m py_compile card_app.py scanner.py`；
2. 跑 `test_switch_race.py` 确认 67 项全绿；
3. **先更新根目录《协作进度.md》**（§二 演进历程 + §八 协作者备注登记本轮）；
4. 定点 `git add` 相关文件后提交，信息格式：`第N轮：<一句话说明>`；**勿用 `add -A`**；
5. 仓库仅本地管理，**不 `git push`**、不添加远程；回滚用 `git log --oneline` 查哈希。

---

## 6. 目录导航

```
token-stats/
├── card_app.py          # 主程序（UI + 商汤同步）
├── scanner.py           # 增量扫描聚合
├── test_switch_race.py  # 回归测试（64 项）
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

---

*本 README 面向使用者速览；《协作进度.md》为主协作文档，二者需同步维护。*
