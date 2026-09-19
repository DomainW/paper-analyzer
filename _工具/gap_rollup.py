# -*- coding: utf-8 -*-
"""全库复现缺口滚动汇总（纯本地读取，不联网）：
  每篇：README §0 状态块的三态分布 + 未勾项数；资源清单 §0 的 ☐/🔄/✅/⛔ 与 ⛔ 步骤；README §8 卡点条数。
  未勾项口径与 pr_status.py 一致——**只认行首** `^\\s*[-*]\\s*\\[ \\]`（v2.1.2 起），
  正文里出现的 `- [ ]` 字面量不计入。
"""
import glob
import io
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIB = os.path.join(ROOT, "论文库")


def read(p):
    return io.open(p, encoding="utf-8").read()


print("%-34s %-26s %-22s %s" % ("论文", "README §0 三态", "清单 §0 (条/☐🔄✅⛔)", "README §8 卡点"))
print("-" * 120)
for rd in sorted(glob.glob(LIB + "/**/复现/README.md", recursive=True)):
    paper_dir = os.path.dirname(os.path.dirname(rd))
    name = os.path.basename(paper_dir)
    short = name.split("（")[0][:32]
    r = read(rd)
    # §0 状态块
    states = []
    for ln in r.split("\n"):
        if re.match(r"^\|\s*\d+\s", ln):
            c = [x.strip() for x in ln.strip().strip("|").split("|")]
            if len(c) >= 2 and c[1] in ("✅", "🔄", "⛔"):
                states.append((c[0].split()[0], c[1]))
    dist = {k: sum(1 for _, s in states if s == k) for k in ("✅", "🔄", "⛔")}
    blocked = [n for n, s in states if s == "⛔"]
    unchecked = sum(1 for ln in r.split("\n") if re.match(r"^\s*[-*]\s*\[ \]", ln))
    # §8 卡点表行数
    cap = 0
    m = re.search(r"##\s*8\.[^\n]*\n(.*?)(?=\n##\s*9\.|\Z)", r, re.S)
    if m:
        cap = sum(1 for ln in m.group(1).split("\n")
                  if ln.startswith("|") and not re.match(r"^\|[\s\-:|]+\|$", ln) and "卡点" not in ln)
    # 清单 §0
    mf = os.path.join(paper_dir, "资源清单.md")
    mstr = ""
    if os.path.exists(mf):
        mt = read(mf)
        for ln in mt.split("\n"):
            if ln.startswith("| **合计**"):
                c = [x.strip().strip("*") for x in ln.strip().strip("|").split("|")]
                mstr = "%s 条 / %s" % (c[0], "/".join(c[1:5]))
                break
    print("%-34s ✅%d 🔄%d ⛔%d 未勾%d   %-22s %s(%s)" % (
        short, dist["✅"], dist["🔄"], dist["⛔"], unchecked, mstr or "(无)", cap,
        ("⛔步骤 " + ",".join(blocked)) if blocked else "无 ⛔ 步骤"))
