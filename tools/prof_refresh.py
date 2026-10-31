#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""刷新链路分阶段计时（只读，不改真实数据）。

用法: python -B tools/prof_refresh.py
分阶段量：缓存载入 / 文件枚举 / 副本去重 / 逐文件解析 / 缓存落盘 / 聚合写出，
外加 DSH 与商汤两条路径（商汤走 TTL 缓存，不主动联网，除非 --sn-force）。
"""
import sys
sys.dont_write_bytecode = True
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import scanner  # noqa: E402


def t(label, fn, *a, **kw):
    t0 = time.perf_counter()
    r = fn(*a, **kw)
    dt = (time.perf_counter() - t0) * 1000
    print("  %-22s %8.1f ms" % (label, dt))
    return r, dt


def main():
    print("数据目录:", scanner.PLUGIN_DATA_DIR)
    print("项目目录:", scanner.PROJECTS_DIR)

    cache_file = scanner.CACHE_FILE
    print("\n[1] 缓存文件")
    print("  cache.json 大小: %.2f MB" % (os.path.getsize(cache_file) / 1e6 if os.path.exists(cache_file) else 0))

    (cache, dt) = t("载入 cache.json", scanner._load_cache)
    print("  缓存条目数: %d (其中文件游标 %d)" % (
        len(cache), len([k for k in cache if k != "__sids__"])))

    files = t("枚举 jsonl 文件", lambda: list(scanner._iter_jsonl_files()))[0]
    total = 0
    for p in files:
        try:
            total += os.path.getsize(p)
        except OSError:
            pass
    print("  文件数: %d, 合计 %.1f MB" % (len(files), total / 1e6))

    print("\n[2] 副本去重 (_dedupe_files)")
    t("_dedupe_files", scanner._dedupe_files, files, cache.get("__sids__") or {})

    print("\n[3] 完整扫描 scan_full() —— 增量路径（默认，模拟点刷新）")
    s1 = t("scan_full() 第1次", scanner.scan_full)[0]
    s2 = t("scan_full() 第2次（缓存已热）", scanner.scan_full)[0]
    print("  会话数/条目: filesScanned=%s entriesTotal=%s" % (s1.get("filesScanned"), s1.get("entriesTotal")))
    print("  两次结果一致:", s1.get("entriesTotal") == s2.get("entriesTotal"))

    print("\n[4] 强制全量 scan_full(force=True) —— 对比用")
    t("scan_full(force=True)", scanner.scan_full, True)

    print("\n[5] DSH 路径")
    try:
        import card_app
        t("load_dsh_stats()", card_app.load_dsh_stats)
    except Exception as e:
        print("  (跳过) %s" % e)

    print("\n[6] 商汤路径（只读 TTL 缓存，不联网）")
    try:
        import card_app
        t("load_sn_stats()", card_app.load_sn_stats)
    except Exception as e:
        print("  (跳过) %s" % e)


if __name__ == "__main__":
    main()
