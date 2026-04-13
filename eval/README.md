# Agent 评测框架

评估简历优化 Agent 的效果，覆盖三个维度：

| 维度 | 指标 | 说明 |
|------|------|------|
| JD 关键词匹配率 | before/after delta | 客观衡量简历与JD的相关性提升 |
| 工具调用正确性 | F1 (precision × recall) | 验证 Agent 是否调用了正确的工具 |
| LLM-as-Judge | 1-5分（三项） | 指令遵循度、内容质量、无幻觉 |

## 目录结构

```
eval/
├── README.md
├── run_eval.py          # 第一步：调用 Agent，收集原始结果
├── score.py             # 第二步：计算评分
├── test_cases.json      # 30 个测试用例
└── cases/
    ├── resume_junior.json    # 应届生简历
    ├── resume_midlevel.json  # 3-5年经验简历
    ├── resume_english.json   # 英文简历
    ├── jd_backend.json       # 后端工程师JD
    ├── jd_product.json       # 产品经理JD
    └── jd_fullstack.json     # 全栈工程师JD
```

## 快速开始

```bash
# 需要在 backend/ 目录下运行（确保 app.* 可被 import）
cd backend

# 设置 API Key
export ANTHROPIC_API_KEY=sk-ant-...

# 第一步：运行 Agent（全部30个用例，约需 10-20 分钟）
uv run python ../eval/run_eval.py --output ../eval/eval_results.json

# 只跑部分用例
uv run python ../eval/run_eval.py --cases TC001,TC002,TC003

# 第二步：计算评分
uv run python ../eval/score.py --input ../eval/eval_results.json --output ../eval/eval_scores.json

# 跳过 LLM-as-Judge（省钱，快速验证）
uv run python ../eval/score.py --input ../eval/eval_results.json --no-llm-judge
```

## 测试用例说明

共 30 个用例，分 6 类场景：

| 类型 | 用例数 | 说明 |
|------|--------|------|
| 应届生简历 × 后端JD | 5 | TC001-005 |
| 中级简历 × 后端JD | 5 | TC006-010 |
| 英文简历 × 全栈JD | 5 | TC011-015 |
| 边界场景 | 5 | TC016-020（无JD/拒绝/删除等）|
| 综合场景 | 10 | TC021-030（格式、风格、追问等）|

## 评分维度解读

### 1. JD 关键词匹配率提升
- 统计修改前后，JD 关键词在简历全文中的覆盖率变化
- delta > 0 表示有改善
- 无 JD 的用例跳过此维度

### 2. 工具调用正确性 (F1)
- `precision` = 实际调用中正确的比例
- `recall` = 期望工具被调用的比例
- F1 = 调和平均，1.0 为满分

### 3. LLM-as-Judge（claude-sonnet-4-6 评审）
- **instruction_follow**（1-5）：是否执行了用户指令
- **quality**（1-5）：优化内容是否专业有说服力
- **no_hallucination**（1-5）：是否基于真实经历，无捏造
- **overall**（1-5）：综合印象分
