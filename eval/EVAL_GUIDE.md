# Agent 评测指南

## 前提

```bash
export ANTHROPIC_API_KEY=sk-ant-...
cd /path/to/chat-resume/backend
```

---

## 第一步：运行 Agent，收集结果

```bash
# 全部 30 个用例（约 10-20 分钟）
uv run python ../eval/run_eval.py --output ../eval/eval_results.json

# 只跑指定用例（调试用）
uv run python ../eval/run_eval.py --cases TC001,TC002,TC003 --output ../eval/eval_results.json
```

---

## 第二步：计算评分

```bash
# 完整评分（含 LLM-as-Judge）
uv run python ../eval/score.py --input ../eval/eval_results.json --output ../eval/eval_scores.json

# 快速评分（跳过 LLM-as-Judge，省费用）
uv run python ../eval/score.py --input ../eval/eval_results.json --no-llm-judge
```

终端会打印三项汇总：

```
[1] JD 关键词匹配率提升    平均 +8.3%，23/25 用例有提升
[2] 工具调用正确性 (F1)    平均 0.82
[3] LLM-as-Judge 综合评分  平均 4.1 / 5
```

---

## 三个评测维度

| 维度 | 满分 | 计算方式 |
|------|------|----------|
| JD 关键词匹配率提升 | — | 修改后覆盖率 − 修改前覆盖率 |
| 工具调用正确性 | F1 = 1.0 | F1(期望工具集, 实际调用集) |
| LLM-as-Judge | 5 分 | 模型对指令遵循、内容质量、无幻觉各打 1-5 分 |

---

## 测试用例分布（共 30 个）

| 场景 | 用例 |
|------|------|
| 应届生简历 × 后端JD | TC001–005 |
| 中级简历 × 后端JD | TC006–010 |
| 英文简历 × 全栈JD | TC011–015 |
| 边界场景（拒绝/删除/无JD） | TC016–020 |
| 综合场景（格式/追问/跨领域） | TC021–030 |

---

## 结果文件

| 文件 | 内容 |
|------|------|
| `eval_results.json` | Agent 原始回复 + 修改前后简历 |
| `eval_scores.json` | 每个用例的三维评分明细 |
