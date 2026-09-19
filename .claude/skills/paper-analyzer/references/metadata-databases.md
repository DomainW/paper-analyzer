# 论文/代码检索：多库数据来源（v3.0）

> 目标：同一篇/同一主题，**交叉多库核对**，别只信单一来源。
> Semantic Scholar（MCP 已接入）仍是"找相似论文"的第一引擎；本表其余库用于补覆盖、核元数据、找代码。

## 1. 各库定位速查

| 库 | 覆盖 | 认证/限速 | 最擅长 | 调用方式 |
|----|------|----------|--------|---------|
| **Semantic Scholar** | 全部学科 | MCP ~1 rps（匿名） | 相似推荐、被引网络、paperId | MCP 工具（首选） |
| **OpenAlex** | 2.5 亿+ 作品，覆盖广 | 免费，mailto 可 10 万/日 | 标题模糊查、元数据权威、OA 链接、全字段过滤 | REST / `pa_query.py openalex` |
| **arXiv** | 预印本（CS/物理等） | 免费，勿超 ~1 req/s | 最新进展、官方预印本 | REST / `pa_query.py arxiv` |
| **DBLP** | 计算机领域会议期刊 | 免费，慢 | CS 会议/作者消歧权威 | REST / `pa_query.py dblp` |
| **GitHub** | 开源代码 | 未认证搜索 ~10 次/分 | **找官方/社区复现代码** | REST / `pa_query.py github` |
| **Hugging Face Hub** | 模型/数据集/论文 | 免费，礼貌节流 | **数据集/模型权重是否公开** | REST |
| Crossref | DOI 注册 | 免费 | 用 DOI 拿标准元数据 | REST |

> 说明：PapersWithCode 官方 API 已下线；其“论文↔代码”信息现在主要靠 GitHub 搜索 + OpenAlex/论文自带的代码链接还原。Semantic Scholar 可优先用于"引用-被引"找 R4 后续。

## 2. 常用 REST 配方（curl 或浏览器即可）

### OpenAlex（最推荐做"标题精确找原文 + 拿 DOI/OA-PDF"）
```
https://api.openalex.org/works?search=VMamba%20speech%20enhancement&per-page=5&sort=relevance_score:desc&mailto=you@example.com
```
加年份过滤：`&filter=from_publication_date:2023-01-01`

### arXiv（预印本/最新）
```
http://export.arxiv.org/api/query?search_query=all:%22speech%20enhancement%22%20AND%20all:mamba&max_results=10
```

### DBLP（CS 会议权威）
```
https://dblp.org/search/publ/api?q=speech%20enhancement%20mamba&format=json&h=10
```

### GitHub（找代码，多试几组关键词）
```
https://api.github.com/search/repositories?q=speech+enhancement+mamba&sort=stars&per_page=10
```
> 必带 `User-Agent` 头；未认证 10 次/分——**调用之间等 7s**（pa_query.py 已内置）。

### Hugging Face（数据集/模型）
```
https://huggingface.co/api/datasets?search=dns%20speech
https://huggingface.co/api/models?search=se%20mamba
```

## 3. 各"分析动作"推荐走哪个源

| 分析动作 | 主源 | 补充 |
|---------|------|------|
| 锁定论文官方元数据/DOI | Semantic Scholar → 拿 paperId；OpenAlex 交叉 | Crossref |
| 找同作者、前作/后作（演进关系 R4） | Semantic Scholar citations/references | arXiv（作者名搜索） |
| 找"同关键词方法"（R1/R3/R5 候选池） | **OpenAlex search** | DBLP（CS）/ arXiv |
| 找同任务直接竞品（R2） | OpenAlex + 原文 Table 基线 → 反查原文 | Semantic Scholar |
| 找官方/第三方复现代码 | **GitHub search** | HF（模型卡常挂官方 repo） |
| 查数据集是否公开/下载地址 | HF datasets | 原论文"数据可用性"小节 |

## 4. 检索纪律（防噪音）

1. **先精确后泛化**：先用完整标题精确找（`search_papers_match` / OpenAlex 带引号），拿准论文本身；再泛化搜方法词。
2. 关键词四维拆法：**方法论词**（核心方法+domain）、**架构词**（核心模块名）、**性能词**（实时/低复杂度/鲁棒…）、**基线词**（论文里的 baseline 名）——每维单独一轮，避免一次串太长。
3. **跨源字段互验**：同一论文在不同库的 标题/作者/年份 应一致；有出入以 OpenAlex/DBLP 消歧结果为准并标注。
4. 年份窗口默认近 3 年（R1 技术出处可放宽到任意年份）。
5. 找不到就明确写"未检索到"，并留一句下一步检索词——**别用 WebSearch 盲目刷屏**。
6. Semantic Scholar MCP 限速 ~1 rps：搜索严格串行；报 `rate limit` 错则等 60s 再重试。
