# -*- coding: utf-8 -*-
"""`paper-reproducer/scripts/pr_status.py` 缺口解析的**回归测试**（只读）。

守的是 v2.1.2 修的那个坑：未勾项解析曾是**整行子串** `if "- [ ]" in ln:` + 取值 `ln.split("]", 1)[1]`
（切到第一个 `]` 之后）——README **正文**里出现 `- [ ]` 字面量（模板提示句即一例，逐字拷进每份新 README）
会被当成真待办、切出**半句乱码**，而缺口面板装配为 `README 未勾项 → 步骤 N 受阻 → 清单缺口`、
去重后 `gaps[:8]` 截断，幽灵项排在真缺口之前 → **挤掉一条真缺口**并画进 `复现进度图.png`。

改了 `pr_status.py` 的解析逻辑后**必须**跑本测试。

用法：python _工具/test_pr_status_gap_parser.py
"""
import glob
import importlib.util
import io
import os
import re
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PRS = os.path.join(ROOT, ".claude", "skills", "paper-reproducer", "scripts", "pr_status.py")

spec = importlib.util.spec_from_file_location("pr_status", PRS)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

# ---------------- ① 单元：正文含字面量的 README ----------------
POISON = ("改上表后需重跑刷新；想补充的「缺口/下一步」直接写进各步说明或 §8/§9 的 `- [ ]` 待办，"
          "会随图呈现。首次复制尚未生成图时，可先删掉上面 `![](...)` 占位")
FIXTURE = (
    "# 复现记录 — 夹具论文\n\n> 当前总体状态：🔄 进行中。\n\n"
    "| 步骤 | 状态 | 说明 |\n|------|------|------|\n"
    "| 1 | ✅ | 环境已建 |\n| 2 | ⛔ | 无 GPU，训练类步骤不执行 |\n| 3 | 🔄 | 权重待下 |\n\n"
    "> 图由 `scripts/pr_status.py` 自动生成到本目录。%s。\n\n" % POISON
    + "## 8 待办\n\n- [ ] 申请受限数据集官方入口\n- [x] 拉取官方代码\n- 正文里提到 `- [ ]` 这种写法的说明行\n"
)

tmpd = tempfile.mkdtemp(prefix="pr_status_fixture_")
fix = os.path.join(tmpd, "复现README.md")
io.open(fix, "w", encoding="utf-8", newline="\n").write(FIXTURE)

_, _, _, new_ghosts = m.parse_readme(fix)
old_ghosts = []
for ln in FIXTURE.splitlines():
    if "- [ ]" in ln:                                  # ← v2.1.1 的旧口径（此处故意复刻，作对照）
        t = m.strip_emoji(ln.split("]", 1)[1].replace("**", "").replace("`", "").strip().strip("*"))
        if t:
            old_ghosts.append(t)

print("① 单元测试（夹具：1 条真待办 + 2 处正文形字面量）")
print("   旧口径（v2.1.1）未勾项 %d 条：" % len(old_ghosts))
for g in old_ghosts:
    print("     -", g[:72])
print("   新口径（v2.1.2 起）未勾项 %d 条：" % len(new_ghosts))
for g in new_ghosts:
    print("     -", g[:72])
assert new_ghosts == ["申请受限数据集官方入口"], new_ghosts
assert len(old_ghosts) == 3, old_ghosts
assert any("会随图呈现" in g for g in old_ghosts), "夹具未复现幽灵场景"
print("   ✅ 旧=3 条（1 真 + 2 幽灵，含 1 条半句乱码）→ 新=1 条（仅真待办）")
print("   ✅ 装配序 `README 未勾项 → 步骤 N 受阻 → 清单缺口` + `gaps[:8]`：旧口径下乱码排在真缺口前，会挤掉真缺口")

# ---------------- ② 实况：全库 7 份 README 不得出现幽灵 ----------------
print("\n② 实况只读复核（全库复现 README）")
rd = sorted(glob.glob(os.path.join(ROOT, "论文库", "**", "复现", "README.md"), recursive=True))
POISON_MARK = ("会随图呈现", "顺序取用，超出的条目", "可先删掉上面", "占位")
bad = 0
for r in rd:
    _, _, _, gaps = m.parse_readme(r)
    pd = os.path.dirname(os.path.dirname(r))
    man = os.path.join(pd, "资源清单.md")
    notes = m.parse_manifest_notes(man) if os.path.exists(man) else []
    frag = [g for g in list(gaps) + list(notes) if any(k in g for k in POISON_MARK)]
    print("   %-44s README 未勾 %d ｜ 清单缺口 %d ｜ 幽灵 %s"
          % (os.path.basename(pd)[:42], len(gaps), len(notes), frag or "无 ✓"))
    bad += len(frag)
assert bad == 0, "活件出现幽灵，需排查"
assert len(rd) > 0, "未找到任何复现 README"

# ---------------- ③ 活件与模板的正文里不得再有该字面量 ----------------
print("\n③ 正文形字面量扫描")
hits = []
for r in rd:
    for i, ln in enumerate(io.open(r, encoding="utf-8").read().splitlines(), 1):
        if "- [ ]" in ln and not re.match(r"^\s*[-*]\s*\[ \]", ln):
            hits.append("%s:%d %s" % (os.path.basename(os.path.dirname(os.path.dirname(r))), i, ln.strip()[:60]))
tp = os.path.join(ROOT, ".claude", "skills", "paper-reproducer", "templates", "复现README-模板.md")
th = [ln.strip()[:60] for ln in io.open(tp, encoding="utf-8").read().splitlines()
      if "- [ ]" in ln and not re.match(r"^\s*[-*]\s*\[ \]", ln)]
print("   活件 README：", hits or "无 ✓")
print("   模板         ：", th or "无 ✓")
assert not hits and not th

print("\n✅ 全部通过")
