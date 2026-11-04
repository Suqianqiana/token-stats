# 项目索引（文件地图）

> 这份文件回答三个问题：**某个文件是干什么的**、**哪些文件不能动**、**想改某个东西该从哪进**。
> 技术细节看 [README.md](README.md)；完整开发历程看 [docs/协作进度.md](docs/协作进度.md)。

**项目**：Token 统计（Token Audit Card）—— Windows 桌面常驻的 Token 用量 / 商汤额度浮窗 + 桌宠。
**实体位置**：`D:\Deepseek-Harness-EAC\token-stats`（`%USERPROFILE%\WorkBuddy\2026-08-25-04-20-35\token-stats` 是指向这里的 Junction）。
**当前版本**：`APP_BUILD = v9.6-bubble`，PySide6 + 纯标准库扫描引擎，无后端。

---

## 一、日常使用：双击哪个

| 我想… | 双击这个 | 说明 |
| --- | --- | --- |
| 启动桌宠 | `启动统计悬浮球.vbs` | 静默启动（无黑框），推荐 |
| 启动（看得到控制台） | `start_card.bat` | 调试用，能看到报错 |
| 开机自启开关 | `enable_autostart.bat` | 在启动文件夹建/更新快捷方式 |
| 重新打包 exe | `重新打包exe.bat` | 改完代码后重建 `TokenStats.exe`，并覆盖桌面 |
| 推送到 GitHub | `推送到GitHub.bat` | 需要 Clash 代理开着 |
| 把桌面图标指回 exe | `桌面图标指向exe.bat` | 桌面快捷方式被改坏时用 |
| 商汤账号自动登录 | `商汤自动登录.bat` | 凭据过期时跑一次 |

---

## 二、顶层文件地图

### 2.1 程序本体（⚠️ 不能改名、不能移动）

| 文件 | 作用 | 为什么不能动 |
| --- | --- | --- |
| `card_app.py` | 主程序（UI + 业务逻辑，约 1.1 万行） | 启动脚本、`TokenStats.exe`、回归测试都按这个名字找它 |
| `scanner.py` | Token 用量扫描引擎（增量缓存、字节偏移） | `card_app.py` 里 `import scanner` |
| `peer_store.py` | 多机数据导入/导出/合并（`token-stats.peer/1` 格式） | `card_app.py` 里 `import peer_store` |
| `win_backdrop.py` | DWM 真毛玻璃（Acrylic）调用 | `card_app.py` 里 `import win_backdrop` |
| `launcher.py` | 启动器逻辑，**被编译进 `TokenStats.exe`** | 改了必须重新打包才生效 |
| `TokenStats.exe` | 带图标的启动器（内部再拉起 pythonw） | 开机自启、桌面快捷方式都指向它 |

### 2.2 辅助脚本

| 文件 | 作用 |
| --- | --- |
| `sn_login.py` | 商汤 SenseNova 登录（取 JWT 凭据） |
| `sn_autologin_fetch.py` | 商汤自动登录 + 抓取凭据 |
| `test_switch_race.py` | 全量回归测试（数百项断言，`QT_QPA_PLATFORM=offscreen` 跑） |
| `README.md` | 主技术文档（界面预览、功能详解、架构、数据格式） |
| `INDEX.md` | 本文件，文件地图 |

### 2.3 启动脚本（⚠️ 不能移动）

`start_card.bat`、`启动统计悬浮球.bat`、`启动统计悬浮球.vbs`、`enable_autostart.bat`、
`商汤自动登录.bat`、`推送到GitHub.bat`、`桌面图标指向exe.bat`、`重新打包exe.bat`

> **为什么不能移动**：它们靠 `%~dp0`（bat）和 `WScript.ScriptFullName`（vbs）取"自己所在目录"，
> 再拼 `card_app.py`。移到子目录里就找不到主程序了。想重组必须同时改脚本内容，不建议。

---

## 三、目录地图

```
token-stats/
├── card_app.py 等主程序        ← 见上面 2.1，不能动
├── assets/                     ← 桌宠帧库 + 图标 + 毛玻璃底纹（429M）
├── tools/                      ← 开发/素材处理工具（71 个脚本）
├── docs/                       ← 全部文档与素材批次数据
├── _archive/                   ← 归档区：只移动不删除，可随时取回
├── _tmp/                       ← 临时实验目录（内容可随时清空）
└── .git/
```

### 3.1 `assets/` —— 程序会直接读取（⚠️ 目录名与层级不能改）

`card_app.py` 用 `res("assets", ...)` 拼路径，`FROST_TEX_DIR = APP_DIR/assets`。

| 子目录 | 用途 | 能否移动 |
| --- | --- | --- |
| `pet/` | 主题 v1「经典素材（旧版）」 | ❌ 不能 |
| `pet_v2/` | 主题 v2「新版素材（高清）」 | ❌ 不能 |
| `pet_v3r/` | 主题 v3「最新素材（与原版合并）」 | ❌ 不能 |
| `pet_v4/` | 主题 v4「deepseek娘V4Pro」 | ❌ 不能 |
| `pet_v5/` | 主题 v5「鲸鱼少女 V5」 | ❌ 不能 |
| `pet_v6/` | 主题 v6「睡衣日常 V6」（**当前默认主待机**） | ❌ 不能 |
| `pet_alt/` | 退役帧仓库（`apply_retire.py` 写入 + 回归测试读取） | ❌ 不能 |
| `pet_v3_add/` | V3 补充帧 + `installed_map.json`（回归测试读取） | ❌ 不能 |
| `pet_new_20261023/` `...1026/` `...1028/` `...1030/` `...1031/` `...1101/` `...1105/` `pet_new_v6sel/` | **素材批次仓库**：每批原始帧 + `manifest.json` + `thumbs/`（**不进 git**，`.gitignore` 已排除，共约 360M；可从 `Downloads` 源图重切再生） | ⚠️ 工具链按 `pet_new_<批次>` 固定命名读取，改路径会导致 `apply_pet_selection.py` / `gen_pet_picker_html.py` 失效 |

`assets/` 根下的文件：`app_icon.ico` / `app_icon.png`（程序图标）、`frost_bg.png` / `frost_bg_user.png`（毛玻璃底纹）、若干 `pet_v*_qc.json`（质检记录）。

### 3.2 `tools/` —— 开发工具（71 个脚本）

程序运行**不依赖**这个目录，但改了素材/代码后要用。按用途分：

| 前缀 | 用途 | 典型脚本 |
| --- | --- | --- |
| `scan_` / `split_` | 素材切分（网格投影法） | `scan_sources.py`、`split_sources.py` |
| `gen_` | 生成选择器网页 / 总览图 | `gen_pet_picker_html.py`、`gen_lib_sheet.py` |
| `apply_` | 把勾选结果落地入库 | `apply_pet_selection.py`、`apply_retire.py` |
| `analyze_` | 素材分析（饱和度、尺寸） | `analyze_new_batch_saturation.py` |
| `normalize_` / `fix_` / `refix_` | 素材归一化与修帧 | `normalize_lib_height.py`、`fix_stuck_frames.py` |
| `check_` / `probe_` / `diag_` | 诊断探针 | `check_incr_scan.py`、`probe_v5_cols.py` |
| `bench_` / `prof_` | 性能基准与分阶段计时 | `bench_refresh.py`、`prof_refresh.py` |
| `shot_` / `demo_` | 截图与演示 | `shot_settings.py`、`demo_frost_variants.py` |
| `build_` | 打包 | `build_exe.py`、`build_launcher.py` |
| `restart_app` / `pet_status` | 重启应用 / 查桌宠状态 | `restart_app.py`、`pet_status.py` |
| `syntax_check` | 内存语法检查（**禁用 py_compile**，规避火绒误杀） | `syntax_check.py` |

### 3.3 `docs/` —— 文档与素材批次数据

| 文件 | 内容 |
| --- | --- |
| `协作进度.md` | **完整开发历程**（229 KB，按轮次记录，改代码前值得先搜这里） |
| `迁移记录_2026-11-04.md` | 从 WorkBuddy 会话快照迁到 D 盘的完整记录 |
| `协作记录_第87轮_2026-10-19.md` | 第 87 轮专项记录（圆角材质清零 + 像素差分核验器） |
| `Qt无感圆角毛玻璃-技术路线.md` | 毛玻璃技术调研与实现路线 |
| `毛玻璃模式方案.md` | Frost 模式实施方案（方案稿） |
| `刷新速度优化_20261031.md` | 刷新从 23~30s 降到 ~1s 的实测与方案 |
| `素材饱和度优化.md` | V3 新素材饱和度调整记录 |
| `V3补充素材清单.md` | V3 补充素材来源与映射 |
| `pet_selection_*.json` / `pet_preselect_*.json` / `_sources_*.json` / `pet_retire_*.json` | 各批次勾选结果、预筛结果、源清单、退役记账 |
| `pet_picker_*.html` | 素材选择器页面（勾选用） |
| `assets/` `screenshots/` `previews/` | 文档配图、界面截图、预览图 |

### 3.4 `_archive/` —— 归档区（只移动不删除）

详见 [_archive/README.md](_archive/README.md)。当前分类：

| 子目录 | 内容 |
| --- | --- |
| `assets-pet-legacy/` | 桌宠历史版本与中间产物（各 `*_bak_*` / `pet_v3_sat` 等） |
| `assets-pet-v6-backups/` | V6 素材归一化/勾选前的 6 份备份（2026-11-05 归档，148M） |
| `assets-debug/` | 根级调试截图 |
| `docs-reviews/` | 历史审查页与 QA 报告 |
| `debug-probes-202609/` | 根级调试探针残留（`%SystemDrive%` `mk_*` `_tmpprobe*` `_dwm_out.txt` 等，2026-11-05 归档） |
| `tmp-scratch-202609/` | 旧 `_tmp/` 全量快照（140 项调试脚本与产物，2026-11-05 归档） |
| `pet-v5-20261025/` | V5 素材批次存档 |
| `root-legacy/` | 根级历史物 |
| `tools-once/` | 一次性脚本（`diag_*` / `review_*` / `split_*` 等） |

### 3.5 `_tmp/` —— 临时实验区

**内容可随时清空**，程序不读取、测试不读取（测试用 `tempfile.mkdtemp()` 落在系统临时目录）。
放短期验证脚本、一次性输出即可。

---

## 四、⚠️ 改代码前必读

1. **`card_app.py` 里禁用 Qt 虚函数名做实例属性**（`metric` / `event` / `sizeHint` / `paintEvent`）。
   `self.metric = "total"` 会让 `QPainter(self)` 撞成字符串，进程直接 abort（exit 139，不可捕获）。

2. **本机火绒会把 `__pycache__/card_app*.pyc` 判成木马**并删除 + 结束进程。
   症状是「退出码 0 但零输出」或「启动器日志写着 OK，桌宠一秒后就没了」。
   对策：跑脚本一律加 `-B`；**不要用 `python -m py_compile` 做语法检查**，改用 `python -B tools/syntax_check.py`。

3. **改了 `launcher.py` 不会自动生效**——它被编译进 `TokenStats.exe`。要生效必须双击 `重新打包exe.bat`。
   （当前 exe 是 2026-10-25 打包的版本。）

4. **跑回归测试**：`QT_QPA_PLATFORM=offscreen python -B test_switch_race.py`。
   测试数量以实际输出为准，别相信任何文档里的定值。

5. **新增脚本一律相对定位**：`os.path.dirname(os.path.abspath(__file__))` / `%~dp0`，不要再写绝对路径。

---

## 五、常见任务入口

| 我想… | 从这里进 |
| --- | --- |
| 改 UI 样式 / 主题 | `card_app.py`（QSS 与自绘在 `paintEvent` 系列） |
| 换桌宠帧库 / 补动作帧 | `assets/pet_v6/seq/<场景>/<组>/NN.png` 丢进去即可，零改代码 |
| 处理一批新素材 | `tools/scan_sources.py` → `split_sources.py` → `gen_pet_picker_html.py` → 勾选 → `apply_pet_selection.py` |
| 查历史为什么这么改 | `docs/协作进度.md` 里搜关键词或轮次号 |
| 看当前版本号 | `card_app.py` 里的 `APP_BUILD` |
| 排查启动失败 | `%USERPROFILE%\.workbuddy\plugins\data\token-usage-stats\launcher.log` |
| 排查刷新慢 | `python -B tools/prof_refresh.py` |
| 查桌宠是否活着 | `python -B tools/pet_status.py` |

---

## 六、不在项目目录里但很重要的东西

| 路径 | 内容 |
| --- | --- |
| `%USERPROFILE%\.workbuddy\plugins\data\token-usage-stats\` | **运行期数据**：`cache.json` / `stats.json` / `settings.json` / `ball_status.json` / `machine.json` / `peers/` / `launcher.log` |
| 启动文件夹 `TokenAuditCard.vbs` | 开机自启入口，已指向 `D:\Deepseek-Harness-EAC\token-stats\TokenStats.exe` |
| 桌面 `Token统计.lnk` | 桌面快捷方式 |

> 运行期数据**故意留在 C 盘**，与代码分离，不要搬进项目目录。

---

## 七、本次整理（2026-11-05）

| 动作 | 内容 |
| --- | --- |
| 归档根级垃圾 | 13 项 → `_archive/debug-probes-202609/`（`%SystemDrive%`、`mk_*`、`_tmpprobe*`、`_dwm_out.txt`、`_frost_real*.png`、`_sys_blur*.png`、`Token统计.lnk`） |
| 归档临时区 | 旧 `_tmp/`（140 项 9.6M）→ `_archive/tmp-scratch-202609/`，重建空 `_tmp/` |
| 归档素材备份 | 6 个 `pet_v6_bak_*`（148M）→ `_archive/assets-pet-v6-backups/` |
| 文档归集 | `协作进度.md`、`迁移记录` → `docs/`；`2026-10-19.md` → `docs/协作记录_第87轮_2026-10-19.md` |
| 新增 | 本索引 `INDEX.md` |

**未改动**：所有程序本体、assets 的 6 个主题目录、`pet_alt` / `pet_v3_add` / `pet_new_*`、全部启动脚本。
