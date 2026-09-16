# -*- coding: utf-8 -*-
"""读取火绒的日志库 (只读拷贝到临时目录再查), 列出完整的查杀历史。"""
import os, shutil, sqlite3, tempfile, time, glob

SRC = r"C:\ProgramData\Huorong\Sysdiag"
TMP = tempfile.mkdtemp(prefix="hr_")
print("临时目录:", TMP)

for name in ("log.db", "log.db-wal", "log.db-shm", "applog.db", "applog.db-wal",
             "QuarantineEx.db", "QuarantineEx.db-wal"):
    s = os.path.join(SRC, name)
    if os.path.exists(s):
        try:
            shutil.copy2(s, os.path.join(TMP, name))
            print("  已拷贝", name, os.path.getsize(s), "B")
        except Exception as e:
            print("  拷贝失败", name, e)

for db in ("log.db", "applog.db", "QuarantineEx.db"):
    p = os.path.join(TMP, db)
    if not os.path.exists(p):
        continue
    print("\n" + "=" * 66)
    print("DB:", db)
    try:
        con = sqlite3.connect("file:%s?mode=ro" % p.replace("\\", "/"), uri=True)
        cur = con.cursor()
        tabs = [r[0] for r in cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        print("  表:", tabs)
        for t in tabs:
            try:
                n = cur.execute("SELECT COUNT(*) FROM [%s]" % t).fetchone()[0]
            except Exception:
                n = "?"
            cols = []
            try:
                cols = [c[1] for c in cur.execute("PRAGMA table_info([%s])" % t).fetchall()]
            except Exception:
                pass
            print("   - %-24s 行数=%-7s 列=%s" % (t, n, ",".join(cols)[:150]))
        con.close()
    except Exception as e:
        print("  打开失败:", e)
        continue

    # 尝试把可能含查杀记录的表 dump 出来
    try:
        con = sqlite3.connect("file:%s?mode=ro" % p.replace("\\", "/"), uri=True)
        cur = con.cursor()
        for t in tabs:
            cols = [c[1] for c in cur.execute("PRAGMA table_info([%s])" % t).fetchall()]
            low = " ".join(cols).lower()
            if any(k in low for k in ("path", "file", "name", "virus", "threat", "time", "desc")):
                rows = cur.execute("SELECT * FROM [%s] ORDER BY rowid DESC LIMIT 25" % t).fetchall()
                if not rows:
                    continue
                print("\n  --- %s 最近 %d 行 ---" % (t, len(rows)))
                for r in rows:
                    cells = []
                    for c, v in zip(cols, r):
                        s = str(v)
                        if len(s) > 60:
                            s = s[:60] + "…"
                        cells.append("%s=%s" % (c, s))
                    print("     " + " | ".join(cells)[:300])
        con.close()
    except Exception as e:
        print("  查询失败:", e)

print("\n== 隔离区文件体积与文件头 (pyc 魔数检查) ==")
q = os.path.join(SRC, "Quarantine")
for f in sorted(glob.glob(os.path.join(q, "*"))):
    try:
        st = os.stat(f)
        head = open(f, "rb").read(16)
        is_pyc = head[:4] == b"\xcb\x0d\x0d\x0a"
        print("  %s %8d B  头=%s  %s" % (
            time.strftime("%m-%d %H:%M", time.localtime(st.st_mtime)), st.st_size,
            head[:8].hex(), "Py3.13 pyc" if is_pyc else ""))
    except Exception as e:
        print("  ", f, e)
