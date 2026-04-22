# 评测证据包

这份文档用于把仓库里已有的 `eval` 和性能测速能力，整理成面向求职展示的“证据包”。

目标不是追求论文式评测，而是稳定产出三类可以直接放进 README、简历和面试表达里的内容：

- Agent 质量指标
- 生产模式性能指标
- 尚未完全自动化的补充指标，例如面试链路完成率

## 产物

建议最终固定产出两份文件：

- `eval/evidence-summary.json`：结构化摘要，便于后续脚本或页面消费
- `docs/product/agent-metrics-summary.md`：面向人阅读的 Markdown 指标摘要

## 第一步：跑 Resume Agent 离线评测

```bash
cd backend
uv run python ../eval/run_eval.py --output ../eval/eval_results.json
uv run python ../eval/score.py --input ../eval/eval_results.json --output ../eval/eval_scores.json
```

你会得到：

- Agent 修改成功率的原始分母分子
- JD 关键词匹配率提升
- 工具调用正确性 F1
- LLM-as-Judge 综合评分

## 第二步：跑生产模式性能测速

```bash
cd frontend
npm run perf:prod -- \
  --frontend-url http://localhost:3000 \
  --api-url http://localhost:8000 \
  --runs 5 \
  --output perf-report.json
```

你会得到：

- API 探针平均耗时 / P95
- 页面导航平均耗时 / P95
- 关键页面例如简历编辑页的平均打开耗时

## 第三步：补充尚未自动化的指标

当前最值得补充的是：

- 面试链路完成率
- 面试报告生成成功率
- 线上转化或留存类指标

其中“面试链路完成率”现在已经可以自动统计：

```bash
cd backend
uv run python ../eval/measure_interview_pipeline.py \
  --api-url http://localhost:8000 \
  --runs 2 \
  --output ../eval/interview_metrics.json
```

脚本会真实回放：

- 创建 session
- 开始面试
- 流式提交回答
- 练习模式下等待评估就绪
- 结束面试并拉取最终 report

输出里会包含：

- 创建成功率
- 开始成功率
- 回答成功率
- 练习模式评估就绪率
- 报告生成成功率
- 面试链路完成率

对于暂时还没有自动脚本承接的业务指标，可以继续用 `eval/manual_metrics.example.json` 的格式手工维护：

```json
{
  "metrics": [
    {
      "label": "面试链路完成率",
      "value": "18/20 (90.0%)",
      "description": "从创建 session 到生成最终 report 的完整闭环成功率。"
    }
  ]
}
```

## 第四步：生成可讲述的摘要

```bash
cd backend
uv run python ../eval/build_evidence_report.py \
  --eval-scores ../eval/eval_scores.json \
  --perf-report ../frontend/perf-report.json \
  --interview-report ../eval/interview_metrics.json \
  --manual-metrics ../eval/manual_metrics.example.json \
  --output-json ../eval/evidence-summary.json \
  --output-md ../docs/product/agent-metrics-summary.md
```

脚本会把原始评测结果整理成：

- `快速结论`
- `核心指标表`
- `可直接复用的项目表述`
- `Agent 质量细分`
- `性能测量细分`

## 推荐放进简历的指标

优先保留这 4 到 6 个：

- Agent 修改成功率
- JD 匹配度提升
- 工具调用正确性 F1
- LLM Judge 综合评分
- API P95 响应
- 面试链路完成率
- 简历编辑页平均打开耗时

如果你已经有稳定数据，再加入：

- 面试报告生成成功率

## 面试里怎么讲

可以直接按这个顺序说：

1. 我先给 Resume Agent 建了一套离线评测集，不只看主观感觉。
2. 我用关键词覆盖率衡量简历对 JD 的匹配度提升，用工具调用 F1 衡量 Agent 是否按结构化策略执行。
3. 我还回放了结构化面试的端到端链路，统计从创建 session 到生成最终报告的完成率。
4. 最后把这些结果汇总成一份固定格式的证据包，便于在 README、简历和面试里复用。

## 下一步建议

- 为多次评测结果增加时间序列对比
- 把摘要 JSON 接到一个内部 dashboard 或 README badge 上
