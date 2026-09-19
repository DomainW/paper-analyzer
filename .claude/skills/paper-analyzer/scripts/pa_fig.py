#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
paper-analyzer v3 · 从 JSON 图描述自动渲染 PNG + Mermaid 源码
------------------------------------------------
按 descriptor 的 type 分发四种图型:
  * lineage / flow  —— 有向分层图（节点带 layer；脉络图 / 方法论演进 / 旧式架构）
  * scatter2d      —— 二维关系定位散点图（研究关系定位）
  * arch           —— 论文自身「逻辑架构图」：忠实方法数据流（列=处理阶段，每列
                        一个阶段名；框=模块/数据，大字短标签 + 要点/尺寸/参数/源章节
                        小字注；箭头由前一步指下一步）。只画论文本身信息。
  * rel            —— 该论文与相关论文的「关系图」：左侧相关论文卡（按角色上色，
                        颜色沿用 pa_fig 角色配色）→ 右侧金色本文框；箭头带 [k] 编号，
                        k 的解释与证据放图下列表。方向级内容归 direction-survey。

用法:
  python pa_fig.py <descriptor.json> [--png out.png] [--mermaid out.mermaid] [--qa]
  不传 --png/--mermaid 时：与 JSON 同路径生成 <同名>.png 与 <同名>.mermaid
  传 --png - 可只出 PNG；传 --mermaid - 可只出 Mermaid（- 表示跳过；arch/rel 不出 Mermaid）
  --qa  渲染后做程序化几何自检（仅 arch/rel 生效）：文字出画布 / 两两压叠 → 列出并以退出码 1 拦下

descriptor.json 结构（lineage/flow）:
{
  "title": "研究脉络：SE-VMUnet → SE-VMUnet++",
  "orientation": "LR",                 // LR 横向 | TB 纵向
  "nodes": [
    {"id":"main","label":"SE-VMUnet++\n（2026 学位论文）","type":"this","layer":1}
  ],
  "edges": [
    {"u":"vmamba","v":"main","label":"前驱·技术来源","style":"solid"}
  ]
}
  type ∈ this|pre|rival|module|next|adj|generic  → 决定配色（图例）
  layer: 0,1,2… → 同一列=同代；箭头从低层指向高层（也可显式跨层连）

descriptor.json 结构（scatter2d）:
{
  "title": "关系定位：常规场景能力 vs 低SNR鲁棒",
  "x": "常规 VB PESQ →", "y": "低 SNR ΔPESQ ↑",
  "points": [
    {"id":"main","label":"SE-VMUnet++","x":0.42,"y":1.32,"type":"this"}
  ]
}

descriptor.json 结构（arch）:
{
  "type": "arch",
  "title": "PPN 逻辑架构（忠实数据流）",
  "stages": [
    {"name": "输入", "nodes": [
       {"id": "mix", "label": "混合语音", "note": "48k→感知特征 68 维", "kind": "input"},
       {"id": "enr", "label": "注册语音", "note": "3s", "kind": "cond"}
    ]},
    {"name": "编码", "nodes": [
       {"id": "enc", "label": "Speaker Encoder", "note": "GRU→embed", "kind": "module"}
    ]}
  ],
  "edges": [{"u": "enr", "v": "enc", "label": ""}]
}

descriptor.json 结构（rel）:
{
  "type": "rel",
  "title": "PPN 与相关论文的关系",
  "this": {"id": "ppn", "label": "Personalized PercepNet 2021", "note": "本文（库内）"},
  "nodes": [
    {"id": "sb", "label": "time-domain SpeakerBeam", "type": "pre"}
  ],
  "edges": [
    {"u": "sb", "v": "ppn", "evidence": "上游任务骨架来源（§5 R1）"}
  ]
}
"""
import argparse
import json
import os
import re
import sys

TYPES = ["this", "pre", "rival", "module", "next", "adj", "generic"]
COL = {
    "this": "#f2b134",   # 金：本文
    "pre":  "#6fbf73",   # 绿：上游/前驱
    "rival":"#e0645a",   # 红：直接竞品
    "module":"#5b9bd5",  # 蓝：模块/子技术来源
    "next": "#ab82c8",   # 紫：后续/演进
    "adj":  "#8aa2b8",   # 灰蓝：细分邻域
    "generic":"#cfd8dc",
}
TYPE_CN = {"this":"本文", "pre":"上游前驱", "rival":"直接竞品",
           "module":"模块来源", "next":"后续演进", "adj":"细分邻域", "generic":"其他"}


def utf8():
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8")
        except Exception:
            pass


def pick_cjk_font():
    from matplotlib import font_manager
    want = ["Microsoft YaHei", "SimHei", "Noto Sans CJK SC", "PingFang SC",
            "Source Han Sans SC", "WenQuanYi Zen Hei", "Arial Unicode MS"]
    have = {f.name for f in font_manager.fontManager.ttflist}
    return next((f for f in want if f in have), None)


def sanitize_label(s):
    # 仅替换会破坏 mermaid/docx 的字符，保留中文与换行
    s = (s or "").replace("\\", "").replace("\"", "“").replace("'", "’")
    s = s.replace("\n", "<br/>")
    return s


def esc_attr(s):
    return (s or "").replace("&", "&amp;").replace("\"", "&quot;")


def render_layer_graph(d, out_png, out_md):
    import matplotlib
    import matplotlib.pyplot as plt
    import matplotlib.patches as mp
    import networkx as nx

    fam = pick_cjk_font()
    if fam:
        matplotlib.rcParams["font.sans-serif"] = [fam]
    matplotlib.rcParams["axes.unicode_minus"] = False

    G = nx.DiGraph()
    for n in d.get("nodes", []):
        t = n.get("type", "generic")
        if t not in TYPES:
            t = "generic"
        G.add_node(n["id"], label=sanitize_label(n.get("label", n["id"])).replace("<br/>", "\n"),
                   layer=int(n.get("layer", 0)), type=t)
    for e in d.get("edges", []):
        G.add_edge(e["u"], e["v"], label=e.get("label", ""),
                   style="dash" if e.get("style") == "dash" else "solid")

    if not G.nodes:
        print("[pa_fig] 空图，跳过"); return False

    # 布局：x=层(col)，y=列内顺序
    order = {i: n for i, n in enumerate(G.nodes)}
    pos = nx.multipartite_layout(G, subset_key="layer", align="vertical", scale=1.0)
    # multipartite 会把每列节点堆到竖直一条线；稍作展开系数
    xs = [p[0] for p in pos.values()]; ys = [p[1] for p in pos.values()]
    dx = (max(xs) - min(xs)) or 1
    for nid in pos:
        pos[nid] = (pos[nid][0], pos[nid][1] * 2.2 + (len(G.nodes) % 2) * 0.0)

    fig, ax = plt.subplots(figsize=(max(6.5, 1.35 * dx + 2), 4.2))
    ax.axis("off")
    if d.get("title"):
        ax.set_title(d["title"], fontsize=12, pad=10)

    # 边（先画，避免压节点）
    for u, v, ed in G.edges(data=True):
        p1, p2 = pos[u], pos[v]
        rad = 0.12
        style = "solid" if ed.get("style", "solid") == "solid" else "dashed"
        arrow = mp.FancyArrowPatch(p1, p2, connectionstyle=f"arc3,rad={rad}",
                                   arrowstyle="-|>", mutation_scale=14,
                                   color="#555555", linewidth=1.2,
                                   linestyle=style, shrinkA=16, shrinkB=16)
        ax.add_patch(arrow)
        if ed.get("label"):
            mx, my = (p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2 + 0.16
            ax.text(mx, my, ed["label"], fontsize=7.5, ha="center", va="center",
                    color="#333333", bbox=dict(boxstyle="round,pad=0.15",
                                               fc="white", ec="#cccccc", lw=0.5, alpha=0.9))

    # 节点
    for nid, nd in G.nodes(data=True):
        x, y = pos[nid]
        col = COL[nd["type"]]
        ax.annotate(nd["label"], (x, y), ha="center", va="center", fontsize=9,
                    bbox=dict(boxstyle="round,pad=0.35", fc=col, ec="none",
                               alpha=0.95, linewidth=0),
                    zorder=5)

    # 图例（按实际出现的类型）
    used = sorted({nd["type"] for _, nd in G.nodes(data=True)},
                  key=lambda t: TYPES.index(t))
    handles = [mp.Patch(fc=COL[t], ec="none", alpha=0.95,
                        label=f"{TYPE_CN[t]}")
               for t in used]
    if handles:
        ax.legend(handles=handles, loc="lower center", bbox_to_anchor=(0.5, -0.06),
                  ncol=len(handles), frameon=False, fontsize=8)

    os.makedirs(os.path.dirname(out_png) or ".", exist_ok=True)
    fig.savefig(out_png, dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"[PNG] {out_png}")

    # Mermaid
    if out_md:
        ori = "LR" if d.get("orientation", "LR") == "LR" else "TB"
        lines = ["flowchart " + ori, f"  %% {d.get('title','')}"]
        for i, n in enumerate(d.get("nodes", [])):
            nid = f'n{i}'
            lines.append(f'  {nid}["{sanitize_label(n.get("label", n["id"]))}"]:::{n.get("type","generic")}')
        for e in d.get("edges", []):
            uid = f'n{list(G.nodes).index(e["u"])}' if e["u"] in G.nodes else e["u"]
            vid = f'n{list(G.nodes).index(e["v"])}' if e["v"] in G.nodes else e["v"]
            lbl = esc_attr(e.get("label", ""))
            lines.append(f'  {uid} -->|{lbl}| {vid}')
        for t in used:
            lines.append(f'  classDef {t} fill:{COL[t]},stroke:#333,stroke-width:0.5;')
        with open(out_md, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        print(f"[Mermaid] {out_md}")
    return True


def render_scatter(d, out_png):
    import matplotlib
    import matplotlib.pyplot as plt
    import matplotlib.patches as mp

    fam = pick_cjk_font()
    if fam:
        matplotlib.rcParams["font.sans-serif"] = [fam]
    matplotlib.rcParams["axes.unicode_minus"] = False

    pts = d.get("points", [])
    fig, ax = plt.subplots(figsize=(6.8, 4.8))
    ax.set_xlabel(d.get("x", "维度 1"), fontsize=10)
    ax.set_ylabel(d.get("y", "维度 2"), fontsize=10)
    if d.get("title"):
        ax.set_title(d["title"], fontsize=12)
    seen = set()
    for p in pts:
        t = p.get("type", "generic")
        if t not in TYPES:
            t = "generic"
        col = COL[t]
        mark = "*" if t == "this" else "o"
        size = 220 if t == "this" else 90
        ax.scatter(p["x"], p["y"], s=size, c=col, marker=mark,
                   edgecolors="#333", linewidths=0.6, zorder=3)
        ax.annotate(p.get("label", p["id"]), (p["x"], p["y"]),
                    xytext=(6, 5), textcoords="offset points",
                    fontsize=9, color="#222")
        seen.add(t)
    # 象限灰网格 + 图例
    ax.grid(alpha=0.25, ls=":")
    ax.axhline(0, color="#999", lw=0.8)
    ax.axvline(0, color="#999", lw=0.8)
    used = sorted(seen, key=lambda t: TYPES.index(t))
    handles = [mp.Patch(fc=COL[t], ec="#333", label=TYPE_CN[t]) for t in used]
    if handles:
        ax.legend(handles=handles, loc="lower center", bbox_to_anchor=(0.5, -0.18),
                  ncol=len(handles), frameon=False, fontsize=8)
    os.makedirs(os.path.dirname(out_png) or ".", exist_ok=True)
    fig.savefig(out_png, dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"[PNG] {out_png}")


# ------------------------------------------------------------------------------
# 共享：几何自检(--qa) + 文本度量 / 画布（供 arch / rel 图型使用）
# ------------------------------------------------------------------------------
DPI = 100
QA_ON = False
QA_PROBLEMS = []

KIND_FILL = {"input": "#e9f1f9", "feat": "#e9f1f9", "cond": "#e9f1f9",
             "module": "#ffffff", "decode": "#ffffff",
             "fuse": "#fdf3dd", "output": "#f1f4f8", "loss": "#fbe9e7",
             "aux": "#eef5ec"}
KIND_EDGE = {"input": "#7d93ab", "feat": "#7d93ab", "cond": "#7d93ab",
             "module": "#4a5a66", "decode": "#4a5a66",
             "fuse": "#c89b3c", "output": "#8aa2b8", "loss": "#d98880",
             "aux": "#5e9a6e"}
KIND_CN = {"input": "输入/数据", "feat": "特征表示", "cond": "条件/注册",
           "module": "模块", "decode": "解码/重建", "fuse": "融合/查询",
           "output": "输出", "loss": "损失", "aux": "辅助"}


def _lighten(hexcol, f=0.45):
    hexcol = hexcol.lstrip("#")
    r, g, b = (int(hexcol[i:i + 2], 16) for i in (0, 2, 4))
    return f"#{int(r + (255 - r) * f):02x}{int(g + (255 - g) * f):02x}{int(b + (255 - b) * f):02x}"


class Measure:
    """测量文本铺开尺寸（英寸；1 数据单位 = 1 英寸）。dpi 固定 100。"""

    def __init__(self):
        import matplotlib
        matplotlib.use("Agg")
        self.fam = pick_cjk_font()
        if self.fam:
            matplotlib.rcParams["font.sans-serif"] = [self.fam]
        matplotlib.rcParams["axes.unicode_minus"] = False
        import matplotlib.pyplot as plt
        self.plt = plt
        self.fig = plt.figure(figsize=(2, 2), dpi=DPI)
        self._rend = self.fig.canvas.get_renderer()

    def ext(self, txt, fs, weight="normal"):
        t = self.fig.text(0, 0, txt, fontsize=fs, fontweight=weight)
        bb = t.get_window_extent(renderer=self._rend)
        t.remove()
        return (bb.width / DPI, bb.height / DPI)

    def wrap(self, txt, fs, max_w, weight="normal"):
        out = []
        for raw in (txt or "").split("\n"):
            if not raw:
                out.append("")
                continue
            cur, cur_w = "", 0.0
            for ch in raw:
                w = self.ext(ch, fs, weight)[0]
                if cur and cur_w + w > max_w:
                    out.append(cur)
                    cur, cur_w = ch, w
                else:
                    cur += ch
                    cur_w += w
            out.append(cur)
        return out

    def width(self, lines, fs):
        return max((self.ext(x, fs)[0] for x in lines), default=0.0)


class Canvas:
    """最终画布（figsize=(W,H) 英寸，全幅等比例坐标，1 数据单位 = 1 英寸）。"""

    def __init__(self, W, H, fam):
        import matplotlib
        import matplotlib.pyplot as plt
        import matplotlib.patches as mp
        if fam:
            matplotlib.rcParams["font.sans-serif"] = [fam]
        matplotlib.rcParams["axes.unicode_minus"] = False
        self.plt, self.mp = plt, mp
        self.W, self.H = W, H
        self.fig = plt.figure(figsize=(W, H), dpi=DPI)
        self.fig.patch.set_facecolor("white")
        self.ax = self.fig.add_axes([0, 0, 1, 1])
        self.ax.set_xlim(0, W)
        self.ax.set_ylim(0, H)
        self.ax.set_aspect("equal")
        self.ax.axis("off")
        self._qa = QA_ON

    def rbox(self, x0, y0, w, h, fc, ec, ls="-", lw=0.8, rounding=0.08, z=1):
        box = self.mp.FancyBboxPatch(
            (x0, y0), w, h, boxstyle=f"round,pad=0,rounding_size={rounding}",
            fc=fc, ec=ec, lw=lw, linestyle=ls, zorder=z)
        self.ax.add_patch(box)
        return box

    def text(self, x, y, s, fs, **kw):
        kw.setdefault("color", "#1a1a1a")
        return self.ax.text(x, y, s, fontsize=fs, **kw)

    def arrow(self, x0, y0, x1, y1, dashed=False, color=None, lw=1.3,
              rad=0.0, z=3):
        from matplotlib.patches import FancyArrowPatch
        c = color or ("#9aa5b0" if dashed else "#3f5160")
        arr = FancyArrowPatch((x0, y0), (x1, y1),
                              connectionstyle=f"arc3,rad={rad}",
                              arrowstyle="-|>", mutation_scale=12,
                              color=c, linewidth=lw,
                              linestyle="dashed" if dashed else "solid",
                              zorder=z)
        self.ax.add_patch(arr)
        return arr

    def save(self, out_png):
        os.makedirs(os.path.dirname(out_png) or ".", exist_ok=True)
        if self._qa:
            probs = _geometry_qa(self)
            if probs:
                QA_PROBLEMS.extend(probs)
                print("[QA] 几何自检发现问题：")
                for p in probs:
                    print(p)
        self.fig.savefig(out_png, dpi=180, bbox_inches="tight",
                         facecolor="white", pad_inches=0.08)
        self.plt.close(self.fig)
        print(f"[PNG] {out_png}")


def _geometry_qa(cv):
    """保存前几何自检：把每个 ax.text 的窗口 bbox 换算到数据坐标
    （1 数据单位 = 1 英寸），检查是否出画布（容差 0.02）与两两压叠
    （ox,oy>0.01 且面积>0.002 in^2）。返回问题清单。"""
    from matplotlib.transforms import Bbox
    renderer = cv.fig.canvas.get_renderer()
    inv = cv.ax.transData.inverted()
    boxes = []
    for t in cv.ax.texts:
        s = t.get_text()
        if not s or not s.strip():
            continue
        bb = t.get_window_extent(renderer=renderer)
        (x0, y0), (x1, y1) = inv.transform([(bb.x0, bb.y0), (bb.x1, bb.y1)])
        boxes.append((s, Bbox([[x0, y0], [x1, y1]])))
    W, H = cv.W, cv.H
    probs, pad = [], 0.02
    for s, bb in boxes:
        if bb.x0 < -pad or bb.y0 < -pad or bb.x1 > W + pad or bb.y1 > H + pad:
            probs.append(f"    · 出界 {s[:18]!r}: ({bb.x0:.2f},{bb.y0:.2f})-"
                         f"({bb.x1:.2f},{bb.y1:.2f}) 画布 {W:.1f}x{H:.1f}")
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            s0, b0 = boxes[i]
            s1, b1 = boxes[j]
            ox = min(b0.x1, b1.x1) - max(b0.x0, b1.x0)
            oy = min(b0.y1, b1.y1) - max(b0.y0, b1.y0)
            if ox > 0.01 and oy > 0.01:
                area = ox * oy
                if area > 0.002:
                    probs.append(f"    · 压叠 {s0[:18]!r} x {s1[:18]!r} "
                                 f"面积 {area:.3f} in^2")
    return probs


def _kind_chips(cv, m, usedk, yl):
    """在底线 yl 画 kind 图例小chip。"""
    lx = 0.2
    for k in usedk:
        cv.rbox(lx, yl - 0.055, 0.17, 0.11, KIND_FILL.get(k, "#ffffff"),
                KIND_EDGE.get(k, "#4a5a66"), lw=0.9, rounding=0.02)
        labcn = KIND_CN.get(k, k)
        cv.text(lx + 0.2, yl, labcn, fs=7.5, va="center", color="#333")
        lx += 0.2 + m.ext(labcn, 7.5)[0] + 0.3


def _role_chips(cv, m, roles, yl):
    """在底线 yl 画角色图例小chip（配色沿用 COL/TYPE_CN）。"""
    lx = 0.2
    for t in roles:
        col = COL.get(t, COL["generic"])
        cv.rbox(lx, yl - 0.055, 0.17, 0.11, col, "#555", lw=0.7,
                rounding=0.02)
        labcn = TYPE_CN.get(t, t)
        cv.text(lx + 0.2, yl, labcn, fs=7.5, va="center", color="#333")
        lx += 0.2 + m.ext(labcn, 7.5)[0] + 0.3
    return lx


# ------------------------------------------------------------------------------
# fig 类型 "arch" —— 论文自身逻辑架构图（忠实方法数据流）
# ------------------------------------------------------------------------------
def render_arch(d, out_png, out_md=None):
    """『架构图』：列=处理阶段；框=模块/数据（短标签 + 要点/尺寸/参数/源章节小字注）。
    JSON：
    { "type":"arch", "title":.., "sub":..(可选一句读法),
      "stages":[ {"name":.., "nodes":[
                    {"id","label","note"?,"kind"?} ]} ],
      "edges":[ {"u","v","label"?,"style":"dash"?} ] }   # 通常相邻列推进
    kind ∈ input/cond/feat/module/fuse/decode/output/loss/aux（决定填色与图例）。
    只保留论文自身信息；方向级内容归 direction-survey，不在本图画。
    """
    import matplotlib
    m = Measure()
    fam = m.fam
    if fam:
        matplotlib.rcParams["font.sans-serif"] = [fam]
    fs_l, fs_n = 8.6, 6.8
    pl, pn = fs_l / 72 * 1.5, fs_n / 72 * 1.6
    stages = d.get("stages", [])
    if not stages:
        raise SystemExit("[pa_fig] arch：无 stages")
    infos = []
    for st in stages:
        nodes = []
        for n in st.get("nodes", []):
            lid = str(n.get("id", ""))
            lab = []
            for raw in str(n.get("label", lid)).split("\n"):
                lab += m.wrap(raw, fs_l, 2.95)
            note = str(n.get("note", ""))
            nls = m.wrap(note, fs_n, 2.95) if note else []
            w = min(max(max(m.width(lab, fs_l), m.width(nls, fs_n)) + 0.34, 1.3), 3.4)
            h = 0.18 + len(lab) * pl + (0.07 + len(nls) * pn if nls else 0.0)
            nodes.append({"id": lid, "lab": lab, "nls": nls,
                          "kind": str(n.get("kind", "module")),
                          "w": w, "h": h})
        colH = sum(x["h"] for x in nodes) + 0.13 * max(len(nodes) - 1, 0)
        infos.append({"name": str(st.get("name", "")), "nodes": nodes, "colH": colH})

    # ---- 水平布局（列从左到右）
    gx = 1.0
    xs, x = [], 0.55
    for it in infos:
        bw = max((nd["w"] for nd in it["nodes"]), default=1.3)
        xs.append(x + bw / 2)
        x += bw + gx
    W = max(x - gx + 0.45, 7.0)

    title = d.get("title", "")
    sub = d.get("sub", "")
    sl = m.wrap(sub, 8, W - 1.6) if sub else []
    topH = 0.64 + 0.16 * len(sl)
    sh = 0.34                      # 阶段名带
    bodyH = max(it["colH"] for it in infos)
    usedk = []
    for it in infos:
        for nd in it["nodes"]:
            if nd["kind"] not in usedk:
                usedk.append(nd["kind"])
    legH = 0.4 if (len(usedk) > 1 or any(k not in ("module", "decode") for k in usedk)) else 0.0
    H = topH + sh + bodyH + 0.4

    cv = Canvas(W, H, fam)
    cv.text(W / 2, H - 0.2, title, fs=12, ha="center", va="center",
            fontweight="bold", color="#111")
    yy = H - 0.52
    for ln in sl:
        cv.text(W / 2, yy, ln, fs=8, ha="center", va="center", color="#5a6b7a")
        yy -= 0.16

    # 阶段名 + 框位置（top-anchor 到 bodyTopY）
    bodyTopY = H - topH - sh
    ny = H - topH - sh / 2
    for i, it in enumerate(infos):
        nml = m.wrap(it["name"], 8.8, 3.6)
        yy2 = ny + (len(nml) - 1) * 0.15 / 2
        for ln in nml:
            cv.text(xs[i], yy2, ln, fs=8.8, ha="center", va="center",
                    fontweight="bold", color="#31424f")
            yy2 -= 0.15
        top = bodyTopY
        for nd in it["nodes"]:
            nd["cx"] = xs[i]
            nd["yc"] = top - nd["h"] / 2
            top -= nd["h"] + 0.13

    # 框底
    for it in infos:
        for nd in it["nodes"]:
            cv.rbox(nd["cx"] - nd["w"] / 2, nd["yc"] - nd["h"] / 2,
                    nd["w"], nd["h"], KIND_FILL.get(nd["kind"], "#ffffff"),
                    KIND_EDGE.get(nd["kind"], "#4a5a66"), lw=1.0,
                    rounding=0.09, z=2)
    # 箭头（逐模块 → 下一步）
    nmap = {}
    for it in infos:
        for nd in it["nodes"]:
            if nd["id"]:
                nmap[nd["id"]] = nd
    for e in d.get("edges", []):
        u, v = nmap.get(e["u"]), nmap.get(e["v"])
        if not u or not v:
            print(f"[pa_fig] arch：跳过缺节点边 {e.get('u')} -> {e.get('v')}")
            continue
        x0, y0 = u["cx"] + u["w"] / 2, u["yc"]
        x1, y1 = v["cx"] - v["w"] / 2, v["yc"]
        if x1 <= x0:
            print(f"[pa_fig] arch：跳过逆向/同列边 {e.get('u')} -> {e.get('v')}")
            continue
        cv.arrow(x0, y0, x1, y1, dashed=(e.get("style") == "dash"))
        if e.get("label"):
            cv.text((x0 + x1) / 2, (y0 + y1) / 2 + 0.09, str(e["label"]),
                    fs=6.8, ha="center", va="center", color="#333",
                    bbox=dict(boxstyle="round,pad=0.12", fc="white",
                              ec="#cccccc", lw=0.4))
    # 框内文字
    for it in infos:
        for nd in it["nodes"]:
            xc, y = nd["cx"], nd["yc"] + nd["h"] / 2 - 0.05
            for ln in nd["lab"]:
                cv.text(xc, y, ln, fs=fs_l, ha="center", va="top",
                        fontweight="bold", color="#1b2530")
                y -= pl
            if nd["nls"]:
                y -= 0.04
                for ln in nd["nls"]:
                    cv.text(xc, y, ln, fs=fs_n, ha="center", va="top",
                            color="#5a6b77")
                    y -= pn
    # 底线图例 / 提示
    if legH:
        cv.ax.axhline(0.2, xmin=0, xmax=1, color="#e2e6ea", lw=0.8)
        _kind_chips(cv, m, usedk, 0.2)
    cv.text(W - 0.2, 0.2, "从左到右 = 方法数据流（箭头 = 前一步 → 下一步）",
            fs=7.3, ha="right", va="center", color="#7a8794")
    cv.save(out_png)


# ------------------------------------------------------------------------------
# fig 类型 "rel" —— 该论文与相关论文的关系图（本文中心）
# ------------------------------------------------------------------------------
def render_rel(d, out_png, out_md=None):
    """『关系图』：左侧相关论文（按角色上色）→ 右侧金色本文框；箭头带 [k] 编号，
    编号解释放图下 k 列表（关系 + 证据）。
    JSON：
    { "type":"rel", "title":.., "sub":..(可选),
      "this": {"id","label","note"?},
      "nodes":[ {"id","label","type"(pre/rival/module/next/adj),"note"?} ],
      "edges":[ {"u"(相关论文),"v"(本文id),"evidence":..} ] }
    角色配色沿用 COL/TYPE_CN；只画本文与相关论文的关系，方向级内容归 direction-survey。
    """
    import matplotlib
    m = Measure()
    fam = m.fam
    if fam:
        matplotlib.rcParams["font.sans-serif"] = [fam]
    fs, fsn = 8.8, 6.8
    pl, pn = fs / 72 * 1.55, fsn / 72 * 1.6
    nodes = d.get("nodes", [])
    this = d.get("this", {})
    edges = d.get("edges", [])
    thisid = str(this.get("id", "this"))

    cards = []
    cw = 0.0
    for n in nodes:
        lines = []
        for raw in str(n.get("label", n.get("id", ""))).split("\n"):
            lines += m.wrap(raw, fs, 3.0)
        note = str(n.get("note", ""))
        nls = m.wrap(note, fsn, 3.0) if note else []
        w = min(max(max(m.width(lines, fs), m.width(nls, fsn)) + 0.34, 1.4), 3.3)
        cw = max(cw, w)
        h = 0.2 + len(lines) * pl + (0.08 + len(nls) * pn if nls else 0.0)
        cards.append({"id": str(n.get("id", "")), "type": str(n.get("type", "adj")),
                      "lines": lines, "nls": nls, "w": w, "h": h})
    cardH = sum(c["h"] for c in cards) + 0.12 * max(len(cards) - 1, 0)

    tlab = []
    for raw in str(this.get("label", thisid)).split("\n"):
        tlab += m.wrap(raw, 9.2, 2.6)
    tnote = str(this.get("note", ""))
    tnls = m.wrap(tnote, 7.2, 2.6) if tnote else []
    pt, ptn = 9.2 / 72 * 1.5, 7.2 / 72 * 1.6
    tw = min(max(max(m.width(tlab, 9.2), m.width(tnls, 7.2)) + 0.42, 1.6), 3.2)
    thisH = 0.2 + len(tlab) * pt + (0.08 + len(tnls) * ptn if tnls else 0.0)

    bodyH = max(cardH, thisH)
    gapX = 1.7
    W = max(0.5 + cw + gapX + tw + 0.6, 8.2)

    title = d.get("title", "")
    sub = d.get("sub", "")
    sl = m.wrap(sub, 8, W - 1.6) if sub else []
    topH = 0.64 + 0.16 * len(sl)

    # 编号证据列表（图下）
    byid = {}
    for c in cards:
        byid[c["id"]] = c
    byid[thisid] = None
    list_lines = []
    roles = []
    for k, e in enumerate(edges, 1):
        us, vs = str(e.get("u", "")), str(e.get("v", ""))
        if us not in byid or vs not in byid:
            print(f"[pa_fig] rel：跳过缺节点边 {us} -> {vs}")
            continue
        other = vs if us == thisid else us
        c = byid.get(other)
        if not c:
            continue
        typ = c["type"]
        if typ not in roles:
            roles.append(typ)
        tcn = TYPE_CN.get(typ, typ)
        sh = (c["lines"][0] if c["lines"] else c["id"])[:24]
        ev = str(e.get("evidence", ""))
        head = f"[{k}] {tcn} · {sh}：{ev}"
        list_lines += m.wrap(head, 7.2, W - 1.5)
    legH = 0.42 if (roles or True) else 0.0
    listH = len(list_lines) * 0.15 + 0.1
    H = topH + bodyH + listH + legH + 0.25

    cv = Canvas(W, H, fam)
    cv.text(W / 2, H - 0.2, title, fs=12, ha="center", va="center",
            fontweight="bold", color="#111")
    yy = H - 0.52
    for ln in sl:
        cv.text(W / 2, yy, ln, fs=8, ha="center", va="center", color="#5a6b7a")
        yy -= 0.16

    bodyTopY = H - topH
    # 相关论文卡（左列，top-anchor）
    xcardL, xcardR = 0.5, 0.5 + cw
    y = bodyTopY
    for c in cards:
        yc = y - c["h"] / 2
        c["yc"] = yc
        y -= c["h"] + 0.12
    # 本文金色框（右，贯穿 body 高度，便于箭头水平进入）
    thisX = W - 0.6 - tw / 2
    thisL, thisR = W - 0.6 - tw, W - 0.6
    for c in cards:
        t = c["type"]
        col = COL.get(t, COL["generic"])
        cv.rbox(xcardL, c["yc"] - c["h"] / 2, cw, c["h"],
                _lighten(col), col if t == "this" else "#777",
                ls="-" if t == "this" else "--", lw=1.0, rounding=0.1, z=2)
        yy = c["yc"] + c["h"] / 2 - 0.06
        for ln in c["lines"]:
            cv.text(0.5 + cw / 2, yy, ln, fs=fs, ha="center", va="top",
                    fontweight="bold", color="#1b2530")
            yy -= pl
        if c["nls"]:
            yy -= 0.03
            for ln in c["nls"]:
                cv.text(0.5 + cw / 2, yy, ln, fs=fsn, ha="center", va="top",
                        color="#55616c")
                yy -= pn
    cv.rbox(thisL, bodyTopY - bodyH, tw, bodyH, COL["this"], "#7a5a1a",
            lw=1.2, rounding=0.14, z=2)
    off = (bodyH - thisH) / 2
    yy = bodyTopY - off - 0.1
    for ln in tlab:
        cv.text(thisX, yy, ln, fs=9.2, ha="center", va="top",
                fontweight="bold", color="#3d2f0a")
        yy -= pt
    if tnls:
        yy -= 0.05
        for ln in tnls:
            cv.text(thisX, yy, ln, fs=7.2, ha="center", va="top", color="#5a4a1c")
            yy -= ptn

    # 编号箭头
    for k, e in enumerate(edges, 1):
        us, vs = str(e.get("u", "")), str(e.get("v", ""))
        U, V = byid.get(us), byid.get(vs)
        if (U is None and V is None) or (U is not None and V is not None):
            continue
        other = V if U is None else U        # 非本文端（卡片）
        if U is None:                        # this -> 卡：指向左
            x0, y0 = thisL, other["yc"]
            x1, y1 = xcardR, other["yc"]
        else:                                # 卡 -> this：指向右
            x0, y0 = xcardR, other["yc"]
            x1, y1 = thisL, other["yc"]
        cv.arrow(x0, y0, x1, y1)
        mx = (x0 + x1) / 2
        cv.text(mx, other["yc"] + 0.1, str(k), fs=6.8, ha="center", va="center",
                fontweight="bold", color="#222", zorder=6,
                bbox=dict(boxstyle="circle,pad=0.18", fc="white",
                          ec="#9aa5b0", lw=0.6))

    # 图下证据列表 + 图例
    yl_top = bodyTopY - bodyH - 0.15
    yl_top = max(yl_top, 0.52)
    yy = yl_top
    for ln in list_lines:
        cv.text(0.5, yy, ln, fs=7.2, ha="left", va="top", color="#333333")
        yy -= 0.15
    cv.ax.axhline(0.2, xmin=0, xmax=1, color="#e2e6ea", lw=0.8)
    roles.insert(0, "this")
    _role_chips(cv, m, roles, 0.2)
    cv.text(W - 0.2, 0.2, "金=本文 · 箭头带 [k]，k 解释见图下列表",
            fs=7.3, ha="right", va="center", color="#7a8794")
    cv.save(out_png)


def main():
    global QA_ON
    utf8()
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("json")
    ap.add_argument("--png", help="输出 png 路径；传 - 跳过")
    ap.add_argument("--mermaid", help="输出 .mermaid 路径；传 - 跳过")
    ap.add_argument("--qa", action="store_true",
                    help="渲染后做程序化几何自检（arch/rel；出界/压叠→退出码 1）")
    a = ap.parse_args()
    QA_ON = a.qa
    with open(a.json, encoding="utf-8") as f:
        d = json.load(f)
    stem = os.path.splitext(a.json)[0]
    gtype = d.get("type", "lineage")
    png = a.png if a.png and a.png != "-" else (a.png is None and (stem + ".png"))
    if gtype == "scatter2d":
        if png:
            render_scatter(d, png)
        elif a.png == "-":
            print("[跳过 PNG]")
    elif gtype in ("arch", "rel"):
        if not png:
            print("[pa_fig] arch/rel 至少需要一个 PNG 输出；用 --png out.png")
            sys.exit(2)
        if a.mermaid and a.mermaid != "-":
            print("[pa_fig] arch/rel 不出 Mermaid（语义在图上）")
        if gtype == "arch":
            render_arch(d, png)
        else:
            render_rel(d, png)
    else:
        md = a.mermaid if a.mermaid is not None else (stem + ".mermaid")
        if a.mermaid == "-":
            md = None
        if png:
            render_layer_graph(d, png, md)
        else:
            print("[pa_fig] lineage 至少需要一个 PNG 输出；用 --png out.png")
    if a.qa:
        if QA_PROBLEMS:
            print(f"[QA] 几何自检：{len(QA_PROBLEMS)} 处问题（见上，退出码 1）")
            sys.exit(1)
        print("[QA] 几何 QA 通过：无出界 / 无压叠。")


if __name__ == "__main__":
    main()
