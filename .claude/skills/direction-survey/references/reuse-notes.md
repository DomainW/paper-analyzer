# 渲染分工、JSON schema 与 docx（reuse-notes）

> direction-survey v3.0 渲染分两路：
> - **方向级 G1 阶段带 / G2 家族泳道 / G3 机会象限 / G4 生态盘点矩阵**（`stage/family/quad/audit`）+ **学科级 T1 学科地形图**（`terrain`）= 本 skill 自带 `scripts/ds_fig.py`（pa_fig 画不了这五类）。
> - **默认 lineage / scatter2d** = 复用 paper-analyzer `pa_fig.py`（方向级/学科级都不用，仅旧图/降级兜底）。
> 统一入口：`scripts/ds_render.py` 校验 schema + 无 emoji 后**按图型分发**。

## 目录
- [前置依赖](#前置依赖)
- [JSON schema：fig:"stage"](#json-schema-figstage)
- [JSON schema：fig:"family"](#json-schema-figfamily)
- [JSON schema：fig:"quad"（G3 机会象限）](#json-schema-figquadg3-机会象限)
- [JSON schema：fig:"audit"（G4 生态盘点矩阵）](#json-schema-figauditg4-生态盘点矩阵)
- [JSON schema：fig:"terrain"（T1 学科地形图 · 学科级）](#json-schema-figterrain-t1-学科地形图--学科级)
- [调用方式（ds_render.py）](#调用方式ds_renderpy)
- [配色 / 字号 / 图例 / CJK](#配色--字号--图例--cjk)
- [docx 生成](#docx-生成)
- [降级方案与红线](#降级方案与红线)

## 前置依赖
- 仓库根执行；脚本在 `.claude/skills/direction-survey/scripts/`，`ds_render.py` 自动定位 `ds_fig.py`。
- pa_fig 在 `.claude/skills/paper-analyzer/scripts/pa_fig.py`（仅默认 lineage/scatter 需要）。
- Python：matplotlib 已随本机可用；CJK 回退 Microsoft YaHei/SimHei。

## JSON schema：fig:"stage"
（字段与 author 纪律详见 `figure-design.md`；此处给渲染器会读的键）
```json
{
  "fig": "stage", "title": "…", "orientation": "LR",
  "stages": [
    {"id":"s1","name":"…","period":"…","driver":"…",
     "works":[{"label":"…","type":"this|pre|rival|module|next|adj","year":"…"}],
     "breakthrough":"…","gap":"…"}
  ],
  "stage_edges":[{"a":"s1","b":"s2","label":"…"}]
}
```
渲染器行为：一列一个阶段带；带内工作色块 `this` 实色金/非 `this` 浅色虚线框；带底「突破/遗留」自动配色（绿/红）；阶段间箭头只在相邻阶段之间画。标签内可含 `\n` 换行。

## JSON schema：fig:"family"
```json
{
  "fig": "family", "title": "…", "intro": "…",
  "lanes": [
    {"id":"famA","name":"A · 家族名（约束/擅长）",
     "nodes":[{"id":"p","label":"PercepNet\\n2020","type":"pre"}],
     "edges":[{"u":"p","v":"q","label":"继承"}]
    }
  ],
  "cross": [
    {"from":"famA.p","to":"famB.q","label":"模块来源",
     "note":"一句人话","evidence":"PPN §5 R3"}
  ],
  "cross_notes": [
    {"label":"竞品","note":"A 与 C 泳道不相邻不画线，作文字边",
     "evidence":"PPN §6.3 / …"}
  ]
}
```
- 节点 `label` 用 `\n` 断 2 行（如名称+年份/身份）。
- `cross` 的 `from/to` 必须是 `道id.节点id` 形式；渲染器按数组序编号 `[1][2]…` 画虚线并在图下自动生成**边注表文字**。
- **跨族虚线只画上下相邻泳道**（两端泳道索引差 `|Δ|=1`）；非相邻道之间的关系**不画线**，填 `cross_notes`（label/note/evidence）→ 边注表末尾记 `〔文字·未画线〕`。虚线出/入点取两框相对一侧的框边，**走框外不压字**。
- 道内实线、跨族虚线为固定语义；标量字段 `type` ∈ this/pre/rival/module/next/adj。

## JSON schema：fig:"quad"（G3 机会象限）
G3 只用 quad，不再走 pa_fig scatter：
```json
{
  "fig": "quad",
  "title": "G3 · 机会象限图：空白度 × 前沿活跃度（右上 = 又热又空 = 最该投）",
  "sub": "坐标 0–1 仅供示意。判据…（x_lo/x_hi/y_lo/y_hi 说明见上）",
  "x": "机会空间 / 空白度", "y": "前沿活跃度",
  "x_lo": "已有人系统做", "x_hi": "没人系统做（空白大）",
  "y_lo": "冷 · 少人问", "y_hi": "热 · 正当红",
  "quad": {"tl": "又热已满\n拼执行", "tr": "又热又空\n最该投",
           "bl": "又冷又满\n可不用追", "br": "空但冷\n早留意/布局"},
  "foot": "点=机会子题；越靠右上越该投。",
  "points": [
    {"id":"O1","label":"O1 三方横评","x":0.8,"y":0.86,"note":"…"}
  ]
}
```
- 必需：`x`/`y` 轴名、`x_lo/x_hi`、`y_lo/y_hi`（消歧）、`quad{}` 四区文案；`points[]` 每点 id/label/x/y 数值 0–1。
- 右上=又热又空=最该投；点坐标是**示意**，正文读法与坐标必须一致。
- ⚠️ quad **只出 PNG、不产 Mermaid**；G3 不承诺 `.mermaid`。

## JSON schema：fig:"audit"（G4 生态盘点矩阵）
```json
{
  "fig": "audit",
  "title": "G4 · 实时 TSE 生态盘点矩阵：谱系带 × 评测协议 × 复杂度口径",
  "sub": "…", 
  "col_groups": [
    {"label":"方法","cols":[0]},
    {"label":"评测协议 · 主指标","cols":[1,2,3]},
    {"label":"复杂度 / 实时口径","cols":[4,5,6]}
  ],
  "cols": [
    {"label":"方法（谱系内现役）","key":"nm","w":2.0},
    {"label":"带宽 / 域","key":"bw","w":1.4},
    {"label":"主指标","key":"metric","w":2.0}
  ],
  "bands": [
    {"name":"甲 · …组（48k，带内只有自比）",
     "rows":[{"name":"PPN","type":"this",
              "cells":{"nm":"PPN-512\\n2021 库内","bw":"48k 感知域",
                       "metric":"PESQ 2.357 / MOS 3.128"}}]}
  ],
  "note": "读法：…", "legend_tail": "粗黑带=谱系 · 金实=库内 · 浅虚=锚点未读"
}
```
- `cols[]`（label/key/w=英寸）可任意多；`col_groups[]` 给跨列组名；`bands[]` 粗黑带=谱系，行 `type:"this"` 金实身份条、其余浅虚。
- `cells` 的 key 对齐 `cols[].key`；第 0 列键建议 `nm`（方法名，自动粗体）。窄格自动换行、行高自适应。
- 诚实纪律：不同协议/单位**如实并排、不换算**；`note` 写明只有带内同协议可比。
- ⚠️ audit **只出 PNG、不产 Mermaid**。

## JSON schema：fig:"terrain"（T1 学科地形图 · 学科级）
学科级模式唯一图型（输入 `论文库/<学科>`）。字段与 author 纪律详见 `figure-design.md` 的 T1 节；判法见 `discipline-method.md`。
```json
{
  "fig": "terrain",
  "title": "T1 · 学科地形图：<学科>（细分方向论断）",
  "sub": "行=细分方向（带内按成熟度降序）；色深=该维取值高；成立度三色；库内不足 2 篇标「样本不足·推断」。",
  "cols": [
    {"label":"细分方向","key":"name","w":3.4},
    {"label":"成立度","key":"standing","w":1.15,"kind":"standing"},
    {"label":"成熟度","key":"maturity","w":2.6,"kind":"level","hue":"#5b9bd5"},
    {"label":"活跃度","key":"activity","w":2.6,"kind":"level","hue":"#e0645a"},
    {"label":"空白度","key":"blank","w":2.6,"kind":"level","hue":"#6fbf73"},
    {"label":"库内样本","key":"n","w":1.7},
    {"label":"边界一句话","key":"boundary","w":3.4}
  ],
  "bands": [
    {"name":"库内已建目录","type":"this","rows":[
      {"name":"…","standing":"成立",
       "maturity":{"level":"高","why":"…一行判据"},
       "activity":{"level":"中","why":"…"},
       "blank":{"level":"中","why":"…"},
       "n":"3 篇 ｜ 1 份方向综述",
       "boundary":"与 <邻方向> 的边界：…"}
    ]},
    {"name":"论断新增候选（待补证据）","type":"next","rows":[
      {"name":"候选：…（未建目录）","standing":"存疑",
       "maturity":{"level":"不详","why":"库内无已分析报告"},
       "activity":{"level":"不详","why":"未做库外检索，不得计入论断"},
       "blank":{"level":"不详","why":"同上"},
       "n":{"text":"0 篇 ｜ 样本不足·推断","color":"#c0392b","bold":true},
       "boundary":"…"}
    ]}
  ],
  "conclusion": "学科级一句话论断（必填）",
  "note": "读法 + 证据门一句；legend_tail 可覆盖右下尾注"
}
```
- `cols[].kind` ∈ `text`（缺省，逐格文本）/ `standing`（成立度胶囊）/ `level`（分级格）；`level` 列须给 `hue`，值须为 `{"level":"低|中|高|不详","why":"…"}`。
- `rows[]` 每行必须给 `name`，且每个 `level` 列都要有值（schema 会拦）；`type` 给左侧身份条（`this` 金实 / 其余浅虚，缺省取所属 band 的 `type`）。
- 文本列的值可写成 `{"text","color","bold"}` 做强调（样本不足用红字）。
- `conclusion` **必填**（ds_render 会拦），禁止只复述表格。
- ⚠️ terrain **只出 PNG、不产 Mermaid**（语义图）。

## 调用方式（ds_render.py）
```bash
# 仓库根
python .claude/skills/direction-survey/scripts/ds_render.py "<图>.json" \
    --png "<方向综述>/assets/<图名>.png" --mermaid "<方向综述>/assets/<图名>.mermaid"
```
- `--png -` 只出 Mermaid；`--mermaid -` 只出 PNG。
- `--qa`：透传 ds_fig 内置**几何自检**（文字出画布/两两压叠 → 列出，退出码非 0 拦下）。完成线 gate 与日常出图都建议带。
- 自动分发：`fig ∈ stage/family/quad/audit/terrain` → `ds_fig.py`（quad/audit/terrain 只收 png，忽略 mermaid 参数）；默认 `type=="scatter2d"/lineage` → `pa_fig.py`（lineage 需 `--pa-fig` 指向 pa_fig，默认在仓库根）。
- ds_render 校验：必备字段、cross from/to 格式、`style∈solid|dash`、quad/audit/terrain 分支字段（terrain 另校验 `kind` 取值、每行 `level` 列齐备且只能 低/中/高/不详、`conclusion` 必填）、全图字符串**无 emoji/易缺字形**（U+2600–27BF 等）→ 违规直接报错不渲染。
- 若要手工直接跑渲染器：`ds_fig.py <json> --png <p>.png [--mermaid <m>.mermaid] [--qa]`。

## 配色 / 字号 / 图例 / CJK
- 节点/行配色沿用 pa_fig 语汇：`this=金 #f2b134 / pre=绿 / rival=红 / module=蓝 / next=紫 / adj=灰蓝`。非 `this`（库外锚点）浅化 + 虚线框；audit 的谱系粗黑带 + `this` 金实身份条另有说明。
- **terrain 专用色**：三维分级各一色（成熟度蓝 `#5b9bd5` / 活跃度红 `#e0645a` / 空白度绿 `#6fbf73`，每列由 `hue` 给），档位=同色深浅（低 0.70 / 中 0.38 / 高 0.05 的白底混合比）+ 条长 0.33/0.66/1.0；成立度胶囊 `成立=绿 #3f8f52 / 部分成立=黄 #c98a1e / 存疑=红 #b8433a`；`不详` 走浅底 + 灰字（不得当档位读）。
- 字号：ds_fig 用自动排版（1 数据单位 = 1 英寸，逐字量宽，行高/列宽按量出高度推进），作者**不用管字号**；只要遵守 figure-design 的"短标签"纪律。
- **图内不得出现 emoji**（豆腐块）；需要 ✓/× 用文字；标题尽量 ≤ 40 字。**别用 `↔`（U+2194）**，YaHei 缺字形；写「与/对」。
- **改渲染器时的 z-order 纪律（v3.0.1 教训）**：给文字画**白底衬框**时，框的 `z` 必须**低于**文字的 zorder（matplotlib `ax.text` 默认 **3**，`FancyBboxPatch` 靠 `z=` 指定）。`_edge_arrow` 曾把衬框设成 `z=4`、文字用默认 3 → **框画在字上，G1 箭头文字与 G2 编号 `[k]` 整块被盖掉**。判定要点：**几何 `--qa` 不检查遮挡**（框与字同心同尺寸 → 量出"零压叠"，退出码 0 却什么都看不见）；改图后要**看图确认**（或逐像素比对新旧渲染）才算验过。
- 图文件放 `<方向综述>/assets/`，报告以相对路径嵌入。

## docx 生成
```bash
# 方向级
cd "<方向>/方向综述"                        # 关键：保证 md 里 assets/ 相对图路径可用
pandoc "方向综述-<YYYY-MM-DD>.md" -o "方向综述-<YYYY-MM-DD>.docx" \
  --from markdown --to docx --toc --toc-depth=2 \
  --metadata title="<方向> 方向演进综述"

# 学科级
cd "<学科>/方向论断"
pandoc "学科方向论断-<YYYY-MM-DD>.md" -o "学科方向论断-<YYYY-MM-DD>.docx" \
  --from markdown --to docx --toc --toc-depth=2 \
  --metadata title="<学科> 细分方向论断"
```
pandoc 不在 → 只出 md，明确告知用户 docx 以后可转。

## 降级方案与红线
- ds_fig 或 matplotlib 缺失 → 不出 PNG：G1/G2 用「Mermaid 代码块 + 表」、G3 用象限表格、G4 用盘点表表达、**T1 terrain 用「行列分级表（档位写成文字 + 样本列）」**表达，并在 §1 说明「本次无新版图，以表替代」。**不要**退回旧 lineage 硬画。
- pa_fig 缺失 → 不影响 G1–G4（四图全走 ds_fig）；只影响默认 lineage/scatter 旧图。
- 红线：不代下受限数据；不把未读库外锚点写成已读/给假指标；文件/夹名全角标点（Windows 禁半角 `:`），路径加引号；被覆盖的旧文件先快照。
