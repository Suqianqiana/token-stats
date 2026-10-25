# -*- coding: utf-8 -*-
"""恢复被回归测试污染的 settings.json —— 只改指定键, 其余原样保留。

用法: python -B tools/fix_settings_keys.py
背景: 2026-10-25 跑回归后真实 settings.json 的 source/pet_theme 被改成 dsh/v3。
"""
import sys
sys.dont_write_bytecode = True
import json
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import scanner

SETTINGS = os.path.join(scanner.PLUGIN_DATA_DIR, "settings.json")

# 浅浅猫的真实取值(2026-10-25 09:00 人工核对)
WANT = {"source": "wb", "pet_theme": "v5", "pet": True}


def main():
    with open(SETTINGS, encoding="utf-8") as f:
        d = json.load(f)
    print("修改前:", {k: d.get(k) for k in WANT})
    for k, v in WANT.items():
        d[k] = v
    with open(SETTINGS, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
    print("修改后:", {k: d.get(k) for k in WANT})
    print("完整:", json.dumps(d, ensure_ascii=False))


if __name__ == "__main__":
    main()
