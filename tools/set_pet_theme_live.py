# -*- coding: utf-8 -*-
"""把桌宠主题切到指定值并重启应用 (只改 pet_theme / pet 两个键, 其它设置原样保留)。

用法: python -B tools/set_pet_theme_live.py v5
"""
import sys
sys.dont_write_bytecode = True
import json
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import scanner

SETTINGS = os.path.join(scanner.PLUGIN_DATA_DIR, "settings.json")


def main():
    theme = sys.argv[1] if len(sys.argv) > 1 else "v5"
    with open(SETTINGS, encoding="utf-8") as f:
        d = json.load(f)
    before = {k: d.get(k) for k in ("pet", "pet_theme", "source", "dark", "frost")}
    d["pet"] = True
    d["pet_theme"] = theme
    with open(SETTINGS, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
    print("before:", before)
    print("after :", {k: d.get(k) for k in ("pet", "pet_theme", "source", "dark", "frost")})


if __name__ == "__main__":
    main()
