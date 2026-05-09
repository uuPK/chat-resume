## Parent

PRD: `PRD.md`

## What to build

在评估摘要中记录运行元数据，为后续趋势对比、结果复现和 LLM Judge 漂移排查打基础。

元数据应覆盖输入文件、运行时间、评估器版本、是否启用 LLM Judge、模型信息和关键配置。

## Acceptance criteria

- [ ] 结构化摘要包含生成时间、输入文件路径或标识、case 数量和评估器版本。
- [ ] 摘要明确记录是否启用 LLM Judge。
- [ ] 当启用 LLM Judge 时，摘要记录 judge 模型、prompt 版本或可追踪标识。
- [ ] 摘要记录 gate 配置来源或内联阈值快照。
- [ ] 终端摘要或 Markdown 报告能显示关键元数据。
- [ ] 添加测试覆盖默认元数据和显式传入配置元数据。

## Blocked by

Blocked by: `01-deterministic-eval-analyzer.md`
