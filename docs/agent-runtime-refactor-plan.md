# Agent Runtime 改造精简方案

## 目标

把当前 `ResumeAgent + AgentRuntime + ResumeTools + SSE 确认` 的实现，升级为更可恢复、可观测、可扩展的轻量 Managed Agent 架构。

本方案不追求一次性引入重型多 Agent 或 Docker 沙箱。优先补齐当前系统最薄弱的三件事：

1. Session 与 Event Log：让任务状态独立于单次请求。
2. Harness：把 Agent 调度流程从业务路由中收拢。
3. Tool 协议：让工具调用、失败、重试、前端展示有统一结构。

## 当前判断

当前实现已经有几个好的基础：

- `AgentRuntime` 已经把通用 ReAct 循环从 `ResumeAgent` 中拆出。
- `ResumeAgent` 已经通过 `AgentDefinition` 注入 prompt、tools schema、tool executor。
- 流式模式已有 `tool_pending -> confirm/reject -> tool_confirmed` 的人工确认链路。
- `ResumeTools` 已经按结构化 JSON 做精准修改，而不是让模型直接改全文。

主要问题是：

- 流程状态仍绑定在一次 HTTP/SSE 请求里，中断后不可恢复。
- 工具调用失败缺少统一错误协议，容易冒泡成 500 或 Python TypeError。
- 事件没有持久化，前端展示、调试、回放、恢复没有统一事实来源。
- 非流式、流式、确认、proposal 创建等逻辑分布在 endpoint 和 runtime 中，后续扩展多 Agent 会变复杂。

## 目标架构

采用四层结构：

```text
Client Layer
  前端页面 / SSE / API

Agent Runtime Layer
  AgentHarness / AgentRuntime / Planner-style prompt

Execution Layer
  ToolExecutor / BaseTool / Sandbox interface

State Layer
  AgentSession / AgentEvent / Checkpoint
```

核心原则：

- 模型只做决策，不直接改状态。
- 工具只做执行，统一返回结构化结果。
- 状态只写入 Session/Event Store，前端展示和恢复都从事件来。

## 数据模型

### AgentSession

表示一次可恢复的 Agent 任务。

建议字段：

```text
id
user_id
resume_id
task_type
status
current_step
created_at
updated_at
completed_at
failed_reason
```

`status` 建议值：

```text
created
running
paused
waiting_confirmation
failed
completed
cancelled
```

### AgentEvent

表示任务中的每个关键动作。

建议字段：

```text
id
session_id
sequence
event_type
source
payload
created_at
```

第一阶段建议支持这些事件：

```text
user_message
agent_response_delta
agent_response
tool_call_started
tool_call_previewed
tool_call_confirmed
tool_call_rejected
tool_call_finished
tool_call_failed
checkpoint_saved
session_failed
session_completed
```

## Tool 协议

新增统一结果结构，所有工具都返回同一种 envelope：

```json
{
  "success": true,
  "tool_name": "update_overview",
  "data": {},
  "error": null,
  "display_message": "项目经历 / xxx 修改摘要...",
  "metadata": {
    "updated_section": "projects",
    "recoverable": false
  }
}
```

失败时：

```json
{
  "success": false,
  "tool_name": "update_overview",
  "data": null,
  "error": {
    "type": "missing_required_argument",
    "message": "缺少必填参数 section",
    "recoverable": true
  },
  "display_message": "工具参数不完整，请重新生成 update_overview 调用。",
  "metadata": {
    "expected_arguments": ["section", "item_id", "overview"]
  }
}
```

重试规则：

- 可确定的默认值本地修复，例如 `update_overview` 缺 `section` 时补 `"projects"`。
- 不可确定的参数不猜，例如 `item_id`、`highlight_id`。
- 可恢复错误写入 `tool_call_failed` 事件，并回填给模型，让下一轮重新生成 tool call。
- 同一工具同类错误连续 2 次后停止重试，返回用户可理解的失败说明。

## AgentHarness

新增 `AgentHarness` 作为统一执行入口，逐步替代 endpoint 中散落的 orchestration 逻辑。

职责：

1. 创建或恢复 `AgentSession`。
2. 写入 `user_message` 事件。
3. 从 EventStore 拉取相关上下文。
4. 调用 `AgentRuntime` 获取模型输出。
5. 执行工具或进入确认等待。
6. 写入 tool 与 response 事件。
7. 更新 session 状态。

简化接口：

```python
class AgentHarness:
    async def run_stream(
        self,
        session_id: str,
        user_message: str,
        resume_content: dict,
    ):
        ...

    async def confirm_tool(
        self,
        session_id: str,
        call_id: str,
        confirmed: bool,
    ) -> dict:
        ...
```

第一阶段可以先让 `AgentHarness` 包住现有 `ResumeAgent.optimize_stream()`，不要急着重写整个 runtime。



## 分阶段路线

### 阶段 1：工具错误可恢复

改动范围最小，优先解决当前 `missing required positional argument` 这类问题。

任务：

- 在 `ResumeAgent._run_tool()` 增加参数校验和异常包装。
- 对 `update_overview` 缺 `section` 自动补 `"projects"`。
- 缺 `item_id`、`overview` 时返回结构化 recoverable error。
- 给非法 JSON、未知工具、隐藏板块分别返回明确错误类型。
- 增加单元测试覆盖。

产出：

- 工具错误不再直接变成 500。
- 模型可以根据 tool error 进行下一轮修正。

### 阶段 2：Session + Event Log

任务：

- 新增 `AgentSession` 和 `AgentEvent` 表。
- 增加 `AgentSessionStore`、`AgentEventStore`。
- 流式接口收到用户消息时创建 session。
- SSE 关键事件先写 EventStore，再推给前端。
- `confirm-tool` 从 session 查找待确认工具，而不是只依赖内存 queue。

产出：

- 能回放一次 Agent 执行过程。
- 断线后可以查询 session 当前状态。

### 阶段 3：AgentHarness

任务：

- 新增 `AgentHarness`。
- 把 `/api/ai/chat/stream` 中的 session、event、tool confirmation 编排迁入 Harness。
- endpoint 只负责鉴权、取简历、调用 Harness、返回 SSE。
- `ResumeAgent` 继续保留业务 prompt 和工具定义。

产出：

- 简历优化和面试 Agent 可以复用同一调度入口。
- 后续增加多角色 agent 不需要复制 endpoint 流程。

### 阶段 4：Checkpoint + Resume

任务：

- 定义 `checkpoint_saved` payload。
- 每次工具确认后保存 checkpoint。
- 增加 `resume_session(session_id)` 能力。
- 前端支持打开未完成 session 并继续确认或取消。

产出：

- 长任务具备断点续跑基础。
- 面试、报告生成、简历优化都能使用同一恢复机制。



任务：

- 定义 `Sandbox` 协议。
- 增加 `LocalSandbox` 轻量实现。
- 将未来高风险工具迁移到 sandbox executor。

产出：

- 决策层与执行环境解耦。
- 后续替换 Docker 或 remote executor 不影响 AgentHarness。

## 面试表达

可以这样讲：

> 这个项目一开始是典型的 Prompt + Tool + SSE 确认链路。我后续把它重构成轻量 Managed Agent 架构：用 AgentRuntime 负责 ReAct 循环，用 AgentHarness 负责编排，用 ToolExecutor 统一工具协议，用 Session/Event Log 管理可恢复状态。模型只负责决策，工具层负责执行，状态层负责记录和恢复。这样工具失败不会直接打穿请求，而是变成可观测、可重试的事件；长任务也可以通过 checkpoint 和 event replay 恢复。

再补一句当前取舍：

> 我没有一开始就上 Docker 沙箱，因为当前核心工具主要是结构化简历 JSON 修改，风险边界较小。我的做法是先抽象 Sandbox 接口，当前用轻量本地实现，后续可以替换成 Docker 或远程 executor。

## 推荐优先级

当前最建议先做：

1. 工具错误结构化与重试。
2. `AgentSession` / `AgentEvent`。
3. `AgentHarness`。
4. Checkpoint。



