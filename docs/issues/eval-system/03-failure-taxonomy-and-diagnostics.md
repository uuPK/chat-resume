## Parent

PRD: `PRD.md`

## What to build

为确定性评估结果增加稳定的失败分类和逐用例诊断信息。每个失败 case 都应能说明失败类型、失败证据和建议排查方向，帮助开发者判断问题更可能来自 prompt、工具选择、事实安全、输入处理还是运行时稳定性。

## Acceptance criteria

- [x] 失败结果会映射到稳定 taxonomy：`execution_error`、`tool_mismatch`、`missing_required_keyword`、`forbidden_content`、`decision_rule_failure`、`unsafe_fabrication_risk`、`instruction_miss`、`quality_judge_low`、`latency_or_fallback`。
- [x] 单个 case 可以包含多个失败分类，并保留每类失败的证据。
- [x] 汇总输出包含按失败分类聚合的数量和 case 列表。
- [x] 逐用例输出包含可行动诊断，例如缺失关键词、禁用内容命中、工具差异或决策规则失败原因。
- [x] 添加测试覆盖 taxonomy 映射、多个失败分类并存、无失败分类的成功 case。

## Blocked by

Blocked by: `02-consume-explicit-case-expectations.md`
