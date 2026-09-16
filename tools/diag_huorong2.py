# -*- coding: utf-8 -*-
"""把火绒 log.db 里 filemon / c_malinfo / quarantine 相关记录完整解出来。"""
import os, shutil, sqlite3, tempfile, json, time

SRC = r"C:\ProgramData\Huorong\Sysdiag"
TMP = tempfile.mkdtemp(prefix="hr2_")
for name in ("log.db", "log.db-wal", "log.db-shm"):
    s = os.path.join(SRC, name)
    if os.path.exists(s):
        try:
            shutil.copy2(s, os.path.join(TMP, name))
        except Exception:
            pass
db = os.path.join(TMP, "log.db")
con = sqlite3.connect("file:%s?mode=ro" % db.replace("\\", "/"), uri=True)
cur = con.cursor()

print("=" * 70)
print("① 最近 20 条 filemon (文件监控) 记录")
rows = cur.execute("SELECT id,ts,detail FROM HrLogV3_60 WHERE fname='filemon' "
                   "ORDER BY id DESC LIMIT 20").fetchall()
for i, ts, det in rows:
    try:
        d = json.loads(det)
    except Exception:
        d = {"raw": str(det)[:200]}
    inner = d.get("detail", d)
    task = inner.get("task")
    print("--- id=%s  %s  task=%s" % (i, time.strftime("%m-%d %H:%M:%S", time.localtime(ts)), task))
    drop = {"guid", "fid"}
    for k, v in inner.items():
        if k in drop:
            continue
        s = json.dumps(v, ensure_ascii=False) if not isinstance(v, str) else v
        print("     %-14s %s" % (k, s[:220]))

print("\n" + "=" * 70)
print("② 最近 12 条 c_malinfo (恶意 URL/进程信息)")
rows = cur.execute("SELECT id,ts,detail FROM HrLogV3_60 WHERE fname='c_malinfo' "
                   "ORDER BY id DESC LIMIT 12").fetchall()
for i, ts, det in rows:
    try:
        d = json.loads(det)
    except Exception:
        d = {}
    print("--- id=%s  %s" % (i, time.strftime("%m-%d %H:%M:%S", time.localtime(ts))))
    print("     " + json.dumps(d.get("detail", d), ensure_ascii=False)[:400])

print("\n" + "=" * 70)
print("③ 所有 fname 种类与条数 (近期)")
for fn, n in cur.execute("SELECT fname,COUNT(*) FROM HrLogV3_60 GROUP BY fname "
                         "ORDER BY COUNT(*) DESC").fetchall():
    print("     %-16s %d" % (fn, n))

print("\n" + "=" * 70)
print("④ 含 python / pyc / token-stats 的记录 (全表扫描)")
seen = 0
for i, ts, fn, det in cur.execute("SELECT id,ts,fname,detail FROM HrLogV3_60 "
                                  "ORDER BY id DESC").fetchall():
    low = (det or "").lower()
    if any(k in low for k in ("python", ".pyc", "token-stats", "card_app", "shellloader", "huorong")):
        seen += 1
        if seen <= 15:
            print("--- id=%s %s fn=%s" % (i, time.strftime("%m-%d %H:%M:%S",
                                                           time.localtime(ts)), fn))
            print("     " + str(det)[:400])
print("     命中总数:", seen)
con.close()
