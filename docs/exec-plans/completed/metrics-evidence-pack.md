# Metrics Evidence Pack

## 背景

当前仓库已经具备两类可复用的评测能力：

- `eval/` 下的 Resume Agent 离线评测与评分
- `frontend/scripts/measure-production.mjs` 的生产模式性能测速

但这些结果仍然以原始 JSON 和终端输出为主，不利于在求职材料、README 和面试表达中复用。

## 目标

- 增加一个统一汇总脚本，把 `eval_scores.json` 和 `perf-report.json` 转成面向求职展示的指标摘要
- 产出一份可直接照着跑的文档，说明如何生成“证据包”
- 为后续补充“面试链路完成率”等手工或半自动指标预留入口

## 非目标

- 这次不重写现有 `eval/run_eval.py` 或 `eval/score.py`
- 这次不直接实现完整的面试链路自动评测平台
- 这次不提交固定的真实评测结果，避免把一次性的本地数字写死进仓库

## 步骤

1. 设计统一摘要结构，覆盖 Agent 质量、性能、手工补充指标 -> verify: 人工检查输出字段是否能映射到求职叙事
2. 新增汇总脚本和样例输入文件 -> verify: `cd backend && uv run python ../eval/build_evidence_report.py --help`
3. 补充文档与索引入口 -> verify: 人工检查文档链接和命令是否可执行

## 决策日志

- 选择在 `eval/` 目录下新增脚本，而不是改造现有评分器，避免影响当前评测链路
- 支持 `manual_metrics` 输入，用于先接住“面试链路完成率”这类尚未完全自动化的指标
- 输出同时支持 Markdown 和 JSON，便于面向人展示和后续二次处理

## 当前状态

已完成：统一汇总脚本、面试链路评估脚本、样例输入文件和使用文档均已落盘。

## 下一步

- 后续按需补充更多真实评测结果，并继续完善 README / 求职材料中的复用方式
