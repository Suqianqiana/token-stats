# -*- coding: utf-8 -*-
"""第97轮: 自定义来源用量统计修复验证。

根因(浅猫反馈"step-5-preview / hy-4, 接口 127.0.0.1:8788/v1 统计不上用量"):
  WorkBuddy 对自定义来源只在 providerData 里落 **rawUsage**(OpenAI snake_case),
  而折算后的 providerData.usage **全是 0** —— 旧扫描器只读 usage, 于是这些用量凭空消失。
另: requestModelId 带 `custom-local:` 前缀, model 为空的记录会把同一个模型拆成两组。

本脚本:
  ① 用 rawUsage 回退重扫(隔离数据目录, 不碰真实 cache/stats);
  ② 对比修复前后今日 step-5-preview / hy4-preview 的用量;
  ③ 断言 custom-local: 前缀已被归一化(不再出现带前缀的 key)。
"""
import os, sys, json, tempfile, time
sys.dont_write_bytecode = True
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

TMP = tempfile.mkdtemp(prefix="tokstat_verify_")
import scanner
scanner.PLUGIN_DATA_DIR = TMP
scanner.CACHE_FILE = os.path.join(TMP, "cache.json")
scanner.STATS_FILE = os.path.join(TMP, "stats.json")

# ---- 修复前(旧逻辑)参照: 直接读 usage, 不读 rawUsage ----
def old_scan_models():
    from collections import defaultdict
    agg = defaultdict(lambda: {"requests": 0, "input": 0, "output": 0, "total": 0})
    for path in scanner._iter_jsonl_files():
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    if len(line) > scanner._MAX_LINE:
                        continue
                    try:
                        o = json.loads(line)
                    except Exception:
                        continue
                    pd = o.get("providerData") if isinstance(o, dict) else None
                    if not isinstance(pd, dict):
                        continue
                    u = pd.get("usage")
                    if not isinstance(u, dict):
                        continue
                    if not (u.get("inputTokens") or u.get("outputTokens")):
                        continue                      # ← 旧逻辑: 全 0 直接丢
                    m = (pd.get("model") or pd.get("requestModelId") or "unknown")
                    if scanner._norm_date(o.get("timestamp")) != time.strftime("%Y-%m-%d"):
                        continue
                    a = agg[m]
                    a["requests"] += 1
                    a["input"] += int(u.get("inputTokens") or 0)
                    a["output"] += int(u.get("outputTokens") or 0)
                    a["total"] += int(u.get("totalTokens") or 0)
        except OSError:
            continue
    return agg

print("=== 修复前(旧逻辑) 今日 ===", flush=True)
old = old_scan_models()
for k in ("step-5-preview", "hy4-preview"):
    v = old.get(k)
    print("   %-18s %s" % (k, v or "(无)"))

print("=== 修复后(带 rawUsage 回退) 全量重扫 ===", flush=True)
res = scanner.scan_full(force=True)
today = time.strftime("%Y-%m-%d")
daily_today = res["daily"].get(today, {})
for k in ("step-5-preview", "hy4-preview"):
    v = daily_today.get(k)
    print("   %-18s %s" % (k, json.dumps(v, ensure_ascii=False) if v else "(无)"))

bad = [k for k in res["models"] if k.startswith("custom-local:")]
print()
print("带 custom-local: 前缀的模型 key:", bad if bad else "无(已归一化)")

o_s = old.get("step-5-preview") or {"requests": 0, "input": 0}
n_s = daily_today.get("step-5-preview") or {"requests": 0, "input": 0}
o_h = old.get("hy4-preview") or {"requests": 0, "input": 0}
n_h = daily_today.get("hy4-preview") or {"requests": 0, "input": 0}
print()
print("step-5-preview : requests %d -> %d, input %d -> %d" % (
    o_s["requests"], n_s["requests"], o_s["input"], n_s["input"]))
print("hy4-preview    : requests %d -> %d, input %d -> %d" % (
    o_h["requests"], n_h["requests"], o_h["input"], n_h["input"]))

fails = []
if n_s["requests"] <= o_s["requests"]:
    fails.append("step-5-preview 记录数没有变多")
if n_s["input"] <= o_s["input"]:
    fails.append("step-5-preview input 没有变多")
if bad:
    fails.append("仍有 custom-local: 前缀 key")

# ---- 泛化用例: 合成数据验证"其它来源也不会漏" ----
print()
print("=== 泛化用例(合成数据) ===", flush=True)
def mk(obj):
    import json as _j
    return _j.dumps(obj, ensure_ascii=False)

cases = [
    # (名称, providerData+obj, 期望 input/output)
    ("usage 全 0 + rawUsage 有值",
     {"providerData": {"model": "m1", "usage": {"inputTokens": 0, "outputTokens": 0, "totalTokens": 0},
                       "rawUsage": {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120}}},
     (100, 20)),
    ("usage 全 0 + raw_usage(下划线名) 有值",
     {"providerData": {"model": "m2", "usage": {"inputTokens": 0, "outputTokens": 0, "totalTokens": 0},
                       "raw_usage": {"prompt_tokens": 55, "completion_tokens": 7, "total_tokens": 62}}},
     (55, 7)),
    ("usage 全 0 + usageRaw 有值",
     {"providerData": {"model": "m3", "usage": {"inputTokens": 0, "outputTokens": 0, "totalTokens": 0},
                       "usageRaw": {"prompt_tokens": 33, "completion_tokens": 4, "total_tokens": 37}}},
     (33, 4)),
    ("usage 正常(不触发回退)",
     {"providerData": {"model": "m4", "usage": {"inputTokens": 11, "outputTokens": 2, "totalTokens": 13}}},
     (11, 2)),
    ("顶层 usage 兜底",
     {"providerData": {"model": "m5"}, "usage": {"inputTokens": 9, "outputTokens": 1, "totalTokens": 10}},
     (9, 1)),
    ("custom-local: 前缀归一化",
     {"providerData": {"model": "", "requestModelId": "custom-local:step-5-preview",
                       "usage": {"inputTokens": 5, "outputTokens": 1, "totalTokens": 6}}},
     (5, 1)),
    ("无 usage 容器 → 不计(工具结果)",
     {"providerData": {"model": "m7", "toolResult": "ok"}},
     None),
    ("usage 全 0 且无原始响应 → 保留 requests、值为 0",
     {"providerData": {"model": "m8", "usage": {"inputTokens": 0, "outputTokens": 0, "totalTokens": 0}}},
     (0, 0)),
]
for name, obj, expect in cases:
    got = scanner._extract_usage_from_line(mk(obj))
    if expect is None:
        ok = (len(got) == 0)
        print("   %-38s -> %s" % (name, "不计 ✓" if ok else "误计 ✗ %s" % got))
    else:
        ok = bool(got) and got[0]["input"] == expect[0] and got[0]["output"] == expect[1]
        extra = ""
        if name.startswith("custom-local"):
            extra = " model=%s" % (got[0]["model"] if got else "?")
            ok = ok and bool(got) and got[0]["model"] == "step-5-preview"
        print("   %-38s -> input=%s output=%s%s %s" % (
            name, got[0]["input"] if got else "-", got[0]["output"] if got else "-",
            extra, "✓" if ok else "✗"))
    if not ok:
        fails.append("泛化用例失败: " + name)

print()
print("DONE fails=%d" % len(fails))
sys.exit(1 if fails else 0)
