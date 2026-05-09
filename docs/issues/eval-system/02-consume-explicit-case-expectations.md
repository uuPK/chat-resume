## Parent

PRD: `PRD.md`

## What to build

扩展确定性评估分析器，使其消费评测用例里已经声明的显式期望字段，包括必需关键词、禁用内容、期望工具调用、拒绝期望和温和拒绝期望。

完成后，case 文件里的评估意图应真正进入评分结果，而不是只作为人工阅读的注释。

## Acceptance criteria

- [x] `must_contain_keywords` 会在最终简历文本中检查，并输出命中和缺失列表。
- [x] `forbidden_content` 会在最终简历文本和 Agent 回复中检查，并输出命中位置或命中来源。
- [x] `expected_tool_calls` 会和实际工具调用比较，输出 precision、recall、F1 和缺失/多余工具。
- [x] `expect_refusal` 和 `expect_moderate_refusal` 会产生确定性行为判断，并在证据不足时给出明确的不可判定原因。
- [x] 期望无工具调用的 case 在出现意外工具调用时会失败。
- [x] 添加覆盖各类期望字段通过和失败场景的单元测试。

## Blocked by

Blocked by: `01-deterministic-eval-analyzer.md`
