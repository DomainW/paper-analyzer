# -*- coding: utf-8 -*-
"""Markdown 表格完整性 + 转义自查（纯本地读，不联网）。查两类**会静默丢字的口子**：

【一】表格单元格里出现未转义的裸 `|`（如 `|P|×|F|`、`ρ=|a-b|/c`）。
GitHub / pandoc 的管道表格按 `|` 切格，于是该行的列数**多出表头**；
超出表头的单元格会被**直接丢弃** → 该行靠右的列（含金量、为什么重要等）**在 md 渲染与 docx 里整列消失**，
而 md 源文看起来"全都在"。必查项。

【二】代码段 / 数学环境 / 围栏块之外出现**裸「反斜杠+字母」**（`\\x`、`\\Program`、`\\MATLAB`）。
pandoc 把 `\\xxx` 当 LaTeX 控制词：`|y\\x|` 渲染成 `|y|`（丢了 `x`！）、`C:\\Program Files\\MATLAB\\R2018b`
渲染成 `C:Files2018b`。合法写法：标点转义 `\\|`／`\\*`、或**双写** `\\\\x`、或用代码段包住（代码段内按字面）。
（`\\` 后接标点的转义、以及已双写的反斜杠，均不报。）

用法：
    python _工具/table_check.py                 # 扫 论文库/ + 根目录 + _工具/ + .claude/skills/
    python _工具/table_check.py <文件或目录>…    # 只扫指定范围
退出码：发现问题 = 1（可直接用于完成线判定），全清 = 0。
不在默认范围的两处（要扫请显式传路径）：`存档/`（冻结快照，历史件不追改，其"来自…（原路径）"注释天然带裸反斜杠）、
`资料/official-代码/`（第三方镜像按纪律不改一字）。
"""
import glob
import io
import os
import re
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEP = re.compile(r"^\s*\|[\s\-:|]+\|\s*$")
FENCE = re.compile(r"^```.*?^```", re.S | re.M)
DISP = re.compile(r"\$\$.*?\$\$", re.S)
INLINE_MATH = re.compile(r"\$[^$\n]*\$")
CODE = re.compile(r"`[^`\n]*`")


def ncols(ln):
    """按 `|` 切出的单元格数（`\\|` 视为转义，不算分隔符）。"""
    s = ln.strip().strip("|").replace("\\|", "\x00")
    return s.count("|") + 1


def scan(path):
    out = []
    lines = io.open(path, encoding="utf-8").read().splitlines()
    i = 0
    while i < len(lines):
        ln = lines[i]
        if ln.strip().startswith("|") and i + 1 < len(lines) and SEP.match(lines[i + 1]):
            h = ncols(ln)
            j = i + 2
            while j < len(lines) and lines[j].strip().startswith("|"):
                c = ncols(lines[j])
                if c != h:
                    out.append((j + 1, h, c, lines[j].strip()))
                j += 1
            i = j
        else:
            i += 1
    return out


def _blank(m):
    """围栏块 → 等量空行（保住后续行号）。"""
    return "\n" * m.group(0).count("\n")


def escapes(path):
    """裸「反斜杠+字母」的行（先剔围栏块、展示/行内数学、行内代码段、已双写的反斜杠）。"""
    out = []
    txt = FENCE.sub(_blank, io.open(path, encoding="utf-8").read())
    for i, ln in enumerate(txt.split("\n"), 1):
        s = DISP.sub(" ", ln).replace("\\\\", "  ")
        s = INLINE_MATH.sub(" ", s)
        s = CODE.sub(" ", s)
        for m in re.finditer(r"\\[A-Za-z]", s):
            out.append((i, s[max(0, m.start() - 42):m.start() + 26]))
    return out


def expand(t):
    """一个参数 → 若干 .md：目录则递归取其下 *.md，文件则原样（非 .md 跳过）。"""
    p = t if os.path.isabs(t) else os.path.join(ROOT, t)
    if os.path.isdir(p):
        return sorted(glob.glob(os.path.join(p, "**", "*.md"), recursive=True))
    if os.path.isfile(p) and p.lower().endswith(".md"):
        return [p]
    return []


targets = sys.argv[1:]
skipped = 0
if not targets:
    files = []
    for pat in ("论文库/**/*.md", "*.md", "_工具/*.md", ".claude/skills/**/*.md"):
        files += glob.glob(os.path.join(ROOT, pat), recursive=True)
    # 第三方镜像按纪律「未改一字、不得编辑」，其报告口径问题不在自查范围（默认范围里剔除；
    # 显式指定路径时照扫不误）。
    kept = []
    for f in files:
        if "/official-代码/" in f.replace("\\", "/"):
            skipped += 1
        else:
            kept.append(f)
    files = kept
else:
    files = []
    for t in targets:
        got = expand(t)
        if not got:
            print("⚠ 跳过（非 .md / 不存在 / 空目录）：%s" % t)
        files += got
if skipped:
    print("（默认范围已跳过 %d 个第三方镜像 md：`资料/official-代码/` 按纪律不改一字；要扫请显式传路径）" % skipped)

bad, esc = [], []
for f in sorted(set(files)):
    rel = os.path.relpath(f, ROOT).replace("\\", "/")
    for ln_no, h, c, txt in scan(f):
        bad.append((rel, ln_no, h, c, txt))
    for ln_no, ctx in escapes(f):
        esc.append((rel, ln_no, ctx))

print("扫描 %d 个 .md" % len(set(files)))
print("【一】单元格数与表头不符的表行（= 表内有未转义裸 `|`）：共 %d 处\n" % len(bad))
if bad:
    print("按文件：")
    for f, n in Counter(x[0] for x in bad).most_common():
        print("  %3d  %s" % (n, f))
    print("\n明细：")
    for f, ln_no, h, c, txt in bad:
        print("  %s:%d   表头 %d 列 → 本行 %d 列" % (f, ln_no, h, c))
        print("      %s" % txt[:150])
else:
    print("✅ 全部表格列数一致")

print("\n【二】代码段/数学环境之外的裸「反斜杠+字母」（pandoc 当 LaTeX 控制词吞字）：共 %d 处\n" % len(esc))
if esc:
    for f, ln_no, ctx in esc:
        print("  %s:%d  「…%s…」" % (f, ln_no, ctx))
    print("\n  修法：双写 `\\\\x`、或用代码段包住（`C:\\Program Files\\MATLAB\\R2018b`）；`\\|`、`\\*` 等标点转义是合法的。")
else:
    print("✅ 无反斜杠吞字风险")

sys.exit(1 if (bad or esc) else 0)
