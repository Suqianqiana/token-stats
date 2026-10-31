#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""老版本 vs 新版 统计口径逐字段对账（第105轮刷新提速的安全性证明）。

只回答一个问题：**提速有没有动到"去重 + 精准统计"**。
做法：从 git 取出提速前的 scanner.py（默认 ee26e0c），把同一份真实会话数据
（体积 <= 上限的一批文件，拷到临时目录冻结）分别喂给老/新两版，逐字段比对。

四条断言：
  A. 老版(全量) == 新版(全量)         → 统计口径没变
  B. 新版(增量命中缓存) == 新版(全量)  → 缓存重放不漏不重
  C. 追加数据后 增量 == 全量           → 尾部增量不漏不重
  D. 截断重写后 增量 == 全量           → 回退全量路径正确

用法: python -B tools/check_refresh_equiv.py [--max-mb=1]
"""
import sys
sys.dont_write_bytecode = True
import importlib.util
import json
import os
import shutil
import subprocess
import tempfile
import time

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REAL_PROJECTS = os.path.expanduser("~/.workbuddy/projects")
OLD_REV = os.environ.get("EQ_OLD_REV", "ee26e0c")   # 第104轮末 = 提速前

PASS = 0
FAIL = 0

# 要比对的字段（老版没有 filesAppended / cache 相关的新字段）
FIELDS = ("entriesTotal", "models", "daily", "sessionsTotal", "dailySessions",
          "dupFilesDropped", "dupFilesTotal", "today", "firstDay", "lastDay")


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  ✅ %s" % name)
    else:
        FAIL += 1
        print("  ❌ %s %s" % (name, detail))


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def diff_fields(a, b):
    out = []
    for f in FIELDS:
        if a.get(f) != b.get(f):
            out.append(f)
    return out


def detail_diff(a, b):
    """把差异说清楚：哪个字段、差多少。"""
    lines = []
    for f in diff_fields(a, b):
        va, vb = a.get(f), b.get(f)
        if f in ("entriesTotal", "sessionsTotal", "dupFilesDropped", "dupFilesTotal"):
            lines.append("    %s: 老=%s 新=%s (差 %s)" % (f, va, vb, (vb or 0) - (va or 0)))
        elif f == "models":
            keys = set(va or {}) | set(vb or {})
            n = 0
            for k in sorted(keys):
                if (va or {}).get(k) != (vb or {}).get(k):
                    n += 1
                    if n <= 3:
                        lines.append("    model %s: 老=%s 新=%s" % (k, (va or {}).get(k), (vb or {}).get(k)))
            lines.append("    共 %d 个模型桶不一致" % n)
        elif f == "daily":
            keys = set(va or {}) | set(vb or {})
            n = sum(1 for k in keys if (va or {}).get(k) != (vb or {}).get(k))
            lines.append("    daily 有 %d 天不一致" % n)
        else:
            lines.append("    %s: 老=%s 新=%s" % (f, str(va)[:80], str(vb)[:80]))
    return "\n".join(lines)


def snapshot_projects(dst, max_mb):
    """把体积 <= max_mb 的会话文件拷到 dst（冻结一份，供两版共用）。"""
    picked, total = 0, 0
    for root, _d, files in os.walk(REAL_PROJECTS):
        for fn in files:
            if not fn.endswith(".jsonl"):
                continue
            s = os.path.join(root, fn)
            try:
                size = os.path.getsize(s)
            except OSError:
                continue
            if size == 0 or size > max_mb * 1024 * 1024:
                continue
            shutil.copy2(s, os.path.join(dst, fn))
            picked += 1
            total += size
    return picked, total


def main():
    max_mb = 1.0
    for a in sys.argv[1:]:
        if a.startswith("--max-mb="):
            max_mb = float(a.split("=", 1)[1])

    root = tempfile.mkdtemp(prefix="ts_eq_")
    old_src = os.path.join(root, "scanner_old.py")
    try:
        blob = subprocess.run(["git", "-C", BASE, "show", "%s:scanner.py" % OLD_REV],
                              capture_output=True, check=True).stdout
        with open(old_src, "wb") as f:
            f.write(blob)
    except Exception as e:
        print("取不到老版本 scanner.py (%s)，中止" % e)
        shutil.rmtree(root, ignore_errors=True)
        return 2

    proj = os.path.join(root, "projects")
    os.makedirs(proj)
    picked, total = snapshot_projects(proj, max_mb)
    print("冻结数据: %d 个文件 / %.0f MB（%d MB 以下的全部会话）" % (picked, total / 1e6, max_mb))
    if picked == 0:
        print("没有可用的会话文件，中止")
        shutil.rmtree(root, ignore_errors=True)
        return 2

    old = load_module(old_src, "scanner_old")
    new = load_module(os.path.join(BASE, "scanner.py"), "scanner_new")

    def setup(mod, tag):
        d = os.path.join(root, "data_" + tag)
        os.makedirs(d, exist_ok=True)
        mod.PROJECTS_DIR = proj
        mod.CACHE_FILE = os.path.join(d, "cache.json")
        mod.STATS_FILE = os.path.join(d, "stats.json")
        return mod

    setup(old, "old")
    setup(new, "new_full")          # 全量基准（每轮都强制全扫）
    setup(new, "new_incr")          # 增量基准（保留缓存）

    print("\n[1] 老版 全量扫描（提速前代码）…")
    t0 = time.time()
    r_old = old.scan_full(force=True)
    print("    耗时 %.1fs" % (time.time() - t0))

    print("\n[2] 新版 全量扫描（同一份数据，不用缓存）…")
    t0 = time.time()
    r_new_full = new.scan_full(force=True)
    print("    耗时 %.1fs" % (time.time() - t0))
    d = diff_fields(r_old, r_new_full)
    check("A. 老版全量 == 新版全量（统计口径没变）", not d, "\n" + detail_diff(r_old, r_new_full))
    check("A2. 条目数一致 (%s)" % r_old["entriesTotal"], r_old["entriesTotal"] == r_new_full["entriesTotal"])

    print("\n[3] 新版 第一次增量扫描（建缓存）…")
    t0 = time.time()
    r1 = new.scan_full()
    print("    耗时 %.1fs（filesRescanned=%s filesAppended=%s）"
          % (time.time() - t0, r1.get("filesRescanned"), r1.get("filesAppended")))

    print("\n[4] 新版 第二次增量扫描（全部命中缓存重放）…")
    t0 = time.time()
    r2 = new.scan_full()
    print("    耗时 %.1fs（filesRescanned=%s filesAppended=%s）"
          % (time.time() - t0, r2.get("filesRescanned"), r2.get("filesAppended")))
    d = diff_fields(r_new_full, r2)
    check("B. 缓存重放 == 全量（不漏不重）", not d, "\n" + detail_diff(r_new_full, r2))

    print("\n[5] 追加 2 条 usage 后：增量 == 全量")
    victim = None
    for fn in sorted(os.listdir(proj))[:1]:
        victim = os.path.join(proj, fn)
    with open(victim, "a", encoding="utf-8") as f:
        for i in range(2):
            f.write(json.dumps({
                "id": "eqcase-%d" % i, "sessionId": "eq-sid",
                "timestamp": 1793400000000,
                "providerData": {"model": "eq-model",
                                 "usage": {"inputTokens": 11, "outputTokens": 3,
                                           "totalTokens": 14}}}) + "\n")
    r_incr = new.scan_full()
    print("    增量: entries=%s filesAppended=%s filesRescanned=%s"
          % (r_incr["entriesTotal"], r_incr.get("filesAppended"), r_incr.get("filesRescanned")))
    r_full2 = new.scan_full(force=True)
    d = diff_fields(r_full2, r_incr)
    check("C. 追加后 增量 == 全量（尾部增量不漏不重）", not d, "\n" + detail_diff(r_full2, r_incr))
    check("C2. 追加的 2 条确实计入了", r_incr["entriesTotal"] == r2["entriesTotal"] + 2,
          f"{r2['entriesTotal']} -> {r_incr['entriesTotal']}")
    check("C3. 尾部路径真的被走到（filesAppended>=1）", (r_incr.get("filesAppended") or 0) >= 1,
          str(r_incr.get("filesAppended")))

    print("\n[6] 截断重写该文件后：增量 == 全量")
    with open(victim, "w", encoding="utf-8") as f:
        f.write(json.dumps({
            "id": "eq-rewrite-0", "sessionId": "eq-sid2", "timestamp": 1793400000000,
            "providerData": {"model": "eq-model",
                             "usage": {"inputTokens": 5, "outputTokens": 1,
                                       "totalTokens": 6}}}) + "\n")
    r_incr2 = new.scan_full()
    r_full3 = new.scan_full(force=True)
    d = diff_fields(r_full3, r_incr2)
    check("D. 截断重写后 增量 == 全量（回退全量路径正确）", not d, "\n" + detail_diff(r_full3, r_incr2))

    print("\n[7] 历史副本场景（两账号轮换 / sid 被改的副本 / 无 sid 文件）：老版 == 新版")
    # 这批用例对应第67~70轮反复踩过的坑；提速改动不能让它有任何漂移。
    # ⚠️ 消息 id 必须 >= 6 字符 —— _msg_id_sample 的正则是 {6,}，短 id 不会被采样，
    #    副本识别就永远不触发（踩过一次，是夹具问题不是代码问题）。
    fx = os.path.join(root, "fixture")
    os.makedirs(fx, exist_ok=True)

    def _line(mid, sid, i=10, o=5, model="fx-model"):
        return json.dumps({"id": mid, "sessionId": sid, "timestamp": 1793400000000,
                           "providerData": {"model": model,
                                            "usage": {"inputTokens": i, "outputTokens": o,
                                                      "totalTokens": i + o}}})

    # A: 账号1 的前 6 条
    with open(os.path.join(fx, "aaaa-1111.jsonl"), "w", encoding="utf-8") as f:
        for k in range(6):
            f.write(_line("fxmsg-A-%d" % k, "sid-A") + "\n")
    # B: 账号2 —— 共享 A 的前 4 条, 再加自己的 4 条(轮换继续对话)
    with open(os.path.join(fx, "bbbb-2222.jsonl"), "w", encoding="utf-8") as f:
        for k in range(4):
            f.write(_line("fxmsg-A-%d" % k, "sid-B") + "\n")
        for k in range(4):
            f.write(_line("fxmsg-B-%d" % k, "sid-B", i=20) + "\n")
    # C: A 的副本, sid 被改掉、少最后一条(较小) —— 旧的"sid 判据"抓不到
    with open(os.path.join(fx, "cccc-3333.jsonl"), "w", encoding="utf-8") as f:
        for k in range(5):
            f.write(_line("fxmsg-A-%d" % k, "sid-C") + "\n")
    # D: B 的整份复制, sid 与大小都不同(各自续写)
    with open(os.path.join(fx, "dddd-4444.jsonl"), "w", encoding="utf-8") as f:
        for k in range(4):
            f.write(_line("fxmsg-A-%d" % k, "sid-D") + "\n")
        for k in range(4):
            f.write(_line("fxmsg-B-%d" % k, "sid-D", i=20) + "\n")
        f.write(_line("fxmsg-D-0", "sid-D", i=99) + "\n")
    # E: 完全没有 sessionId 的文件(必须原样保留, 宁多勿漏)
    with open(os.path.join(fx, "eeee-5555.jsonl"), "w", encoding="utf-8") as f:
        f.write(json.dumps({"id": "fxmsg-E-0", "timestamp": 1793400000000,
                            "providerData": {"model": "fx-model",
                                             "usage": {"inputTokens": 7, "outputTokens": 2,
                                                       "totalTokens": 9}}}) + "\n")

    for mod, tag in ((old, "fx_old"), (new, "fx_new")):
        d = os.path.join(root, "data_" + tag)
        os.makedirs(d, exist_ok=True)
        mod.PROJECTS_DIR = fx
        mod.CACHE_FILE = os.path.join(d, "cache.json")
        mod.STATS_FILE = os.path.join(d, "stats.json")
    r_old_fx = old.scan_full(force=True)
    r_new_fx = new.scan_full(force=True)
    d = diff_fields(r_old_fx, r_new_fx)
    check("E. 历史副本场景 老版 == 新版", not d, "\n" + detail_diff(r_old_fx, r_new_fx))
    check("E2. 共享历史确实只计一次(条目 = 6 + 4 + 1 + 1 = 12)",
          r_new_fx["entriesTotal"] == 12, r_new_fx["entriesTotal"])
    # 判据是 Jaccard >= 0.6：A↔C(5/6=0.83)、B↔D(8/9=0.89) 各成一组 → 各丢一份；
    # 而 A↔B 只有 4/10=0.40（两账号轮换的"共享前半段"）—— **不该被判成同源**，这正是第70轮的口径。
    check("E3. 副本识别仍然生效(dropped == 2)", (r_new_fx["dupFilesDropped"] or 0) == 2,
          r_new_fx["dupFilesDropped"])
    check("E5. 两账号轮换的两份都保留(部分重合不算副本)",
          (r_new_fx["dupFilesTotal"] or 0) - (r_new_fx["dupFilesDropped"] or 0) >= 3,
          f"total={r_new_fx['dupFilesTotal']} dropped={r_new_fx['dupFilesDropped']}")
    # 增量复跑也必须一致
    r_new_fx2 = new.scan_full()
    check("E4. 副本场景下 增量 == 全量", not diff_fields(r_new_fx, r_new_fx2),
          "\n" + detail_diff(r_new_fx, r_new_fx2))

    print("\n" + "=" * 52)
    print("口径摘要（新版全量）: 条目 %s / 会话 %s / 模型桶 %s / 天 %s / 副本丢弃 %s"
          % (r_new_full["entriesTotal"], r_new_full["sessionsTotal"],
             len(r_new_full["models"]), len(r_new_full["daily"]),
             r_new_full["dupFilesDropped"]))
    print("结果: %d 通过, %d 失败" % (PASS, FAIL))
    shutil.rmtree(root, ignore_errors=True)
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
