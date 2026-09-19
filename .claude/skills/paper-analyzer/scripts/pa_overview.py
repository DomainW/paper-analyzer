#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pa_overview.py — paper-analyzer 分析流程总览（教学图）
=====================================================
把「论文分析怎么一步步走」渲染成 PNG（matplotlib，可嵌入 md/docx）+ Mermaid（可编辑），
并打印一段流程要点。突出：入口先判执行模式（A 默认全流程 / A+ 加做复现资料 / B 轻量检索）
→ A 走报告线（步骤 0/1/2/3/4/5/7/8，默认只出 md + 两图）→ ◇ 步骤 6 与 8b 为按需分支
→ 完成线判定（gate）→ 否 = 列缺口不虚报。

用法：
  python pa_overview.py [-o 分析流程总览.png] [--mmd 分析流程总览.mermaid]

依赖：matplotlib（缺省仅写 Mermaid 并给提示）。中文输出建议加 PYTHONIOENCODING=utf-8。
与 pr_status.py（paper-reproducer）布局同源、相互独立（本脚本不 import 对方，保证两 skill 自洽）。
"""

import argparse
from pathlib import Path

# ----------------------------------------------------------------------------
# 配色 / 记号（与库内图体系一致）
# ----------------------------------------------------------------------------
COLORS = {
    "ok":    "#3ba55d",
    "run":   "#f2b134",
    "block": "#e0645a",
    "wait":  "#8aa2b8",
    "ink":   "#20242b",
    "paper": "#ffffff",
    "dim":   "#6b7480",
    "gate":  "#5b9bd5",
}

# 流程卡片：(主标签, 副标签, 色键, 记号字符)
# 记号只用 ASCII 数字 / 内置字形（? ✗ ✓ ↺ …），保证 matplotlib 不依赖 CJK 补字形。
FLOW = [
    ("入口：先判定执行模式（A 默认 / A+ / B）",
     "要完整分析/报告/归档 → A(默认)；还要复现资料清单 → A+；只要相关论文/脉络 → B(轻量检索)",
     "gate", "?"),
    ("步骤 0  确认分析目标",
     "扫 未分析/ 列候选 · 判粒度(单篇/学位论文合并) · 多篇用 AskUserQuestion 选定",
     "wait", "1"),
    ("步骤 1  读取 PDF（分层抽取 + 页面体检）",
     "pa_extract.py 抽全文+体检 · 稀疏/扫描页用 Read 视觉补读 · 表格公式对原文页码",
     "wait", "2"),
    ("步骤 2  核心逻辑分析",
     "背景瓶颈/研究问题 · 创新点含金量评级 · 方法论脉络(文字一段) · 论证链+最薄弱环节",
     "wait", "3"),
    ("步骤 3  关键公式与验证步骤提取",
     "§3.1 架构图 · 公式三要素(编号/LaTeX/符号表) · 实验表提取 · §3.4 论文自述的公开状态",
     "wait", "4"),
    ("步骤 4  批判性分析（五段）",
     "必扫清单11组 → 不足点判定表(≥8条) → 致命一击 → 可核验性就地登记 → Top-3 小结回填速览卡",
     "wait", "5"),
    ("步骤 5  多库搜索 5 篇分角色相关论文",
     "R1前驱·R2竞品·R3模块来源·R4后续·R5邻域；S2 MCP(串行) + pa_query.py 回退",
     "wait", "6"),
    ("◇ 步骤 6  代码与数据溯源（按需 · 默认跳过）",
     "仅当用户要复现资料：建 复现/数据/资料 + 写 资源清单.md 六类初稿(每项收集方法+状态)",
     "run", "7"),
    ("步骤 7  生成 Markdown 报告 + 渲染两图",
     "report-v4 骨架填满速览卡 · pa_fig 出 arch 架构图 + rel 关系图(均带 --qa) 嵌入报告",
     "wait", "8"),
    ("步骤 8  归档（◇8b 转 Word 按需）",
     "定发表年：原文 mv 入 已分析/<发表年>/<论文名>/原文/ · 更新馆藏清单 · 汇报(含未做的按需项)",
     "wait", "9"),
    ("完成线：默认六项逐过才报「完成」",
     "速览卡五要素 / 指标公式标页码 / 5篇×5角色 / 两图 --qa 通过并嵌入 / table_check 两类 0 / md 成功 + 已归档(发表年层)",
     "gate", "?"),
    ("◇ 按需项（做了才纳入判定）",
     "资源清单六类逐行有状态可区分无与未查 · docx(pandoc+TOC+图) 成功 —— 用户点名才做",
     "run", "?"),
    ("若否 → 记为 受阻/进行中 并列缺口，不虚报",
     "任一不过就不报「完成」；缺口如实写出，不凑数",
     "block", "✗"),
    ("若是 → 报「完成」",
     "归档路径含发表年 · 两图齐 · 报告自洽；要复现时再由 paper-reproducer 接手",
     "ok", "✓"),
]

# ----------------------------------------------------------------------------
# 字体（Windows 微软雅黑优先，回退常见 CJK）—— 与 pr_status.py 同策略
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
# 文本工具（中文≈1.6 单位 / ASCII≈0.85）
# ----------------------------------------------------------------------------
def text_units(s):
    return sum(1.6 if ord(c) > 0x2E7F else 0.85 for c in s)


def wrap_cjk(text, width):
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


def clip_cjk(s, max_units=80):
    u, out = 0.0, []
    for ch in s:
        w = 1.0 if ord(ch) > 0x2E7F else 0.55
        if u + w > max_units:
            return "".join(out).rstrip() + "…"
        out.append(ch)
        u += w
    return s


MARK_GLYPH = "DejaVu Sans"  # 记号字形（? ✗ ✓ …），中文走 CJK 字体

# ----------------------------------------------------------------------------
# 渲染
# ----------------------------------------------------------------------------
def _sub_wrap(sub, width=92):
    """副标签按宽度折行（中文粗估单位）。"""
    return "\n".join(wrap_cjk(sub, width))


def render_png(png_path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyBboxPatch, Circle
    fname = setup_cjk_font()
    plt.rcParams["font.family"] = fname if fname != "sans-serif" else ["Microsoft YaHei", "sans-serif"]
    plt.rcParams["axes.unicode_minus"] = False

    rows = FLOW
    W_IN = 14.0
    row_h, pitch = 0.72, 1.06
    n = len(rows)
    first_top = 1.55
    # 副标签需多行时该行高度略增——统一给足 pitch，多行副文本控制在 2 行内
    TOT = first_top + (n - 1) * pitch + row_h + 0.7

    def Y(d):
        return TOT - d

    fig = plt.figure(figsize=(W_IN, TOT), facecolor="white")
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, W_IN)
    ax.set_ylim(0, TOT)
    ax.axis("off")

    x0, x1 = 0.5, W_IN - 0.5
    CX, R = x0 + 0.36, 0.20
    TX = x0 + 0.72

    ax.text(x0, Y(0.16), "论文分析流程总览（paper-analyzer v4.1.0 · 默认只出 md 报告 + 两张图）",
            fontsize=19, weight="bold", va="top", color=COLORS["ink"])

    # 图例
    ly = Y(0.82)
    LEG = [("?", "判定点 / 分支", "gate"),
           ("✗", "未过（列缺口）", "block"),
           ("✓", "通过", "ok"),
           ("·", "顺序步骤", "wait")]
    ax.text(x0, ly, "图例：", fontsize=10.5, va="center", color=COLORS["ink"])
    lx = x0 + 1.30
    for glyph, label, ck in LEG:
        color = COLORS[ck]
        ax.add_patch(Circle((lx + 0.13, ly), 0.12, facecolor=color,
                            edgecolor="white", linewidth=0.7))
        ax.text(lx + 0.13, ly, glyph, ha="center", va="center", fontsize=9,
                weight="bold", color="white", fontfamily=MARK_GLYPH)
        ax.text(lx + 0.35, ly, label, fontsize=9.5, va="center", color=COLORS["ink"])
        lx += 0.35 + text_units(label) * 0.15 + 0.26

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
        ax.text(CX, cy, marker, ha="center", va="center", fontsize=11,
                weight="bold", color="white", fontfamily=MARK_GLYPH)
        ax.text(TX, cy + 0.13, main, ha="left", va="center",
                fontsize=12.5, weight="bold", color=COLORS["ink"])
        # 副标签两行最大
        sub_show = clip_cjk(sub, 150)
        ax.text(TX, cy - 0.20, sub_show, ha="left", va="center",
                fontsize=9.2, color=COLORS["dim"])

    fig.savefig(png_path, dpi=150)
    plt.close(fig)


# ----------------------------------------------------------------------------
# Mermaid（同内容、可编辑）
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
        "%% 分析流程总览 — paper-analyzer（pa_overview.py 生成，可手工编辑）",
        "flowchart TB",
        '    MODE{"先判定执行模式 A / A+ / B"}',
        '    MODE -- B 只要相关论文/脉络 --> B5["仅步骤5 多库检索<br/>候选清单+对比表，不产报告不归档"]',
        '    MODE -- A 要完整分析/报告/归档 --> S0["步骤0 确认目标"]',
        '    S0 --> S1["步骤1 读PDF（分层抽取+页面体检）"]',
        '    S1 --> S2["步骤2 核心逻辑分析"]',
        '    S2 --> S3["步骤3 公式与验证提取"]',
        '    S3 --> S4["步骤4 批判性分析（五段）"]',
        '    S4 --> S5["步骤5 搜索5篇分角色(R1前驱…R5邻域)"]',
        '    S5 --> S7["步骤7 生成 md 报告 + pa_fig 两图(arch/rel, --qa)"]',
        '    S7 --> S8["步骤8 归档 → 已分析/<发表年>/<论文名>/"]',
        '    S8 --> G{"完成线：默认六项逐过才报完成？"}',
        '    MODE -. A+ 还要复现资料 .-> S6["◇步骤6 代码与数据溯源<br/>建 复现/数据/资料 + 资源清单六类初稿"]',
        '    S5 -. 按需 .-> S6',
        '    S6 -.-> S7',
        '    S8 -. ◇8b 按需 .-> S8B["◇转 Word（pandoc + TOC）"]',
        '    G -- 否 受阻/进行中 --> GAP["记为受阻/进行中，列缺口不虚报"]',
        '    G -- 是 --> DONE["报完成 ✅（归档含发表年 · 两图齐）"]',
        '    DONE --> HANDOFF["要复现时 → paper-reproducer 接手"]',
        "    MODE:::gate",
        "    B5:::wait",
        "    S0:::wait",
        "    S1:::wait",
        "    S2:::wait",
        "    S3:::wait",
        "    S4:::wait",
        "    S5:::wait",
        "    S6:::run",
        "    S7:::wait",
        "    S8:::wait",
        "    S8B:::run",
        "    G:::gate",
        "    GAP:::block",
        "    DONE:::ok",
        "    HANDOFF:::ok",
    ]
    return "\n".join(L + mermaid_class_lines())


def main():
    ap = argparse.ArgumentParser(description="分析流程总览（PNG + Mermaid）")
    ap.add_argument("-o", "--out", default="", help="PNG 输出路径")
    ap.add_argument("--mmd", default="", help="Mermaid 输出路径")
    args = ap.parse_args()
    png = args.out or str(Path(__file__).resolve().parent.parent / "assets" / "分析流程总览.png")
    mmd = args.mmd or str(Path(png).with_suffix(".mermaid"))
    try:
        render_png(png)
        print(f"[PNG]  {png}")
    except Exception as e:
        print(f"[PNG 失败，仍写 Mermaid] {e}")
    Path(mmd).write_text(overview_mermaid(), encoding="utf-8")
    print(f"[MMD] {mmd}")
    print("要点：A=默认只出 md 报告+两图(md 归档按发表年)；A+=加做步骤6(资源清单/复现目录)；"
          "B=仅步骤5检索不归档；◇项(步骤6/8b)默认不做。复现环节由 paper-reproducer 接手。")


if __name__ == "__main__":
    main()
