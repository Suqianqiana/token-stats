#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""真实数据下的刷新提速基准（只读真实会话，缓存走临时副本）。

用法: python -B tools/bench_refresh.py
做法: 把线上 cache.json / stats.json 拷到 tempfile 目录后再跑三遍扫描,
      既不污染线上缓存(应用正在跑), 又能拿到真实规模下的前后耗时。
"""
import sys
sys.dont_write_bytecode = True
import json
import os
import shutil
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import scanner  # noqa: E402

LIVE_DATA = scanner.PLUGIN_DATA_DIR


def main():
    tmp = tempfile.mkdtemp(prefix="ts_bench_")
    for fn in ("cache.json", "stats.json"):
        src = os.path.join(LIVE_DATA, fn)
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(tmp, fn))
    scanner.CACHE_FILE = os.path.join(tmp, "cache.json")
    scanner.STATS_FILE = os.path.join(tmp, "stats.json")

    base = {}
    try:
        with open(os.path.join(tmp, "stats.json"), "r", encoding="utf-8") as f:
            base = json.load(f)
    except Exception:
        pass
    print("线上 stats.json 基线: entriesTotal=%s scanSeconds=%s files=%s"
          % (base.get("entriesTotal"), base.get("scanSeconds"), base.get("filesTracked")))
    print("拷来的 cache.json: %.2f MB" % (os.path.getsize(scanner.CACHE_FILE) / 1e6))
    print()

    for i in range(1, 4):
        t0 = time.perf_counter()
        r = scanner.scan_full()
        dt = time.perf_counter() - t0
        print("第%d次  %6.2f s  | 重扫 %d 个 / 尾部 %d 个 | 条目 %d | 会话 %d | 缓存 %.2f MB"
              % (i, dt, r["filesRescanned"], r.get("filesAppended", -1),
                 r["entriesTotal"], r["sessionsTotal"],
                 os.path.getsize(scanner.CACHE_FILE) / 1e6))
        if i == 1:
            print("        （第1次含旧格式迁移：变化过的文件要全量读一遍）")
        if base:
            print("        条目较基线 +%d" % (r["entriesTotal"] - (base.get("entriesTotal") or 0)))

    print("\n清理临时目录:", tmp)
    shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
