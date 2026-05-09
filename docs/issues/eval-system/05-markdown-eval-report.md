## Parent

PRD: `PRD.md`

## What to build

基于结构化评估输出生成面向人阅读的 Markdown 报告。报告应突出快速结论、门禁状态、失败分组、最需要处理的 case，以及本地复现命令。

这个切片让评估结果可以直接用于 code review、异步协作和下一轮 Agent 修改。

## Acceptance criteria

- [x] Markdown 报告包含快速结论、核心指标、门禁结果、失败分类、重点失败 case、复现命令和说明。
- [x] 报告中的失败 case 能显示 case ID、描述、失败分类和关键证据。
- [x] 当所有 gate 通过时，报告仍展示覆盖范围和剩余风险。
- [x] 报告生成不需要调用 LLM。
- [x] 添加快照类测试或结构断言，确保关键章节稳定存在。

## Blocked by

Blocked by: `03-failure-taxonomy-and-diagnostics.md`, `04-gate-config-and-pass-summary.md`
