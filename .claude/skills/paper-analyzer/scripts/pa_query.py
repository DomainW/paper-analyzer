#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
paper-analyzer v3 · 多源论文 / 代码检索（无需 API key，各源内置限速）
------------------------------------------------
用法（源之间可连用，即为"多库交叉核对"）:
  python pa_query.py openalex  "state space speech enhancement mamba" [--year 2020] [--limit 8]
  python pa_query.py arxiv     "VMamba speech enhancement"            [--limit 8]
  python pa_query.py dblp      "state space speech enhancement"       [--limit 8]
  python pa_query.py github    "speech enhancement mamba"             [--limit 8]

输出: 每行一条命中，字段尽量对齐：年份|标题|venue|被引|链接（GitHub 为★数|语言|链接）。
语义学者(Semantic Scholar)由 MCP 工具承担，无需本脚本。
"""
import argparse
import json
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

UA = {"User-Agent": "paper-analyzer/3.0 (local research; mailto:user@example.com)"}


def utf8():
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8")
        except Exception:
            pass


def http_json(url, headers=None, timeout=30):
    req = urllib.request.Request(url, headers={**UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def http_text(url, timeout=30):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


# ---------- 各源 ----------

def openalex(q, limit, year=""):
    params = {"search": q, "per-page": str(limit),
              "sort": "relevance_score:desc", "mailto": "user@example.com"}
    if year:
        params["filter"] = f"from_publication_date:{year}-01-01"
    url = "https://api.openalex.org/works?" + urllib.parse.urlencode(params)
    try:
        d = http_json(url)
    except Exception as e:
        print(f"[OpenAlex 错误] {e}"); return
    cnt = (d.get("meta") or {}).get("count", "?")
    print(f"== OpenAlex: 「{q}」 命中 {cnt} ==")
    for it in (d.get("results") or [])[:limit]:
        src = ((it.get("primary_location") or {}).get("source") or {}).get("display_name", "")
        oa = (it.get("open_access") or {})
        print(f"  | {it.get('publication_year','?')} | {(it.get('title') or '')[:92]} | "
              f"{src[:30]} | 引{it.get('cited_by_count','-')} | {oa.get('pdf_url') or it.get('doi') or it.get('id')}")
    time.sleep(0.6)


def arxiv(q, limit):
    url = ("http://export.arxiv.org/api/query?search_query="
           + urllib.parse.quote(f"all:{q}") + f"&max_results={limit}&sortBy=relevance")
    ns = {"a": "http://www.w3.org/2005/Atom"}
    try:
        root = ET.fromstring(http_text(url))
    except Exception as e:
        print(f"[arXiv 错误] {e}"); return
    print(f"== arXiv: 「{q}」 ==")
    for e in (root.findall("a:entry", ns))[:limit]:
        title = " ".join((e.findtext("a:title", "", ns) or "").split())
        pub = (e.findtext("a:published", "", ns) or "")[:4]
        pdf = next((l.get("href") for l in e.findall("a:link", ns)
                    if l.get("title") == "pdf"), "")
        au = e.find("a:author", ns)
        first = au.findtext("a:name", "", ns) if au is not None else ""
        print(f"  | {pub} | {title[:92]} | arXiv | - | {pdf}")
        if first:
            print(f"      · 一作 {first}")
    time.sleep(1.0)


def dblp(q, limit):
    url = ("https://dblp.org/search/publ/api?q=" + urllib.parse.quote(q)
           + f"&format=json&h={limit}")
    try:
        d = http_json(url)
    except Exception as e:
        print(f"[DBLP 错误] {e}"); return
    hits = (d.get("result", {}).get("hits", {}) or {})
    print(f"== DBLP: 「{q}」 命中 {hits.get('@total','?')} ==")
    for h in (hits.get("hit") or [])[:limit]:
        info = h.get("info", {})
        authors = info.get("authors", {}).get("author", [])
        if isinstance(authors, dict):
            authors = [authors]
        first = authors[0]["text"] if authors else ""
        print(f"  | {info.get('year','?')} | {(info.get('title') or '').replace(chr(10),' ')[:92]} | "
              f"{(str(info.get('venue') or info.get('type') or ''))[:28]} | - | "
              f"{info.get('ee') or info.get('url') or ''}")
        if first:
            print(f"      · 一作 {first}")
    time.sleep(0.6)


def github(q, limit):
    url = ("https://api.github.com/search/repositories?q="
           + urllib.parse.quote(q) + f"&per_page={limit}&sort=stars")
    try:
        d = http_json(url, headers={"Accept": "application/vnd.github+json"})
    except Exception as e:
        print(f"[GitHub 错误] {e}"); return
    print(f"== GitHub 仓库: 「{q}」 命中 {d.get('total_count','?')} ==")
    for it in (d.get("items") or [])[:limit]:
        desc = (it.get("description") or "")[:66]
        print(f"  | ★{it.get('stargazers_count','-')} | {(it.get('full_name') or '')[:44]} | "
              f"{(it.get('language') or '')[:12]} | {it.get('html_url')}")
        if desc:
            print(f"      · {desc}")
    time.sleep(7)  # GitHub 未认证搜索 ≈ 10 次/分


def main():
    utf8()
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source", choices=["openalex", "arxiv", "dblp", "github"])
    ap.add_argument("query")
    ap.add_argument("--limit", type=int, default=8)
    ap.add_argument("--year", default="", help="仅 OpenAlex：起始年份过滤，如 2020")
    a = ap.parse_args()
    if a.source == "openalex":
        openalex(a.query, a.limit, a.year)
    elif a.source == "arxiv":
        arxiv(a.query, a.limit)
    elif a.source == "dblp":
        dblp(a.query, a.limit)
    else:
        github(a.query, a.limit)


if __name__ == "__main__":
    main()
