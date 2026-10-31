#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""增量扫描专项校验 (@2026-10-31 第105轮: 刷新提速)。

覆盖：首次全量 / 无变化复用 / 追加尾部 / 半行 / 截断重写 / 首部重写 /
      超大行跳过 / 消息级去重 / 去重结论缓存。

全部在 tempfile.mkdtemp() 里造假的 projects + 假 cache，**绝不触碰真实会话数据**。
用法: python -B tools/check_incr_scan.py
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

PASS = 0
FAIL = 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  ✅ %s" % name)
    else:
        FAIL += 1
        print("  ❌ %s %s" % (name, detail))


def ms_line(mid, model="test-model", i=10, o=5, ts=1793400000000, sid="sess-a"):
    return json.dumps({
        "id": mid, "timestamp": ts, "sessionId": sid,
        "providerData": {"model": model,
                         "usage": {"inputTokens": i, "outputTokens": o,
                                   "totalTokens": i + o}},
    }, ensure_ascii=False)


def write(p, lines, newline=True):
    with open(p, "w", encoding="utf-8") as f:
        for idx, ln in enumerate(lines):
            if idx == len(lines) - 1 and not newline:
                f.write(ln)          # 最后一行故意不写换行(模拟"正在写")
            else:
                f.write(ln + "\n")


def append(p, lines, newline=True):
    with open(p, "a", encoding="utf-8") as f:
        for idx, ln in enumerate(lines):
            if idx == len(lines) - 1 and not newline:
                f.write(ln)
            else:
                f.write(ln + "\n")


def main():
    root = tempfile.mkdtemp(prefix="ts_incr_")
    proj = os.path.join(root, "projects")
    data = os.path.join(root, "data")
    os.makedirs(proj)
    os.makedirs(data)
    # 打补丁: 全部指向临时目录(项目目录 + 缓存/统计文件)
    scanner.PROJECTS_DIR = proj
    scanner.CACHE_FILE = os.path.join(data, "cache.json")
    scanner.STATS_FILE = os.path.join(data, "stats.json")

    fa = os.path.join(proj, "a.jsonl")
    fb = os.path.join(proj, "b.jsonl")
    write(fa, [ms_line("m1"), ms_line("m2")])
    write(fb, [ms_line("m3", i=20, o=7)])

    print("\n[1] 首次全量")
    r1 = scanner.scan_full()
    check("条目数 3", r1["entriesTotal"] == 3, r1["entriesTotal"])
    check("模型合计 = 10+10+20", r1["models"]["test-model"]["input"] == 40,
          r1["models"]["test-model"]["input"])
    check("filesRescanned = 2", r1["filesRescanned"] == 2, r1["filesRescanned"])
    check("有 3 条会话", r1["dailySessions"] and sum(r1["dailySessions"].values()) == 1)

    print("\n[2] 无变化 → 全部复用（一次都不重读）")
    t = time.time()
    r2 = scanner.scan_full()
    check("条目数仍为 3", r2["entriesTotal"] == 3, r2["entriesTotal"])
    check("filesRescanned = 0", r2["filesRescanned"] == 0, r2["filesRescanned"])
    check("filesAppended = 0", r2.get("filesAppended") == 0, r2.get("filesAppended"))
    check("结果与首次一致", r2["models"] == r1["models"])

    print("\n[3] 追加两条 → 只读尾部")
    append(fa, [ms_line("m4", i=3), ms_line("m5", i=4)])
    r3 = scanner.scan_full()
    check("条目数 5", r3["entriesTotal"] == 5, r3["entriesTotal"])
    check("走尾部追加的文件 = 1", r3.get("filesAppended") == 1, r3.get("filesAppended"))
    check("输入合计 47", r3["models"]["test-model"]["input"] == 47,
          r3["models"]["test-model"]["input"])
    check("没把老条目算两遍(requests=5)", r3["models"]["test-model"]["requests"] == 5,
          r3["models"]["test-model"]["requests"])

    print("\n[4] 半行不解析，补全后只计一次")
    append(fa, [ms_line("m6", i=100)], newline=False)
    r4 = scanner.scan_full()
    check("条目数仍 5(半行不计)", r4["entriesTotal"] == 5, r4["entriesTotal"])
    append(fa, [], newline=True)          # 补一个换行
    with open(fa, "a", encoding="utf-8") as f:
        f.write("\n")
    r5 = scanner.scan_full()
    check("补全后 6 条", r5["entriesTotal"] == 6, r5["entriesTotal"])
    check("补全后输入 147", r5["models"]["test-model"]["input"] == 147,
          r5["models"]["test-model"]["input"])
    r5b = scanner.scan_full()
    check("再扫不重复计(仍 6 条)", r5b["entriesTotal"] == 6, r5b["entriesTotal"])

    print("\n[5] 截断重写 → 回退全量，结果按新内容")
    write(fa, [ms_line("m10", i=1), ms_line("m11", i=2)])
    r6 = scanner.scan_full()
    check("条目数 3 (2 新 + b 的 1)", r6["entriesTotal"] == 3, r6["entriesTotal"])
    check("输入合计 1+2+20=23", r6["models"]["test-model"]["input"] == 23,
          r6["models"]["test-model"]["input"])

    print("\n[6] 首部重写(内容整体替换且变长) → 回退全量")
    write(fa, [ms_line("x1", i=50), ms_line("x2", i=50), ms_line("x3", i=50)])
    r7 = scanner.scan_full()
    check("输入合计 150+20=170", r7["models"]["test-model"]["input"] == 170,
          r7["models"]["test-model"]["input"])
    check("旧条目 m10/m11 已消失", r7["entriesTotal"] == 4, r7["entriesTotal"])

    print("\n[7] 超大行跳过(> _MAX_LINE)")
    big = os.path.join(proj, "big.jsonl")
    with open(big, "w", encoding="utf-8") as f:
        f.write(json.dumps({"id": "huge", "pad": "x" * (scanner._MAX_LINE + 10)}) + "\n")
        f.write(ms_line("after-huge", i=9) + "\n")
    r8 = scanner.scan_full()
    check("超大行没让扫描出错", isinstance(r8["entriesTotal"], int))
    check("超大行后的正常行仍计入", r8["models"]["test-model"]["input"] == 179,
          r8["models"]["test-model"]["input"])

    print("\n[8] 消息级去重: 两个文件含同一条消息 → 只计一次")
    fc = os.path.join(proj, "c.jsonl")
    write(fc, [ms_line("x1", i=50), ms_line("dup1", i=7, sid="sess-c")])
    r9 = scanner.scan_full()
    check("重复的 x1 不被重复计", r9["models"]["test-model"]["requests"] == 6,
          r9["models"]["test-model"]["requests"])
    check("输入合计 179+7=186", r9["models"]["test-model"]["input"] == 186,
          r9["models"]["test-model"]["input"])

    print("\n[9] 去重结论缓存: 未变化时不再重算")
    cache = scanner._load_cache()
    sig1 = (cache.get("__dup__") or {}).get("sig")
    check("缓存里有 __dup__ 段", bool(sig1))
    r10 = scanner.scan_full()
    cache2 = scanner._load_cache()
    check("结论签名稳定(未重算)", (cache2.get("__dup__") or {}).get("sig") == sig1)
    check("两次结果一致", r10["entriesTotal"] == r9["entriesTotal"])

    print("\n[10] 缓存格式与体积")
    raw = open(scanner.CACHE_FILE, "rb").read()
    check("落盘是紧凑 JSON(无空格分隔)", b", " not in raw[:4000])
    ent = [v for k, v in cache2.items() if not k.startswith("__")][0]
    check("条目是 list(紧凑格式)", isinstance(ent.get("entries", [None])[0], list),
          type(ent.get("entries", [None])[0]))
    check("缓存带 off / hd 字段", "off" in ent and "hd" in ent, sorted(ent))
    print("   cache.json = %.1f KB" % (len(raw) / 1024))

    print("\n[11] 旧格式(dict 条目)自动升级")
    # 手工造一份 v1 缓存: 条目是 dict, 且没有 off/hd
    v1 = {}
    for k, v in cache2.items():
        if k.startswith("__"):
            continue
        v1[k] = {"sig": v["sig"], "entries": [
            {"d": e[0], "m": e[1], "i": e[2], "o": e[3], "t": e[4], "c": e[5],
             "r": e[6], "s": e[7], "mid": e[8], "ts": e[9]}
            for e in v["entries"]]}
    with open(scanner.CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(v1, f)
    r11 = scanner.scan_full()
    check("升级后条目数不变", r11["entriesTotal"] == r9["entriesTotal"],
          r11["entriesTotal"])
    check("升级后数值不变", r11["models"] == r9["models"])
    cache3 = scanner._load_cache()
    e3 = [v for k, v in cache3.items() if not k.startswith("__")][0]
    check("升级后条目变成 list", isinstance(e3["entries"][0], list))

    print("\n" + "=" * 52)
    print("结果: %d 通过, %d 失败" % (PASS, FAIL))
    shutil.rmtree(root, ignore_errors=True)
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
