# 前端 Demo 验收清单

本文档用于支撑中文 README、3 分钟 Demo 脚本和截图/GIF 采集。重点展示 `chat-resume` 作为 ReAct Agent 项目的真实前端闭环，而不是普通简历编辑器。

## Demo 主线

目标：用一条完整链路证明系统具备 `目标输入 -> Agent 工具调用 -> JD 匹配摘要 -> diff 确认 -> 简历更新` 的闭环。

当前事实边界：代码里只保留一个 JD 分析工具 `generate_job_match_summary`。它返回 `matched_keywords`、`missing_keywords`、`resume_changes`、`fact_gaps` 和 `top_gaps`；前端“岗位匹配摘要”优先展示 Top gaps 行动建议，并保留命中/缺失关键词作为二级信息。

建议 3 分钟 Demo 顺序：

1. 进入简历编辑页，展示左侧结构化编辑、中间预览、右侧 Agent 对话的三栏工作台。
2. 在目标岗位弹窗或岗位信息区粘贴 Agent 开发工程师 JD。
3. 发送或触发“分析简历与目标岗位匹配情况”的请求。
4. 展示 Agent 工具状态：`Running/Ran generate_job_match_summary`。
5. 展示“岗位匹配摘要”卡片，重点停留在“优先补强 Top 3”区域。
6. 展示 Agent 生成的结构化 diff 确认卡，用户点击确认修改。
7. 展示简历内容更新，并说明可重新跑匹配进入下一轮。

## 推荐演示数据

JD 应包含清晰的 Agent 工程关键词，便于 Top gaps 和 diff 建议稳定出现。

推荐 JD 片段：

```text
岗位：AI Agent 开发工程师

职责：
1. 负责基于 LLM 的 Agent 应用开发，设计 tool calling、workflow orchestration 和 human-in-the-loop 机制。
2. 构建 RAG、LlamaIndex、LangChain 或自研工具链，支持复杂任务分解和结果校验。
3. 熟悉 FastAPI、React、SSE 流式输出，能把 Agent 推理、工具调用和执行结果可视化。
4. 熟悉 MySQL、Redis、RabbitMQ 等工程基础设施。
```

简历应至少包含一个可承接补强的项目，例如 `Deep Research Agent`、`Chat Resume` 或类似 Agent 项目。否则 JD 摘要会出现较多缺失关键词，后续 diff 也更容易进入需要用户补充真实事实的状态。

## 必拍页面状态

### 1. 工作台全景

路由：`/zh/resume/{id}/edit`

画面要点：

- 左侧：简历结构化编辑区。
- 中间：简历预览区。
- 右侧：`简历智能体` 对话区。
- 顶部或按钮区可见导出、布局设置等工作台能力。

用途：证明这不是单一 chat demo，而是完整简历编辑工作台。

### 2. JD 输入状态

触发方式：

- 新建或上传简历后进入 first-run 状态；或在编辑区的目标岗位/JD 字段手动填写。

画面要点：

- 目标公司、目标岗位、JD 文本输入。
- `开始分析` 按钮。

用途：展示 Agent 的目标来自真实 JD，而不是硬编码 prompt。

### 3. 工具调用状态

触发方式：

- 发送“请分析我的简历与目标岗位的匹配情况...”
- 或 first-run 自动发送同类请求。

画面要点：

- 工具调用活动卡片显示工具执行状态。
- 当前实现中只应出现 `generate_job_match_summary`。
- 不要在 Demo 话术中声称调用了独立 `analyze_jd_top_gaps` 工具；Top gaps 是 `generate_job_match_summary` 的结构化返回字段。

用途：证明前端可观测真实 tool call / tool result，不是只展示最终文本。

### 4. JD 匹配摘要卡片

组件：`JobMatchSummaryCard`

画面要点：

- 标题：`岗位匹配摘要`
- 指标：命中率、命中数量、缺失数量。
- 主区：`优先补强 Top 3`。
- 每个 gap 包含缺口名称、风险标签、优先级原因、建议位置、建议补法和 JD 证据。
- 二级信息：命中关键词列表、缺失关键词列表。

用途：展示一个 JD 工具从真实 JD 和简历正文中生成“匹配总览 + 优先补强建议”，但不把它包装成完整语义匹配。

### 5. Diff 确认卡

触发方式：

- Agent 调用 `update_bullet`、`add_bullet` 或类似修改工具后进入 `tool_pending`。

画面要点：

- 修改摘要。
- 改前 / 改后内容。
- 修改理由。
- `确认修改` / `拒绝` 按钮。

用途：展示 human-in-the-loop confirmation gate，证明系统不会让 Agent 直接写简历。

### 6. 确认后状态

画面要点：

- 工具确认成功状态。
- 简历预览中出现已确认的新表达。
- Agent 回复“已应用修改”或同类完成文案。

用途：展示闭环完成：用户确认后才持久化修改。

## GIF 脚本

建议录 20-30 秒 GIF，覆盖以下动作：

1. 粘贴 Agent 工程师 JD。
2. 点击 `开始分析` 或发送分析请求。
3. 等待工具调用卡片出现。
4. 停留在 `优先补强 Top 3`。
5. 展示 diff 卡并点击 `确认修改`。
6. 简历预览内容变化。

如果只录 10 秒短 GIF，优先保留第 3-5 步。

## 验收标准

Demo 前应确认：

- 页面使用中文 locale：`/zh/...`。
- 工作台三栏布局在 1440px 宽度下不重叠。
- JD 输入框、Agent 对话输入、岗位匹配摘要卡片和 diff 确认按钮均可见。
- `岗位匹配摘要` 可显示命中率、命中数量、缺失数量、Top gaps、命中关键词和缺失关键词。
- Top gaps 最多 3 条，每条包含原因、建议位置和 JD 证据。
- Demo 只声称一个 JD 工具返回 Top gaps，不声称存在第二个 JD 工具。
- Agent 修改必须经过确认按钮，不能直接静默写入。
- README 中测试结果只写已真实验证的命令，不写未跑过的 Playwright 全量覆盖。

## 当前风险

- 当前 `generate_job_match_summary` 的 Top gaps 仍是轻量规则和能力归并，不是完整语义模型判断。
- 如果简历没有可承接的真实项目，Top gaps 会出现“需要确认/缺少证据”，这是正确安全行为，但不适合作为最亮眼 Demo。
- 当前截图应避免把轻量关键词摘要讲成完整语义匹配。

## 与其他任务的交付边界

- task #15 README 主稿可引用本文档的 Demo 主线、架构页面状态和验收标准。
- task #17 Demo 脚本可引用本文档的 3 分钟顺序和 GIF 脚本。
- task #18 技术事实核对应重点检查本文档中的工具名、路由、测试命令和能力边界。
