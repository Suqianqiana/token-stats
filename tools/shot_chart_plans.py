# -*- coding: utf-8 -*-
"""把方案 HTML 里的 SVG 抽出来, 用 QSvgRenderer 真实渲染成 PNG(供肉眼核验)。"""
import os, re, sys
sys.dont_write_bytecode = True
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from PySide6.QtGui import QGuiApplication, QImage, QPainter
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtCore import QByteArray

HTML = os.path.join(ROOT, "docs", "每日用量分布-三套方案.html")
OUTDIR = os.path.join(ROOT, "docs", "screenshots")
os.makedirs(OUTDIR, exist_ok=True)

h = open(HTML, encoding="utf-8").read()
svgs = re.findall(r'(<svg class="card".*?</svg>)', h, re.S)
print("找到 svg:", len(svgs))
names = ["planA_chart", "planB_chart", "planC_chart", "planA_chart_light"]

app = QGuiApplication(sys.argv)
SCALE = 2
for nm, s in zip(names, svgs[::2]):
    doc = ('<?xml version="1.0" encoding="UTF-8"?>'
           '<svg xmlns="http://www.w3.org/2000/svg"' + s[s.index(' viewBox') - 0:].replace(
               '<svg class="card"', '', 1) if False else s)
    # 直接补 xmlns
    doc = s.replace('<svg ', '<svg xmlns="http://www.w3.org/2000/svg" ', 1)
    m = re.search(r'viewBox="0 0 (\d+) (\d+)"', doc)
    vw, vh = int(m.group(1)), int(m.group(2))
    r = QSvgRenderer(QByteArray(doc.encode("utf-8")))
    if not r.isValid():
        print("  渲染器拒绝:", nm)
        continue
    img = QImage(vw * SCALE, vh * SCALE, QImage.Format_ARGB32)
    img.fill(0)
    p = QPainter(img)
    r.render(p)
    p.end()
    out = os.path.join(OUTDIR, "chartplan_%s.png" % nm)
    img.save(out)
    print("saved", out, img.width(), "x", img.height())
print("DONE")
