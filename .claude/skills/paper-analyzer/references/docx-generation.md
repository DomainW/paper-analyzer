# Markdown → DOCX 转换方案（v3.0）

> **⚠️ 按需文档（v4.1.0 起）**：`.docx` **不是 paper-analyzer 的默认产物**——默认只出 **md 报告 + 两张图**。本文件仅在**用户明确要求 Word 版**（或需要交付给别人看）时使用，对应 SKILL.md 的 **步骤 8b**。不要在默认流程里顺手跑 pandoc。

## 目录

- [方案选择](#方案选择)
- [方案 A: Pandoc（首选）](#方案-a-pandoc首选)
- [方案 B: docx npm 包（备选）](#方案-b-docx-npm-包备选)
- [方案 C: python-docx（Python 备选）](#方案-c-python-docxpython-备选)
- [表格竖线（必读）](#表格竖线必读--v403)
- [反斜杠（必读）](#反斜杠必读--v403)
- [公式处理](#公式处理)
- [图片与 TOC（v3 新增）](#图片与-tocv3-新增)
- [样式规范](#样式规范)

---

## 方案选择

> **当前环境**: ✅ Pandoc 已安装（Windows 下通常位于 `C:\ProgramData\anaconda3\Library\bin\pandoc.exe`）
> **备选**: ✅ Node.js `docx` npm 包已安装
>
> **v3.0 说明**：报告含 PNG 图（脉络图等）与 Word 目录。**PNG 图只在 Pandoc 路线下能进 docx**
> （docx npm 包路线不带图，仅兜底用）——所以优先保证 Pandoc 可用。

```
优先级:
  ├── ✅ Pandoc（首选，公式保留最好）
  ├── ✅ docx npm 包（项目已安装，无需额外依赖）
  └──   python-docx（备选）
```

---

## 方案 A: Pandoc（首选）

Pandoc 是学术界标准的文档转换工具，**原生支持 LaTeX 公式转 Word OMML**。

### 检查是否已安装
```bash
where pandoc
# Windows 常见路径: C:\ProgramData\anaconda3\Library\bin\pandoc.exe
```

### 基本转换命令（v3：带目录、带图）

```bash
# 关键：先 cd 到 分析/ 目录，保证报告里的相对图片路径（PNG）能被 pandoc 找到
cd "论文库/<学科>/<方向>/已分析/<发表年>/<论文名>/分析"

pandoc "<论文名>-分析报告.md" \
       -o "<论文名>-分析报告.docx" \
  --from markdown \
  --to docx \
  --toc --toc-depth=2 \
  --metadata title="<论文名> — 深度分析报告"
```

> `--toc` 生成 Word 目录（需在 Word 里"更新域"后显示页码）；图片（`![...](xxx.png)`）会被原样嵌入 Word。

### 关键参数
| 参数 | 说明 |
|------|------|
| `--from markdown` | 输入格式（支持 gfm, markdown+tex_math_dollars 等扩展） |
| `--to docx` | 输出为 Word 文档 |
| `--reference-doc=template.docx` | 使用自定义样式模板（可选，有模板时才用） |

> ⚠️ `--mathjax` 参数对 docx 输出无效（仅对 HTML 输出有效）。Pandoc 会自动将 LaTeX 公式转为 Word OMML。

### 如果 Pandoc 未安装
```bash
# Windows (需管理员权限)
winget install --id JohnMacFarlane.Pandoc

# 或使用 Chocolatey
choco install pandoc

# 或从官网下载
# https://pandoc.org/installing.html
```

---

## 方案 B: docx npm 包（备选）

项目已安装 `docx` npm 包。需用 JavaScript 程序化构建 DOCX。

### 基本用法
```javascript
const { Document, Packer, Paragraph, TextRun, HeadingLevel, Table, TableRow, TableCell } = require('docx');
const fs = require('fs');

const doc = new Document({
  sections: [{
    properties: {},
    children: [
      new Paragraph({
        text: "标题",
        heading: HeadingLevel.HEADING_1,
      }),
      new Paragraph({
        children: [
          new TextRun({ text: "正文内容...", size: 24 }),
        ],
      }),
    ],
  }],
});

Packer.toBuffer(doc).then(buffer => {
  fs.writeFileSync("output.docx", buffer);
});
```

### 高级功能
```javascript
// 表格
new Table({
  rows: [
    new TableRow({
      children: [
        new TableCell({ children: [new Paragraph("Cell 1")] }),
        new TableCell({ children: [new Paragraph("Cell 2")] }),
      ],
    }),
  ],
})

// 公式（作为 MathML 文本嵌入）
new Paragraph({
  children: [
    new TextRun({ text: "E = mc²", italics: true, font: "Cambria Math" }),
  ],
})
```

### 运行
```bash
node generate_report.js
```

> 注意：`docx` 包对公式的支持有限。复杂公式建议先用 Pandoc，或在 DOCX 中保留 LaTeX 文本。

---

## 方案 C: python-docx（Python 备选）

```python
from docx import Document
from docx.shared import Inches, Pt, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH

doc = Document()

# 标题
doc.add_heading('论文分析报告', level=1)

# 段落
doc.add_paragraph('正文内容...')

# 表格
table = doc.add_table(rows=3, cols=2)
table.style = 'Table Grid'
table.cell(0, 0).text = '属性'
table.cell(0, 1).text = '内容'

# 保存
doc.save('output.docx')
```

安装：`pip install python-docx`

---

## 图片与 TOC（v3 新增）

- **PNG 图**：报告 md 与 PNG 必须在同一 `分析/` 目录，用相对路径 `![图名](xx.png)`；转换前 `cd` 进 `分析/`（见上）。pandoc 会自动把图片嵌入 docx。
- **目录**：`--toc --toc-depth=2` 生成 Word 自动目录；第一次在 Word 打开若空白 → 全选 F9 / 右键"更新域"。
- **多版本文档对照**：报告若引用库内另一篇报告（如论文与其衍生学位论文互为勘误），在报告速览卡写明对照链即可，docx 无需合并。
- **docx npm 兜底路线**：不渲染图片与 OMML 公式；仅当 pandoc 不可用且内容以文字/表格为主时使用。

---

## 表格竖线（必读 · v4.0.3）

pandoc 以**管道表格**语法解析 md，`|` 即格边界：单元格里出现**未转义的裸竖线**（绝对值 `|P|`、基数 `|F|`、`ρ=|a−b|/c`）会让该行切出**多于表头**的格数，而 pandoc（GFM 同理）**把超出表头的单元格直接丢弃**——该行**靠右的列整列消失**（含金量、为什么重要…），Word 里看不到、**md 源也看不出来**。库内实证见 `存档/README.md` 2026-09-19 条（SM-MOEA §2.2 创新点表 C1 行丢 4 列）。

- **写法**：单元格内竖线一律转义 `\|`（如 `\|P\|×\|F\|`、`O(\|P\|·\|F\|)`）。
- **别把竖线留在行内代码段里**（v4.0.3 同日修订补）：`` `b = \|x\|` `` 里的反斜杠**不会被解析**——代码段按字面输出，docx 里就是可见的 `\|x\|`。所以含竖线的那处**不要包反引号**，写成普通文本 `b = \|x\|` → docx 中 `b = |x|`。（若该处本在代码段内，去掉那一对反引号即可；`&#124;` 也不行，实体在代码段内同样按字面显示。）
- **数学环境内的竖线**（`$…$`）：不能写 `\|`——pandoc 按 LaTeX 解成 `\Vert` → **∥（U+2225）**；`\vert` / `\lvert` 在其 **markdown 读入器**里会被吃掉（实测 `$1 \ldots \vert F \vert$` → `1 …ert Fert`）。**可行写法 = 把竖线移出数学环境**：`$1 \ldots$ \|F\|` → docx 中 `1 … |F|`。
- **非缺陷**：docx 里另有 **∣（U+2223）** 属正常，是 pandoc 对 `\mid` / `\big|` 的既有渲染（条件熵 `H(F_j∣C)`、`P_i∣P_j`、集合基数）。
- **交 Word 前自查**：`python _工具/table_check.py "<分析目录>"` —— 输出 `✅ 全部表格列数一致` 且退出码 0 才过（有问题时**退出码 1**，可直接当完成线闸门）。

---

## 反斜杠（必读 · v4.0.3 同日修订）

同一类静默丢字的第二处口子：**普通文本里的「反斜杠 + 字母」会被 pandoc 当 LaTeX 控制词吃掉**（实测：`|y\x|` → `|y|`，**`x` 整个没了**；Windows 路径 `C:\Program Files\MATLAB\R2018b` → `C:Files2018b`）。它只在**代码段之外**发生——代码段里反斜杠按字面，所以同一串字放在反引号内是安全的。

- **要显示字面反斜杠** → **双写** `\\x`（渲染出 `\x`）。
- **路径、命令** → 直接**用代码段包住**：`` `C:\Program Files\MATLAB\R2018b` ``。
- **标点转义是合法的、不报**：`\|`（竖线）、`\*`、`\_`、`\\`。
- **自查**：`_工具/table_check.py` 第二类即扫这个（代码段 / 数学环境 / 围栏块之外），报出即需修。

---

## 公式处理

### 策略优先级
1. **Pandoc 原生转换**：LaTeX → Word OMML，质量最高
2. **保留 LaTeX 源码**：在 Word 中以等宽字体显示 `$E = mc^2$`，用户可在 Word 中手动转换
3. **截图备用**：如果公式特别复杂，在 Markdown 中保留原文公式，Word 中保留 LaTeX 文本
4. **复杂公式简化**：如果 Markdown 中有大量公式导致 Pandoc 转换后 Word 显示异常，**只保留最核心的 ≤10 个公式用 Pandoc 转换，其余保留 LaTeX 源码文本**

### Pandoc 安装后验证公式支持
```bash
echo '$E = mc^2$' | pandoc -f markdown -t docx -o test_formula.docx
```

---

## 样式规范

### 推荐 Word 文档样式
| 元素 | 样式 | 说明 |
|------|------|------|
| 一级标题 | 黑体, 18pt, 加粗 | 对应 `#` |
| 二级标题 | 黑体, 16pt, 加粗 | 对应 `##` |
| 三级标题 | 黑体, 14pt, 加粗 | 对应 `###` |
| 正文 | 宋体, 12pt | 对应段落 |
| 公式 | Cambria Math, 12pt, 斜体 | 数学表达式 |
| 表格 | 宋体, 10pt, 带边框 | 数据表格 |
| 代码块 | Consolas, 10pt, 灰色背景 | 代码/Python 片段 |

### Pandoc 自定义样式
如有模板需求，创建 `reference.docx`，设置好样式，然后用：
```bash
pandoc input.md -o output.docx --reference-doc=reference.docx
```
