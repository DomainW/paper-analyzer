# _工具 —— 仓库自用的巡查 / 核对脚本

> 这里放**跨论文、跨 skill** 的仓库运维脚本：它们不属于任何一个 skill 的产出流程，
> 而是「想知道全库现在什么状态」「想核对某类产物有没有漂移」时随时可跑的**只读巡检**（`_工具/docx_date_check.py` 加 `--fix` 才写盘）。
> 与 `.claude/skills/*/scripts/` 的分工：那里是** skill 产出流程的一部分**（`pa_fig.py` 渲染图、`pr_status.py` 出进度图），
> 这里是**维护者视角的体检工具**，不参与任何 skill 的产出。

## 脚本一览

| 脚本 | 干什么 | 何时用 | 写盘? |
|------|--------|--------|-------|
| `status_rollup.py` | 扫描 `论文库/**/复现/README.md`，逐篇打印：分析报告 md/docx 字节+日期、图数、docx 内嵌图数、`资源清单.md` §0 合计、README §0 三态、⛔ 步骤、§8 卡点数；末附方向综述/学科论断产物清单 | 想知道**全库现在什么状态**；做完一批复现/分析后回看 | 只读 |
| `gap_rollup.py` | 全库**复现缺口**滚动汇总（一行一篇）：README §0 三态 + 未勾项数、`资源清单.md` §0 的 ☐/🔄/✅/⛔、§8 卡点数 | 想快速比「哪几篇卡在哪」；给复现排优先级 | 只读 |
| `docx_date_check.py` | 核对每篇 `分析/*-分析报告.md` 与同名 `.docx` 的**日期集合**是否一致（md 是源、docx 是 pandoc 派生物）；`--fix` 时先快照旧 docx 再从 md 重出，并核验「除日期外无其它文字差异 + 内嵌图与 `分析/*.png` 逐字节一致」 | 改了报告日期后；定期体检 docx 有没有跟上 md | 默认只读，`--fix` 写盘 |
| `test_pr_status_gap_parser.py` | `paper-reproducer/scripts/pr_status.py` 缺口解析的**回归测试**：合成含正文形 `- [ ]` 字面量的 README，断言旧解析出幽灵、新解析只出真待办；并对全库 7 份活件断言 0 幽灵 | 改了 `pr_status.py` 的解析逻辑后**必须**跑 | 只读（夹具走临时目录） |
| `table_check.py` | 扫 `论文库/**` + 根 + `_工具/` + `.claude/skills/**` 的 .md，报**两类会静默丢字的口子**：**①** 单元格数与表头不符的表行——即单元格里写了**未转义的裸竖线**（`\|P\|×\|F\|`），这类行的**靠右列会被渲染器静默丢弃**（GFM 与 pandoc/docx 都丢），md 源却看不出；**②** 代码段/数学环境/围栏块之外的**裸「反斜杠 + 字母」**——pandoc 把它当 LaTeX 控制词**连字母一起吞**（Windows 绝对路径会截成 `C:Files`、集合差算子会少一个字母；实测细节见 `references/docx-generation.md` 的「反斜杠（必读）」）。默认范围**跳过 `资料/official-代码/` 第三方镜像**（纪律：不改一字）；**发现问题退出码 1** | 出完报告/改过表格后；**`paper-analyzer` 完成线已接**（v4.0.3 起，收尾必跑） | 只读 |

## 用法

```bash
cd <仓库根>                       # 脚本以自身位置推导仓库根，任意 cwd 均可
python _工具/status_rollup.py
python _工具/gap_rollup.py
python _工具/docx_date_check.py                 # 只核对
python _工具/docx_date_check.py --fix           # 核对 + 快照 + 从 md 重出漂移的 docx
python _工具/test_pr_status_gap_parser.py
python _工具/table_check.py                     # 全库自查（表格列数 + 反斜杠转义；跳过第三方镜像）
python _工具/table_check.py "<文件或目录>"…      # 只查指定范围（目录 = 递归取其下 *.md；此处不跳过镜像）
```

Windows / Git Bash 下中文输出需 `PYTHONIOENCODING=utf-8`（否则控制台可能报编码错）。
需要 `pandoc` 的只有 `docx_date_check.py --fix`。

## 纪律

- **只读优先**：前三个脚本默认不写盘；`--fix` 是显式开关，且**先快照再改**（快照进 `存档/论文层快照/`，并登记索引）。
- **不是 skill 的一部分**：往里加脚本不必动 skill 版本；但若某个脚本的**判定口径**要与 skill 保持一致（如缺口来源口径），
  改 skill 时须同步此处的对应脚本——`test_pr_status_gap_parser.py` 就是这条口径的看门人。
- **被 skill 引用的脚本**：`paper-analyzer` v4.0.3 起把 `table_check.py` 写进**完成线**（收尾自查全表列数 + 反斜杠转义），
  故它虽在 `_工具/`（不参与产出流程），其**存在与用法**已成为 skill 的约定之一——改它的**检查范围 / 退出码 / 调用方式**须同步 skill
  （v4.0.3 同日修订即按此同步：加第二类检查、退出码 1、默认跳过第三方镜像）。
- **一次性脚本不进这里**：打完补丁、记完日志就删；只有「以后还会再跑」的才归入本目录。
