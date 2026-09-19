#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ds_scan.py — 扫描方向/学科目录 → 档案.json 草稿（direction-survey 步骤 0/1 的自动化一半）

用法:
    # 方向级（缺省，v2.1 起不变）
    python .claude/skills/direction-survey/scripts/ds_scan.py "<方向目录>" [--out <方向档案.json>] [--quiet]
    # 学科级（v3.0 新增）
    python .claude/skills/direction-survey/scripts/ds_scan.py "<学科目录>" --discipline \
        [--out <学科档案.json>] [--quiet]

输入: 论文库/<学科>/<方向>/（内含 已分析/ 与 未分析/） 或 论文库/<学科>/
      ※ paper-analyzer v4.1.0 起 已分析/ 下多一层「发表年」目录（已分析/<四位年份>/<论文名>/）；
        本脚本两种布局都认（见 iter_paper_dirs），并在 record["year"] 里给出年份层名（旧扁平 = ""）。
输出: 方向档案.json 草稿（篇目 + 报告md/docx路径 + 引擎版本 + 未分析PDF + 元信息）
      学科档案.json 草稿（--discipline：逐方向篇目/报告/综述件 + 锚点标记命中 + 样本充足性提示）
      --out 缺省 = <方向>/方向综述/工作/方向档案.json ｜ <学科>/方向论断/工作/学科档案.json

只做机械扫描，不读报告正文 —— digest / 库外锚点 / 边 / 细化论断 由 Claude 步骤 1 补充进同一 JSON。
"""
import argparse
import json
import re
import sys
from pathlib import Path

ENGINE_RE = re.compile(r"paper[- ]analyzer\s*(?:skill)?[\s*_]*v?(\d+\.\d+(?:\.\d+)?)", re.IGNORECASE)
ENGINE_RE2 = re.compile(r"(?:引擎|engine)[^v]{0,8}v?(\d+\.\d+(?:\.\d+)?)", re.IGNORECASE)
# v2/v3 结构变体：判 §4 是否已升级为批判五段（判定表/致命一击/§4.4 核验），而非只看头部声明的引擎号
V3_CRIT_MARKERS = (r"判定表", r"致命一击", r"核验归属", r"批判§4", r"R[1-5]\s*[：:]")
V2_STYLE_HEAD = ("三篇方法相似", "直接相关", "拓展与相关论文")
SURVEY_RE = re.compile(r"方向综述-(\d{4}-\d{2}-\d{2})\.md$")
OUT_DIR_DISCIPLINE = "方向论断"   # 学科级产物根；扫学科时跳过，免得把自己的输出当方向
SURVEY_VER_RE = re.compile(r"direction-survey\s*v?(\d+\.\d+(?:\.\d+)?)", re.IGNORECASE)
ANCHOR_RE = re.compile(r"R([1-5])(?!\d)")
# 发表年层（paper-analyzer v4.1.0 起）：已分析/ 下先按论文发表年分目录，再放论文文件夹
YEAR_DIR_RE = re.compile(r"(\d{4}|年份不详)")


def split_folder_name(folder: str) -> dict:
    """论文文件夹名 = 英文原题（中文译题）；拆出两段。"""
    if "（" in folder and "）" in folder:
        en = folder.split("（", 1)[0].strip()
        zh = folder.split("（", 1)[1].rsplit("）", 1)[0].strip()
        return {"title_en": en, "title_zh": zh}
    return {"title_en": folder, "title_zh": ""}


def detect_engine(report_md: Path) -> str:
    """报告头几行里找 paper-analyzer 版本号；找不到返回 '未标注'。"""
    try:
        head = report_md.read_text(encoding="utf-8", errors="ignore")[:2000]
    except OSError:
        return "未标注"
    for rx in (ENGINE_RE, ENGINE_RE2):
        m = rx.search(head)
        if m:
            return "v" + m.group(1)
    return "未标注"


def detect_variant(report_md: Path) -> str:
    """内容判 § 结构变体：v3-style(批判五段) / v2-style(旧 §4)。头部声明号对混合版失真(如 §4 已 v3.2 而 §5 仍 v2)，以此为准。"""
    try:
        txt = report_md.read_text(encoding="utf-8", errors="ignore")[:200000]
    except OSError:
        return "unknown"
    crit = any((re.search(m, txt) if m[:1] == "R" else m in txt) for m in V3_CRIT_MARKERS)
    return "v3-style" if crit else "v2-style"


def count_anchors(report_md):
    """报告里命中的 §5 R1–R5 角色标记（去重计数）。机器计数，仅作「锚点是否齐备」的提示，
    不等于相关论文实际篇数——判读仍以报告 §5 正文为准。"""
    if report_md is None:
        return []
    try:
        txt = report_md.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return []
    return sorted({m for m in ANCHOR_RE.findall(txt)}, key=int)


def iter_paper_dirs(analyzed_root: Path):
    """产出 (论文文件夹, 发表年层名) —— 兼容两种布局：
    ① v4.1.0 起：已分析/<四位年份>/<论文名>；② 旧扁平：已分析/<论文名>（发表年层名 = ""）。
    年份层判据 = 四位数字目录名（含「年份不详」也视作层名，便于追溯）。"""
    for p in sorted(x for x in analyzed_root.iterdir() if x.is_dir()):
        if YEAR_DIR_RE.fullmatch(p.name):
            for q in sorted(x for x in p.iterdir() if x.is_dir()):
                yield q, p.name
        else:
            yield p, ""


def scan_papers(direction_dir: Path):
    """扫一个方向目录 → (已分析篇目 records, 未分析 PDF 相对路径)。两模式共用，输出字段固定。"""
    analyzed_root = direction_dir / "已分析"
    unanalyzed_root = direction_dir / "未分析"
    records, pdfs = [], []
    if analyzed_root.is_dir():
        for paper_dir, year in iter_paper_dirs(analyzed_root):
            rec = split_folder_name(paper_dir.name)
            rec["folder"] = paper_dir.name
            rec["year"] = year
            analysis_dir = paper_dir / "分析"
            reports_md = sorted((analysis_dir.glob("*.md")) if analysis_dir.is_dir() else [])
            report_md = next((r for r in reports_md if "分析报告" in r.name), reports_md[0] if reports_md else None)
            rec["report_md"] = str(report_md.relative_to(direction_dir)) if report_md else ""
            rec["report_docx"] = str(next((r for r in (analysis_dir.glob("*.docx")) if "分析报告" in r.name), "")) if analysis_dir.is_dir() else ""
            rec["engine_version"] = detect_engine(report_md) if report_md else "无报告"
            rec["section_variant"] = detect_variant(report_md) if report_md else "无报告"
            rec["has_resource_list"] = (paper_dir / "资源清单.md").is_file()
            rec["has_repro_readme"] = (paper_dir / "复现" / "README.md").is_file()
            records.append(rec)
    if unanalyzed_root.is_dir():
        for pdf in sorted(unanalyzed_root.rglob("*.pdf")):
            pdfs.append(str(pdf.relative_to(direction_dir)))
    return records, pdfs


def find_survey(direction_dir: Path) -> dict:
    """方向综述件：取 <方向>/方向综述/ 下最新的 方向综述-YYYY-MM-DD.md（跳过 工作/ 中间档）。"""
    sdir = direction_dir / "方向综述"
    hits = [p for p in sdir.glob("*.md") if SURVEY_RE.search(p.name)] if sdir.is_dir() else []
    if not hits:
        return {"md": "", "date": "", "version": ""}
    p = sorted(hits, key=lambda x: SURVEY_RE.search(x.name).group(1))[-1]
    try:
        head = p.read_text(encoding="utf-8", errors="ignore")[:3000]
    except OSError:
        head = ""
    m = SURVEY_VER_RE.search(head)
    return {"md": str(p.relative_to(direction_dir)),
            "date": SURVEY_RE.search(p.name).group(1),
            "version": ("v" + m.group(1)) if m else "未标注"}


def scan_direction(direction_dir: Path, quiet: bool = False) -> dict:
    if not direction_dir.is_dir():
        raise SystemExit(f"[ds_scan] 目录不存在: {direction_dir}")

    archive = {
        "schema": "direction-archive-v1",
        "generated": "",  # 调用方填或本脚本用今天
        "学科": direction_dir.parent.name,
        "方向": direction_dir.name,
        "path": str(direction_dir),
        "analysed": [],
        "unanalysed_pdf": [],
        "notes": [],
    }
    archive["analysed"], archive["unanalysed_pdf"] = scan_papers(direction_dir)

    if not archive["analysed"]:
        archive["notes"].append("已分析/ 为空：本方向还没有产出报告的论文。")
    if not archive["unanalysed_pdf"]:
        archive["notes"].append("未分析/ 为空：没有待读 PDF。")

    if not quiet:
        print(f"[ds_scan] 学科={archive['学科']}  方向={archive['方向']}")
        print(f"[ds_scan] 已分析 {len(archive['analysed'])} 篇，未分析 PDF {len(archive['unanalysed_pdf'])} 个")
        for r in archive["analysed"]:
            yr = f"{r['year']} ｜ " if r.get("year") else ""
            print(f"    - [{yr}{r['engine_version']} / {r['section_variant']}] {r['folder'][:60]}")
            if not r["report_md"]:
                print("      (!!) 无 分析/*.md 报告")
    return archive


# 样本充足纪律（discipline-method.md）：方向库内 <2 篇 → 该方向论断只能标「样本不足·推断」；
# 学科铺开方向 <3 块 → 地形尚不成「地形」，学科级结论同样只能标「样本不足·推断」且不得据此新开一刀。
MIN_PAPERS_PER_DIRECTION = 2
MIN_DIRECTIONS = 3


def scan_discipline(discipline_dir: Path, quiet: bool = False) -> dict:
    """学科级扫描（v3.0）：逐方向清点库内已分析篇目 + 报告引擎/结构 + 方向综述件 + 未读 PDF，
    并给出样本充足性提示。只做机械扫描；成立度/成熟度/活跃度/空白度等论断由 Claude 步骤 2 填。"""
    if not discipline_dir.is_dir():
        raise SystemExit(f"[ds_scan] 学科目录不存在: {discipline_dir}")
    archive = {
        "schema": "discipline-archive-v1",
        "generated": "",
        "学科": discipline_dir.name,
        "path": str(discipline_dir),
        "directions": [],
        "totals": {"directions": 0, "analysed": 0, "unanalysed_pdf": 0},
        "notes": [],
    }
    for ddir in sorted(p for p in discipline_dir.iterdir() if p.is_dir() and not p.name.startswith("_")
                       and p.name != OUT_DIR_DISCIPLINE
                       and ((p / "已分析").is_dir() or (p / "未分析").is_dir())):
        records, pdfs = scan_papers(ddir)
        rec = {
            "方向": ddir.name,
            "path": str(ddir),
            "n_analysed": len(records),
            "n_unanalysed_pdf": len(pdfs),
            "analysed": [{"title_en": r["title_en"], "title_zh": r["title_zh"],
                          "folder": r["folder"], "year": r.get("year", ""),
                          "report_md": r["report_md"],
                          "engine_version": r["engine_version"],
                          "section_variant": r["section_variant"],
                          "anchor_marks": count_anchors(
                              (ddir / r["report_md"]) if r["report_md"] else None)}
                         for r in records],
            "unanalysed_pdf": pdfs,
            "survey": find_survey(ddir),
            "notes": [],
        }
        if rec["n_analysed"] < MIN_PAPERS_PER_DIRECTION:
            rec["notes"].append(
                f"库内仅 {rec['n_analysed']} 篇（<{MIN_PAPERS_PER_DIRECTION}）→ 该细分方向的一切论断须标「样本不足·推断」")
        if not rec["survey"]["md"]:
            rec["notes"].append("无方向综述件：库内尚未做过方向级综述（成熟度/活跃度判断证据更薄）。")
        archive["directions"].append(rec)
        archive["totals"]["analysed"] += rec["n_analysed"]
        archive["totals"]["unanalysed_pdf"] += rec["n_unanalysed_pdf"]
    archive["totals"]["directions"] = len(archive["directions"])
    if not archive["directions"]:
        archive["notes"].append("学科下没有方向子目录。")
    elif len(archive["directions"]) < MIN_DIRECTIONS:
        archive["notes"].append(
            f"库内只铺开 {len(archive['directions'])} 个方向（<{MIN_DIRECTIONS}）→ 地形尚不成「地形」，"
            "学科级结论只能写成「本库目前只铺开这几块」并标「样本不足·推断」，且不得据此新开一刀")
    if not quiet:
        print(f"[ds_scan] 学科={archive['学科']}  方向 {archive['totals']['directions']} 个，"
              f"已分析 {archive['totals']['analysed']} 篇，未读 PDF {archive['totals']['unanalysed_pdf']} 个")
        for r in archive["directions"]:
            sv = r["survey"]
            print(f"    - {r['方向']}：已分析 {r['n_analysed']} 篇 ｜ 综述 {sv['version']} {sv['date'] or '无'}"
                  f" ｜ 未读 PDF {r['n_unanalysed_pdf']}")
            for n in r["notes"]:
                print(f"      (!) {n}")
        for n in archive["notes"]:
            print(f"    (!) {n}")
    return archive


def main() -> int:
    ap = argparse.ArgumentParser(description="direction-survey 方向/学科扫描 → 档案.json 草稿")
    ap.add_argument("target", help="方向目录 论文库/<学科>/<方向>（或 --discipline 时给学科目录 论文库/<学科>）")
    ap.add_argument("--discipline", action="store_true",
                    help="学科级模式（v3.0）：扫 论文库/<学科> 逐方向清点 → 学科档案.json")
    ap.add_argument("--out", default="", help="输出 json 路径；缺省 方向: <方向>/方向综述/工作/方向档案.json ｜ 学科: <学科>/方向论断/工作/学科档案.json")
    ap.add_argument("--quiet", action="store_true", help="不打印摘要")
    args = ap.parse_args()

    target = Path(args.target)
    if args.discipline:
        archive = scan_discipline(target, quiet=args.quiet)
        default_out = target / "方向论断" / "工作" / "学科档案.json"
    else:
        archive = scan_direction(target, quiet=args.quiet)
        default_out = target / "方向综述" / "工作" / "方向档案.json"
    if not archive["generated"]:
        from datetime import date
        archive["generated"] = date.today().isoformat()

    out = Path(args.out) if args.out else default_out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(archive, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[ds_scan] 已写{('学科' if args.discipline else '方向')}档案草稿 -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
