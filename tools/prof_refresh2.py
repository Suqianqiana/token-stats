#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""刷新链路第二阶段拆解: 到底是哪一步吃掉 20 秒（只读，不改真实数据）。

用法: python -B tools/prof_refresh2.py
"""
import sys
sys.dont_write_bytecode = True
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import scanner  # noqa: E402


def ms(t0):
    return (time.perf_counter() - t0) * 1000


def main():
    t0 = time.perf_counter()
    cache = scanner._load_cache()
    print("载入 cache.json            %8.1f ms" % ms(t0))

    files = list(scanner._iter_jsonl_files())
    print("文件数: %d" % len(files))

    # --- (a) 有多少文件需要重新解析 ---
    t0 = time.perf_counter()
    changed, changed_bytes, total_bytes = [], 0, 0
    sigs = {}
    for p in files:
        try:
            st = os.stat(p)
        except OSError:
            continue
        sig = f"{st.st_mtime_ns}:{st.st_size}"
        sigs[p] = sig
        total_bytes += st.st_size
        prev = cache.get(p)
        if not prev or prev.get("sig") != sig:
            changed.append(p)
            changed_bytes += st.st_size
    print("stat 全量                  %8.1f ms" % ms(t0))
    print("需重解析文件: %d / %d, 需读 %.0f MB / 共 %.0f MB"
          % (len(changed), len(files), changed_bytes / 1e6, total_bytes / 1e6))
    for p in changed[:8]:
        print("   变化: %s (%.1f MB)" % (os.path.basename(p), os.path.getsize(p) / 1e6))

    # --- (b) 缓存里有多少条 entries（= 每次刷新必然要"重放"的条数） ---
    n_entries = sum(len(v.get("entries", [])) for k, v in cache.items() if k != "__sids__")
    print("缓存条目总数(重放量): %d" % n_entries)

    # --- (c) 重放一次的纯 Python 成本(模拟 _agg 循环) ---
    t0 = time.perf_counter()
    seen = set()
    models = {}
    n = 0
    for k, v in cache.items():
        if k == "__sids__":
            continue
        for e in v.get("entries", []):
            mid = e.get("mid") or ""
            if mid:
                if mid in seen:
                    continue
                seen.add(mid)
            m = e.get("m", "")
            b = models.setdefault(m, {})
            b["requests"] = b.get("requests", 0) + 1
            b["input"] = b.get("input", 0) + e.get("i", 0)
            b["total"] = b.get("total", 0) + e.get("t", 0)
            n += 1
    print("重放 %d 条(简化聚合)        %8.1f ms" % (n, ms(t0)))
    print("   -> 真实实现还要多聚合 daily 桶 + output/cached/reasoning，约 2~3 倍")

    # --- (d) 落盘成本 ---
    t0 = time.perf_counter()
    json_size_before = os.path.getsize(scanner.CACHE_FILE)
    # 只测序列化+写临时文件的成本，不覆盖真实缓存：写到 .prof.tmp
    import json
    tmp = scanner.CACHE_FILE + ".prof.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cache, f)
    os.remove(tmp)
    print("写出 cache.json (%.1f MB)   %8.1f ms" % (json_size_before / 1e6, ms(t0)))

    # --- (e) 去重采样成本(抽样 40 个文件外推) ---
    sample = files[:40]
    t0 = time.perf_counter()
    for p in sample:
        scanner._msg_id_sample(p, scanner.DUP_ID_SAMPLE)
    dt = ms(t0)
    print("_msg_id_sample ×40         %8.1f ms  -> 全量 %d 个约 %.0f ms"
          % (dt, len(files), dt / max(1, len(sample)) * len(files)))

    t0 = time.perf_counter()
    for p in sample:
        scanner._head_sig(p)
    print("_head_sig ×40              %8.1f ms  -> 全量约 %.0f ms"
          % (ms(t0), ms(t0) / max(1, len(sample)) * len(files)))


if __name__ == "__main__":
    main()
