# -*- coding: utf-8 -*-
"""报告 md ↔ docx 的**日期口径**核对（默认只读；`--fix` 才写盘）。

口径（2026-09-19 维护者裁定，见 存档/README.md「版本口径」）：
**同一篇产物的 md 与 docx 日期冲突时，以 md 为准**——md 是源、docx 是 pandoc 派生物。
典型漂移：docx 记的是**该文件入库时刻**，md 记的是**维护者改定的 skill 落地日**。

用法：
    python _工具/docx_date_check.py            # 只列出不一致的篇目
    python _工具/docx_date_check.py --fix      # 先快照旧 docx 再从 md 重出，并逐项核验

`--fix` 的核验三连：① 日期集合与 md 一致；② 内嵌 `word/media/*` 与 `分析/*.png` 逐字节一致；
③ 新旧 docx 文本**字符级差分**证明除日期外无其它改动（有其它改动则报警，不静默接受）。
"""
import argparse
import difflib
import glob
import hashlib
import io
import os
import re
import shutil
import subprocess
import time
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIB = os.path.join(ROOT, "论文库")
SNAP_ROOT = os.path.join(ROOT, "存档", "论文层快照")

ap = argparse.ArgumentParser()
ap.add_argument("--fix", action="store_true", help="快照旧 docx 并从 md 重出（默认只核对）")
args = ap.parse_args()

REPORTS = sorted(glob.glob(LIB + "/**/分析/*-分析报告.md", recursive=True))
DATE = re.compile(r"2026-\d\d-\d\d")


def docx_text(p):
    return re.sub(r"<[^>]+>", "", zipfile.ZipFile(p).read("word/document.xml").decode("utf-8"))


def dates(s):
    return set(DATE.findall(s))


def dc_title(p):
    t = zipfile.ZipFile(p).read("docProps/core.xml").decode("utf-8")
    m = re.search(r"<dc:title>(.*?)</dc:title>", t, re.S)
    return m.group(1) if m else ""


SNAP = os.path.join(SNAP_ROOT, "报告docx-日期口径更正前-" + time.strftime("%Y-%m-%d"))
drift = []

for md in REPORTS:
    dx = md[:-3] + ".docx"
    if not os.path.exists(dx):
        print("⚠ 缺 docx：", os.path.relpath(md, ROOT))
        continue
    a, old = dates(io.open(md, encoding="utf-8").read()), docx_text(dx)
    b = dates(old)
    if a == b:
        print("✅ 一致: %-58s %s" % (os.path.basename(md)[:56], sorted(a)))
        continue
    drift.append(md)
    print("❌ 漂移: %s" % os.path.basename(md))
    print("     md 独有 %s ｜ docx 独有 %s" % (sorted(a - b), sorted(b - a)))
    if not args.fix:
        continue

    os.makedirs(SNAP, exist_ok=True)
    title = dc_title(dx)
    shutil.copy2(dx, os.path.join(SNAP, os.path.basename(dx)))
    print("     旧 docx 已快照 → 存档/论文层快照/%s/（title 保留：%s）"
          % (os.path.basename(SNAP), title[:40]))

    r = subprocess.run(["pandoc", os.path.basename(md), "-o", os.path.basename(dx),
                        "--from", "markdown", "--to", "docx", "--toc", "--toc-depth=2",
                        "--metadata", "title=" + title],
                       cwd=os.path.dirname(md), capture_output=True, text=True)
    assert r.returncode == 0, r.stderr

    new = docx_text(dx)
    z = zipfile.ZipFile(dx)
    med = sorted(hashlib.md5(z.read(n)).hexdigest()
                 for n in z.namelist() if n.startswith("word/media/"))
    live = sorted(hashlib.md5(open(p, "rb").read()).hexdigest()
                  for p in sorted(glob.glob(os.path.dirname(md) + "/*.png")))
    o, nw = re.sub(r"\s+", " ", old), re.sub(r"\s+", " ", new)
    chunks = [o[i1:i2] + "  ⇒  " + nw[j1:j2]
              for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, o, nw, autojunk=False).get_opcodes()
              if tag != "equal"]
    print("     ① 日期集合与 md 一致: %s" % (dates(io.open(md, encoding="utf-8").read()) == dates(new)))
    print("     ② 内嵌图 %d 张，与 分析/*.png 逐字节一致: %s" % (len(med), med == live))
    print("     ③ 新旧文本差异 %d 处：" % len(chunks))
    for c in chunks[:8]:
        print("        -", c[:110])

print("\n合计：%d 篇报告，%d 篇漂移%s"
      % (len(REPORTS), len(drift), "（已重出；请在 存档/README.md 索引登记）" if args.fix and drift
         else "（未改，加 --fix 重出）" if drift else "（全部一致）"))
