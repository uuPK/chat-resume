## Parent

PRD: `PRD.md`

## What to build

支持对比两份评估摘要，输出关键指标变化、门禁状态变化、改善或退化的 case，以及新增或消失的失败分类。

这个切片用于把评估系统从单次报告推进到回归追踪。

## Acceptance criteria

- [ ] 支持输入 baseline 和 current 两份摘要。
- [ ] 输出执行成功率、工具 F1、关键词提升、fallback 率、门禁状态等关键指标变化。
- [ ] 输出新增失败、已修复失败和仍然失败的 case 列表。
- [ ] 输出新增或减少的失败分类。
- [ ] 提供结构化 JSON 和简洁终端摘要。
- [ ] 添加测试覆盖改善、退化、case 集合变化和缺失指标。

## Blocked by

Blocked by: `07-eval-run-metadata.md`
