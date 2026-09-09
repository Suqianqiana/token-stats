# -*- coding: utf-8 -*-
"""
Token Usage Scanner — WorkBuddy token 用量增量扫描与聚合引擎
数据源: ~/.workbuddy/projects/**/*.jsonl 中 assistant 消息的 providerData.usage (camelCase)
持久化: 同目录下 cache.json (按文件 mtime+size 增量), stats.json (聚合结果)
仅用标准库。
"""
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

    out.append({
        "ts": ts,
        "model": str(model),
        "input": inp,
        "output": otp,
        "total": tot,
        "cached": cached,
        "reasoning": reasoning,
        "sid": str(sid)[:24],
    })
    return out


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
    for path in _iter_jsonl_files():
        try:
            st = os.stat(path)
            sig_key = f"{st.st_mtime_ns}:{st.st_size}"
            prev = cache.get(path)
            entries_total += 0  # noop for clarity
            if prev and prev.get("sig") == sig_key:
                # 未变化: 直接沿用历史聚合
                for e in prev.get("entries", []):
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
                        date = _norm_date(e["ts"])
                        sid = e.get("sid", "")
                        file_entries.append({"d": date, "m": e["model"],
                                             "i": e["input"], "o": e["output"],
                                             "t": e["total"], "c": e["cached"],
                                             "r": e["reasoning"], "s": sid})
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
