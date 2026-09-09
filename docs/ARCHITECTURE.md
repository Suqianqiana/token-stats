# Token 审计卡片 · 架构与开发文档

> 面向多人协作维护。本文说明小工具的整体架构、核心功能、关键实现逻辑，并给出目录结构与迭代进度，帮助新成员快速理解并接手。
> 项目根目录使用说明见同级 [`README.md`](../README.md)。

---

## 1. 实现说明

### 1.1 产品定位

「Token 审计卡片」是一个常驻桌面的轻量统计浮窗，用于审计 WorkBuddy / DSH 会话的 Token 用量，以及商汤（SenseNova / 日日新）模型的积分额度。

- 屏幕右下角常驻 **悬浮球**（置顶、可拖动、位置记忆）；
- 单击悬浮球弹出 **卡片窗口**（无边框圆角、液态玻璃主题、可拖动、置顶）；
- 卡片内可切换数据源：**WorkBuddy / DSH / 商汤积分**；
- 商汤积分支持 **自动同步**（抓取官网控制台接口 cURL），无需手动填数。

### 1.2 整体架构

```
                 ┌──────────────────────────────────────────────┐
                 │                   main()                       │
                 │  QApplication(Fusion) → load_settings()        │
                 │  → BallWindow(悬浮球) + CardWindow(主卡片)     │
                 └──────────────────────────────────────────────┘
                    │                              │
        ┌───────────┴───────────┐      ┌──────────┴──────────────────┐
        │  BallWindow (悬浮球)   │      │  CardWindow (卡片主窗口)      │
        │  - 常驻右下角          │      │  - 无边框/置顶/可拖动        │
        │  - 单击弹出卡片        │      │  - 三数据源 Tab + 时间区间    │
        │  - 右键菜单            │      │  - 后台线程扫描(RefreshBridge)│
        └───────────────────────┘      └──────────┬──────────────────┘
                                                   │
                       ┌───────────────────────────┼───────────────────────────┐
                       │                           │                           │
                 content_old (WB/DSH)        SNQuotaPage (商汤)          主题/样式系统
                 - 2×2 汇总卡                 - SNPoolCard ×2            THEMES/GLASS_ALPHA
                 - 模型明细表                 - SNPromoCard             refresh_palette()
                 - 堆叠柱状图                 - SNSyncPanel(内嵌)       qrgba()/qname()
                 - GitHub 热力图              - 自动同步零指纹探测
                       │                           │
                 ┌─────┴─────┐             ┌───────┴────────┐
                 │ scanner.py │             │ sn_autosync_*() │
                 │ 增量扫描    │             │ parse_curl/_http│
                 │ 聚合 WB 数据│             │ _detect_paths   │
                 └───────────┘             └────────────────┘
```

**分层职责**

| 层 | 文件 | 职责 |
|---|---|---|
| 入口 | `card_app.py :: main()` | 初始化 QApplication、悬浮球、主窗口、延迟加载数据 |
| 数据·WB | `scanner.py` | 增量扫描 `~/.workbuddy/projects/**/*.jsonl`，聚合 Token 用量 |
| UI·主 | `card_app.py :: CardWindow` | 卡片窗口、Tab 切换、后台扫描调度、race 防护、主题 |
| UI·商汤 | `card_app.py :: SNQuotaPage` 等 | 积分池卡片渲染、cURL 自动同步、结构探测 |
| UI·浮球 | `card_app.py :: BallWindow` | 悬浮球绘制、拖动、弹出卡片、右键菜单 |
| 样式 | `card_app.py :: refresh_palette()` | 深浅色 / 玻璃模式全局调色板 |

### 1.3 核心功能

1. **WB / DSH Token 用量统计**
   - 数据窗口区间切换：今日 / 近 7 天 / 近 30 天 / 全部；
   - 2×2 汇总卡：合计 Token / 缓存命中（率%）/ 输入·输出 / 会话·请求；
   - 今日条 + 按模型明细列表（彩点 + 比例条 + 总量 + 占比% + 缓存命中率 + 请求数）；
   - 每日堆叠柱状图（前 8 模型着色）、GitHub 风活跃热力图。
2. **商汤积分额度页**
   - 双积分池卡片：**通用积分池**（紫，所有 Free 模型）、**Flash-Lite 专属积分池**（橙，仅 Flash-Lite 系列）；
   - **活动固定积分**卡片：Flash-Lite 消费 1:1 返赠（30 天有效）的总量与最近到期；
   - 进度条按官方口径：本周余额（周）/ 5h 窗口剩余·占比（5h）/ 官方重置时间；
   - 内嵌 **同步设置面板**：粘贴官网接口 cURL → 自动识别字段 → 实时同步。
3. **外观与交互**
   - 液态玻璃主题、深浅色、可切换；圆角卡片、无边框、置顶、可拖动、位置记忆；
   - 悬浮球常驻、单击弹出、右键菜单（打开 / 刷新 / 退出）。
4. **运行集成**
   - 窗口固定宽 664px、高度按内容自适应（上限 1000px）；
   - 支持 Windows 开机自启（`enable_autostart.bat`）。

### 1.4 关键实现逻辑

#### 1.4.1 数据来源与增量扫描（scanner.py）

- 读取 `~/.workbuddy/projects/**/*.jsonl`，从每条消息的 `providerData.usage`（camelCase：`inputTokens` / `outputTokens` / `totalTokens` / `inputTokensDetails[].cached_tokens` / `outputTokensDetails[].reasoning_tokens`）提取用量；
- **增量策略**：以 `(mtime_ns, size)` 作为每个文件的签名，未变化的文件直接复用历史聚合（`cache.json`），仅变化或被重写的文件重新解析；首次扫描约 14s，命中缓存后约 0.16s；
- 聚合结果写入 `stats.json`（含每模型 / 每日 / 会话统计），供 UI 直接消费。

#### 1.4.2 主题系统

- `THEMES` 定义 light/dark 调色板，`GLASS_ALPHA` 定义玻璃模式的透明度；
- `refresh_palette()` 根据 `theme_state["dark"/"glass"]` 生成全局色 `BG/CARD/BORDER/TEXT/TEXT2/TEXT3/TRACK/HOVER/ZEBRA`；
- 颜色经 `qrgba()` / `qname()` 输出为 Qt 样式表字符串，集中管理，避免散落硬编码；
- 切换主题时调用 `CardWindow.apply_styles()` 与各处 `apply_theme()` 重刷。

#### 1.4.3 后台扫描与切页 race 防护

- 扫描在后台线程执行，通过 `RefreshBridge.done` 信号回传结果；
- 信号携带 **发起源快照**（src）；若结果到达时用户已切到别的源，则只入 `_sn_cache` 不渲染；
- 扫描期间若发生源切换，置 `_pending_refresh`，扫描结束 `_kick_pending()` 补刷，避免“卡片被拉长 / 需再点一次才恢复”的问题。

#### 1.4.4 商汤积分同步（零指纹 + 频控）

- 用户从官网「积分额度」页 F12 → Network 复制接口 cURL，粘贴到 `SNSyncPanel`；
- `parse_curl()` 手写 tokenizer（兼容 bash / cmd `^` 续行与引号转义）→ `_http_json()`（标准库 urllib，无第三方依赖）发请求；
- `_detect_paths_by_structure()` **零指纹结构探测**：依据商汤响应自带的 `pools[].pool_type` / 名称直接认字段（数字无需填写），比早期按数字值定位更稳；
- `sn_autosync_fetch(force=)` 带 **300s 进程内频控**；`load_sn_stats()` 取值优先级：**auto 实时 > manual 回退 > 本地估算**；
- 凭据（JWT）约 3 小时过期，过期自动回退手动回退值（`sn_points_sync.json`）并提示；auto 模式 remaining 透传接口原始字符串数字，避免浮点往返误差。

#### 1.4.5 窗口定位

- `place_right()` 固定 **基准高度 880** 做垂直居中（`(scr.height()-880)//2`），使 WB/DSH 页（高 880）与商汤页（较矮）**顶部对齐**，切页后窗口位置不漂移。

#### 1.4.6 卡片布局（防截断）

- `SNPromoCard` 采用 **竖向堆叠**：标题 + scope 各一行，总量余额独占一行（Consolas 21pt Bold，千分位），最近到期另起一行；避免长数字被单行挤到右侧截断；
- `SNPoolCard` 底部改为靠左一行（`周额度 600,000 · 下次周重置 …`），不再用 `addStretch` 把信息推到右侧外。

### 1.5 运行环境

- Python 3.13（托管运行时）+ 虚拟环境 `~/.workbuddy/binaries/python/envs/pyside6`；
- 依赖仅 **PySide6 6.11.1**（桌面 UI），其余（扫描、HTTP、JSON）均为标准库；
- 启动器用 `pythonw.exe` 运行，无控制台窗口。

---

## 2. 目录结构

### 2.1 树状图（整理后）

```
token-stats/
├── card_app.py              # 【主程序】PySide6 卡片窗口 + 悬浮球 + 商汤积分页
├── scanner.py               # 【数据层】jsonl 增量扫描聚合引擎（标准库）
├── test_switch_race.py      # 【测试】offscreen 回归测试（52 项断言）
├── start_card.bat           # 【启动】ASCII 启动器（主入口，双击运行）
├── 启动统计悬浮球.bat        # 【启动】中文别名启动器（内容同 start_card.bat）
├── 启动统计悬浮球.vbs        # 【启动】静默启动（无控制台窗口）
├── enable_autostart.bat     # 【启动】注册 Windows 开机自启
├── README.md                # 【文档】项目说明（根目录）
├── legacy/                  # 【归档】已弃用的旧方案（不再被调用）
│   ├── app.py               #   旧 tkinter 悬浮球 + 本地 HTTP 面板方案
│   └── panel.html           #   旧网页版统计面板
├── docs/                    # 【文档】开发资料
│   ├── ARCHITECTURE.md      #   本文：架构与开发文档
│   └── assets/
│       └── previews/        #   界面预览截图（开发验证用）
│           ├── preview_sn_v3.png
│           └── preview_sn_promo_fix.png
└── __pycache__/             # Python 字节码缓存（应加入 .gitignore，忽略）
```

> 外部数据与运行文件（**不在项目仓库内**，位于用户目录）：
> - 数据来源：`~/.workbuddy/projects/**/*.jsonl`
> - 持久化目录：`~/.workbuddy/plugins/data/token-usage-stats/`
>   - `cache.json`（增量游标）、`stats.json`（聚合结果）
>   - `sn_autosync.json`（商汤自动同步配置 + 字段路径）、`sn_points_sync.json`（手动回退值）
>   - `settings.json`（主题 / 数据源等设置）、`ball_pos.json`（悬浮球位置记忆）

### 2.2 各目录 / 文件职责

| 路径 | 职责 | 维护要点 |
|---|---|---|
| `card_app.py` | 全部 UI 与商汤同步逻辑 | 体积最大（~127KB）；改动后跑 `test_switch_race.py` |
| `scanner.py` | WB/DSH 用量扫描聚合 | 纯标准库，独立于 UI，可单独 `python scanner.py --force` 调试 |
| `test_switch_race.py` | 回归测试 | 必须在 `QT_QPA_PLATFORM=offscreen` 下用 pyside6 venv 运行 |
| `start_card.bat` 等 | 启动 / 自启 | 路径硬编码到本机 venv，换机需更新 |
| `legacy/` | 历史方案归档 | 仅阅读参考，勿在新功能中引用 |
| `docs/` | 文档与素材 | 改动设计后同步更新本文与 README |

### 2.3 整理说明（本轮）

- 已弃用的 `app.py` / `panel.html` 由根目录移入 `legacy/`；
- 开发预览图 `preview_sn_*.png` 由根目录移入 `docs/assets/previews/`；
- README 由旧版（描述旧悬浮球方案）重写为当前 `card_app.py` 方案；
- 启动脚本保留 `start_card.bat`（规范入口）、`启动统计悬浮球.vbs`（静默）、`enable_autostart.bat`（自启）；中文 `.bat` 与 `start_card.bat` 内容相同，作为用户友好别名保留。

---

## 3. 迭代进度

### 3.1 当前版本

- **版本标识**：CardWindow V7（分层液态玻璃 + 深色模式）
- **最近迭代**：2026-09 商汤积分页重构 + 自动同步 + 布局防截断
- **代码规模**：`card_app.py` ~3100 行，`scanner.py` ~270 行，测试 52 项断言全过

### 3.2 已完成功能

- [x] WB / DSH Token 用量统计（2×2 汇总、模型明细、堆叠柱状图、活跃热力图）
- [x] 时间窗口切换（今日 / 近 7 天 / 近 30 天 / 全部）
- [x] 液态玻璃主题 + 深浅色切换
- [x] 无边框圆角卡片、置顶、可拖动、位置记忆
- [x] 右下角悬浮球（单击弹出、右键菜单）
- [x] 增量扫描性能优化（14s → 0.16s）
- [x] 商汤积分额度独立页（通用池 / Flash-Lite 池 / 活动固定积分）
- [x] 商汤自动同步（cURL 零指纹结构探测 + 手动回退 + 300s 频控）
- [x] 切页跨源渲染 race 修复、窗口默认位置统一（顶部对齐）
- [x] 卡片布局防右侧截断优化
- [x] 回归测试体系（offscreen，52 项）

### 3.3 已知限制 / 待办

- [ ] 商汤无官方积分 API，自动同步依赖用户抓包 cURL；JWT 凭据约 3 小时过期，过期后回退手动值并提示重抓；
- [ ] 活动固定积分为接口返回值，非本地估算；未配置同步时该卡为占位；
- [ ] offscreen 测试环境下中文显示为方框（缺字体），仅影响测试截图，不影响实机；
- [ ] 启动脚本中的 venv 路径硬编码到本机，跨设备分发需改路径或改为相对探测；
- [ ] `legacy/` 旧方案尚未删除（留作参考），后续稳定后可移除。

---

*文档维护建议：任何影响架构或用户操作的改动（新增页面、改启动方式、改同步逻辑）都应同步更新本文件与 `README.md`。*
