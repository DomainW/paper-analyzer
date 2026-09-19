# paper — Claude Code Skills for Academic Paper Workflows

[中文](README.md) ｜ **English**

Three [Claude Code](https://claude.com/claude-code) skills covering the three stages of working with academic papers:

> **Understand one paper** (`paper-analyzer`) → **Reproduce one paper** (`paper-reproducer`) → **See a whole direction / discipline** (`direction-survey`)

This is not "summarize this paper for me". It is an attempt to distill the *entire operating loop of a personal paper knowledge base* into reusable instructions: fixed artifact shapes, fixed archive paths, fixed definitions of "done" — so every paper's output looks the same, is comparable, is traceable, and can be picked up again later.

> Skill instructions, templates, and prompts are written in **Chinese**; the scripts and output directories are language-neutral. The skills work fine on English papers.

---

## Contents

- [The three skills](#the-three-skills)
- [Installation](#installation)
- [Quick start](#quick-start)
- [Directory conventions](#directory-conventions-the-paper-library-layout)
- [Design notes](#design-notes)
- [Dependencies](#dependencies)
- [Repository layout](#repository-layout)
- [Repository conventions](#repository-conventions)
- [License](#license)

---

## The three skills

| Skill | In one line | Trigger phrases | Main artifacts |
|-------|-------------|-----------------|----------------|
| [`paper-analyzer`](.claude/skills/paper-analyzer/) | Deep analysis of a **single paper** | "分析论文", "深度分析这篇 PDF" | Structured Markdown report + **exactly two** PNGs (architecture / research-relation) + figure source JSON |
| [`paper-reproducer`](.claude/skills/paper-reproducer/) | **Reproduction** loop for one paper | "复现这篇论文", "跑通代码" | `复现/README.md` progress log + progress figure + metric-alignment verdict |
| [`direction-survey`](.claude/skills/direction-survey/) | **Direction survey / discipline assessment** | "出方向综述", "这个学科分成哪几个方向" | Four figures (G1–G4) + evolution-line survey; or T1 terrain figure + per-block assessment |

All three share one set of directory conventions and one versioning discipline. Each works standalone; together they form a pipeline.

### paper-analyzer — deep analysis of a single paper · v4.1.0

Reads a PDF and runs a **nine-step analysis**, producing a structured Markdown report:

- **Layered text extraction + page health check**: PyMuPDF layered extraction; sparse or scanned pages fall back to visual reading instead of trusting the text layer.
- **Core logic and formulas**: explains mechanism, loss, and complexity in plain terms rather than paraphrasing the abstract.
- **Five-part critique** (§4.1–4.5): a domain **failure-mode checklist** you must sweep → a weakness table (≥8 entries per paper, each with category / severity / confidence / verifiability / suggested fix) → **the killer blow** (the strongest rebuttal to the paper's strongest claim) → verifiable items logged in place → Top-3 summary.
- **Five related papers retrieved across databases, each in a distinct role**: predecessor / competitor / module source / follow-up / neighboring field — not "five vaguely related papers".
- **Exactly two figures per report**: §3.1 architecture (faithful data flow) and §5.3 research-relation (this paper vs. related work). Direction-level stage / family / opportunity narratives belong to `direction-survey`, and are not duplicated here.
- **Default output = one Markdown report + two PNGs.** `.docx`, the resource checklist, and the `复现/ 数据/ 资料/` directories are all **on demand**, so the default path spends its tokens on depth rather than bulk.

> Saying only "find related papers / what came before and after this one" switches to a **lightweight retrieval mode**: retrieval and lineage only, no full report.

### paper-reproducer — reproduce a paper · v2.1.3

Runs one paper through the loop *environment → data → code → smoke test → metric alignment*:

- **"Done" means matching the paper's numbers under a stated protocol** (e.g. VB-PESQ 3.58 from Table 3, with tolerance). If it does not match, the skill produces a **discrepancy analysis** — it does not fudge numbers or quietly move the goalposts.
- Progress and blockers live in `复现/README.md`; a script turns that into a **reproduction progress figure**: eight steps, three states each, plus an automatically derived "what's missing / what's next".
- **Gaps stack from several sources**: unchecked `- [ ]` items, ⛔ steps with their blocking reasons, and `☐/⛔` resource rows from the checklist all feed the gap list. Want something surfaced? Write it in one of those places.
- Pairs with `paper-analyzer`: consumes the target tables, hyperparameters, and official numbers from the analysis report, and **writes back** new links, errata, and version discrepancies found during reproduction.

### direction-survey — direction survey / discipline assessment · v3.0.3

Two granularities, both aimed at a single goal: **a reader who has not read any of the individual papers should still understand the picture.**

- **Direction level** (default): an **evolution-driven survey** of one research direction — origins → backbone established → branching into technical families → each family's trajectory and sticking points → what is and is not comparable in this ecosystem → frontiers and gaps → where to go next. Four figures: **G1 stage timeline / G2 technical-family swimlanes / G3 opportunity quadrant (whitespace × activity) / G4 ecosystem audit matrix**. Papers appear only as evidence attached to stages and families; no paper-by-paper reviews.
- **Discipline level**: cuts a discipline into research directions and judges each block on four axes — **establishedness / maturity / activity / whitespace** — plus a one-line boundary statement, and answers "which block should not stand alone, and is there a cut we should have made but didn't". Ships with a **T1 discipline terrain figure**. When evidence is thin it must be labelled "insufficient sample · inferred" — no forced verdicts.

---

## Installation

A skill is just a directory. Copy the ones you want into Claude Code's skill directory — **user level** makes them available everywhere, **project level** keeps them to one repository:

```bash
git clone https://github.com/DomainW/paper.git
cd paper

# Option 1: user level (recommended — available in any directory)
mkdir -p ~/.claude/skills
cp -r .claude/skills/paper-analyzer   ~/.claude/skills/
cp -r .claude/skills/paper-reproducer ~/.claude/skills/
cp -r .claude/skills/direction-survey ~/.claude/skills/

# Option 2: project level (only inside one repository)
cp -r paper/.claude/skills/* <your-repo>/.claude/skills/
```

Then just say the trigger phrase in Claude Code — e.g. "分析论文", "复现这篇论文", "出方向综述" — or invoke it explicitly as a slash command such as `/paper-analyzer`.

> **Windows**: the scripts print Chinese; set `PYTHONIOENCODING=utf-8` first or the console may raise encoding errors.

---

## Quick start

### Analyze a paper

1. Drop the PDF into `论文库/<discipline>/<direction>/未分析/` (use `论文库/_未分类/未分析/` if unsure how to classify it).
2. Say "**分析论文**". The skill recursively scans every `未分析/` folder and lists candidates.
3. After producing the report it moves the whole paper into `论文库/<discipline>/<direction>/已分析/<publication year>/<paper name>/`: the PDF into `原文/`, the report and both figures into `分析/`.
4. Need a Word version or reproduction material? Ask for it in the same request (the `A+` path / step 8b).

### Reproduce a paper

1. Say "**复现这篇论文**", or name a paper already under `已分析/`.
2. The skill scaffolds `复现/README.md`, then walks environment → data → code → smoke test → metric alignment.
3. Refresh the progress figure and gap list after any step:

```bash
python .claude/skills/paper-reproducer/scripts/pr_status.py "<paper>/复现/README.md"
```

### Produce a direction survey

1. Make sure the direction already contains several **analyzed** papers — they are the evidence.
2. Say "**出方向综述**" (direction level) or "**这个学科分成哪几个方向**" (discipline level).
3. Output lands in `<direction>/方向综述/` or `<discipline>/方向论断/`, with the Markdown report and the full set of PNGs.

---

## Directory conventions (the paper library layout)

The three skills work against the layout below by default. **It is a convention, not a hard-coded path** — use it as-is, or edit the path sections inside the skills to match your own layout.

```
论文库/                          # the library
└── <discipline>/
    └── <research direction>/
        ├── 已分析/               # analyzed
        │   └── <publication year>/        # four digits; "年份不详" when unknown
        │       └── <paper name>/
        │           ├── 原文/              # PDF + extracted text
        │           ├── 分析/              # report .md + two PNGs + figure source JSON
        │           ├── 复现/              # ◇on demand: code and notes you ran
        │           ├── 数据/              # ◇on demand: datasets (download scripts in 数据/下载脚本/)
        │           ├── 资料/              # ◇on demand: official code / weights / eval scripts / misc
        │           └── 资源清单.md        # ◇on demand: six-category resource checklist + collection status
        └── 未分析/               # pending, usually just the PDFs
```

Three states: 🟢 **analyzed** (has a report under `分析/`) ｜ 🟡 **pending** (PDF only) ｜ ⚪ **unclassified** (under `论文库/_未分类/`).

Naming habits worth stealing:

- A paper folder is named `English original title（中文译题）`, full subtitle and all — no short aliases.
- Half-width `:` in titles becomes full-width `：` (Windows forbids `:` in filenames).
- Year folders use the **publication year** (conference year / journal volume year / thesis defense year), not the download or analysis year.

---

## Design notes

If you are writing your own skills, these are the parts most worth borrowing:

1. **Fix the artifact shape.** Exactly two figures per report, exactly one progress figure per reproduction. "Exactly" is harder to write than "as many as needed" and far more useful — artifacts stay comparable, batch-inspectable, and regression-testable.
2. **"Done" must be decidable.** Reproduction is done when the metrics match the paper, not when the code runs; analysis runs a table-integrity check at the finish line and **exits non-zero** on failure. Only a decidable finish line can be automated.
3. **Derive gaps, don't summarize them.** The progress figure computes what is missing from unchecked `- [ ]` items, ⛔ states, and `☐` checklist rows rather than from a human-written summary.
4. **Evidence discipline.** Insufficient evidence gets labelled "inferred"; unknown dates get "unknown"; failed reproductions get a discrepancy analysis. **Never fabricate** is a hard constraint written into every skill.
5. **Snapshot before you upgrade.** Every file with version semantics (the skill itself, report templates) is snapshotted in full before being touched, and snapshots are never auto-deleted. The scars are documented in [`docs/版本沿革.md`](docs/版本沿革.md).

---

## Dependencies

A skill is Markdown plus Python scripts. **Scanning, retrieval, and validation scripts use the standard library only**; only PDF extraction and figure rendering need packages:

| Purpose | Dependency | Notes |
|---------|-----------|-------|
| Layered PDF extraction | `PyMuPDF` (`import fitz`) | `paper-analyzer/scripts/pa_extract.py`; falls back to visual reading if missing |
| Figure rendering | `matplotlib` + `networkx` | `pa_fig.py` / `ds_fig.py` / `pr_status.py` / `pa_overview.py` |
| Word export | [`pandoc`](https://pandoc.org/) | Optional; only for on-demand `.docx` |
| Literature search | Semantic Scholar MCP | Optional; `pa_query.py` also speaks plain HTTP |

```bash
pip install pymupdf matplotlib networkx
```

Python 3.9+ (developed on 3.13).

---

## Repository layout

```
paper/
├── .claude/skills/            the three skills (the open-source part)
│   ├── paper-analyzer/        SKILL.md + scripts/ + references/ + templates/ + CHANGELOG.md
│   ├── paper-reproducer/
│   └── direction-survey/
├── _工具/                     repo maintenance scripts (read-only inspection)
├── docs/                      repository conventions and version history
├── CLAUDE.md                  operating rules for this repo (auto-loaded by Claude Code)
├── 论文库/  ·  存档/           personal paper library and version archive (local, not version-controlled)
└── README.md / README.en.md
```

Each skill directory carries its own `CHANGELOG.md` recording its version history and design rationale — that is the most detailed primary source.

---

## Repository conventions

This repository doubles as the maintainer's personal paper knowledge base. The conventions below keep that running; **full detail in [`docs/仓库约定.md`](docs/仓库约定.md)** (Chinese):

- **Snapshot before upgrading** — any file with version semantics (the skill itself, report templates) is snapshotted in full into `存档/` before being touched. Nothing is auto-deleted.
- **Single source of truth for versions** — a skill's version and date must agree across three places: the `SKILL.md` banner, its version-history table, and `CHANGELOG.md`. Dates are the actual landing date as recorded by the maintainer; evidence chain and red lines are in `docs/仓库约定.md`.
- **Classification and naming rules** — discipline / direction hierarchy, paper folder naming, internal file naming.
- **Cross-skill and repo-level history** — [`docs/版本沿革.md`](docs/版本沿革.md).

The operational summary Claude Code actually loads (path conventions, archive exits, red lines) lives in [`CLAUDE.md`](CLAUDE.md). Change the structure, change it in both places.

---

## License

[MIT](LICENSE). The instruction text, scripts, and templates may be freely used, modified, and redistributed.

`.claude/skills/skill-creator/` is a third-party skill (upstream `qiuzhi-skill-creator`) and is kept out of the repository, registered only for provenance.
