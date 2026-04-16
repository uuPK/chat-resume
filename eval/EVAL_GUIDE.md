# Agent 评测指南

## 前提

```bash
export OPENROUTER_API_KEY=sk-or-...
cd /path/to/chat-resume/backend
```

---

## 第一步：运行 Agent，收集结果

```bash
# 全部 39 个用例（约 12-25 分钟）
uv run python ../eval/run_eval.py --output ../eval/eval_results.json

# 只跑指定用例（调试用）
uv run python ../eval/run_eval.py --cases TC001,TC002,TC003 --output ../eval/eval_results.json

# 只跑 optimize-first 决策规则验证（#28）
uv run python ../eval/run_eval.py --cases TC037,TC038,TC039 --output ../eval/optimize_first_results.json
uv run python ../eval/score.py --input ../eval/optimize_first_results.json --no-llm-judge
```

---

## 第二步：计算评分

```bash
# 完整评分（含 LLM-as-Judge）
uv run python ../eval/score.py --input ../eval/eval_results.json --output ../eval/eval_scores.json

# 快速评分（跳过 LLM-as-Judge，省费用）
uv run python ../eval/score.py --input ../eval/eval_results.json --no-llm-judge
```

终端会打印三项汇总；如果结果里包含 `optimize-first` 专项用例，还会额外打印第 4 项 `decision_rule`：

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

## 测试用例分布（共 39 个）

| 场景 | 用例 |
|------|------|
| 应届生简历 × 后端JD | TC001–005 |
| 中级简历 × 后端JD | TC006–010 |
| 英文简历 × 全栈JD | TC011–015 |
| 边界场景（拒绝/删除/无JD） | TC016–020 |
| 综合场景（格式/追问/跨领域） | TC021–030 |
| 前端简历 × 前端JD | TC031–032 |
| 产品简历 × 产品JD | TC033–034 |
| 运营简历 × 运营JD | TC035–036 |
| optimize-first 决策规则 | TC037–039 |

### optimize-first 决策规则专项（#28）

这 3 条用例专门验证：

- `TC037`：常规优化请求 -> 首轮直接调用工具
- `TC038`：缺输入 -> 单轮、具体追问
- `TC039`：高风险请求 -> 先拦截并单轮、具体追问

评分结果里会额外出现 `decision_rule`，用于判断这 3 条是否符合“默认先执行，必要时才追问”的新规则。

---

## 结果文件

| 文件 | 内容 |
|------|------|
| `eval_results.json` | Agent 原始回复 + 修改前后简历 |
| `eval_scores.json` | 每个用例的三维评分明细 |
