#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ds_render.py — 校验综述图 JSON(schema + 无 emoji) → 按图型分发渲染 PNG/Mermaid

direction-survey v3.0 图型分两路：
  * fig:"stage"/"family"/"quad"/"audit"（方向级）/ "terrain"（学科级）
                                        → 调用本 skill 自带 scripts/ds_fig.py（自扩展渲染器）
  * lineage/flow 或 scatter2d           → 沿用 paper-analyzer scripts/pa_fig.py（默认/reuse 图）

用法:
    python .claude/skills/direction-survey/scripts/ds_render.py "<图>.json" \
        --png "<方向综述>/assets/<图名>.png" --mermaid "<方向综述>/assets/<图名>.mermaid" [--qa]
    (--png - 只出 Mermaid；--mermaid - 只出 PNG；--qa 透传给 ds_fig 做程序化几何自检，有问题退出码非 0)

红线：title/节点/边/stage/family 的 label 含 emoji 或易缺字形符号（U+2600–27BF / U+1F000–1FAFF /
      变体选择符）→ 直接报错，不渲染。
"""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def risk_chars(s: str):
    bad = set()
    for ch in str(s):
        cp = ord(ch)
        if 0x2600 <= cp <= 0x27BF or 0x1F000 <= cp <= 0x1FAFF or 0xFE00 <= cp <= 0xFE0F:
            bad.add(ch)
    return sorted(bad)


def walk_strings(obj, out):
    """递归收集 dict/list 里所有字符串（含嵌套），供 emoji 全图扫描。"""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, str):
                out.append((k, v))
            else:
                walk_strings(v, out)
    elif isinstance(obj, list):
        for v in obj:
            walk_strings(v, out)


def validate_fig(fig: dict):
    gtype = fig.get("fig", fig.get("type", "lineage"))
    if "title" not in fig:
        raise SystemExit("[ds_render] JSON 缺 title")

    hits = {}
    collected = []
    walk_strings(fig, collected)
    for k, s in collected:
        for c in risk_chars(s):
            hits.setdefault(f"field {k}", []).append(c)

    def need_node(n, where):
        for k in ("label", "type"):
            if k not in n:
                raise SystemExit(f"[ds_render] {where} 节点缺 {k}: {n}")

    if gtype == "stage":
        stages = fig.get("stages")
        if not stages:
            raise SystemExit("[ds_render] fig:stage 缺 stages[]")
        for s in stages:
            if "id" not in s or "name" not in s:
                raise SystemExit(f"[ds_render] stages[] 每阶段需 id+name: {s}")
            for w in s.get("works", []):
                need_node(w, "stage.works")
        for e in fig.get("stage_edges", []):
            if "a" not in e or "b" not in e:
                raise SystemExit(f"[ds_render] stage_edges[] 需 a/b: {e}")
    elif gtype == "family":
        lanes = fig.get("lanes")
        if not lanes:
            raise SystemExit("[ds_render] fig:family 缺 lanes[]")
        for l in lanes:
            if "id" not in l or "name" not in l:
                raise SystemExit(f"[ds_render] lanes[] 每道需 id+name: {l}")
            for n in l.get("nodes", []):
                need_node(n, "lane.nodes")
        for c in fig.get("cross", []):
            for k in ("from", "to", "label"):
                if k not in c:
                    raise SystemExit(f"[ds_render] cross[] 需 {k}: {c}")
            for f in (c["from"], c["to"]):
                if "." not in f or len(f.split(".")) != 2:
                    raise SystemExit(f"[ds_render] cross.from/to 需 '道id.节点id'：{f}")
    elif "nodes" in fig or gtype in ("lineage", "flow"):
        for n in fig.get("nodes", []):
            need_node(n, "nodes")
        for e in fig.get("edges", []):
            if "u" not in e or "v" not in e:
                raise SystemExit(f"[ds_render] edges[] 缺 u/v: {e}")
            if e.get("style", "solid") not in ("solid", "dash"):
                raise SystemExit(f"[ds_render] edges[] style 只能 solid/dash（pa_fig 判定字面量 dash）：{e}")
    elif "points" in fig or gtype == "scatter2d":
        for p in fig.get("points", []):
            for k in ("id", "label", "x", "y"):
                if k not in p:
                    raise SystemExit(f"[ds_render] points[] 缺 {k}: {p}")
    elif gtype == "quad":
        # 象限图：points 每个要 id/label/x/y；quad 区话可选但若给须 4 键
        pts = fig.get("points")
        if not pts:
            raise SystemExit("[ds_render] fig:quad 缺 points[]")
        for p in pts:
            for k in ("id", "label", "x", "y"):
                if k not in p:
                    raise SystemExit(f"[ds_render] quad points[] 缺 {k}: {p}")
            try:
                float(p["x"]), float(p["y"])
            except ValueError:
                raise SystemExit(f"[ds_render] quad points[] x/y 须为数字: {p}")
        q = fig.get("quad", {})
        if q and not set(q) >= {"tl", "tr", "bl", "br"}:
            raise SystemExit("[ds_render] quad{} 若给须含 tl/tr/bl/br 四区话")
        for key in ("x", "y"):
            if not fig.get(key):
                raise SystemExit(f"[ds_render] fig:quad 缺轴名 {key}")
    elif gtype == "audit":
        cols = fig.get("cols")
        bands = fig.get("bands")
        if not cols:
            raise SystemExit("[ds_render] fig:audit 缺 cols[]")
        if not bands:
            raise SystemExit("[ds_render] fig:audit 缺 bands[]")
        keys = [c.get("key", c.get("label")) for c in cols]
        if any(not k for k in keys):
            raise SystemExit("[ds_render] fig:audit cols[] 每列需 label（或 key）")
        for b in bands:
            if "name" not in b:
                raise SystemExit(f"[ds_render] audit bands[] 每带需 name: {b}")
            for r in b.get("rows", []):
                if "type" not in r:
                    raise SystemExit(f"[ds_render] audit rows[] 每行需 type: {r}")
                if not isinstance(r.get("cells"), dict):
                    raise SystemExit(f"[ds_render] audit rows[] 每行需 cells{{}}: {r}")
    elif gtype == "terrain":
        cols = fig.get("cols")
        bands = fig.get("bands")
        if not cols:
            raise SystemExit("[ds_render] fig:terrain 缺 cols[]")
        if not bands:
            raise SystemExit("[ds_render] fig:terrain 缺 bands[]")
        keys = [c.get("key", c.get("label")) for c in cols]
        if any(not k for k in keys):
            raise SystemExit("[ds_render] fig:terrain cols[] 每列需 label（或 key）")
        for c in cols:
            if c.get("kind", "text") not in ("text", "level", "standing"):
                raise SystemExit(
                    f"[ds_render] terrain cols[] kind 只能 text/level/standing: {c}")
        for b in bands:
            if "name" not in b:
                raise SystemExit(f"[ds_render] terrain bands[] 每带需 name: {b}")
            for r in b.get("rows", []):
                if not r.get("name"):
                    raise SystemExit(f"[ds_render] terrain rows[] 每行需 name: {r}")
                for ci, c in enumerate(cols):
                    if c.get("kind") != "level":
                        continue
                    v = r.get(keys[ci])
                    if v is None:
                        raise SystemExit(
                            f"[ds_render] terrain 行 {r['name']!r} 缺 level 列 {keys[ci]}")
                    if not isinstance(v, dict) or "level" not in v:
                        raise SystemExit(
                            f"[ds_render] terrain level 列需 {{level,why}}: 行 {r['name']!r} {keys[ci]}")
                    if str(v["level"]).strip() not in ("低", "中", "高", "不详"):
                        raise SystemExit(
                            f"[ds_render] terrain level 只能 低/中/高/不详: 行 {r['name']!r} {v['level']!r}")
        if not fig.get("conclusion"):
            raise SystemExit("[ds_render] fig:terrain 缺 conclusion（学科级一句话论断）")
    else:
        raise SystemExit(
            f"[ds_render] 不认的图型 {gtype!r}"
            "（支持 stage/family/quad/audit/terrain/lineage/scatter2d）")

    if hits:
        lines = "\n".join(f"    {loc}: {c}" for loc, cs in hits.items() for c in cs)
        raise SystemExit(f"[ds_render] 发现图内 emoji/易缺字形符号（matplotlib CJK 缺字形 → 豆腐块）:\n{lines}")


def run(cmd):
    env = dict(os.environ)  # 继承原环境：matplotlib 靠 USERPROFILE/HOME 定位 config
    env["PYTHONUTF8"] = "1"
    r = subprocess.run(cmd, env=env)
    if r.returncode != 0:
        raise SystemExit(f"[ds_render] 渲染失败 (rc={r.returncode})")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("json", help="图描述 JSON")
    ap.add_argument("--png", default="-", help="输出 PNG 路径；- 表示不出")
    ap.add_argument("--mermaid", default="-", help="输出 Mermaid 路径；- 表示不出")
    ap.add_argument("--qa", action="store_true",
                    help="透传 ds_fig --qa：渲染后程序化几何自检，有问题退出码非 0（完成线 gate 用）")
    ap.add_argument("--pa-fig", default=".claude/skills/paper-analyzer/scripts/pa_fig.py",
                    help="paper-analyzer pa_fig.py 路径（仅 lineage/scatter 用）")
    args = ap.parse_args()

    try:
        fig = json.loads(Path(args.json).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise SystemExit(f"[ds_render] 读取/解析 JSON 失败: {e}")

    validate_fig(fig)
    gtype = fig.get("fig", fig.get("type", "lineage"))

    js = str(Path(args.json).resolve())
    if gtype in ("stage", "family", "quad", "audit", "terrain"):
        renderer = str(HERE / "ds_fig.py")
        if not Path(renderer).is_file():
            raise SystemExit(f"[ds_render] 找不到自带 ds_fig.py: {renderer}")
        cmd = [sys.executable, renderer, js]
        if args.png != "-":
            cmd += ["--png", args.png]
        if args.qa:
            cmd += ["--qa"]
        cmd += ["--mermaid"] + (["-"] if args.mermaid == "-" else [args.mermaid])
        run(cmd)
    else:
        pa_fig = Path(args.pa_fig)
        if not pa_fig.is_file():
            raise SystemExit(f"[ds_render] 找不到 pa_fig.py: {pa_fig}（检查 --pa-fig / 是否在仓库根执行）")
        cmd = [sys.executable, str(pa_fig), js]
        if args.png != "-":
            cmd += ["--png", args.png]
        if args.mermaid != "-":
            cmd += ["--mermaid", args.mermaid]
        run(cmd)
    print("[ds_render] 渲染完成 OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
