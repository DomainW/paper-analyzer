# PDF 内容提取策略（v3.0）

## 0. 先纠正一个常见混淆：`pdftoppm` 不是提取工具

| 命令 | 归属 | 真正作用 | 是否产出文字 |
|------|------|---------|-------------|
| **pdftotext** | poppler-utils | 从 PDF 文字层抽取文本（`-layout` 保留大致版式） | ✅ 是 |
| **pdfplumber / PyMuPDF(fitz)** | Python 库 | 抽取文本 + 单词坐标（读表）+ 元数据 | ✅ 是 |
| **pdftoppm** | poppler-utils | **把 PDF 页渲染成位图**（PNG/JPEG/PPM） | ❌ **否，只是转图片** |
| Read 工具（Claude 视觉） | Claude Code | 直接"看"PDF 页（含扫描图、公式图） | ✅ 语义理解级 |

> 结论：skill 旧版把 pdftoppm 放在提取第一优先级是**误用**。它唯一合理的用途是「先把页面转成图，再喂给视觉/OCR」；对带文字层的 PDF，用它反而丢文本。

## 1. 本机工具能力（已实测核对）

| 工具 | 状态 | 用途 |
|------|------|------|
| PyMuPDF (`fitz`) | ✅ 已装 | 首选全文抽取、逐页体检、图片数量 |
| pdfplumber | ✅ 已装 | 单词级坐标 → 表格按列重建 |
| pdftotext 4.00 | ✅ 已装 | `-layout` 保版式文本（读表辅助） |
| Read 工具 | ✅ Claude Code | 视觉读 PDF 指定页（公式/扫描图最准） |
| Tesseract / 其它 OCR | ❌ 未装 | 整本扫描 PDF 才需要（可选安装，见 §4） |

## 2. 决策流程（pa_extract.py 自动体检后照此走）

```text
PDF
 │  python pa_extract.py paper.pdf           ← 先体检 + 抽全文
 ▼
文字完整页占绝大多数？
 ├─ 是 → 用 .txt 全文 + 少量稀疏页用 Read 视觉补读即可   （覆盖 90% 论文）
 └─ 否
     ├─ 仅个别页是整页图（图/表/封面/公式）
     │    → 用 Read 工具读这些页（按页区间，≤20 页/次）
     └─ 整本基本无文字层（纯扫描）
          → 可选：pip install 离线 OCR（§4）；或对扫描件逐页用 Read 视觉
```

**推荐默认流程**：
1. `python pa_extract.py "<pdf>" -o "<原文>/<论文名>.txt" --layout`
   - 产出 `.txt`（fitz 全文，带 `<<PAGE n>>`）与 `-health.json`（逐页体检）；
   - `--layout` 额外产出 `pdftotext -layout` 版（保留版式，方便人读与表格坐标定位）。
2. 看体检输出的"需视觉确认页清单"，命中则 **Read 工具读 PDF 对应页**（视觉理解公式/图表最稳）。
3. 全文进上下文后即可开始逻辑分析；**.txt 与 health.json 归档进 `原文/`**。

## 3. 各类内容的推荐取法

| 内容 | 首选 | 备选 |
|------|------|------|
| 正文文本（带文字层 PDF） | fitz（pa_extract） | pdftotext -layout |
| 表格数值 | pdfplumber 单词坐标按行聚簇重建 | `-layout` 版对齐肉眼核对 |
| 公式（文本/排版公式） | 视觉 Read 对应页 → 报告里转 LaTeX | PDF 自带文本层里的字形串（常需手改） |
| 公式（纯图片） | Read 视觉读页 | OCR（公式质量一般） |
| 扫描页/手写批注 | Read 视觉 | 离线 OCR（§4） |
| 中文学位论文 | 同上；注意多为带文字层 PDF | 逐页视觉 Read |

### 表格按列重建（pdfplumber 要点）
```python
import pdfplumber, io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')  # Windows
with pdfplumber.open(pdf) as p:
    for page in p.pages[:N]:
        words = page.extract_words()
        rows = {}
        for w in words:
            rows.setdefault(round(w['top'], 0), []).append(w)
        for top in sorted(rows):
            cells = sorted(rows[top], key=lambda w: w['x0'])
            print(" | ".join(c['text'] for c in cells))
```
⚠️ 遇到上下标被拆、跨行单元格、合并表头，需结合视觉 Read 核对——**任何自动抽取的表格都要与原文页对一遍再进报告**。

## 4. OCR 可选安装（仅整本扫描 PDF 需要）

| 方案 | 安装 | 中文 | 离线 | 备注 |
|------|------|------|------|------|
| RapidOCR（推荐） | `pip install rapidocr-onnxruntime` | ✅ | ✅ | onnxruntime 本地推理，无外部服务，中等模型体积 |
| PaddleOCR | `pip install paddleocr paddlepaddle` | ✅ | ✅ | 准但重（需 paddle 框架） |
| Tesseract | `winget install UB-Mannheim.TesseractOCR` + `chi_sim` 语言包 | 需装语言包 | ✅ | 经典但中英混排一般 |

> 经验：**能走视觉 Read 就别依赖 OCR**——公式/上下标/表格结构 OCR 都不如视觉准；OCR 只作为「文字层完全缺失」时的兜底。

## 5. 质量底线

- 关键指标表、关键公式：**必须与原文页视觉/文字核对**后再进报告；
- 表格标注原文页码（论文里表格所在页，方便回溯）；
- `.txt`/`-layout.txt`/`-health.json` 归档 `原文/`，与 PDF 共存亡。
