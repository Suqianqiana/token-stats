# -*- coding: utf-8 -*-
"""Token 审计卡片 — 多机数据源（导出 / 导入 / 合并）

背景
----
本工具的数据来自本机会话记录（WorkBuddy jsonl、DSH ledger）。多台电脑各自独立，
数据互不可见。本模块提供「导出本机 → 导入别机 → 合并展示」的最小闭环：

    · 导出：把本机 WB + DSH 的**完整聚合快照**打包成一个 JSON 文件（含机器名 / 时间 / 版本）
    · 导入：按机器名存档到 peers/<machine>.json，**累加合并**（不覆盖本机数据）
    · 覆盖：同一台机器再次导入时，可选择「覆盖更新」旧数据（先清该机再写入）
    · 合并：把本机实时数据与各别机存档合并成统一视图，支持按机筛选

设计要点
--------
1. **本机数据不落快照**：本机始终实时扫描（scan_full / load_dsh_stats），导出的只是
   一次性副本。别机数据则以文件形式常驻 peers/ 目录。
2. **累加而非覆盖**：合并时对 models / daily / dailySessions 逐项相加；同名机器重复导入
   会覆盖该机快照（避免同一台机器反复导入导致翻倍），不同名机器各自独立累计。
3. **纯标准库**：与 scanner.py 一致，不引入任何第三方依赖。

文件布局
--------
    ~/.workbuddy/plugins/data/token-usage-stats/
      ├── peers/
      │     ├── index.json          # 机器注册表 {machine: {imported_at, sources, ...}}
      │     └── <machine>.json      # 各机器快照（文件名经过安全化处理）
      └── machine.json              # 本机机器名（可改）

导出包格式（format = "token-stats.peer/1"）
----
    {
      "format": "token-stats.peer/1",
      "version": 1,
      "app": "Token 审计卡片",
      "exported_at": "2026-09-19T03:30:00",
      "machine": "浅浅猫-台式机",
      "sources": {
        "wb":  { ...scanner.scan_full() 的完整返回... },
        "dsh": { ...load_dsh_stats() 的完整返回... }
      }
    }
"""
import json
import os
import re
import time

PLUGIN_DATA_DIR = os.path.join(
    os.path.expanduser("~/.workbuddy"), "plugins", "data", "token-usage-stats"
)
PEERS_DIR = os.path.join(PLUGIN_DATA_DIR, "peers")
PEERS_INDEX = os.path.join(PEERS_DIR, "index.json")
MACHINE_FILE = os.path.join(PLUGIN_DATA_DIR, "machine.json")

FORMAT_ID = "token-stats.peer/1"
FORMAT_VERSION = 1
SOURCE_KEYS = ("wb", "dsh")


# ---------------------------------------------------------------- 机器名

def _sanitize_machine(name):
    """把机器名转成安全的文件名片段（保留中文，去掉路径分隔符等）。"""
    s = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "_", str(name or "")).strip(" .")
    s = s[:64]
    return s or "unknown-machine"


def load_machine_name():
    """读取本机机器名；未设置时用 hostname 作为默认值。"""
    try:
        with open(MACHINE_FILE, "r", encoding="utf-8") as f:
            d = json.load(f)
        name = (d or {}).get("machine")
        if name:
            return str(name)
    except Exception:
        pass
    try:
        import socket
        host = socket.gethostname() or "本机"
    except Exception:
        host = "本机"
    return host


def save_machine_name(name):
    """保存本机机器名（导出时写入包内，导入时据此识别来源）。"""
    try:
        os.makedirs(PLUGIN_DATA_DIR, exist_ok=True)
        with open(MACHINE_FILE, "w", encoding="utf-8") as f:
            json.dump({"machine": str(name)}, f, ensure_ascii=False, indent=1)
        return True
    except OSError:
        return False


# ---------------------------------------------------------------- 导出

def build_export_package(machine, sources):
    """组装导出包（纯函数，便于测试）。

    machine: 机器名
    sources: {"wb": <scan_full 结果>, "dsh": <load_dsh_stats 结果>}（任一可为 None）
    """
    pk = {
        "format": FORMAT_ID,
        "version": FORMAT_VERSION,
        "app": "Token 审计卡片",
        "exported_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "machine": str(machine or "unknown-machine"),
        "sources": {},
    }
    for k in SOURCE_KEYS:
        v = (sources or {}).get(k)
        if isinstance(v, dict) and "error" not in v:
            # 深拷贝一份，避免调用方后续改动影响已构建的包
            pk["sources"][k] = json.loads(json.dumps(v, ensure_ascii=False))
    return pk


def write_export(package, path):
    """把导出包写到指定路径（原子写）。返回 (ok, err)。"""
    try:
        d = os.path.dirname(os.path.abspath(path))
        if d:
            os.makedirs(d, exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(package, f, ensure_ascii=False)
        os.replace(tmp, path)
        return True, ""
    except OSError as e:
        return False, str(e)


def parse_package(path_or_obj):
    """读取并校验导出包。返回 (package, err)。"""
    try:
        if isinstance(path_or_obj, dict):
            d = path_or_obj
        else:
            with open(path_or_obj, "r", encoding="utf-8") as f:
                d = json.load(f)
    except Exception as e:
        return None, f"读取失败: {e}"
    if not isinstance(d, dict):
        return None, "不是有效的 JSON 对象"
    if d.get("format") != FORMAT_ID:
        return None, f"格式不匹配 (期望 {FORMAT_ID})"
    if not isinstance(d.get("sources"), dict) or not d["sources"]:
        return None, "包内没有数据源"
    machine = str(d.get("machine") or "").strip()
    if not machine:
        return None, "包内缺少机器名"
    return d, ""


# ---------------------------------------------------------------- peers 存档

def _read_index():
    try:
        with open(PEERS_INDEX, "r", encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def _write_index(idx):
    try:
        os.makedirs(PEERS_DIR, exist_ok=True)
        tmp = PEERS_INDEX + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(idx, f, ensure_ascii=False, indent=1)
        os.replace(tmp, PEERS_INDEX)
        return True
    except OSError:
        return False


def _peer_path(machine):
    return os.path.join(PEERS_DIR, _sanitize_machine(machine) + ".json")


def list_peers():
    """返回所有已导入的别机快照列表（按导入时间倒序）。

    每项: {machine, path, imported_at, exported_at, sources: ["wb","dsh"], digest}
    """
    idx = _read_index()
    out = []
    for machine, meta in idx.items():
        if not isinstance(meta, dict):
            continue
        p = meta.get("path") or _peer_path(machine)
        if not os.path.exists(p):
            continue
        item = dict(meta)
        item["machine"] = machine
        item["path"] = p
        out.append(item)
    out.sort(key=lambda x: str(x.get("imported_at", "")), reverse=True)
    return out


def load_peer(machine):
    """读取某台机器的快照包；不存在或损坏返回 None。"""
    idx = _read_index()
    meta = idx.get(machine) if isinstance(idx, dict) else None
    p = (meta or {}).get("path") or _peer_path(machine)
    if not os.path.exists(p):
        return None
    try:
        with open(p, "r", encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else None
    except Exception:
        return None


def load_all_peers():
    """读取全部别机快照 → {machine: package}。"""
    out = {}
    for it in list_peers():
        pk = load_peer(it["machine"])
        if pk:
            out[it["machine"]] = pk
    return out


def _snapshot_digest(sources):
    """快照摘要：总 token / 请求数 / 日期跨度，用于列表展示与"是否有更新"判断。"""
    total = requests = 0
    days = []
    for k, v in (sources or {}).items():
        if not isinstance(v, dict):
            continue
        for m, a in (v.get("models") or {}).items():
            total += int(a.get("total", 0) or 0)
            requests += int(a.get("requests", 0) or 0)
        for d, mm in (v.get("daily") or {}).items():
            if d and d != "unknown" and isinstance(mm, dict):
                days.append(d)
    days = sorted(set(days))
    return {
        "total_tokens": total,
        "requests": requests,
        "first_day": days[0] if days else "",
        "last_day": days[-1] if days else "",
    }


def import_peer(package, replace=False):
    """导入别机快照。返回 (ok, msg, info)。

    replace=True  → 覆盖该机器旧数据（先删除再写入）
    replace=False → 若该机器已存在，则按「全量快照语义」仍覆盖（同一台机器的数据应是
                    完整快照，累加会导致同一台机器重复计数）；不同机器互不影响。
    """
    machine = str(package.get("machine") or "").strip()
    if not machine:
        return False, "包内缺少机器名", None
    sources = package.get("sources") or {}

    os.makedirs(PEERS_DIR, exist_ok=True)
    path = _peer_path(machine)
    tmp = path + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(package, f, ensure_ascii=False)
        os.replace(tmp, path)
    except OSError as e:
        return False, f"写入失败: {e}", None

    digest = _snapshot_digest(sources)
    idx = _read_index()
    existed = machine in idx
    idx[machine] = {
        "path": path,
        "imported_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "exported_at": package.get("exported_at", ""),
        "sources": sorted(k for k in sources if isinstance(sources.get(k), dict)),
        "digest": digest,
        "replaced": bool(replace and existed),
    }
    _write_index(idx)
    info = {"machine": machine, "digest": digest, "replaced": bool(existed)}
    if existed and replace:
        return True, f"已覆盖更新「{machine}」的数据", info
    if existed:
        return True, f"「{machine}」的数据已更新为最新快照", info
    return True, f"已新增机器「{machine}」", info


def remove_peer(machine):
    """删除某台机器的快照（同时移出索引）。返回 (ok, msg)。"""
    idx = _read_index()
    if machine not in idx:
        return False, f"未找到机器「{machine}」"
    meta = idx.pop(machine) or {}
    p = meta.get("path") or _peer_path(machine)
    try:
        if os.path.exists(p):
            os.remove(p)
    except OSError as e:
        idx[machine] = meta        # 删除失败则回滚索引
        _write_index(idx)
        return False, f"删除失败: {e}"
    _write_index(idx)
    return True, f"已删除机器「{machine}」"


# ---------------------------------------------------------------- 合并聚合

def _empty_model_agg():
    return {"requests": 0, "input": 0, "output": 0, "cached": 0,
            "cacheWrite": 0, "reasoning": 0, "total": 0}


def _add_model(bucket, a):
    for k in bucket:
        bucket[k] += int((a or {}).get(k, 0) or 0)


def _normalize_wb(stats):
    """把 WB 的 scan_full 结果摊平成与 DSH 同构的 {daily, dailySessions, models, today,...}"""
    if not isinstance(stats, dict) or "error" in stats:
        return None
    daily = {}
    for d, mm in (stats.get("daily") or {}).items():
        if not isinstance(mm, dict):
            continue
        tgt = daily.setdefault(d, {})
        for m, a in mm.items():
            b = tgt.setdefault(m, _empty_model_agg())
            _add_model(b, {"requests": a.get("requests", 0),
                           "input": a.get("input", 0),
                           "output": a.get("output", 0),
                           "cached": a.get("cached", 0),
                           "cacheWrite": a.get("cacheWrite", 0),
                           "reasoning": a.get("reasoning", 0),
                           "total": a.get("total", 0)})
    models = {}
    for m, a in (stats.get("models") or {}).items():
        _add_model(models.setdefault(m, _empty_model_agg()), a)
    return {
        "daily": daily,
        "dailySessions": dict(stats.get("dailySessions") or {}),
        "models": models,
        "today": dict(stats.get("today") or {}),
        "sessionsTotal": int(stats.get("sessionsTotal", 0) or 0),
        "firstDay": stats.get("firstDay", ""),
        "lastDay": stats.get("lastDay", ""),
    }


def _normalize_dsh(stats):
    """DSH 结果本身已同构，补齐 models（load_dsh_stats 只给 daily，需要现算）。"""
    if not isinstance(stats, dict) or "error" in stats:
        return None
    daily = {}
    for d, mm in (stats.get("daily") or {}).items():
        if not isinstance(mm, dict):
            continue
        tgt = daily.setdefault(d, {})
        for m, a in mm.items():
            _add_model(tgt.setdefault(m, _empty_model_agg()), a)
    models = {}
    for mm in daily.values():
        for m, a in mm.items():
            _add_model(models.setdefault(m, _empty_model_agg()), a)
    return {
        "daily": daily,
        "dailySessions": dict(stats.get("dailySessions") or {}),
        "models": models,
        "today": dict(stats.get("today") or {}),
        "sessionsTotal": int(stats.get("sessionsTotal", 0) or 0),
        "firstDay": stats.get("firstDay") or "",
        "lastDay": stats.get("lastDay") or "",
        "totalCost": stats.get("totalCost"),
    }


def normalize_source(source_key, stats):
    """把任一来源的原始结果统一成标准结构（供合并使用）。"""
    if source_key == "dsh":
        return _normalize_dsh(stats)
    return _normalize_wb(stats)


def machine_summary(machine, stats):
    """单机摘要（用于按机统计展示）。stats 为原始结果（未规范化）。

    ⚠️ 注意: load_dsh_stats() 的返回值**只有 daily、没有 models**（models 是按需现算的），
    所以这里不能只累加 models —— 走 normalize_source 统一结构后再统计，
    否则 DSH 那部分用量会被整块漏掉。
    """
    out = {"machine": machine, "total": 0, "requests": 0, "input": 0,
           "output": 0, "cached": 0, "sessions": 0,
           "firstDay": "", "lastDay": "", "cost": None}
    days = []
    for key in SOURCE_KEYS:
        raw = (stats or {}).get(key)
        if not isinstance(raw, dict) or "error" in raw:
            continue
        norm = normalize_source(key, raw)
        if not norm:
            continue
        for a in (norm.get("models") or {}).values():
            out["total"] += int(a.get("total", 0) or 0)
            out["requests"] += int(a.get("requests", 0) or 0)
            out["input"] += int(a.get("input", 0) or 0)
            out["output"] += int(a.get("output", 0) or 0)
            out["cached"] += int(a.get("cached", 0) or 0)
        for d in (norm.get("daily") or {}):
            if d and d != "unknown":
                days.append(d)
        out["sessions"] += int(norm.get("sessionsTotal", 0) or 0)
        if raw.get("totalCost") is not None:
            out["cost"] = (out["cost"] or 0.0) + float(raw["totalCost"] or 0)
    days = sorted(set(days))
    out["firstDay"] = days[0] if days else ""
    out["lastDay"] = days[-1] if days else ""
    return out


def merge_machines(entries, include_local=True, peer_filter=None):
    """把多台机器合并成统一视图。

    entries: [{"machine": name, "local": bool, "stats": {wb:..., dsh:...}}, ...]
             其中 stats 是原始结果；合并时逐来源规范化。
    include_local: 是否把 local=True 的条目计入
    peer_filter: None=全部别机；否则只计入 machine 在该集合中的别机

    返回 {
      "daily": {date: {model: agg}},          # 合并后
      "dailySessions": {date: n},
      "models": {model: agg},
      "sessionsTotal": n,
      "firstDay": ..., "lastDay": ...,
      "machines": {machine: summary},
      "bySource": {"wb": {...}, "dsh": {...}},  # 按来源拆分（可选展示）
    }
    """
    daily = {}
    daily_sessions = {}
    models = {}
    sessions_total = 0
    machines = {}
    by_source = {k: {"models": {}, "daily": {}, "total": 0, "requests": 0} for k in SOURCE_KEYS}
    days = []

    for ent in entries or []:
        machine = ent.get("machine") or "unknown-machine"
        is_local = bool(ent.get("local"))
        if is_local and not include_local:
            continue
        if (not is_local) and peer_filter is not None and machine not in peer_filter:
            continue

        machines[machine] = machine_summary(machine, ent.get("stats"))
        for key in SOURCE_KEYS:
            norm = normalize_source(key, (ent.get("stats") or {}).get(key))
            if not norm:
                continue
            for d, mm in norm["daily"].items():
                tgt = daily.setdefault(d, {})
                src_tgt = by_source[key]["daily"].setdefault(d, {})
                for m, a in mm.items():
                    _add_model(tgt.setdefault(m, _empty_model_agg()), a)
                    _add_model(src_tgt.setdefault(m, _empty_model_agg()), a)
                    _add_model(models.setdefault(m, _empty_model_agg()), a)
                    _add_model(by_source[key]["models"].setdefault(m, _empty_model_agg()), a)
                if d and d != "unknown":
                    days.append(d)
            for d, n in norm["dailySessions"].items():
                daily_sessions[d] = daily_sessions.get(d, 0) + int(n or 0)
            sessions_total += norm["sessionsTotal"]

    for k in SOURCE_KEYS:
        by_source[k]["total"] = sum(a["total"] for a in by_source[k]["models"].values())
        by_source[k]["requests"] = sum(a["requests"] for a in by_source[k]["models"].values())

    days = sorted(set(days))
    return {
        "daily": daily,
        "dailySessions": daily_sessions,
        "models": models,
        "sessionsTotal": sessions_total,
        "firstDay": days[0] if days else "",
        "lastDay": days[-1] if days else "",
        "machines": machines,
        "bySource": by_source,
    }


if __name__ == "__main__":
    import sys
    name = load_machine_name()
    peers = list_peers()
    print(f"本机机器名: {name}")
    print(f"peers 目录: {PEERS_DIR}")
    print(f"已导入机器: {len(peers)}")
    for p in peers:
        dig = p.get("digest", {})
        print(f"  · {p['machine']}  导入于 {p.get('imported_at','?')}  "
              f"token={dig.get('total_tokens',0):,} 请求={dig.get('requests',0):,}  "
              f"{dig.get('first_day','—')}~{dig.get('last_day','—')}")
    if "--dump" in sys.argv:
        print(json.dumps(load_all_peers(), ensure_ascii=False, indent=1)[:2000])
