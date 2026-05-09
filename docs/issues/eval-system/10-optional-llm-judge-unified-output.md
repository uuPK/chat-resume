## Parent

PRD: `PRD.md`

## What to build

整理 LLM Judge 的可选模式，使默认快速路径保持确定性和低成本；当显式启用 LLM Judge 时，将 judge 分数、跳过原因、错误原因和模型元数据纳入统一评估输出。

## Acceptance criteria

- [x] 默认评估流程不调用 LLM Judge。
- [x] 显式启用 LLM Judge 时，输出每个 case 的 judge 分数或跳过原因。
- [x] Judge 结果被纳入统一结构化摘要，而不是散落在单独格式中。
- [x] Judge 失败不会导致确定性指标丢失。
- [x] 输出记录 judge 模型和 prompt 版本或可追踪标识。
- [x] 添加测试覆盖 judge disabled、judge success、judge skipped 和 judge error 场景。

## Blocked by

Blocked by: `01-deterministic-eval-analyzer.md`, `07-eval-run-metadata.md`
