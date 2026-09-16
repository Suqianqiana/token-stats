# -*- coding: utf-8 -*-
"""语法检查 —— 只编译到内存, 绝不落 __pycache__。

为什么不用 `python -m py_compile`: 它会把 .pyc 写到 __pycache__ 里, 而火绒把
`__pycache__/card_app.cpython-313.pyc` 误判成 Trojan/Python.ShellLoader.am
(实测 12 次删除+结束进程) —— 我们不能再制造这个文件。

用法: python tools/syntax_check.py [文件...]   (默认检查项目主要 py 文件)
"""
import ast
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT = ["card_app.py", "scanner.py", "test_switch_race.py", "launcher.py"] + [
    os.path.join("tools", f) for f in sorted(os.listdir(os.path.join(ROOT, "tools")))
    if f.endswith(".py")]


def main(paths):
    bad = 0
    for rel in paths:
        p = rel if os.path.isabs(rel) else os.path.join(ROOT, rel)
        if not os.path.exists(p):
            print("  跳过(不存在) %s" % rel)
            continue
        try:
            src = open(p, encoding="utf-8").read()
        except OSError as e:
            print("  读不到 %s: %s" % (rel, e))
            bad += 1
            continue
        try:
            compile(src, p, "exec", ast.PyCF_ONLY_AST)   # 只做语法分析, 不生成 pyc
            print("  OK   %s" % rel)
        except SyntaxError as e:
            print("  FAIL %s  第 %s 行: %s" % (rel, e.lineno, e.msg))
            bad += 1
    print("\n%s (%d 个文件)" % ("全部通过" if bad == 0 else "%d 个文件有语法错误" % bad,
                                len(paths)))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:] or DEFAULT))
