#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pr_status.py — paper-reproducer 进度可视化
============================================
把「复现进行到哪一步、卡在哪、还缺什么」渲染成 PNG（matplotlib，可嵌入 md/docx）
并同源生成 Mermaid（可编辑），同时打印一段缺口摘要文本供 Claude/用户直接阅读。

两种模式：
  1) 通用总览图（教学）：   python pr_status.py --overview -o <png> [--mmd <mermaid>]
     画出 8 步流程 + 完成线判定 + 差异分析(三查)回环，说明复现流程长什么样。
  2) 单篇进度图（读 README）： python pr_status.py <复现/README.md> [--out 图.png]
     --out 缺省 = 与 README 同目录的 复现进度图.png / .mermaid
     --manifest <资源清单.md> 缺省自动找 '../资源清单.md'

输入约定（README 内的「复现进度状态块」，见 templates/复现README-模板.md，勿改列头）：
  | 步骤 | 状态 | 说明 |
  | 1 选论文… | 🔄/✅/⛔ | 一句话 |
缺口来源 = ① 状态块中 ⛔ 步骤 ② README 里尚未勾选的 `- [ ]` 项
           ③ 论文根 资源清单.md：`- [ ]` 待办 + **六类清单表中状态为 ☐/⛔ 的资料行**
           （后者的前缀「资料·<类>」，把"资料没收集齐"也画进缺口）。取前若干条上图。
依赖：matplotlib（缺省仅写 Mermaid 并给提示）。运行中文输出建议加 PYTHONIOENCODING=utf-8。
"""

import argparse
import re
import sys
from pathlib import Path

# ----------------------------------------------------------------------------
# 状态定义（与 SKILL 一致的三态）
# ----------------------------------------------------------------------------
STATE_OK = "✅"      # 完成
STATE_RUN = "🔄"     # 进行中
STATE_BLOCK = "⛔"    # 受阻（原因写进说明）
STATE_UNKNOWN = "—"  # 未判定

COLORS = {
    "ok":     "#3ba55d",   # 绿：完成
    "run":    "#f2b134",   # 金：进行中
    "block":  "#e0645a",   # 红：受阻
    "wait":   "#8aa2b8",   # 灰蓝：未判定/待办
    "ink":    "#20242b",
    "paper":  "#ffffff",
    "dim":    "#6b7480",
    "gate":   "#5b9bd5",   # 蓝：判定点
}

STEP_META = [
    (1, "选论文 · 定义复现目标", "锁定目标表 / 口径 / 完成线(±Δ)；记硬件与时长预期"),
    (2, "建 复现/README.md 骨架", "复制模板 · 勾 8 步清单；README = 唯一状态记录"),
    (3, "环境就绪", "建 .venv-repro-<缩写> · 记录 Python/框架/GPU/关键包版本 · 依赖自检"),
    (4, "数据就绪", "数据/落位 · 下载脚本留存 · 记划分/SNR/采样率口径 · 受限数据只记入口"),
    (5, "代码就绪", "官方优先(资料/official→复现/src)；无官方→手搓(implementation-guide)"),
    (6, "小规模冒烟", "1 batch/≤2 epoch：前向→损失→反向→存盘全通，损失能降再放大"),
    (7, "指标对齐(完成线)", "同口径复测·填对齐表；默认容忍 PESQ±0.05 / STOI±0.01 / SNR±0.5dB"),
    (8, "收尾 · 回写清单 · 汇报", "更新三态与结论 · 回写 资源清单.md · 汇报 完成/进行/受阻"),
]

def state_class(st):
    if st in (STATE_OK, "✅", "ok"):
        return "ok"
    if st in (STATE_RUN, "🔄", "run"):
        return "run"
    if st in (STATE_BLOCK, "⛔", "block"):
        return "block"
    return "wait"

# ----------------------------------------------------------------------------
# 字体（Windows 微软雅黑优先，回退常见 CJK）
# ----------------------------------------------------------------------------
def setup_cjk_font():
    try:
        from matplotlib import font_manager
    except Exception:
        return None
    cands = [
        ("C:/Windows/Fonts/msyh.ttc", "Microsoft YaHei"),
        ("C:/Windows/Fonts/msyhbd.ttc", "Microsoft YaHei"),
        ("C:/Windows/Fonts/simhei.ttf", "SimHei"),
        ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", "Noto Sans CJK SC"),
        ("/System/Library/Fonts/PingFang.ttc", "PingFang SC"),
    ]
    for path, name in cands:
        p = Path(path)
        if p.exists():
            try:
                font_manager.fontManager.addfont(str(p))
            except Exception:
                pass
            return name
    return "sans-serif"

# ----------------------------------------------------------------------------
# 文本工具
# ----------------------------------------------------------------------------
def wrap_cjk(text, width):
    """按 CJK 近似宽度折行（中文=1.0，ASCII=0.55）。"""
    out, cur, cur_w = [], "", 0.0
    for ch in text:
        w = 1.0 if ord(ch) > 0x2E7F else 0.55
        if cur and cur_w + w > width:
            out.append(cur)
            cur, cur_w = ch, w
        else:
            cur += ch
            cur_w += w
    if cur:
        out.append(cur)
    return out


def text_units(s):
    """文本在图面横向占用的近似宽度（中文=1.6，ASCII=0.85）。"""
    return sum(1.6 if ord(c) > 0x2E7F else 0.85 for c in s)


def clip_cjk(s, max_units=72):
    """截断到不超过 max_units（中文=1、ASCII=0.55），超长加省略号。"""
    u, out = 0.0, []
    for ch in s:
        w = 1.0 if ord(ch) > 0x2E7F else 0.55
        if u + w > max_units:
            return "".join(out).rstrip() + "…"
        out.append(ch)
        u += w
    return s


MARK_GLYPH = "DejaVu Sans"  # 内置字体：含 ✓ ✗ ↻ ↺ · 等记号，缺中文故中文仍走 CJK 字体


def strip_emoji(s):
    """剔除会被 matplotlib CJK 字体渲染成 tofu 的 emoji/装饰符号，保留中文。"""
    return "".join(ch for ch in s
                   if not (0x1F000 <= ord(ch) <= 0x1FAFF   # 补充平面 emoji（🔄 等）
                           or 0x2600 <= ord(ch) <= 0x27BF))  # 杂项符号/装饰符号（✅⛔✓ 等）

# ----------------------------------------------------------------------------
# 解析 README
# ----------------------------------------------------------------------------
def read_file(path):
    try:
        return Path(path).read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return Path(path).read_text(encoding="utf-8", errors="replace")

def _is_sep_line(s):
    """表格分隔行，如 |---|---|。"""
    body = s.strip().strip("|").replace(" ", "")
    return bool(body) and set(body) <= set("-|:")


def parse_manifest_notes(manifest_path):
    """资源清单缺口 → 两类：① `- [ ]` 待办 ② 六类清单表中 状态=☐/⛔ 的资料行。

    待办 → '清单待办： x'；资料行 → '资料·<类>： <条目>'（☐/⛔ 后跟说明则附带）。
    表格按"表头行 + 紧随分隔行"识别，只查每表的「状态」列值，避免把表头/总览列名当缺口。
    兼容 v3 旧清单（无分类表，仅有 - [ ] 待办）：旧清单只产生第①类，行为不变。
    """
    notes = []
    if not (manifest_path and Path(manifest_path).exists()):
        return notes
    lines = read_file(manifest_path).splitlines()
    cat, status_col = "", None
    i, n = 0, len(lines)
    while i < n:
        s = lines[i].strip()
        if s.startswith("## ") and not s.startswith("### "):
            h = re.sub(r"^\s*\d+\s*[.、]?\s*", "", s[3:].strip()).split("（")[0].strip()
            cat = h or ""
            status_col = None
        elif s.startswith("- [ ]"):
            t = lines[i].split("]", 1)[1].strip()
            if t:
                notes.append("清单待办： " + strip_emoji(t[:58]))
        elif s.startswith("|"):
            # 表头行（下一行是分隔行）→ 记录该表「状态」列下标后跳过
            if i + 1 < n and _is_sep_line(lines[i + 1]):
                hdr = [c.strip() for c in s.strip().strip("|").split("|")]
                status_col = next((k for k, c in enumerate(hdr) if c == "状态"), None)
            else:
                cells = [c.strip() for c in s.strip().strip("|").split("|")]
                # 查状态列；无状态列(如 §0 总览)则回退全列扫描，仍跳过非 ☐/⛔
                hits = [cells[status_col]] if (status_col is not None and status_col < len(cells)) else \
                       [c for c in cells if c[:1] in ("☐", "⛔")]
                if hits and hits[0][:1] in ("☐", "⛔"):
                    c = hits[0]
                    item = cells[0] if cells and cells[0][:1] not in ("☐", "⛔") else (cat or "条目")
                    reason = c[1:].strip().strip("（）()")
                    label = strip_emoji(item[:34])
                    suffix = (" · " + strip_emoji(reason[:26])) if reason else ""
                    notes.append(f"资料·{strip_emoji(cat)[:18]}： {label}{suffix}")
        i += 1
    return notes[:8]

def parse_readme(readme):
    txt = read_file(readme)
    lines = txt.splitlines()

    # 论文名：首个 '# 复现记录 — ' 行
    title = ""
    for ln in lines:
        if ln.startswith("# ") and ("复现记录" in ln or "—" in ln or "——" in ln):
            title = ln.lstrip("# ").strip()
            break
    # 总体状态行
    overall = ""
    for ln in lines:
        if "当前总体状态" in ln:
            overall = strip_emoji(ln.split("：", 1)[-1].split("。", 1)[0].strip())
            break

    # 状态块表：找到含「步骤」「状态」「说明」的表头，读其后若干表行
    step_states = {}   # step_no -> (state, note)
    table_on = False
    for i, ln in enumerate(lines):
        if re.match(r"^\s*\|?\s*步骤", ln) and "状态" in ln and "说明" in ln:
            table_on = True
            continue
        if table_on:
            if not ln.strip().startswith("|") or set(ln.strip()) <= set("|-: "):
                # 分隔行 |---|---|
                if "---" in ln:
                    continue
                table_on = False
                continue
            cells = [c.strip() for c in ln.strip().strip("|").split("|")]
            if len(cells) >= 3:
                m = re.match(r"(\d+)", cells[0])
                if m:
                    st = cells[1]
                    note = strip_emoji(cells[2]) if len(cells) > 2 else ""
                    step_states[int(m.group(1))] = (st, note)
        if ln.startswith("## "):
            table_on = False
    # 未勾选项（缺口）
    unchecked = []
    for ln in lines:
        # 行首锚定：只认真正的未勾选复选框行。
        # （曾用子串 `"- [ ]" in ln`：README 正文里出现该字面量即被误当待办，
        #   且 split("]", 1)[1] 会切出半句乱码，占掉 8 条上限、挤掉真缺口）
        if re.match(r"^\s*[-*]\s*\[ \]", ln):
            t = re.sub(r"^\s*[-*]\s*\[ \]\s*", "", ln).replace("**", "").replace("`", "").strip().strip("*")
            t = strip_emoji(t)
            if t:
                unchecked.append(t)
    return strip_emoji(title), overall, step_states, unchecked[:8]

# ----------------------------------------------------------------------------
# 绘图
# ----------------------------------------------------------------------------
def _render_rows(rows, title, png_path, gap_lines=None):
    """rows: list of (main_label, sub_label, color_key, marker_char)
       gap_lines: 缺口清单（红色条带在底部）"""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyBboxPatch, Circle
    fname = setup_cjk_font()
    plt.rcParams["font.family"] = fname if fname != "sans-serif" else ["Microsoft YaHei", "sans-serif"]
    plt.rcParams["axes.unicode_minus"] = False

    gap_lines = gap_lines or []
    W_IN = 13.5
    row_h, pitch = 0.60, 0.86
    n = len(rows)
    first_top = 1.45                     # 距顶距离：首行上边
    last_bottom = first_top + (n - 1) * pitch + row_h
    gap_list = [] if not gap_lines else [ln for g in gap_lines[:6] for ln in wrap_cjk("• " + g, 90)]
    if gap_list:
        TOT = last_bottom + 0.45 + 0.34 + len(gap_list) * 0.28 + 0.25
    else:
        TOT = last_bottom + 0.45 + 0.32 + 0.25

    def Y(d):                            # d = 距顶英寸 → 数据 y（图面自下而上）
        return TOT - d

    fig = plt.figure(figsize=(W_IN, TOT), facecolor="white")
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, W_IN)
    ax.set_ylim(0, TOT)
    ax.axis("off")

    x0, x1 = 0.5, W_IN - 0.5
    CX, R = x0 + 0.34, 0.18               # 状态圆点
    TX = x0 + 0.66                        # 文字左缘

    # 标题
    ax.text(x0, Y(0.16), title, fontsize=19, weight="bold", va="top", color=COLORS["ink"])

    # 图例（记号用内置 DejaVu Sans，避免 CJK 字体缺字形）
    ly = Y(0.80)
    LEG = [("✓", "完成", "ok"), ("↻", "进行中", "run"),
           ("✗", "受阻（原因写入说明）", "block"), ("·", "未判定 / 待办", "wait")]
    ax.text(x0, ly, "图例：", fontsize=10.5, va="center", color=COLORS["ink"])
    lx = x0 + 1.30
    for glyph, label, ck in LEG:
        color = COLORS[ck]
        ax.add_patch(Circle((lx + 0.13, ly), 0.12, facecolor=color,
                            edgecolor="white", linewidth=0.7))
        ax.text(lx + 0.13, ly, glyph, ha="center", va="center", fontsize=9,
                weight="bold", color="white", fontfamily=MARK_GLYPH)
        ax.text(lx + 0.35, ly, label, fontsize=9.5, va="center", color=COLORS["ink"])
        lx += 0.35 + text_units(label) * 0.15 + 0.24

    # 各步骤行（自上而下，每行一块卡片）
    face_map = {"ok": "#e9f7ee", "run": "#fff6e0", "block": "#fdece7",
                "wait": "#eef3f6", "gate": "#e8f1fa"}
    for i, (main, sub, ck, marker) in enumerate(rows):
        topd = first_top + i * pitch
        botd = topd + row_h
        cy = Y(topd + row_h / 2)
        color = COLORS[ck]
        box = FancyBboxPatch((x0, Y(botd)), x1 - x0, row_h,
                             boxstyle="round,pad=0.02,rounding_size=0.09",
                             linewidth=1.3, edgecolor=color,
                             facecolor=face_map.get(ck, "#eef3f6"))
        ax.add_patch(box)
        ax.add_patch(Circle((CX, cy), R, facecolor=color, edgecolor="white", linewidth=1.0))
        ax.text(CX, cy, marker, ha="center", va="center", fontsize=10.5,
                weight="bold", color="white", fontfamily=MARK_GLYPH)
        ax.text(TX, cy + 0.09, main, ha="left", va="center",
                fontsize=12.5, weight="bold", color=COLORS["ink"])
        ax.text(TX, cy - 0.16, sub, ha="left", va="center",
                fontsize=9.5, color=COLORS["dim"])

    # 缺口面板
    gd = last_bottom + 0.45
    if gap_list:
        ax.text(x0, Y(gd), "缺什么 / 下一步", fontsize=13.5, weight="bold",
                color=COLORS["block"], va="top")
        gd += 0.34
        for ln in gap_list:
            ax.text(x0 + 0.12, Y(gd), ln, fontsize=10, color="#8f332a", va="top")
            gd += 0.28
    else:
        ax.text(x0, Y(gd), "暂无未勾选缺口 —— 请到 README「缺口/下一步」人工备注补充。",
                fontsize=10.5, color=COLORS["dim"], va="top")
    fig.savefig(png_path, dpi=150)
    plt.close(fig)

def render_overview_png(png_path):
    rows = []
    for no, main, sub in STEP_META:
        rows.append((f"步骤 {no}  {main}", sub, "wait", str(no)))
    rows.append(("判定点 · 步骤 7：同口径指标对齐 = 完成线？", "默认容忍 PESQ±0.05 / STOI±0.01 / SNR±0.5dB；精度类 ±1%", "gate", "?"))
    rows.append(("若否(超容忍) → 差异分析(三查)", "①版本/口径 ②实现细节 ③评测协议 → 记录归因/最小复现，修正后回到对应步骤", "block", "↺"))
    rows.append(("若是 → 步骤 8 收尾", "更新三态 · 回写 资源清单.md · 报「完成」（达成完成线才算）", "ok", "✓"))
    gap = ["卡在哪一步、缺什么，逐篇用 <复现/README.md> 跑本脚本自动推导。"]
    _render_rows(rows, "论文复现流程总览（paper-reproducer · 8 步闭环）", png_path, gap)

def render_progress_png(readme, png_path, manifest_notes):
    title, overall, step_states, unchecked = parse_readme(readme)
    rows = []
    for no, main, sub in STEP_META:
        st, note = step_states.get(no, (STATE_UNKNOWN, ""))
        ck = state_class(st)
        marker = "✓" if ck == "ok" else ("↻" if ck == "run" else ("✗" if ck == "block" else "·"))
        sub_show = clip_cjk(note) if note and note not in ("...", "—") else sub
        rows.append((f"步骤 {no}  {main}", sub_show, ck, marker))
    gaps = list(unchecked)
    # 受阻行补充：收集 ⛔ 行说明作缺口
    for no in sorted(step_states):
        st, note_t = step_states[no]
        if state_class(st) == "block":
            gaps.append(f"步骤 {no} 受阻 — " + (note_t[:50] if note_t else "原因未写明"))
    gaps += manifest_notes
    # 去重保留顺序
    seen, uniq = set(), []
    for g in gaps:
        if g not in seen:
            seen.add(g)
            uniq.append(g)
    gaps = uniq[:8]
    if overall and not gaps:
        gaps = [f"总体状态：{overall}"]
    # 短名：取 H1「——」后的论文名；去掉「（中文译题）」括号；超宽截断
    if "——" in title:
        name = title.split("——", 1)[-1]
    elif "—" in title:
        name = title.split("—", 1)[-1]
    else:
        name = title
    name = name.split("（", 1)[0].strip() or Path(readme).parent.name
    _render_rows(rows, "复现进度 · " + clip_cjk(name, 40), png_path, gaps)
    return gaps

# ----------------------------------------------------------------------------
# Mermaid
# ----------------------------------------------------------------------------
def mermaid_class_lines():
    return [
        "classDef ok fill:#e9f7ee,stroke:#3ba55d,color:#20242b;",
        "classDef run fill:#fff6e0,stroke:#f2b134,color:#20242b;",
        "classDef block fill:#fdece7,stroke:#e0645a,color:#20242b;",
        "classDef wait fill:#eef3f6,stroke:#8aa2b8,color:#20242b;",
        "classDef gate fill:#e8f1fa,stroke:#5b9bd5,color:#20242b;",
    ]

def overview_mermaid():
    L = [
        "%% 复现流程总览 — paper-reproducer（pr_status.py --overview 生成，可手工编辑）",
        "flowchart TB",
        '    S1["步骤1 · 选论文 · 定义复现目标<br/>锁定目标表/口径/完成线(±Δ)；记硬件与时长"] --> S2',
        '    S2["步骤2 · 建 复现/README.md 骨架<br/>复制模板·勾 8 步；README=唯一状态记录"] --> S3',
        '    S3["步骤3 · 环境就绪<br/>venv·版本留痕·依赖自检✅"] --> S4',
        '    S4["步骤4 · 数据就绪<br/>数据/落位·许可口径·下载脚本"] --> S5',
        '    S5["步骤5 · 代码就绪<br/>官方优先；否则手搓(implementation-guide)"] --> S6',
        '    S6["步骤6 · 小规模冒烟<br/>前向→损失→反向→存盘"] --> G{"步骤7 · 同口径指标对齐 = 完成线？"}',
        '    G -- 是 ✅ --> S8["步骤8 · 收尾<br/>更新三态·回写资源清单·汇报"]',
        '    S8 --> DONE["复现完成 · 全部 ✅"]',
        '    G -- 否 ⛔（超容忍）--> DIFF["差异分析(三查)<br/>①版本/口径 ②实现细节 ③评测协议"]',
        '    DIFF --> FIX["记录归因 / 最小复现 → 修正"]',
        "    FIX -. 修正后回到对应步骤 .-> S5",
        "    FIX -.-> S6",
        '    S1:::wait',
        '    S2:::wait',
        '    S3:::wait',
        '    S4:::wait',
        '    S5:::wait',
        '    S6:::wait',
        '    G:::gate',
        '    S8:::ok',
        '    DONE:::ok',
        '    DIFF:::block',
        '    FIX:::run',
    ]
    return "\n".join(L + mermaid_class_lines())

def progress_mermaid(readme):
    title, overall, step_states, _ = parse_readme(readme)
    L = [
        "%% 复现进度 — paper-reproducer（pr_status.py 生成，可手工编辑）",
        "flowchart LR",
    ]
    ids = [f"S{no}" for no, _, _ in STEP_META]
    classes = {}
    for no, main, _sub in STEP_META:
        st, note = step_states.get(no, (STATE_UNKNOWN, ""))
        ck = state_class(st)
        classes[no] = ck
        L.append(f'    {ids[no-1]}["步骤{no} · {main}"]')
    prev = ids[0]
    for i in range(1, len(ids)):
        L.append(f"    {prev} --> {ids[i]}")
        prev = ids[i]
    for no in classes:
        L.append(f"    {ids[no-1]}:::{classes[no]}")
    if overall:
        L.append(f'    note["总体：{overall}"]:::run')
        L.append(f"    {ids[-1]} -.-> note")
    L += ["", "%% 图例：ok=✅完成  run=🔄进行中  block=⛔受阻  wait=未判定"]
    return "\n".join(L + mermaid_class_lines())

# ----------------------------------------------------------------------------
# main
# ----------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="复现进度可视化（PNG + Mermaid + 缺口摘要）")
    ap.add_argument("readme", nargs="?", help="单篇 复现/README.md 路径（读模式）")
    ap.add_argument("--overview", action="store_true", help="通用流程总览图（教学）")
    ap.add_argument("-o", "--out", default="", help="PNG 输出路径")
    ap.add_argument("--mmd", default="", help="Mermaid 输出路径（缺省与 PNG 同前缀 .mermaid）")
    ap.add_argument("--manifest", default="", help="资源清单.md 路径（缺省自动 ../资源清单.md）")
    args = ap.parse_args()

    def pair(png, mmd):
        if not mmd:
            mmd = str(Path(png).with_suffix(".mermaid"))
        return png, mmd

    if args.overview:
        png = args.out or "复现流程总览.png"
        png, mmd = pair(png, args.mmd)
        try:
            render_overview_png(png)
            print(f"[PNG]  {png}")
        except Exception as e:
            print(f"[PNG 失败，仍写 Mermaid] {e}")
        Path(mmd).write_text(overview_mermaid(), encoding="utf-8")
        print(f"[MMD] {mmd}")
        print("说明：这是通用流程图；逐篇进度用：pr_status.py <论文>/复现/README.md")
        return

    if not args.readme:
        ap.error("请给 <复现/README.md> 路径，或用 --overview 出总览图")
    readme = Path(args.readme)
    manifest = Path(args.manifest) if args.manifest else readme.parent.parent / "资源清单.md"
    manifest_notes = parse_manifest_notes(manifest)
    png = args.out or str(readme.with_name("复现进度图.png"))
    png, mmd = pair(png, args.mmd)
    try:
        gaps = render_progress_png(str(readme), png, manifest_notes)
    except Exception as e:
        print(f"[PNG 失败] {e}")
        gaps = parse_readme(readme)[3]
    Path(mmd).write_text(progress_mermaid(str(readme)), encoding="utf-8")
    print(f"[PNG]  {png}")
    print(f"[MMD] {mmd}")
    print("\n—— 缺口 / 下一步 ——")
    if gaps:
        for g in gaps:
            print("  -", g)
    else:
        print("  （无未勾选缺口；请人工补 README「缺口/下一步」备注）")

if __name__ == "__main__":
    main()
