#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
direction-survey v3.0 · ds_fig.py —— 方向级/学科级综述图专用渲染器（PNG + Mermaid）
----------------------------------------------------------------------
方向综述 v2 的"方向级"布局不用通用 lineage（跨家族/跨阶段边会乱成一团），分四种：

  * fig:"stage"   阶段演进图 —— 横向一列一个"阶段带"：带顶=阶段名+时期+推动力，
                                 带中=代表工作（库内实心/库外浅虚线），
                                 带底=标志突破（绿）/ 遗留问题（红），带与带之间一根转向箭头。
                                 回答「方向怎么走过来的」。

  * fig:"family"  家族泳道图 —— 每条技术家族 = 一条横向泳道；道内节点从左到右按血缘/时间
                                 排成链（道内实线=继承）；跨家族虚线短箭头只画"相邻泳道"，
                                 编号解释在图下"边注表"；跨非相邻泳道的关系进 cross_notes 只作文本。
                                 回答「现在岔成几股、谁借了谁」。

  * fig:"quad"    象限机会图 —— x=机会空间/空白度(右大)、y=前沿活跃度(上高) 的 0–1 示意象限，
                                 右上=又热又空=空白最大处最该投。只在正交坐标上投点，回答
                                 「机会子题落在哪」。无 Mermaid。

  * fig:"audit"   生态盘点矩阵表图 —— 行=方法（按研发谱系分带）、列=评测协议/复杂度/质量等
                                 维度，逐格排文本；回答「这个方向生态里各队做了什么、同表能不能比」。
                                 无 Mermaid。

  * fig:"terrain" 学科地形图（v3.0 新，**学科级**）—— 行=细分方向（分带=库内已建目录 /
                                 论断新增候选），列=成立度 / 成熟度 / 活跃度 / 空白度 / 库内样本 /
                                 边界一句话；level 列格内色深=该维取值高（低/中/高三档）。
                                 回答「这个学科现在是几块、哪块成熟、哪块还空、哪块本不该这么切」。
                                 无 Mermaid。

沿用 paper-analyzer pa_fig 的配色 / 无 emoji / CJK 回退纪律。pa_fig 的 lineage 与 scatter2d
仍由 pa_fig 渲染（本脚本不接管）。quad / audit / terrain 为语义图，其数据不在 Mermaid 表达范围内。

用法:
  python ds_fig.py <descriptor.json> --png <out>.png [--mermaid <out>.mermaid] [--qa]
  （--mermaid -  则只出 PNG；不传 --mermaid 缺省同路径 .mermaid）
  （--qa         渲染后做程序化几何自检：文字出画布 / 两两压叠 → 有问题列出并以退出码 1 拦下）

JSON —— fig:"stage"
{
  "fig":"stage", "title":"…",
  "stages":[
    {"id":"s1","name":"S1 · 起源：任务被经典前驱定义","period":"2018–2020",
     "driver":"实时设备需求把『只要目标说话人』拉起",
     "works":[{"label":"time-domain SpeakerBeam","type":"pre","year":"2020"},
              {"label":"PercepNet","type":"pre","year":"2020"}],
     "breakthrough":"TSE 由 enrollment 条件化定义；时域/感知骨架定型",
     "gap":"目标条件化与实时低复杂度未统一"}
  ],
  "stage_edges":[{"a":"s1","b":"s2","label":"转向：个性化+实时低复杂度整合"}]
}

JSON —— fig:"family"
{
  "fig":"family", "title":"…", "intro":"…",
  "lanes":[
    {"id":"fam_a","name":"A · 感知特征条件化（48k 实时个性化）",
     "nodes":[{"id":"p","label":"PercepNet 2020","type":"pre"},
              {"id":"ppn","label":"Personalized PercepNet 2021·库内","type":"this"}],
     "edges":[{"u":"p","v":"ppn","label":"最小侵入改造"}]}
  ],
  "cross":[
    {"from":"fam_a.p","to":"fam_b.q","label":"模块来源",
     "note":"GE2E 说话人损失被 B 用于 SE","evidence":"PPN §5 R3"}
  ]
}
节点 type ∈ this/pre/rival/module/next/adj/generic（this=库内已分析金色实色，其余=库外未读锚点
按角色浅色+虚线框）。边 style：stage/family 道内继承实线；跨家族借用虚线。红线：图上不放 emoji
（ds_render 已先校验）。layout 以"1 数据单位 = 1 英寸"铺开，文本逐字量宽，不越界不重叠。
"""
import argparse
import json
import os
import sys

TYPES = ["this", "pre", "rival", "module", "next", "adj", "generic"]
COL = {
    "this": "#f2b134",
    "pre": "#6fbf73",
    "rival": "#e0645a",
    "module": "#5b9bd5",
    "next": "#ab82c8",
    "adj": "#8aa2b8",
    "generic": "#cfd8dc",
}
TYPE_CN = {"this": "库内已读", "pre": "上游前驱", "rival": "直接竞品",
           "module": "模块来源", "next": "后续演进", "adj": "细分邻域", "generic": "其他"}
DPI = 100

# --qa 几何自检开关与问题收集（Figure.save 在关闭前写入）
QA_ON = False
QA_PROBLEMS = []


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


def _lighten(hexcol, f=0.45):
    hexcol = hexcol.lstrip("#")
    r, g, b = (int(hexcol[i:i + 2], 16) for i in (0, 2, 4))
    return f"#{int(r + (255 - r) * f):02x}{int(g + (255 - g) * f):02x}{int(b + (255 - b) * f):02x}"


class Measure:
    """测量文本铺开尺寸（单位=英寸）。dpi 固定 100，figsize 不影响 text 度量。"""

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
        self._cache = {}

    def ext(self, txt, fs, weight="normal"):
        key = (txt, fs, weight)
        if key in self._cache:
            return self._cache[key]
        t = self.fig.text(0, 0, txt, fontsize=fs, fontweight=weight)
        bb = t.get_window_extent(renderer=self._rend)
        t.remove()
        r = (bb.width / DPI, bb.height / DPI)
        self._cache[key] = r
        return r

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


class Figure:
    """最终画布：figsize=(W,H) 英寸，1 数据单位 = 1 英寸（全幅等比例坐标）。"""

    def __init__(self, W, H, fam):
        import matplotlib
        import matplotlib.pyplot as plt
        import matplotlib.patches as mp
        if fam:
            matplotlib.rcParams["font.sans-serif"] = [fam]
        matplotlib.rcParams["axes.unicode_minus"] = False
        self.plt = plt
        self.mp = mp
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

    def save(self, out_png):
        os.makedirs(os.path.dirname(out_png) or ".", exist_ok=True)
        if self._qa:
            probs = _geometry_qa(self)
            if probs:
                QA_PROBLEMS.extend(probs)
                print("[QA] 几何自检发现问题：")
                for p in probs:
                    print(p)
        self.fig.savefig(out_png, dpi=180, bbox_inches="tight", facecolor="white",
                         pad_inches=0.08)
        self.plt.close(self.fig)
        print(f"[PNG] {out_png}")


def _geometry_qa(fig):
    """保存前几何自检：把每个 ax.text 的窗口 bbox 换算到数据坐标（1 数据单位=1 英寸），
    检查是否出画布（容差 0.02）与两两压叠（ox,oy>0.01 且面积>0.002 in^2）。返回问题清单。"""
    from matplotlib.transforms import Bbox
    renderer = fig.fig.canvas.get_renderer()
    inv = fig.ax.transData.inverted()
    boxes = []
    for t in fig.ax.texts:
        s = t.get_text()
        if not s or not s.strip():
            continue
        bb = t.get_window_extent(renderer=renderer)
        (x0, y0), (x1, y1) = inv.transform([(bb.x0, bb.y0), (bb.x1, bb.y1)])
        boxes.append((s, Bbox([[x0, y0], [x1, y1]])))
    W, H = fig.W, fig.H
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
                    probs.append(f"    · 压叠 {s0[:18]!r} x {s1[:18]!r} 面积 {area:.3f} in^2")
    return probs


def _edge_arrow(fig, m, x0, y0, x1, y1, label=None, dashed=False, fs=7.5,
                idx=None, rad=0.18):
    from matplotlib.patches import FancyArrowPatch
    style = "dashed" if dashed else "solid"
    col = "#7f8c98" if dashed else "#4a5a66"
    arr = FancyArrowPatch((x0, y0), (x1, y1),
                          connectionstyle=f"arc3,rad={rad}",
                          arrowstyle="-|>", mutation_scale=13,
                          color=col, linewidth=1.2, linestyle=style,
                          shrinkA=8, shrinkB=8, zorder=2)
    fig.ax.add_patch(arr)
    mx, my = (x0 + x1) / 2, (y0 + y1) / 2
    if idx is not None:
        w, h = m.ext(idx, fs)[0] + 0.07, m.ext(idx, fs)[1] + 0.02
        bx, by = mx - w / 2, my + 0.04
        fig.rbox(bx, by, w, h, "white", "#999999", lw=0.6, rounding=0.03, z=4)
        fig.text(mx, by + h / 2, idx, fs=fs, ha="center", va="center",
                 fontweight="bold", color="#222", zorder=5)
    if label:
        lw_, lh = m.ext(label, fs)[0], m.ext(label, fs)[1]
        lab_x, lab_y = mx - lw_ / 2 - 0.03, my - lh / 2 - 0.02
        fig.rbox(lab_x, lab_y, lw_ + 0.06, lh + 0.04, "#ffffff", "#d5dadd",
                 lw=0.5, rounding=0.03, z=4)
        fig.text(mx, my, label, fs=fs, ha="center", va="center", color="#333",
                 zorder=5)


# ------------------------------------------------------------------------------
# fig:"stage"
# ------------------------------------------------------------------------------
def render_stage(d, out_png, out_md):
    m = Measure()
    stages = d.get("stages", [])
    for s in stages:
        s["_works"] = [(w, m.wrap(w.get("label", w.get("id", "")), 8.5, 3.0))
                       for w in s.get("works", [])]

    # 列宽 = 工作标签 + 脚注换行需要 的综合（两次逼近）
    col_w = 3.0
    for _ in range(2):
        need = 2.2
        for s in stages:
            for _, wlines in s["_works"]:
                need = max(need, m.width(wlines, 8.5) + 0.4)
            foot_in = col_w - 0.9
            nfoot = len(m.wrap("突破：" + s.get("breakthrough", ""), 8, foot_in)) + \
                    len(m.wrap("遗留：" + s.get("gap", ""), 8, foot_in))
            need = max(need, min(1.5 + nfoot * 0.18, 5.2))
        col_w = min(max(need, 2.6), 4.6)
    gap_x = 2.4
    for e in d.get("stage_edges", []):
        gap_x = max(gap_x, min(m.ext(e.get("label", ""), 7.5)[0] + 0.6, 3.2))

    # 垂直尺寸（各阶段同高 = 最大值）
    def stage_inner_h(s):
        head_lines = m.wrap(s.get("name", ""), 10.5, col_w - 0.5)
        hh = len(head_lines) * (10.5 / 72) * 1.3 + 0.05
        if s.get("period"):
            hh += (8.5 / 72) * 1.3 + 0.04
        dls = m.wrap("推动：" + s.get("driver", ""), 7.8, col_w - 0.5) if s.get("driver") else []
        hh += len(dls) * 0.112 + 0.04
        n = max(len(s["_works"]), 1)
        hh += n * 0.6 + 0.2
        foot_in = col_w - 0.9
        fl = len(m.wrap("突破：" + s.get("breakthrough", ""), 8, foot_in)) + \
             len(m.wrap("遗留：" + s.get("gap", ""), 8, foot_in))
        hh += fl * (8 / 72) * 1.4 + 0.2
        return hh

    inner_h = max([stage_inner_h(s) for s in stages] or [5.0])
    title_h = 0.55
    top = title_h + 0.08
    legend_h = 0.34
    H = top + inner_h + legend_h + 0.1
    n = len(stages)
    W = max(1.2 + n * col_w + (n - 1) * gap_x, 8.0)

    fig = Figure(W, H, m.fam)
    _ = fig
    # 标题
    fig.text(W / 2, H - 0.18, d.get("title", ""), fs=13, ha="center", va="center",
             fontweight="bold", color="#111")
    y0_band = legend_h + 0.12        # 阶段带底
    y1_band = H - title_h            # 阶段带顶

    # 每个阶段带内做垂直布局
    def place_stage(s, x0):
        xc = x0 + col_w / 2
        import matplotlib.patches as _mp
        fig.rbox(x0, y0_band, col_w, y1_band - y0_band, "#f2f6fb", "#c9d4e0",
                 rounding=0.12, z=0)
        y = y1_band - 0.1
        head_lines = m.wrap(s.get("name", ""), 10.5, col_w - 0.5)
        for ln in head_lines:
            fig.text(xc, y, ln, fs=10.5, ha="center", va="top", fontweight="bold",
                     color="#20303f")
            y -= (10.5 / 72) * 1.32
        if s.get("period"):
            fig.text(xc, y - 0.02, s.get("period", ""), fs=8.5, ha="center",
                     va="top", color="#5a6b7a")
            y -= (8.5 / 72) * 1.35 + 0.06
        if s.get("driver"):
            for ln in m.wrap("推动：" + s.get("driver", ""), 7.8, col_w - 0.5):
                fig.text(xc, y, ln, fs=7.8, ha="center", va="top",
                         color="#5f6b76", style="italic")
                y -= 0.112
            y -= 0.05
        # 工作 chip 区 + 脚注：脚注贴底
        foot_in = col_w - 0.9
        fl = m.wrap("突破：" + s.get("breakthrough", ""), 8, foot_in) + \
             m.wrap("遗留：" + s.get("gap", ""), 8, foot_in)
        foot_h = len(fl) * (8 / 72) * 1.42
        foot_top = y0_band + 0.14 + foot_h
        avail = y - foot_top - 0.12
        if avail < 0.1:
            avail = 0.1
        works = s["_works"]
        nw = max(len(works), 1)
        pitch = avail / nw
        wy = y - 0.05
        for (wk, wlines), i in zip(works, range(nw)):
            cy = wy - (i + 0.5) * pitch
            t = wk.get("type", "pre")
            show = list(wlines)
            if wk.get("year"):
                show = show + [wk.get("year", "")]
            # chip 宽以文本量宽为准
            cw = m.width(show, 8.5) + 0.42
            cw = min(max(cw, 1.2), col_w - 0.35)
            col = COL.get(t, COL["generic"])
            ch = (len(show) * (8.5 / 72) * 1.28 + 0.14)
            if t == "this":
                fig.rbox(xc - cw / 2, cy - ch / 2, cw, ch, col, "#333", lw=0.7,
                         rounding=0.09)
            else:
                fig.rbox(xc - cw / 2, cy - ch / 2, cw, ch, _lighten(col), "#666",
                         ls="--", lw=0.8, rounding=0.09)
            fig.text(xc, cy, "\n".join(show), fs=8.5, ha="center", va="center",
                     color="#161616", linespacing=1.22)
            used.add(t)
        # 脚注
        fy = foot_top - (8 / 72) * 1.42
        for j, ln in enumerate(fl):
            color = "#8a3b3b" if ln.startswith("遗留") else "#2f5c3a"
            yt = y0_band + 0.14 + (len(fl) - 1 - j) * (8 / 72) * 1.42
            fig.text(xc, yt, ln, fs=8, ha="center", va="bottom", color=color)
        return xc, col_w

    used = set()
    x = 1.0
    bx = []
    for s in stages:
        c, _ = place_stage(s, x)
        bx.append((x, x + col_w))
        x += col_w + gap_x
    # 阶段间转向箭头（在带之间顶部区域）
    for e in d.get("stage_edges", []):
        ia = next((i for i, s in enumerate(stages) if s.get("id") == e.get("a")), None)
        ib = next((i for i, s in enumerate(stages) if s.get("id") == e.get("b")), None)
        if ia is None or ib is None:
            continue
        ya = H - title_h - 0.12
        if ia < ib:
            _edge_arrow(fig, m, bx[ia][1] + 0.02, ya, bx[ib][0] - 0.02, ya,
                        label=e.get("label", ""), fs=7.5, rad=0.0)
    # 图例 + 说明
    _legend(fig, m, used, legend_h)
    fig.text(W - 1.0, legend_h / 2, "列=阶段（左早右晚）· 箭头=阶段间转向",
             fs=7.5, ha="right", va="center", color="#7a7a7a")

    fig.save(out_png)
    if out_md:
        _write(out_md, _mermaid_stage(d))


# ------------------------------------------------------------------------------
# fig:"family"
# ------------------------------------------------------------------------------
def render_family(d, out_png, out_md):
    m = Measure()
    lanes = d.get("lanes", [])
    gutter = 0.0
    node_w = 3.0
    for l in lanes:
        nm = m.wrap(l.get("name", ""), 9.5, 3.0)
        gutter = max(gutter, m.width(nm, 9.5))
        l["_nm_lines"] = nm
        cum = 0.0
        l["_xs"] = {}
        for n in l.get("nodes", []):
            lines = []
            for raw in n.get("label", n.get("id", "")).split("\n"):
                lines += m.wrap(raw, 8.5, 3.0)
            n["_lines"] = lines
            w = m.width(lines, 8.5) + 0.5
            n["_w"] = min(max(w, 1.3), 3.6)
            l["_xs"][n.get("id")] = gutter + 0.25 + n["_w"] / 2 + cum
            cum += n["_w"] + 0.85
        l["_cum"] = cum
        node_w = max(node_w, max((n["_w"] for n in l.get("nodes", [])), default=1.3))
    gutter_w = max(min(gutter + 0.8, 3.4), 1.2)
    x_start = gutter_w + 0.15
    # x 再算一次（用真正起点）
    for l in lanes:
        cx = x_start
        l["_xs"] = {}
        for n in l.get("nodes", []):
            l["_xs"][n.get("id")] = cx + n["_w"] / 2
            cx += n["_w"] + 0.85
        l["_cx_end"] = cx
    content_w = max(l["_cx_end"] for l in lanes)
    W = max(content_w + 0.4, 9.0)

    intro_lines = []
    if d.get("intro"):
        intro_lines = m.wrap(d["intro"], 8, W - 1.4)
    laneH = max(1.55, min(max(len(n["_lines"]) for l in lanes for n in l.get("nodes", [])), 6) * 0.16 + 1.1)
    gapY = 1.0
    note_lines = []
    for k, c in enumerate(d.get("cross", []), 1):
        note_lines.append(f"边{k}　{c.get('label','')}：{c.get('note','')}（{c.get('evidence','')}）")
    for cn in d.get("cross_notes", []):
        note_lines.append(f"〔文字·未画线〕{cn.get('label','')}：{cn.get('note','')}（{cn.get('evidence','')}）")
    title_h = 0.55
    legend_h = 0.34
    intro_h = len(intro_lines) * 0.16 + 0.05
    note_h = len(note_lines) * 0.17 + (0.06 if note_lines else 0)
    H = title_h + intro_h + 0.1 + len(lanes) * laneH + (len(lanes) - 1) * gapY + note_h + legend_h + 0.15

    fig = Figure(W, H, m.fam)
    fig.text(W / 2, H - 0.18, d.get("title", ""), fs=13, ha="center", va="center",
             fontweight="bold", color="#111")
    y = H - title_h - intro_h - 0.05
    if intro_lines:
        for ln in intro_lines:
            fig.text(W / 2, y + 0.12, ln, fs=8, ha="center", va="center",
                     color="#5a6b7a")
            y -= 0.16
    used = set()
    lane_y = {}
    node_xy = {}
    for i, l in enumerate(lanes):
        yc = y - i * (laneH + gapY) - laneH / 2
        lane_y[l.get("id")] = yc
        # 道带
        fig.rbox(0.08, yc - laneH / 2, W - 0.16, laneH, "#f7f8fb", "#d5dbe3",
                 rounding=0.12, z=0)
        # 道名（左栏）
        nml = l["_nm_lines"]
        fig.text(gutter_w - 0.15, yc + laneH / 2 - 0.12, "\n".join(nml), fs=9.5,
                 ha="right", va="top", fontweight="bold", color="#24313c")
        # 节点
        for n in l.get("nodes", []):
            t = n.get("type", "pre")
            used.add(t)
            cx = l["_xs"][n.get("id")]
            ch = (len(n["_lines"]) * (8.5 / 72) * 1.3 + 0.16)
            cy = yc
            col = COL.get(t, COL["generic"])
            if t == "this":
                fig.rbox(cx - n["_w"] / 2, cy - ch / 2, n["_w"], ch, col, "#333",
                         lw=0.8, rounding=0.1, z=2)
            else:
                fig.rbox(cx - n["_w"] / 2, cy - ch / 2, n["_w"], ch, _lighten(col),
                         "#666", ls="--", lw=0.9, rounding=0.1, z=2)
            fig.text(cx, cy, "\n".join(n["_lines"]), fs=8.5, ha="center",
                     va="center", color="#161616", linespacing=1.25, zorder=3)
            node_xy[(l.get("id"), n.get("id"))] = (cx, yc, n["_w"], ch)
    # 道内边（走泳道底部横轨，避免穿过同排节点）
    for l in lanes:
        lid = l.get("id")
        y_rail = lane_y[lid] - laneH / 2 + 0.16
        for e in l.get("edges", []):
            if (lid, e["u"]) not in node_xy or (lid, e["v"]) not in node_xy:
                continue
            xa, ya, wa, _ = node_xy[(lid, e["u"])]
            xb, yb, wb, _ = node_xy[(lid, e["v"])]
            if xb - xa > 0.5:
                _edge_arrow(fig, m, xa + wa / 2, y_rail, xb - wb / 2, y_rail,
                            label=(e.get("label") or None), fs=6.8, rad=0.0,
                            dashed=(e.get("style") == "dash"))
    # 跨族借用：编号虚线（只画相邻泳道；出/入点取两框相对一侧的框边，走框外，不穿框压字）
    lane_rank = {l.get("id"): i for i, l in enumerate(lanes)}
    for k, c in enumerate(d.get("cross", []), 1):
        try:
            fa, na = c["from"].split(".")
            fb, nb = c["to"].split(".")
        except ValueError:
            continue
        if (fa, na) not in node_xy or (fb, nb) not in node_xy:
            continue
        ia, ib = lane_rank.get(fa), lane_rank.get(fb)
        if ia is None or ib is None or abs(ia - ib) != 1:
            print(f"[ds_fig] 跨族边 {k} 跨 {abs((ia or 0)-(ib or 0))} 层泳道，"
                  f"只画相邻泳道 → 跳过不画：{c['from']} -> {c['to']}")
            continue
        xa, ya, wa, cha = node_xy[(fa, na)]
        xb, yb, wb, chb = node_xy[(fb, nb)]
        if yb < ya:                       # 对方节点在下 → 出源框下边、入目标框上边
            y0, y1 = ya - cha / 2, yb + chb / 2
        else:                             # 对方节点在上 → 出源框上边、入目标框下边
            y0, y1 = ya + cha / 2, yb - chb / 2
        _edge_arrow(fig, m, xa, y0, xb, y1, dashed=True, fs=7, idx=str(k),
                    rad=0.12)
    # 边注表（从最末泳道底边之下开始排，避免越界）
    lanes_bottom = y - (len(lanes) - 1) * (laneH + gapY) - laneH
    y = lanes_bottom - 0.08
    for ln in note_lines:
        fig.text(0.15, y, ln, fs=7.8, ha="left", va="top", color="#333333")
        y -= 0.165
    # 图例
    _legend(fig, m, used, legend_h)
    fig.text(W - 1.0, legend_h / 2, "实线=道内继承；虚线带编号=跨族借用（见上方边注表）",
             fs=7.5, ha="right", va="center", color="#7a7a7a")
    fig.save(out_png)
    if out_md:
        _write(out_md, _mermaid_family(d))


def _legend(fig, m, used, legend_h):
    x = 0.2
    y = legend_h / 2
    fig.ax.axhline(y, xmin=0, xmax=1, color="#e2e6ea", lw=0.8)
    for t in TYPES:
        if t in used:
            col = COL[t] if t == "this" else _lighten(COL[t])
            ls = "-" if t == "this" else "--"
            fig.rbox(x, y - 0.055, 0.17, 0.11, col, "#666", ls=ls, lw=0.7,
                     rounding=0.02)
            fig.text(x + 0.21, y, TYPE_CN[t], fs=7.5, va="center", color="#333")
            x += 0.21 + m.ext(TYPE_CN[t], 7.5)[0] + 0.28


# ------------------------------------------------------------------------------
# fig:"quad" 象限机会图（G3：空白度/机会空间 × 前沿活跃度）
# ------------------------------------------------------------------------------
QUAD_FILL = {"tl": "#edf3fb", "tr": "#fdf3dd", "bl": "#eef0f4", "br": "#efe9f7"}


def render_quad(d, out_png, out_md):
    """4 象限机会图：x=机会空间/空白度(右大)，y=前沿活跃度(上高)。
    JSON：
    { "fig":"quad", "title":.., "sub":..(空白度判据/阅读一句话),
      "x":..(横轴名), "y":..(纵轴名),
      "x_lo":..,"x_hi":..,"y_lo":..,"y_hi":..(轴端话),
      "quad":{"tl":..,"tr":..,"bl":..,"br":..}(四区话),
      "foot":..(图下一行读法),
      "points":[{id,label,x,y,note?}...] }
    坐标 0–1 仅示意；空白度判据写在 sub，避免『空白多=机会大』歧义。
    """
    m = Measure()
    title = d.get("title", "")
    sub = d.get("sub", "")
    sub_lines = m.wrap(sub, 8, 9.2) if sub else []
    W = 10.6
    ps = 5.9                       # 绘图方形边长（英寸）
    x0, y0 = 1.5, 1.5              # 绘图左下角（给纵轴名/横轴名留边）
    x1, y1 = x0 + ps, y0 + ps
    # 画布高：顶部留标题/说明
    title_h = 0.55
    sub_h = len(sub_lines) * 0.16 + 0.1
    legend_h = 0.4
    H = y1 + 0.3 + sub_h + title_h + legend_h + 0.1
    fig = Figure(W, H, m.fam)
    fig.text(W / 2, H - 0.2, title, fs=13, ha="center", va="center",
             fontweight="bold", color="#111")
    yy = H - title_h
    if sub_lines:
        for ln in sub_lines:
            fig.text(W / 2, yy + 0.02, ln, fs=8, ha="center", va="center",
                     color="#5a6b7a")
            yy -= 0.16
    # 四区底色
    for key, (qx, qy) in {"tl": (0.25, 0.75), "tr": (0.75, 0.75),
                          "bl": (0.25, 0.25), "br": (0.75, 0.25)}.items():
        px, py = x0 + qx * ps, y0 + qy * ps
        fig.ax.add_patch(fig.mp.Rectangle(
            (px - ps / 4, py - ps / 4), ps / 2, ps / 2,
            fc=QUAD_FILL[key], ec="none", zorder=0))
    # 中轴十字
    cx, cy = x0 + ps / 2, y0 + ps / 2
    fig.ax.plot([x0, x1], [cy, cy], color="#c9d2da", lw=0.7, ls="--", zorder=1)
    fig.ax.plot([cx, cx], [y0, y1], color="#c9d2da", lw=0.7, ls="--", zorder=1)
    # 区标签（四角轻灰）
    qlab = d.get("quad", {})
    for key, (qx, qy) in {"tl": (0.25, 0.75), "tr": (0.75, 0.75),
                          "bl": (0.25, 0.25), "br": (0.75, 0.25)}.items():
        if key not in qlab:
            continue
        fig.text(x0 + qx * ps, y0 + qy * ps, qlab[key], fs=8.5,
                 ha="center", va="center", color="#7a8794", style="italic",
                 zorder=2)
    # 轴箭头与轴名
    _axis_arrow(fig, (x0, y0), (x1, y0), (W, H))          # x 向右
    _axis_arrow(fig, (x0, y0), (x0, y1), (W, H))          # y 向上
    fig.text(W / 2, y0 - 0.14, d.get("x", ""), fs=9, ha="center",
             va="center", color="#20303f")
    fig.text(x0 - 0.14, y0 + ps / 2, d.get("y", ""), fs=9, ha="center",
             va="center", color="#20303f", rotation=90)
    # 轴端话（提示两极端含义）
    if d.get("x_hi"):
        fig.text(x1, y0 - 0.42, d["x_hi"], fs=7.2, ha="right", va="center",
                 color="#8894a0")
    if d.get("x_lo"):
        fig.text(x0, y0 - 0.42, d["x_lo"], fs=7.2, ha="left", va="center",
                 color="#8894a0")
    if d.get("y_hi"):
        fig.text(x0 - 0.05, y1, d["y_hi"], fs=7.2, ha="right", va="center",
                 color="#8894a0", rotation=0)
    if d.get("y_lo"):
        fig.text(x0 - 0.05, y0, d["y_lo"], fs=7.2, ha="right", va="center",
                 color="#8894a0")
    # 散点
    for p in d.get("points", []):
        vx = min(max(float(p.get("x", 0.5)), 0.0), 1.0)
        vy = min(max(float(p.get("y", 0.5)), 0.0), 1.0)
        px, py = x0 + vx * ps, y0 + vy * ps
        fig.ax.add_patch(fig.mp.Circle(
            (px, py), 0.075, fc="#3a6ea5", ec="white", lw=1.2, zorder=6))
        fig.text(px, py, str(p.get("id", "")), fs=6.5, ha="center",
                 va="center", color="white", fontweight="bold", zorder=7)
        lab = p.get("label", "")
        lw_, lh = m.ext(lab, 7.5)[0], m.ext(lab, 7.5)[1]
        # 放点右侧；靠右边界就放左侧；靠上界就下移一点
        lx = px + 0.12 if vx < 0.86 else px - lw_ - 0.12
        lx = max(x0 + 0.05, min(lx, x1 - lw_ - 0.05))
        ly = py + 0.14 if vy < 0.9 else py - 0.1
        fig.text(lx, ly, lab, fs=7.5, ha="left", va="bottom", color="#222",
                 zorder=6)
    # 图例/尾注
    _quad_foot(fig, m, d, legend_h)
    fig.save(out_png)
    # quad 无 Mermaid（同 scatter2d，语义需图片本身）


def _axis_arrow(fig, a, b, canvas):
    from matplotlib.patches import FancyArrowPatch
    col = "#6b7a89"
    arr = FancyArrowPatch(a, b, arrowstyle="-|>", mutation_scale=11,
                          color=col, linewidth=1.2, shrinkA=0, shrinkB=0,
                          zorder=3)
    fig.ax.add_patch(arr)


def _quad_foot(fig, m, d, legend_h):
    y = legend_h / 2
    fig.ax.axhline(y, xmin=0, xmax=1, color="#e2e6ea", lw=0.8)
    txt = d.get("foot", "")
    if txt:
        fig.text(0.2, y, txt, fs=7.2, ha="left", va="center", color="#6b7a89")
    fig.text(fig.ax.get_xlim()[1] - 0.3, y, "坐标仅供示意（0–1），非精确测量",
             fs=7.2, ha="right", va="center", color="#a0aab5")


# ------------------------------------------------------------------------------
# fig:"audit" 生态盘点矩阵表图（G4：谱系 × 评测协议 × 复杂度/质量）
# ------------------------------------------------------------------------------
def render_audit(d, out_png, out_md):
    """盘点矩阵表图：行=方法（按谱系分带），列=评测协议/复杂度/质量等维度。
    JSON：
    { "fig":"audit","title":..,"sub":..(可选读法),
      "col_groups":[{label,cols:[i..j]}..],   # 列头分组（可选）
      "cols":[{label,key,w?}..],              # 各列头（key 用于取 cells）
      "bands":[{name,type?,rows:[{name,type,note?,cells:{key:text}}]}] }
    自动按文本量排版；type 给行身份色（this=库内金实）。"""
    m = Measure()
    title = d.get("title", "")
    sub = d.get("sub", "")
    sub_lines = m.wrap(sub, 8, 10.0) if sub else []
    cols = d.get("cols", [])
    ckeys = [c.get("key", c.get("label", "")) for c in cols]
    cwid = []
    for c in cols:
        cap = float(c.get("w", 2.1))
        hl = m.wrap(c.get("label", ""), 7.6, cap)
        cwid.append(min(max(m.width(hl, 7.6) + 0.14, 1.0), cap))
    # 预先 wrap 所有 cells，存行长（第 0 列=方法名，粗体）
    bands = d.get("bands", [])
    padx = 0.14
    for b in bands:
        for r in b.get("rows", []):
            cells = r.get("cells", {})
            r["_lines"] = {}
            for ci, k in enumerate(ckeys):
                txt = str(cells.get(k, ""))
                if not txt:
                    r["_lines"][k] = []
                    continue
                fs_ = 7.8 if ci == 0 else 7.4
                wt_ = "bold" if ci == 0 else "normal"
                r["_lines"][k] = m.wrap(txt, fs_, cwid[ci] - padx, wt_)
    # 计算几何尺寸
    x0 = 0.3
    colw_sum = sum(cwid) + padx * (len(cols) - 1)
    W = x0 + colw_sum + 0.35
    title_h = 0.55
    sub_h = len(sub_lines) * 0.16 + 0.05
    group_h = 0.24 if d.get("col_groups") else 0.0
    head_h = 0.37                        # 列头余量
    notes = m.wrap(d.get("note", ""), 7.4, W - x0 - 0.2) if d.get("note") else []
    note_h = len(notes) * 0.15 + 0.05
    legend_h = 0.34
    BAND_GAP = 0.12                      # band 首尾空隙
    # 先统一量尺寸：每个 band 块高 = 名带 nh + 0.03 空隙 + rows 高和 + BAND_GAP
    bnd = []
    for b in bands:
        name_lines = m.wrap(b.get("name", ""), 8.2, W - x0 - 0.2)
        n_h = len(name_lines) * 0.155 + 0.16
        rows_h = []
        for r in b.get("rows", []):
            nl = max([len(r["_lines"].get(k, [])) for k in ckeys] or [1])
            rows_h.append(max(nl, 1) * 0.155 + 0.12)
        bnd.append({"nl": name_lines, "nh": n_h, "rh": rows_h})
    head_top = title_h + sub_h + group_h + head_h
    body_h = sum(x["nh"] + 0.03 + sum(x["rh"]) + BAND_GAP for x in bnd)
    H = head_top + body_h + note_h + legend_h + 0.15
    fig = Figure(W, H, m.fam)
    fig.text(W / 2, H - 0.18, title, fs=12, ha="center", va="center",
             fontweight="bold", color="#111")
    used = set()
    y = H - title_h - 0.1
    if sub_lines:
        for ln in sub_lines:
            fig.text(W / 2, y, ln, fs=8, ha="center", va="center",
                     color="#5a6b7a")
            y -= 0.16
        y -= 0.05
    # 列分组带
    col_x = _col_offsets(x0, cwid, padx)
    colc = _col_offsets(x0 + 0.02, cwid, padx)   # 文本左对齐基准
    if d.get("col_groups"):
        for grp in d["col_groups"]:
            i0, i1 = grp["cols"][0], grp["cols"][-1]
            lx = (col_x[i0] + col_x[i1 + 1]) / 2
            fig.text(lx, y - group_h / 2, grp.get("label", ""), fs=7.6,
                     ha="center", va="center", fontweight="bold", color="#39474f")
        y -= group_h
    # 列头
    for ci, c in enumerate(cols):
        lx = (col_x[ci] + col_x[ci + 1]) / 2
        fig.text(lx, y - head_h / 2, c.get("label", ""), fs=7.6, ha="center",
                 va="center", fontweight="bold", color="#39474f")
    y -= head_h
    # bands
    for bi, b in enumerate(bands):
        blk = bnd[bi]
        top = y
        nh = blk["nh"]
        # band 名带（居中于名带）
        fig.ax.add_patch(fig.mp.Rectangle((x0, top - nh), W - x0 - 0.3, nh,
                         fc="#eef2f6", ec="#d5dbe3", lw=0.5, zorder=0))
        for j, ln in enumerate(blk["nl"]):
            fig.text(x0 + 0.06, top - 0.11 - j * 0.155, ln, fs=8.2, ha="left",
                     va="center", fontweight="bold", color="#24313c")
        y = top - nh - 0.03
        fig.ax.axhline(y, xmin=0, xmax=1, color="#e8edf2", lw=0.5)
        for ri, r in enumerate(b.get("rows", [])):
            t = r.get("type", "pre")
            used.add(t)
            rh = blk["rh"][ri]
            cy = y - rh / 2
            col = COL.get(t, COL["generic"])
            if t == "this":
                fig.rbox(x0 - 0.02, y - rh, 0.07, rh, col, "#333", lw=0.6,
                         rounding=0.02, z=3)
            else:
                fig.rbox(x0 - 0.02, y - rh, 0.07, rh, _lighten(col), "#999",
                         ls="--", lw=0.5, rounding=0.02, z=3)
            for ci, k in enumerate(ckeys):
                xcell = colc[ci]
                lines = r["_lines"].get(k, [])
                if not lines:
                    continue
                fs_ = 7.8 if ci == 0 else 7.4
                wt_ = "bold" if ci == 0 else "normal"
                ytop = cy + (len(lines) - 1) * 0.155 / 2
                for j, ln in enumerate(lines):
                    fig.text(xcell + 0.02, ytop - j * 0.155, ln, fs=fs_,
                             ha="left", va="center", fontweight=wt_, color="#222")
            y -= rh
            fig.ax.axhline(y, xmin=0, xmax=1, color="#e8edf2", lw=0.5)
        y -= BAND_GAP
    # 底部注释
    if notes:
        for ln in notes:
            fig.text(x0, y + 0.02, ln, fs=7.4, ha="left", va="center",
                     color="#7a8794")
            y -= 0.15
    _legend(fig, m, used, legend_h)
    fig.text(W - 0.3, legend_h / 2, d.get("legend_tail", "行=方法 · 分带=谱系"),
             fs=7.2, ha="right", va="center", color="#7a8794")
    fig.save(out_png)
    # audit 无 Mermaid（矩阵语义在正文）


def _col_offsets(x0, cwid, padx):
    out = [x0]
    for w in cwid:
        out.append(out[-1] + w + padx)
    return out


# ------------------------------------------------------------------------------
# fig:"terrain" 学科地形图（学科级：细分方向 × 成立度/成熟度/活跃度/空白度/样本/边界）
# ------------------------------------------------------------------------------
LEVELS = ["低", "中", "高"]
LEVEL_F = {"低": 0.70, "中": 0.38, "高": 0.05}   # 与白底混合比：越小越深
LEVEL_R = {"低": 0.33, "中": 0.66, "高": 1.00}   # 实心条占格宽比
STANDING_COL = {"成立": "#3f8f52", "部分成立": "#c98a1e",
                "部分成立（边界模糊）": "#c98a1e", "存疑": "#b8433a"}
# 图上只写短词：书面上可写「部分成立（边界模糊）」，进图压成「部分成立」（判定仍以正文为准）
STANDING_ALIAS = {"部分成立（边界模糊）": "部分成立", "部分成立(边界模糊)": "部分成立"}


def _lvl_fill(hue, level):
    return _lighten(hue, LEVEL_F.get(str(level).strip(), 0.38))


def render_terrain(d, out_png, out_md):
    """学科地形图：行=细分方向（按「库内已建目录 / 论断新增候选」分带），列=成立度 /
    成熟度 / 活跃度 / 空白度 / 库内样本 / 边界一句话；色深=该维取值高。
    JSON：
    { "fig":"terrain","title":..,"sub":..(口径一句),
      "cols":[{"label":..,"key":..,"w"?:2.4,"kind"?:text|level|standing,"hue"?:level 列底色}..],
      "bands":[{"name":..,"type"?:..,"rows":[{"name":..,"type"?:..,"standing":"成立|部分成立|存疑",
               "maturity"/"activity"/"blank":{"level":"低|中|高","why":..},
               <文本列 key>: "字串" 或 {"text":..,"color":..,"bold":..}}]}],
      "conclusion":"学科级一句话论断","note":..,"legend_tail":.. }
    样本不足的行必须在样本列写明「样本不足·推断」（纪律见 references/discipline-method.md）。"""
    m = Measure()
    title = d.get("title", "")
    sub = d.get("sub", "")
    sub_lines = m.wrap(sub, 8, 12.0) if sub else []
    cols = d.get("cols", [])
    ckeys = [c.get("key", c.get("label", "")) for c in cols]
    padx = 0.14
    cwid = []
    for c in cols:
        cap = float(c.get("w", 2.4))
        hl = m.wrap(c.get("label", ""), 7.6, cap)
        cwid.append(min(max(m.width(hl, 7.6) + 0.14, 1.0), cap))
    # 逐格排版计划（kind: text/level/standing 决定高度与画法）
    bands = d.get("bands", [])
    for b in bands:
        for r in b.get("rows", []):
            plan, hmax = {}, 0.0
            for ci, c in enumerate(cols):
                k = ckeys[ci]
                kind = c.get("kind", "text")
                val = r.get(k, "")
                if kind == "level":
                    val = val if isinstance(val, dict) else {}
                    why = m.wrap(str(val.get("why", "")), 6.8, cwid[ci] - padx)
                    p = {"kind": "level", "level": str(val.get("level", "")).strip(),
                         "why": why, "hue": c.get("hue", "#5b9bd5"),
                         "h": (0.22 + 0.03 + len(why) * 0.14 + 0.02) if why else 0.28}
                else:
                    if isinstance(val, dict):
                        txt = str(val.get("text", ""))
                        col_ = val.get("color", "#222")
                        bold_ = bool(val.get("bold", ci == 0))
                    else:
                        txt = str(val)
                        col_ = "#222"
                        bold_ = (ci == 0)
                        if kind == "standing":
                            col_ = STANDING_COL.get(txt.strip(), "#5a6b7a")
                            bold_ = True
                    fs_ = 7.8 if ci == 0 else 7.4
                    if kind == "standing":
                        txt = STANDING_ALIAS.get(txt.strip(), txt.strip())
                        while txt and fs_ > 6.0 and m.ext(txt, fs_)[0] > cwid[ci] - 0.08:
                            fs_ -= 0.2
                        lines = [txt] if txt else []
                    else:
                        lines = m.wrap(txt, fs_, cwid[ci] - padx) if txt else []
                    chip = (kind == "standing") and bool(lines)
                    p = {"kind": "standing" if chip else "text", "lines": lines,
                         "color": col_, "bold": bold_, "fs": fs_,
                         "h": (len(lines) * 0.155 + (0.16 if chip else 0.08)) if lines else 0.0}
                plan[k] = p
                hmax = max(hmax, p["h"])
            r["_plan"] = plan
            r["_h"] = max(hmax, 0.34)
    # 几何
    x0 = 0.3
    colw_sum = sum(cwid) + padx * (len(cols) - 1)
    W = x0 + colw_sum + 0.35
    col_x = _col_offsets(x0, cwid, padx)
    colc = _col_offsets(x0 + 0.02, cwid, padx)      # 文本左对齐基准
    title_h = 0.55
    sub_h = len(sub_lines) * 0.16 + 0.05
    head_h = 0.37
    notes = m.wrap(d.get("note", ""), 7.4, W - x0 - 0.2) if d.get("note") else []
    note_h = len(notes) * 0.15 + 0.05
    legend_h = 0.64
    BAND_GAP = 0.14
    ctext_x = colc[1] if len(colc) > 1 else colc[0]
    clines = m.wrap(d.get("conclusion", ""), 7.8, W - ctext_x - 0.35) if d.get("conclusion") else []
    concl_h = (len(clines) * 0.16 + 0.20) if clines else 0.0
    bnd = []
    for b in bands:
        nl = m.wrap(b.get("name", ""), 8.2, W - x0 - 0.2)
        bnd.append({"nl": nl, "nh": len(nl) * 0.155 + 0.16})
    body_h = sum(x["nh"] + 0.03 + sum(r["_h"] for r in b.get("rows", [])) + BAND_GAP
                 for x, b in zip(bnd, bands))
    H = title_h + sub_h + head_h + body_h + concl_h + note_h + legend_h + 0.15
    fig = Figure(W, H, m.fam)
    fig.text(W / 2, H - 0.18, title, fs=12.5, ha="center", va="center",
             fontweight="bold", color="#111")
    y = H - title_h - 0.1
    if sub_lines:
        for ln in sub_lines:
            fig.text(W / 2, y, ln, fs=8, ha="center", va="center", color="#5a6b7a")
            y -= 0.16
        y -= 0.05
    for ci, c in enumerate(cols):
        lx = (col_x[ci] + col_x[ci + 1]) / 2
        fig.text(lx, y - head_h / 2, c.get("label", ""), fs=7.6, ha="center",
                 va="center", fontweight="bold", color="#39474f")
    y -= head_h
    # 分带 + 行
    for bi, b in enumerate(bands):
        blk = bnd[bi]
        top, nh = y, blk["nh"]
        fig.ax.add_patch(fig.mp.Rectangle((x0, top - nh), W - x0 - 0.3, nh, fc="#eef2f6",
                                          ec="#d5dbe3", lw=0.5, zorder=0))
        for j, ln in enumerate(blk["nl"]):
            fig.text(x0 + 0.06, top - 0.11 - j * 0.155, ln, fs=8.2, ha="left",
                     va="center", fontweight="bold", color="#24313c")
        y = top - nh - 0.03
        fig.ax.axhline(y, xmin=0, xmax=1, color="#e8edf2", lw=0.5)
        for r in b.get("rows", []):
            t = r.get("type", b.get("type", "pre"))
            rh = r["_h"]
            cy = y - rh / 2
            chip_col = COL.get(t, COL["generic"])
            if t == "this":
                fig.rbox(x0 - 0.02, y - rh, 0.07, rh, chip_col, "#333", lw=0.6,
                         rounding=0.02, z=3)
            else:
                fig.rbox(x0 - 0.02, y - rh, 0.07, rh, _lighten(chip_col), "#999",
                         ls="--", lw=0.5, rounding=0.02, z=3)
            for ci, c in enumerate(cols):
                p = r["_plan"][ckeys[ci]]
                if p["kind"] == "level":
                    lv = p["level"]
                    bw = cwid[ci] - padx
                    by = y - 0.03 - 0.17
                    fig.ax.add_patch(fig.mp.Rectangle(
                        (col_x[ci], by), bw, 0.17, fc=_lighten(p["hue"], 0.86),
                        ec="#d5dbe3", lw=0.4, zorder=1))
                    if lv in LEVEL_R:
                        fgw = bw * LEVEL_R[lv]
                        fig.ax.add_patch(fig.mp.Rectangle(
                            (col_x[ci], by), fgw, 0.17, fc=_lvl_fill(p["hue"], lv),
                            ec="none", zorder=2))
                        fig.text(col_x[ci] + fgw / 2, by + 0.085, lv, fs=7.2,
                                 ha="center", va="center", zorder=3,
                                 color="#ffffff" if lv == "高" else "#24313c")
                    else:
                        fig.text(col_x[ci] + 0.05, by + 0.085, lv or "不详", fs=7.2,
                                 ha="left", va="center", color="#8894a0", zorder=3)
                    for j, ln in enumerate(p["why"]):
                        fig.text(colc[ci], by - 0.05 - j * 0.14, ln, fs=6.8,
                                 ha="left", va="center", color="#5a6b7a")
                elif p["lines"]:
                    lines = p["lines"]
                    ytop = cy + (len(lines) - 1) * 0.155 / 2
                    if p["kind"] == "standing":
                        sw = m.width(lines, p["fs"]) + 0.16
                        sh = len(lines) * 0.155 + 0.10
                        fig.rbox(colc[ci] - 0.02, ytop - (len(lines) - 1) * 0.155 / 2 - sh / 2,
                                 sw, sh, _lighten(p["color"], 0.82), p["color"],
                                 lw=0.7, rounding=0.04, z=2)
                        fig.text(colc[ci] + 0.06, ytop, lines[0], fs=p["fs"], ha="left",
                                 va="center", fontweight="bold", color=p["color"], zorder=3)
                    else:
                        for j, ln in enumerate(lines):
                            fig.text(colc[ci], ytop - j * 0.155, ln, fs=p["fs"],
                                     ha="left", va="center", fontweight=p["bold"],
                                     color=p["color"])
            y -= rh
            fig.ax.axhline(y, xmin=0, xmax=1, color="#e8edf2", lw=0.5)
        y -= BAND_GAP
    # 学科级结论条
    if clines:
        ch = concl_h - 0.06
        fig.ax.add_patch(fig.mp.Rectangle((x0, y - ch), W - x0 - 0.3, ch, fc="#f6f2e6",
                                          ec="#e2d9bd", lw=0.6, zorder=0))
        fig.text(x0 + 0.06, y - 0.10, "学科级结论", fs=8.2, ha="left", va="center",
                 fontweight="bold", color="#6b5a1e")
        for j, ln in enumerate(clines):
            fig.text(ctext_x, y - 0.11 - j * 0.16, ln, fs=7.8, ha="left",
                     va="center", fontweight="bold", color="#3a3222")
        y -= ch + 0.06
    # 注释 + 图例
    if notes:
        for ln in notes:
            fig.text(x0, y + 0.02, ln, fs=7.4, ha="left", va="center", color="#7a8794")
            y -= 0.15
    ly1, ly2 = legend_h * 0.74, legend_h * 0.26      # 上排=分级色阶；下排=成立度 + 尾注
    fig.ax.axhline(legend_h, xmin=0, xmax=1, color="#e2e6ea", lw=0.8)
    x = 0.2
    for c in cols:
        if c.get("kind") != "level":
            continue
        hue, lab = c.get("hue", "#5b9bd5"), c.get("label", "")
        fig.text(x, ly1, lab + "：", fs=7.2, va="center", color="#333")
        x += m.ext(lab + "：", 7.2)[0]
        for lv in LEVELS:
            fig.rbox(x, ly1 - 0.05, 0.15, 0.10, _lvl_fill(hue, lv), "#999",
                     lw=0.4, rounding=0.01)
            fig.text(x + 0.075, ly1 - 0.115, lv, fs=6.2, ha="center", va="center",
                     color="#8894a0")
            x += 0.19
        x += 0.26
    x = 0.2
    for c in cols:
        if c.get("kind") != "standing":
            continue
        lab = c.get("label", "")
        fig.text(x, ly2, lab + "：", fs=7.2, va="center", color="#333")
        x += m.ext(lab + "：", 7.2)[0]
        for st in ("成立", "部分成立", "存疑"):
            fig.rbox(x, ly2 - 0.05, 0.15, 0.10, _lighten(STANDING_COL[st], 0.82),
                     STANDING_COL[st], lw=0.6, rounding=0.01)
            fig.text(x + 0.19, ly2, st, fs=7.2, va="center", color="#333")
            x += 0.23 + m.ext(st, 7.2)[0] + 0.16
        break
    fig.text(W - 0.3, ly2, d.get("legend_tail", "色深=该维取值高 · 行分带=库内已建目录 / 论断新增候选"),
             fs=7.2, ha="right", va="center", color="#7a8794")
    fig.save(out_png)
    # terrain 无 Mermaid（矩阵+分级语义在正文）


def _write(path, txt):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(txt + "\n")
    print(f"[Mermaid] {path}")


# ------------------------------------------------------------------------------
# Mermaid 源码（留档/在线编辑用，PNG 仍为准）
# ------------------------------------------------------------------------------
def _mermaid_stage(d):
    lines = ["flowchart LR", f"  %% {d.get('title','')} · ds_fig stage 布局"]
    for s in d.get("stages", []):
        sid = s.get("id", "s")
        name = s.get("name", "").replace('"', " ")
        lines.append(f'  subgraph {sid}["{name} · {s.get("period","")}"]')
        for wi, wk in enumerate(s.get("works", [])):
            nid = f"{sid}_w{wi}"
            lab = wk.get("label", "")
            if wk.get("year"):
                lab += "<br/>(" + str(wk.get("year")) + ")"
            lines.append(f'    {nid}["{lab}"]:::{wk.get("type","pre")}')
        lines.append("  end")
    for e in d.get("stage_edges", []):
        lines.append(f'  {e.get("a")} -->|{e.get("label","")}| {e.get("b")}')
    return "\n".join(lines) + "\n" + _classdefs()


def _mermaid_family(d):
    lines = ["flowchart LR", f"  %% {d.get('title','')} · ds_fig family 泳道布局"]
    for l in d.get("lanes", []):
        lid = l.get("id", "lane")
        name = l.get("name", "").replace('"', " ")
        lines.append(f'  subgraph {lid}["{name}"]')
        for n in l.get("nodes", []):
            nid = lid + "_" + str(n.get("id"))
            lab = n.get("label", "").replace("\n", "<br/>")
            lines.append(f'    {nid}["{lab}"]:::{n.get("type","pre")}')
        lines.append("  end")
    for l in d.get("lanes", []):
        lid = l.get("id", "lane")
        for e in l.get("edges", []):
            lines.append(f'  {lid}_{e["u"]} -->|{e.get("label","")}| {lid}_{e["v"]}')
    for k, c in enumerate(d.get("cross", []), 1):
        fa, na = c["from"].split(".")
        fb, nb = c["to"].split(".")
        lines.append(f'  {fa}_{na} -.->|"{k} {c.get("label","")}"| {fb}_{nb}')
    return "\n".join(lines) + "\n" + _classdefs()


def _classdefs():
    out = []
    for t in TYPES:
        out.append(f'  classDef {t} fill:{COL[t]},stroke:#333333,stroke-width:0.6;')
    return "\n".join(out)


def main():
    global QA_ON
    utf8()
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("json")
    ap.add_argument("--png", help="输出 PNG 路径")
    ap.add_argument("--mermaid", default="-", help="输出 Mermaid 路径；- 表示不出")
    ap.add_argument("--qa", action="store_true",
                    help="渲染后做程序化几何自检（文字出画布/两两压叠）并以退出码判定")
    a = ap.parse_args()
    QA_ON = a.qa
    with open(a.json, encoding="utf-8") as f:
        d = json.load(f)
    gtype = d.get("fig", d.get("type", "lineage"))
    png = a.png or os.path.splitext(a.json)[0] + ".png"
    md = None
    if a.mermaid and a.mermaid != "-":
        md = a.mermaid
    elif a.mermaid is None:
        md = os.path.splitext(a.json)[0] + ".mermaid"
    if gtype == "stage":
        render_stage(d, png, md)
    elif gtype == "family":
        render_family(d, png, md)
    elif gtype == "quad":
        render_quad(d, png, None)
    elif gtype == "audit":
        render_audit(d, png, None)
    elif gtype == "terrain":
        render_terrain(d, png, None)
    else:
        raise SystemExit(
            f"[ds_fig] 只支持 fig: stage / family / quad / audit / terrain，收到 {gtype!r}")
    if a.qa:
        if QA_PROBLEMS:
            print(f"[QA] 几何自检：{len(QA_PROBLEMS)} 处问题（见上，退出码 1）")
            sys.exit(1)
        print("[QA] 几何 QA 通过：无出界 / 无压叠。")


if __name__ == "__main__":
    main()
