# Semantic Scholar 学术搜索参考

> ⚠️ **v2 遗留参考（工具用法向）**：本文只讲 Semantic Scholar MCP 的**工具操作**。选论文的**标准以 SKILL.md 步骤 5 为准**（多库 + 5 篇 × 5 脉络角色 R1–R5），**不要**照本文旧流程"人工筛选 3 篇最相关"执行；本文第 1–3 步仅作候选获取的手段。

## 目录

- [MCP 工具概览](#mcp-工具概览)
- [搜索策略](#搜索策略)
- [工具详细用法](#工具详细用法)
  - [search_papers — 关键词搜索](#search_papers--关键词搜索)
  - [bulk_search_papers — 高级搜索](#bulk_search_papers--高级搜索)
  - [get_recommendations_for_paper — 论文推荐](#get_recommendations_for_paper--论文推荐)
  - [search_papers_match — 标题匹配](#search_papers_match--标题匹配)
  - [get_paper / batch_get_papers — 详情查询](#get_paper--batch_get_papers--详情查询)
  - [get_paper_citations / get_paper_references — 引用关系](#get_paper_citations--get_paper_references--引用关系)
- [Rate Limit 应对](#rate-limit-应对)
- [回退方案](#回退方案)
- [论文 ID 格式](#论文-id-格式)

---

## MCP 工具概览

Semantic Scholar MCP 服务器提供以下核心工具（**以实际运行时可用列表为准**）：

| MCP 工具 | 功能 | 最适用场景 |
|----------|------|-----------|
| `search_papers` | 关键词搜索论文 | 第一步：从方法论关键词找到候选论文 |
| `bulk_search_papers` | 高级搜索（支持年份范围、领域过滤） | 第一步：带过滤条件的精准搜索 |
| `search_papers_match` | 按标题精确匹配 | 获取原文的 Semantic Scholar paperId |
| `get_recommendations_for_paper` | 基于种子论文推荐相似论文 | **第二步：核心步骤——找方法相似的论文** |
| `get_paper` | 获取单篇论文完整元数据 | 查看候选论文的摘要、引用数等 |
| `batch_get_papers` | 批量获取论文（最多 500 篇） | 批量获取候选论文详情 |
| `get_paper_citations` | 查找引用某论文的论文 | 查看后续改进工作 |
| `get_paper_references` | 查找某论文引用的论文 | 追溯方法基础 |

---

## 搜索策略

```
输入: 已分析的论文 PDF 全文
    │
    ▼
第 1 步: 获取原文 paperId + 多维关键词搜索
    1a. search_papers_match(title="<原文标题>")
        → 获取原文的 Semantic Scholar paperId
    1b. bulk_search_papers(query="<方法关键词组合1>",
           year_range="2022-2025", limit=20)
    1c. bulk_search_papers(query="<方法关键词组合2>",
           year_range="2022-2025", limit=20)
    │
    ▼
第 2 步: get_recommendations_for_paper — 方法相似论文推荐 (★ 核心)
    以原文 paperId 作为种子
    → get_recommendations_for_paper(paper_id="<原文paperId>", limit=20)
    → 获得 20 篇方法论最相似的论文
    │
    ▼
第 3 步: batch_get_papers — 批量获取详细元数据
    → 获取摘要、引用数、发表信息
    │
    ▼
候选送 SKILL.md 步骤 5「五角色」筛 5 篇（R1–R5 各一）:
    1. 先按脉络角色归类候选：上游前驱 / 直接竞品 / 模块来源 / 后续演进 / 细分邻域
    2. 近 3 年优先（R1 出处可放宽）、引用数与作者重叠辅助
    3. 某角色缺候选 → 明确"降级/未找到 + 理由"，不得凑同质
    │
    ▼
对比分析: 每篇论文的方法 vs 原文方法 → 输出对比表
```

### 为什么 get_recommendations_for_paper 是核心步骤？

`search_papers` 基于关键词匹配，容易出现"同一领域但方法不同"的结果。
`get_recommendations_for_paper` 基于 Semantic Scholar 的 SPECTER v2 论文嵌入向量计算相似度，
专门找出**方法论相似**的论文，精准度远超关键词搜索。

**建议直接用原文 paperId 做种子**（而非先找候选再用候选做种子），
因为原文自身就是最好的种子——推荐结果会天然偏向与原文方法论相似的论文。

---

## 工具详细用法

### search_papers — 关键词搜索

| 参数 | 说明 | 推荐值 |
|------|------|--------|
| `query` | 搜索关键词（必填） | 方法核心词组合 |
| `limit` | 返回数量 | 20 |
| `year` | 单年份过滤（仅接受整数） | 可省略，用 bulk_search_papers 替代 |
| `fields_of_study` | 研究领域 | 可选，如 ["Computer Science"] |
| `sort` | 排序 | "relevance" / "citationCount" / "year" |
| `fields` | 返回字段 | 可选，节省带宽 |

> ⚠️ `year` 参数只接受单个整数（如 `2024`），不支持范围。需要年份范围请用 `bulk_search_papers`。

**关键词提取示例**：

对于 SpeakerBeam-SS (Conv-TasNet, S4D, target speaker extraction, real-time):
```
query: "real-time target speaker extraction state space model S4D causal Conv-TasNet"
query: "S4D Mamba speech separation speaker extraction streaming lightweight"
query: "state space model neural network speech enhancement causal real-time"
```
每组关键词从不同角度切入，增加覆盖广度。

### bulk_search_papers — 高级搜索

| 参数 | 说明 | 推荐值 |
|------|------|--------|
| `query` | 搜索关键词（必填） | 方法核心词组合 |
| `year_range` | 年份范围 | `"2022-2025"` |
| `limit` | 返回数量 | 20 |
| `fields_of_study` | 研究领域 | ["Computer Science"] |
| `publication_types` | 发表类型 | ["JournalArticle", "Conference"] |
| `min_citation_count` | 最低引用数 | 可选，5-10 |
| `sort` | 排序 | "citationCount" 或 "relevance" |
| `venue` | 指定会议/期刊 | 可选 |

**示例**：
```
bulk_search_papers(
  query="target speaker extraction causal streaming state space model",
  year_range="2022-2025",
  fields_of_study=["Computer Science"],
  limit=20,
  sort="relevance"
)
```

### get_recommendations_for_paper — 论文推荐

| 参数 | 说明 | 推荐值 |
|------|------|--------|
| `paper_id` | 种子论文 ID（必填） | **直接使用原文 paperId** |
| `limit` | 返回数量 | 20 |
| `fields` | 返回字段 | 可选 |

**推荐用法**：直接用原文做种子，一步到位：
```
get_recommendations_for_paper(paper_id="<原文paperId>", limit=20)
```

### search_papers_match — 标题匹配

| 参数 | 说明 |
|------|------|
| `title` | 论文标题（精确或部分匹配） |

**用途**：快速获取某篇已知论文的 Semantic Scholar paperId。
```
search_papers_match(title="SpeakerBeam-SS: Real-time Target Speaker Extraction")
```

### get_paper / batch_get_papers — 详情查询

**单篇**：
```
get_paper(paper_id="<paperId>", fields=["title","abstract","year","authors","citationCount","venue","externalIds"])
```

**批量**（推荐，减少 API 调用次数）：
```
batch_get_papers(
  paper_ids=["id1","id2","id3",...],
  fields=["title","abstract","year","authors","citationCount","venue"]
)
```

返回字段列表（常用）：`title`, `abstract`, `year`, `authors`, `citationCount`, `influentialCitationCount`, `venue`, `publicationTypes`, `externalIds`, `url`, `isOpenAccess`, `openAccessPdf`, `fieldsOfStudy`

### get_paper_citations / get_paper_references — 引用关系

```
get_paper_citations(paper_id="<paperId>", limit=100)   # 谁引用了这篇论文（后续工作）
get_paper_references(paper_id="<paperId>", limit=100)   # 这篇论文引用了谁（基础工作）
```

用于：
- 找到与原论文方法最相关、同时引用了原论文的后续工作（citations）
- 追溯方法论基础（references）

---

## Rate Limit 应对

### 限制规则
- 匿名 API：~1 请求/秒
- 超限惩罚：HTTP 429 + `retry_after: 60` 秒
- 连续触发 3 次 rate limit 后 MCP 工具会抛出 `RateLimitExhaustedError`

### 最佳实践
1. **并发控制在 2 个以内**：一次最多同时发 2 个 MCP 搜索调用
2. **批量代替逐个**：能用 `batch_get_papers` 就不用多次 `get_paper`
3. **错峰调用**：如果发 2 个并行搜索，等结果返回后再发下一批
4. **遇错等待**：收到 rate limit 错误后等待 60s，换用 WebSearch 先补位
5. **优先保核心步骤**：如果 rate limit 紧张，跳过第 1 步的多次关键词搜索，**直接做第 2 步**——用原文 paperId 调 `get_recommendations_for_paper`

---

## 回退方案

如果 MCP 工具全部不可用或连续 rate limit 失败：

### 方案 1: WebSearch（首选回退）
```
WebSearch("<论文核心方法词> paper <年份>")
WebSearch("<论文标题关键词> related work similar method")
```
从搜索结果取候选，按 SKILL.md 步骤 5 五角色（R1–R5）筛出 5 篇（某角色缺则注明降级）。

### 方案 2: Python 直接调用 API（备选）
```bash
python -c "
import urllib.request, json, time
# 搜索原文 paperId
title = 'SpeakerBeam-SS target speaker extraction'
url = 'https://api.semanticscholar.org/graph/v1/paper/search?query=' + title.replace(' ', '%20') + '&limit=5&fields=title,paperId'
req = urllib.request.Request(url)
data = json.loads(urllib.request.urlopen(req, timeout=15).read())
paper_id = data['data'][0]['paperId']
print(f'Found: {paper_id}')

time.sleep(2)  # 尊重 rate limit

# 获取推荐
url2 = f'https://api.semanticscholar.org/graph/v1/paper/{paper_id}/recommendations?limit=10&fields=title,abstract,year,citationCount'
req2 = urllib.request.Request(url2)
data2 = json.loads(urllib.request.urlopen(req2, timeout=15).read())
for r in data2.get('recommendedPapers', []):
    print(f\"- {r['title']} ({r.get('year','?')}), citations: {r.get('citationCount',0)}\")
"
```

---

## 论文 ID 格式

Semantic Scholar 支持多种 ID 格式：

| 格式 | 示例 |
|------|------|
| S2 ID (SHA) | `649def34f8be52c8b66281af98ae884c09aef38b` |
| Corpus ID | `CorpusId:215416146` |
| DOI | `DOI:10.18653/v1/N18-3011` |
| arXiv | `ARXIV:2106.15928` |
| PMID | `PMID:12345678` |
| URL | `URL:https://arxiv.org/abs/2106.15928` |

MCP 工具自动识别 ID 格式，直接传入即可。
