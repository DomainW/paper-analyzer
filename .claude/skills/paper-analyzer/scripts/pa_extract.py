#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
paper-analyzer v3 · PDF 文本分层抽取 + 页面"体检"
------------------------------------------------
用法:
  python pa_extract.py <paper.pdf> [-o out.txt] [--layout] [--min-chars 40] [--quiet]

产出:
  1) <out>.txt           全文文本（每页前插 <<PAGE n>> 分隔）——PyMuPDF(fitz)
  2) <out>-health.json   逐页体检：字符数 / 图片数 / 文字密度 / 判定标记
  3) 若给 --layout 且本机有 pdftotext：另存 <stem>-layout.txt（保版式，利于按坐标读表）

stdout 会打印"哪些页疑似图/扫描页 → 需 Read 工具视觉确认或 OCR"清单。
"""
import argparse, json, os, re, subprocess, sys


def utf8():
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8")
        except Exception:
            pass


def main():
    utf8()
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pdf")
    ap.add_argument("-o", "--out", help="txt 输出路径（默认 = pdf 同名 .txt）")
    ap.add_argument("--layout", action="store_true",
                    help="额外用 pdftotext -layout 生成 <stem>-layout.txt")
    ap.add_argument("--min-chars", type=int, default=40,
                    help="低于此字符数判为「疑似图/扫描页」(默认 40)")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()

    if not os.path.isfile(a.pdf):
        sys.exit(f"[错误] 找不到 PDF: {a.pdf}")

    import fitz  # PyMuPDF

    doc = fitz.open(a.pdf)
    stem = os.path.splitext(a.pdf)[0]
    out_txt = a.out or (stem + ".txt")

    pages_text, health, low = [], [], []
    for i, page in enumerate(doc, 1):
        t = page.get_text("text") or ""
        words = page.get_text("words")
        nchar = sum(len(w[4]) for w in words) if words else len(t.strip())
        nimg = len(page.get_images(full=True))
        rec = {"page": i, "chars": nchar, "images": nimg,
               "density": round(min(1.0, nchar / 1500.0), 3), "flag": "normal"}
        if nchar < a.min_chars:
            rec["flag"] = "图/扫描页(需视觉/OCR)" if nimg else "无文字层(需视觉/OCR)"
        elif nchar < a.min_chars * 3:
            rec["flag"] = "稀疏文字(建议抽查)"
        if rec["flag"] != "normal":
            low.append(rec)
        health.append(rec)
        pages_text.append(f"\n<<PAGE {i}>>\n\n" + t)

    full = "\n".join(pages_text)
    with open(out_txt, "w", encoding="utf-8") as f:
        f.write(full)

    health_path = os.path.splitext(out_txt)[0] + "-health.json"
    with open(health_path, "w", encoding="utf-8") as f:
        json.dump({"source": a.pdf, "pages": len(doc), "health": health},
                  f, ensure_ascii=False, indent=1)

    layout_txt = None
    if a.layout:
        try:
            if subprocess.call([os.environ.get("PDFTOTEXT", "pdftotext"),
                                "-layout", a.pdf, stem + "-layout.txt"],
                               stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL) == 0:
                layout_txt = stem + "-layout.txt"
        except (FileNotFoundError, OSError):
            pass

    if not a.quiet:
        n = len(doc)
        print(f"[提取完成] 共 {n} 页 → {out_txt}")
        if layout_txt:
            print(f"[版式文本]  {layout_txt}")
        print(f"[判定] 文字完整页 {n - len(low)}/{n}；疑似图/扫描/稀疏页 {len(low)}/{n}")
        if low:
            print("\n[需视觉确认页]（用 Read 工具读 PDF 对应页，或对这几页单独 OCR）:")
            for r in low:
                print(f"  - Page {r['page']}: {r['flag']} (字符≈{r['chars']}, 图片={r['images']})")
        else:
            print("[体检] 全文文字层完整，无需视觉/OCR。")
        print(f"[体检JSON] {health_path}")


if __name__ == "__main__":
    main()
