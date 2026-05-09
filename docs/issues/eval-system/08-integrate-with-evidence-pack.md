## Parent

PRD: `PRD.md`

## What to build

将改进后的评估摘要接入现有指标证据包生成流程，让 Resume Agent 质量指标、门禁结论和面试链路指标能在同一套摘要和 Markdown 输出中呈现。

接入时应保持现有证据包输入兼容，避免破坏已有使用方式。

## Acceptance criteria

- [x] 证据包生成流程可以读取新的评估摘要结构。
- [x] 证据包输出包含门禁状态、关键失败分类概览和原有核心指标。
- [x] 现有面试链路指标仍能正常展示。
- [x] 对旧版 `eval_scores` 输入保持兼容，或在不兼容时给出清晰错误信息和迁移说明。
- [x] 添加测试覆盖新摘要输入、缺失可选字段和面试指标同时存在的场景。

## Blocked by

Blocked by: `05-markdown-eval-report.md`, `07-eval-run-metadata.md`
