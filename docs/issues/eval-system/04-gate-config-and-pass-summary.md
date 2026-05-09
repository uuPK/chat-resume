## Parent

PRD: `PRD.md`

## What to build

在指标结果之上增加质量门禁层。门禁层应读取可配置阈值，输出整体通过/失败结论，并明确指出哪些 gate 失败、对应实际值和阈值。

默认阈值可以先采用保守配置，但最终阈值需要人工确认后作为项目标准沉淀。

## Acceptance criteria

- [x] 支持配置至少五类 gate：执行成功率、平均工具 F1、禁用内容失败数、optimize-first 通过率、fallback 触发率。
- [x] 每个 gate 输出名称、阈值、实际值、通过状态和失败 case 证据。
- [x] 总体评估结论根据 gate 状态给出 pass/fail。
- [x] 本地调试可以使用宽松阈值，完整基准可以使用严格阈值。
- [x] 添加测试覆盖 gate 通过、失败、阈值缺失和空结果输入。

## Blocked by

Blocked by: `03-failure-taxonomy-and-diagnostics.md`
