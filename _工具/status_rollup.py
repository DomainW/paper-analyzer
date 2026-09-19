# -*- coding: utf-8 -*-
"""库内各论文「分析 + 复现」现状一览（纯本地读，不联网）。
输出：每篇 = 报告 md/docx 字节+日期、图数、docx 内嵌图数、资源清单 §0 合计、README §0 三态、⛔ 步骤、卡点数；
      末附方向综述 / 学科论断产物清单。
"""
import glob
import io
import os
import re
import time
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIB = os.path.join(ROOT, "论文库")


def dt(p):
    return time.strftime("%m-%d %H:%M", time.localtime(os.path.getmtime(p)))


def sz(p):
    return os.path.getsize(p)


rows = []
for rd in sorted(glob.glob(LIB + "/**/复现/README.md", recursive=True)):
    pd = os.path.dirname(os.path.dirname(rd))
    rel = os.path.relpath(pd, LIB).replace("\\", "/")
    disc, direc = rel.split("/")[0], rel.split("/")[1]
    name = os.path.basename(pd)
    short = name.split("（")[0][:34]

    an = os.path.join(pd, "分析")
    mds = sorted(glob.glob(an + "/*-分析报告.md"))
    docxs = sorted(glob.glob(an + "/*-分析报告.docx"))
    pngs = sorted(glob.glob(an + "/*.png"))
    mdi = "[%d B %s]" % (sz(mds[0]), dt(mds[0])) if mds else "(缺)"
    dxi = "[%d B %s]" % (sz(docxs[0]), dt(docxs[0])) if docxs else "(缺)"
    emb = "-"
    if docxs:
        try:
            z = zipfile.ZipFile(docxs[0])
            emb = str(len([n for n in z.namelist() if n.startswith("word/media/")]))
        except Exception:
            emb = "ERR"

    r = io.open(rd, encoding="utf-8").read()
    st = {}
    blocked = []
    for ln in r.split("\n"):
        if re.match(r"^\|\s*\d+\s", ln):
            c = [x.strip() for x in ln.strip().strip("|").split("|")]
            if len(c) >= 2 and c[1] in ("✅", "🔄", "⛔"):
                st[c[1]] = st.get(c[1], 0) + 1
                if c[1] == "⛔":
                    blocked.append(c[0].split()[0])
    cap = 0
    m = re.search(r"##\s*8\.[^\n]*\n(.*?)(?=\n##\s*9\.|\Z)", r, re.S)
    if m:
        cap = sum(1 for ln in m.group(1).split("\n")
                  if ln.startswith("|") and not re.match(r"^\|[\s\-:|]+\|$", ln) and "卡点" not in ln)

    mf = os.path.join(pd, "资源清单.md")
    mtot = "(无)"
    if os.path.exists(mf):
        for ln in io.open(mf, encoding="utf-8").read().split("\n"):
            if ln.startswith("| **合计**"):
                c = [x.strip().strip("*") for x in ln.strip().strip("|").split("|")]
                if len(c) >= 6:
                    mtot = "%s条 ☐%s 🔄%s ✅%s ⛔%s" % (c[1], c[2], c[3], c[4], c[5])
                break

    rows.append((disc, direc, short, mdi, dxi, len(pngs), emb, mtot, st, blocked, cap))

print("学科 / 方向")
for (disc, direc, short, mdi, dxi, npng, emb, mtot, st, blocked, cap) in rows:
    print("=" * 118)
    print("【%s】%s" % (disc, direc))
    print("  论文: %s" % short)
    print("  分析: 报告 %s | docx %s | 图 %d 张 | docx 内嵌图 %s" % (mdi, dxi, npng, emb))
    print("  复现: 清单 §0 = %s | README 状态 ✅%d 🔄%d ⛔%d | ⛔步骤 %s | §8 卡点 %d 条"
          % (mtot, st.get("✅", 0), st.get("🔄", 0), st.get("⛔", 0),
             ",".join(blocked) if blocked else "无", cap))

print("=" * 118)
print("方向综述 / 学科论断产物：")
for p in sorted(glob.glob(LIB + "/**/方向综述/*.md", recursive=True)) + \
        sorted(glob.glob(LIB + "/方向论断/*.md", recursive=True)):
    print("   %8d B %s  %s" % (sz(p), dt(p), os.path.relpath(p, LIB).replace("\\", "/")))
