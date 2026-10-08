# -*- coding: utf-8 -*-
"""
Token Usage Scanner — WorkBuddy token 用量增量扫描与聚合引擎
数据源: ~/.workbuddy/projects/**/*.jsonl 中 assistant 消息的 providerData.usage (camelCase)
持久化: 同目录下 cache.json (按文件 mtime+size 增量), stats.json (聚合结果)
仅用标准库。
"""
import hashlib
import json
import os
import re
import sys
import time

WB_DIR = os.path.expanduser("~/.workbuddy")
PROJECTS_DIR = os.path.join(WB_DIR, "projects")
PLUGIN_DATA_DIR = os.path.join(
    WB_DIR, "plugins", "data", "token-usage-stats"
)
os.makedirs(PLUGIN_DATA_DIR, exist_ok=True)

CACHE_FILE = os.path.join(PLUGIN_DATA_DIR, "cache.json")   # 文件级增量游标
STATS_FILE = os.path.join(PLUGIN_DATA_DIR, "stats.json")   # 聚合结果（含每日/每模型明细）

# ---------------------------------------------------------------- helpers

def _iter_jsonl_files():
    """遍历 projects 下所有 .jsonl"""
    if not os.path.isdir(PROJECTS_DIR):
        return
    for root, _dirs, files in os.walk(PROJECTS_DIR):
        for fn in files:
            if fn.endswith(".jsonl"):
                yield os.path.join(root, fn)


# ---------------------------------------------------------------- 副本去重
# workdaddy(同账号多开) 会把同一份会话**复制**成新文件(文件名换成新 UUID),
# 但文件内部的 sessionId 仍是原值 -> 按文件路径扫描会把同一会话统计两次(token 翻倍)。
# 判据: 同一 sessionId 出现多份时, 保留"最完整"的那份:
#   ① 文件更大者优先(复制后两边可能各自续写, 大者内容更全)
#   ② 大小相同则"文件名 == sessionId"者优先(规范性命名 = 原始文件)
SID_HEAD_LINES = 40          # 读首部多少行找 sessionId
SID_HEAD_BYTES = 512 * 1024  # 首部最多读多少字节
SID_SIG_BYTES = 8192         # sid 缓存的"首部指纹"取多少字节(见 _sid_cache_stale)

# ---------------------------------------------------------------- 内容级判据(第69轮: 统一判据)
# ⭐ 教训(第67/68/69轮连续复发): 副本的**外部特征会变**, 靠特征猜永远补不完 ——
#   第67轮: 两份 sid 相同, 但缓存记错 → 分成两组(修缓存)
#   第68轮: 两份 sid 不同, 但大小/行数/mtime 全同 → 按 sid 分组抓不到(加"大小相同"判据)
#   第69轮: 同一会话有 **3 份**, sid 各不相同、**大小也都不同**(各自续写)
#     —— "sid 相同"和"大小相同"两条判据**同时失效**, 于是又复发。
# 根治: 不再猜外部特征, 直接**按消息内容本身判重**:
#   · 每个文件取前 DUP_ID_SAMPLE 条"消息 id"当内容指纹
#   · 用 **id → 文件** 倒排索引找候选对(对比次数从 O(n²) 降到几十)
#   · 重合率 ≥ DUP_ID_RATIO 判同源, 用**并查集**做传递闭包 → 3 份、4 份也能合并成一组
#   · 组内保留"内容最全"的那份(大小最大), 其余丢弃
DUP_ID_SAMPLE = 120          # 每个文件取前多少条消息 id 做指纹
DUP_ID_RATIO = 0.60          # 指纹重合率阈值(放宽以兼容"复制后各自续写"的分支)


def _read_session_id(path):
    """读文件首部若干行, 返回第一个非空 sessionId (找不到返回 None)。"""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            for i, line in enumerate(f):
                if i >= SID_HEAD_LINES:
                    break
                # 轻量提取, 避免为取一个字段而完整 json.loads 超大行
                if '"sessionId"' not in line:
                    continue
                m = re.search(r'"sessionId"\s*:\s*"([^"]+)"', line)
                if m:
                    return m.group(1)
    except OSError:
        pass
    return None


def _msg_id_sample(path, n=DUP_ID_SAMPLE):
    """抽前 n 行里的消息 id 集合 —— 用来识别"连内部 sid 都改掉了"的整体复制。

    只看前 n 行: 副本若是整体复制, 开头必然一致, 这已足够判定; 且不必读完整文件(几十 MB)。
    """
    ids = set()
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            for i, line in enumerate(f):
                if i >= n:
                    break
                m = re.search(r'"id"\s*:\s*"([^"]{6,})"', line)
                if m:
                    ids.add(m.group(1))
    except OSError:
        pass
    return ids


def _is_same_content(a_ids, b_ids):
    """两份是不是同一份会话内容(消息 id 集合重合率)。无 id 可比对时返回 False(宁多勿漏)。"""
    if not a_ids or not b_ids:
        return False
    union = len(a_ids | b_ids)
    return bool(union) and (len(a_ids & b_ids) / union) >= DUP_ID_RATIO


def _size_of(path):
    try:
        return os.path.getsize(path)
    except OSError:
        return 0


def _dedupe_by_content(files):
    """按**消息内容**判重(第69轮统一判据), 返回 (keep, dropped)。

    与 sid、文件大小、文件名全都无关 —— 只要两份共享足够多的消息 id, 就是同一份会话的副本。
    并查集传递闭包 → "同一会话被复制成 3 份且各自续写"也能一次合并成一组。
    组内保留**内容最全**(大小最大)者; 大小相同则按路径字典序(保证结果可复现)。
    """
    sigs = {}
    for p in files:
        sigs[p] = _msg_id_sample(p, DUP_ID_SAMPLE)

    # 倒排索引: 只比较"共享过至少一个 id"的文件对(实测 468 个文件 → 74 个候选对)
    inv = {}
    for p, ids in sigs.items():
        for mid in ids:
            inv.setdefault(mid, []).append(p)
    cand = set()
    for ps in inv.values():
        if len(ps) > 1:
            ps = sorted(ps)
            for i in range(len(ps)):
                for j in range(i + 1, len(ps)):
                    cand.add((ps[i], ps[j]))

    parent = {p: p for p in files}

    def _find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for a, b in cand:
        if _is_same_content(sigs.get(a) or set(), sigs.get(b) or set()):
            ra, rb = _find(a), _find(b)
            if ra != rb:
                parent[rb] = ra

    groups = {}
    for p in files:
        groups.setdefault(_find(p), []).append(p)

    keep, dropped = [], []
    for members in groups.values():
        members = sorted(members, key=lambda p: (-_size_of(p), p))
        keep.append(members[0])
        dropped.extend(members[1:])
    return keep, dropped


def _head_sig(path):
    """文件首部指纹(前 SID_SIG_BYTES 字节的 md5)。

    会话文件是**追加**写的, 首部一旦写完就基本不变 —— 所以这个指纹既稳定(不会因续写而
    频繁失效), 又能识别"首部被重写/恢复/替换"的情况。
    """
    try:
        with open(path, "rb") as f:
            return hashlib.md5(f.read(SID_SIG_BYTES)).hexdigest()
    except OSError:
        return ""


def _sid_cache_valid(entry):
    """sid 缓存条目是否仍是新格式 {s: sid, h: 首部指纹}。

    ⚠️ 旧格式是**裸字符串** sid(第60轮写的), 没有指纹 —— 见 _dedupe_files 的注释:
    它会把一次误读的 sessionId 永久记住, 直接导致副本不去重。这里一律判为失效并自愈。
    """
    return isinstance(entry, dict) and isinstance(entry.get("s"), str) \
        and isinstance(entry.get("h"), str)


def _dedupe_files(files, sid_map=None):
    """按内部 sessionId 去重, 返回 (keep_list, dropped_list, sid_map)。

    sid_map: {path: {"s": sid, "h": 首部指纹}} 缓存(可传入并在返回时合并), 避免每次重读首部。
    无 sessionId 的文件一律保留(宁多勿漏)。

    ⚠️ 2026-10-01 修真 bug(浅猫报"翼型优化·最新(09-28)"没去重):
       旧实现只要 sid_map 里有这个路径就**直接用**, 不再重读 —— 于是一次误读就会被永久记住。
       实测案例: `8170daf4….jsonl` 在缓存里记成了 `222c96b0-…`(会话边写边改时首部抓错),
       于是它和真正的同会话副本 `242b0035….jsonl`(内部 sid 都是 8170daf4)被分进两组,
       **两份都统计 → token 翻倍**; 清空缓存后立刻正确(保留大的、丢弃小的)。
       修法: 缓存条目带**首部指纹**, 指纹不符(或旧格式)就重读 —— 旧的坏缓存会自动自愈。
    """
    if sid_map is None:
        sid_map = {}
    groups = {}   # sid -> [paths]
    passthrough = []   # 无 sid: 直接保留
    for p in files:
        entry = sid_map.get(p)
        sig = _head_sig(p)
        if not _sid_cache_valid(entry) or entry.get("h") != sig:
            entry = {"s": _read_session_id(p) or "", "h": sig}
            sid_map[p] = entry
        sid = entry.get("s") or ""
        if sid:
            groups.setdefault(sid, []).append(p)
        else:
            passthrough.append(p)

    keep, dropped = list(passthrough), []
    for sid, ps in groups.items():
        if len(ps) == 1:
            keep.append(ps[0])
            continue

        def _rank(path):
            # 先比大小(大者优先), 同大小再比"文件名==sid"
            stem = os.path.splitext(os.path.basename(path))[0]
            try:
                size = os.path.getsize(path)
            except OSError:
                size = 0
            return (-size, 0 if stem == sid else 1)

        ordered = sorted(ps, key=_rank)
        keep.append(ordered[0])
        dropped.extend(ordered[1:])

    # ---- 第二道(第69轮改为**统一判据**): 按消息内容判重 ----
    # 上面按 sid 分组抓不到"sid 被改掉"的副本; 第68轮的"大小相同"判据也抓不到
    # "复制后各自续写导致大小不同"的副本(实测同一会话有 3 份, sid 与大小三者皆不同)。
    # 这里不再看任何外部特征, 直接用消息 id 指纹 + 并查集一次性合并所有同源副本。
    keep, dropped2 = _dedupe_by_content(keep)
    dropped.extend(dropped2)
    # 只保留仍存在的文件的 sid 缓存(剪掉已删除文件)
    alive = set(files)
    sid_map = {k: v for k, v in sid_map.items() if k in alive}
    return keep, dropped, sid_map


def _dedupe_same_size(keep, sid_map=None):
    """对"大小完全相同"的文件做内容级去重, 返回 (new_keep, extra_dropped)。

    ⭐ 目的(第68轮): 抓住"整体复制 + 连内部 sessionId 一起改掉"的副本 ——
      这类副本的内部 sid 各不相同, 按 sid 分组永远分不到一起。
      保留顺序: 文件名==内部 sid 优先 → mtime 更新优先 → 路径字典序(保证结果可复现)。
    """
    by_size = {}
    for p in keep:
        try:
            size = os.path.getsize(p)
        except OSError:
            continue
        by_size.setdefault(size, []).append(p)

    new_keep, extra_dropped = [], []
    for _size, ps in by_size.items():
        if len(ps) < 2:
            new_keep.extend(ps)
            continue

        def _rank2(path):
            stem = os.path.splitext(os.path.basename(path))[0]
            sid = ""
            if sid_map:
                ent = sid_map.get(path)
                if isinstance(ent, dict):
                    sid = ent.get("s") or ""
            if not sid:
                sid = _read_session_id(path) or ""
            try:
                mt = os.stat(path).st_mtime_ns
            except OSError:
                mt = 0
            return (0 if (sid and stem == sid) else 1, -mt, path)

        kept, sigs = [], {}
        for p in sorted(ps, key=_rank2):
            ids = _msg_id_sample(p)
            dup_of = None
            for q in kept:
                if _is_same_content(ids, sigs.get(q) or set()):
                    dup_of = q
                    break
            if dup_of is None:
                kept.append(p)
                sigs[p] = ids
            else:
                extra_dropped.append(p)
        new_keep.extend(kept)
    return new_keep, extra_dropped


def _load_cache():
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_cache(cache):
    tmp = CACHE_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cache, f)
    os.replace(tmp, CACHE_FILE)


def _safe_int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0


# 每个文件最多读多少字节做尾部截断保护（防止异常超大行）
_MAX_LINE = 4 * 1024 * 1024


def _norm_date(ts):
    """timestamp -> YYYY-MM-DD。兼容 ISO 字符串与 Unix 秒/毫秒整数。"""
    if ts is None or ts == "":
        return "unknown"
    if isinstance(ts, (int, float)):
        v = float(ts)
        if v > 1e12:      # 毫秒
            v /= 1000.0
        try:
            return time.strftime("%Y-%m-%d", time.localtime(v))
        except Exception:
            return "unknown"
    s = str(ts)
    m = re.match(r"(\d{4}-\d{2}-\d{2})", s)
    return m.group(1) if m else "unknown"


def _extract_usage_from_line(line):
    """
    从一行 JSON 提取 usage 条目列表。
    权威来源: providerData.usage (camelCase)。一行可能含多个 assistant 消息块,
    但实际 WorkBuddy 会话文件里通常一行一条消息; 若一行是消息数组也兼容。
    返回 list[dict]: {ts, model, input, output, total, cached, reasoning}
    """
    out = []
    try:
        obj = json.loads(line)
    except Exception:
        return out
    if not isinstance(obj, dict):
        return out

    pd = obj.get("providerData")
    if not isinstance(pd, dict):
        return out
    usage = pd.get("usage")
    if not isinstance(usage, dict):
        return out

    inp = _safe_int(usage.get("inputTokens"))
    otp = _safe_int(usage.get("outputTokens"))
    tot = _safe_int(usage.get("totalTokens")) or (inp + otp)
    cached = 0
    itd = usage.get("inputTokensDetails")
    if isinstance(itd, list):
        for d in itd:
            if isinstance(d, dict):
                cached += _safe_int(d.get("cached_tokens"))
    reasoning = 0
    otd = usage.get("outputTokensDetails")
    if isinstance(otd, list):
        for d in otd:
            if isinstance(d, dict):
                reasoning += _safe_int(d.get("reasoning_tokens"))

    model = (
        pd.get("model")
        or pd.get("requestModelId")
        or pd.get("requestModelName")
        or "unknown"
    )
    ts = obj.get("timestamp") or ""
    sid = obj.get("sessionId") or ""
    mid = obj.get("id") or obj.get("messageId") or ""

    out.append({
        "ts": ts,
        "mid": str(mid),
        "model": str(model),
        "input": inp,
        "output": otp,
        "total": tot,
        "cached": cached,
        "reasoning": reasoning,
        "sid": str(sid)[:24],
    })
    return out


def _msg_key_test(e):
    """一条 usage 的消息级去重键(模块级, 便于测试直接验证; scan_full 内部用同名闭包)。

    ⚠️ 第70轮两个坑(详见 scan_full 内注释):
      坑1 用 sid 做键 → 两账号轮换时 sid 不同, 共享历史被算成两条;
      坑2 缺 mid/ts 时返回空兜底键 → **全部条目撞成一个键, 统计只剩 1 条**(曾真实发生)。
    正确行为: 有消息 id 用它; 没有则 sid+ts 都齐备才拼; 否则返回 **None**(调用方不去重)。
    """
    mid = e.get("mid") or ""
    if mid:
        return mid
    sid = e.get("sid") or ""
    ts = e.get("ts") or ""
    if sid and ts:
        return "%s|%s|%s|%s" % (sid, str(ts), str(e.get("total", 0)), e.get("model", ""))
    return None


def scan_full(force=False):
    """
    全量+增量扫描。返回聚合 dict:
    {
      "generatedAt": iso, "filesScanned": n, "entriesTotal": n,
      "models": {model: {"requests","input","output","total","cached","reasoning"}},
      "daily": {date: {model: {"requests","input","output"}}},
      "firstDay": "YYYY-MM-DD", "lastDay": "...",
    }
    增量策略: 记录每个文件的 (mtime,size) 与累计偏移量, 只解析新增尾部;
             mtime 变化但变小(被重写)则整文件重扫。
    """
    t0 = time.time()
    cache = {} if force else _load_cache()

    # ---- 副本处理(第70轮改口径: 不再丢文件, 改为【按消息去重】) ----
    # ⚠️ 浅猫的真实用法: 两个账号轮换 —— A 号额度用完后, 会话被同步到 B 号继续对话。
    #    于是"同一会话"会有多个文件: 它们**共享前半段历史**, 但各自都有**后半段真实新用量**。
    #    第69轮按"文件"判重(整份丢掉), 把 B 号的新用量一起丢了 → **统计偏少**
    #    (实测: 今日 hy4-preview 只显示 1998 万, 真实应为 8049 万)。
    # 正确口径: **每个文件都扫**, 但同一条消息(唯一键)只计一次 —— 既不吃重复, 也不丢真实用量。
    all_files = list(_iter_jsonl_files())
    _sid_cache = cache.get("__sids__") or {}
    keep_files, dropped_files, _sid_cache = _dedupe_files(all_files, _sid_cache)
    # 口径变更: 疑似副本的文件仍然全部扫描(下面按消息去重), 所以真正参与统计的是 all_files。
    # keep_files / dropped_files 仅用于观测与会话数统计。

    models = {}   # model -> agg
    daily = {}    # date -> model -> agg
    sids = set()  # 全局会话 id 集合
    daily_sids = {}  # date -> set(sid)
    entries_total = 0
    files_scanned = 0

    def _agg(bucket, e):
        i = e.get("input", e.get("i", 0))
        o = e.get("output", e.get("o", 0))
        t = e.get("total", e.get("t", i + o))
        c = e.get("cached", e.get("c", 0))
        r = e.get("reasoning", e.get("r", 0))
        bucket["requests"] = bucket.get("requests", 0) + 1
        bucket["input"] = bucket.get("input", 0) + i
        bucket["output"] = bucket.get("output", 0) + o
        bucket["total"] = bucket.get("total", 0) + t
        bucket["cached"] = bucket.get("cached", 0) + c
        bucket["reasoning"] = bucket.get("reasoning", 0) + r

    new_cache = {}
    # 第70轮: 消息级去重 —— 扫全部文件, 但同一条消息只计一次(见上方口径说明)
    _seen_msgs = set()

    def _msg_key(e):
        """一条 usage 的唯一键 —— **必须用消息 id**, 不能用 sessionId。

        ⚠️ 第70轮踩了两个坑, 都记在这里:
        坑1: 一开始用 "sid|ts|total|model" —— 两个账号轮换时 sid 不同,
             共享历史被算成两条(测试 requests=16, 正确 10)。
             sessionId 是可被改写的外部特征(第68轮已验证); **消息 id 才是内容固有的**。
        坑2(致命): 缓存条目里没存 mid/ts, 于是键退化成空串 "||0|" ——
             **全部 49985 条撞成同一个键, 统计只剩 1 条**(实测 50549 → 1)。
             所以: **拿不到消息 id 时返回 None = "无法确定", 调用方跳过不去重**
             (宁可重复, 绝不许丢), 绝不能返回会撞车的兜底键。
        """
        mid = e.get("mid") or ""
        if mid:
            return mid
        # 没有消息 id: 只有 sid + ts 都齐备时才敢拼内容键
        sid = e.get("sid") or ""
        ts = e.get("ts") or ""
        if sid and ts:
            return "%s|%s|%s|%s" % (sid, str(ts), str(e.get("total", 0)), e.get("model", ""))
        return None      # ← 无法判定 → 调用方不去重

    for path in all_files:
        try:
            st = os.stat(path)
            sig_key = f"{st.st_mtime_ns}:{st.st_size}"
            prev = cache.get(path)
            entries_total += 0  # noop for clarity
            if prev and prev.get("sig") == sig_key:
                # 未变化: 直接沿用历史聚合(仍要走消息级去重, 与其它文件的新消息比对)
                for e in prev.get("entries", []):
                    _k = _msg_key(e)
                    if _k is not None:
                        if _k in _seen_msgs:
                            continue
                        _seen_msgs.add(_k)
                    date = e["d"]
                    daily.setdefault(date, {})
                    _agg(daily[date].setdefault(e["m"], {}), e)
                    _agg(models.setdefault(e["m"], {}), e)
                    if e.get("s"):
                        sids.add(e["s"])
                        daily_sids.setdefault(date, set()).add(e["s"])
                    entries_total += 1
                new_cache[path] = prev
                continue

            # 需要解析: 若文件被追加(prev 存在且 size 变大且 mtime 变化),
            # 简单起见仍全量重读该文件 —— 单文件通常 < 几 MB, 成本可接受
            file_entries = []
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    if len(line) > _MAX_LINE:
                        continue
                    for e in _extract_usage_from_line(line):
                        # 第70轮: 同一条消息只计一次(两个账号轮换时共享的历史不重复计)
                        # 拿不到消息 id 时 _msg_key 返回 None → 不去重(宁多勿漏)
                        _k = _msg_key(e)
                        if _k is not None:
                            if _k in _seen_msgs:
                                continue
                            _seen_msgs.add(_k)
                        date = _norm_date(e["ts"])
                        sid = e.get("sid", "")
                        file_entries.append({"d": date, "m": e["model"],
                                             "i": e["input"], "o": e["output"],
                                             "t": e["total"], "c": e["cached"],
                                             "r": e["reasoning"], "s": sid,
                                             # 第70轮: 消息级去重必须能在"读缓存"时也拿到键,
                                             # 所以这里要把 mid / ts 一并存下来(否则键退化为空串 →
                                             # 全部条目撞车, 统计只剩 1 条)。
                                             "mid": e.get("mid", ""), "ts": e.get("ts", "")})
                        _agg(daily.setdefault(date, {}).setdefault(e["model"], {}), e)
                        _agg(models.setdefault(e["model"], {}), e)
                        if sid:
                            sids.add(sid)
                            daily_sids.setdefault(date, set()).add(sid)
                        entries_total += 1
            new_cache[path] = {"sig": sig_key, "entries": file_entries}
            files_scanned += 1
        except OSError:
            continue

    new_cache["__sids__"] = _sid_cache
    _save_cache(new_cache)

    days = sorted(d for d in daily if d != "unknown")
    today = time.strftime("%Y-%m-%d")
    today_agg = daily.get(today, {})
    today_summary = {
        "requests": sum(a.get("requests", 0) for a in today_agg.values()),
        "input": sum(a.get("input", 0) for a in today_agg.values()),
        "output": sum(a.get("output", 0) for a in today_agg.values()),
        "cached": sum(a.get("cached", 0) for a in today_agg.values()),
        "sessions": len(daily_sids.get(today, ())),
    }
    result = {
        "generatedAt": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "scanSeconds": round(time.time() - t0, 2),
        "filesTracked": len(new_cache),
        "filesRescanned": files_scanned,
        "entriesTotal": entries_total,
        "models": models,
        "daily": daily,
        "sessionsTotal": len(sids),
        "dailySessions": {d: len(s) for d, s in daily_sids.items()},
        "today": today_summary,
        "firstDay": days[0] if days else "",
        "lastDay": days[-1] if days else "",
        # 副本去重观测(workdaddy 复制产生的重复会话)
        "dupFilesDropped": len(dropped_files),
        "dupFilesTotal": len(all_files),
    }
    _write_stats(result)
    return result


def _write_stats(result):
    tmp = STATS_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False)
    os.replace(tmp, STATS_FILE)


if __name__ == "__main__":
    force = "--force" in sys.argv
    r = scan_full(force=force)
    print(json.dumps({k: v for k, v in r.items()
                      if k in ("generatedAt", "scanSeconds", "filesTracked",
                               "filesRescanned", "entriesTotal",
                               "firstDay", "lastDay")},
                     ensure_ascii=False))
    print("top models:")
    ranked = sorted(r["models"].items(), key=lambda kv: -kv[1].get("total", 0))[:10]
    for m, a in ranked:
        print(f"  {m}: req={a['requests']} in={a['input']:,} out={a['output']:,}")
