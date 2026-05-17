# 可观测性排障说明

本文档记录线上和本地排障时先看哪类日志、用哪些字段关联请求，以及常见问题的 grep 入口。

## 日志入口

- 本地后端日志：`backend/logs/backend.log`
- 后端请求关联：`request_id`
- 前端 AI stream 关联：`client_request_id`
- Resume Agent 会话关联：`session_id`
- 工具调用关联：`tool_call_id` / `call_id`

本地开发默认通过 `backend.sh` 开启 `AGENT_TRACE_LOG_ENABLED=true`，日志写入 `backend/logs/backend.log`。生产环境如果开启 Agent trace，需要先确认日志访问权限和保留策略，因为 trace 可能包含简历或 JD 摘要。

## 常用查询

查看某个前端错误 ID 对应的后端日志：

```bash
rg "client=.*<短ID或完整ID>|client_request_id.*<短ID或完整ID>|<短ID或完整ID>" backend/logs/backend.log
```

查看一次后端请求：

```bash
rg "<request_id>" backend/logs/backend.log
```

查看一次 Resume Agent 会话：

```bash
rg "<session_id>" backend/logs/backend.log
```

查看一次 Agent run 摘要：

```bash
rg "resume_agent.run.summary" backend/logs/backend.log
```

## 常见问题

### 用户看到 AI stream 错误

先让用户提供 UI 中的 `错误ID`。它来自前端生成的 `client_request_id` 短 ID。

```bash
rg "<错误ID>" backend/logs/backend.log
```

重点看：

- `request.failed`：后端未处理异常。
- `request.finished`：错误请求或慢请求的状态码、耗时和 DB 统计。
- `resume_agent.run.summary`：本次 Agent run 的模型、工具次数、确认等待、总耗时和成功状态。
- `openrouter.stream.*`：OpenRouter 慢在连接、首个 SSE、首个 token，还是流式输出阶段。

### AI 看起来卡住或很慢

```bash
rg "resume_agent.run.summary|openrouter.stream" backend/logs/backend.log
```

重点字段：

- `elapsed_ms`：Agent run 总耗时。
- `tool_call_count`：模型实际触发的工具次数。
- `confirmation_wait_ms`：用户确认工具改动等待时间。
- `first_token_latency_ms`：首个模型输出耗时。
- `model`：当前模型。

如果 `confirmation_wait_ms` 很高，优先检查前端确认按钮和 `/api/ai/chat/confirm-tool`。如果 `first_token_latency_ms` 或 `openrouter.stream.first_*_timeout` 异常，优先检查 OpenRouter 网络或模型响应。

### 工具状态显示不对

```bash
rg "resume_agent.sse.tool_event.sent|agent.trace.tool|client=<ID>|client_request_id.*<ID>" backend/logs/backend.log
```

重点字段：

- `event_type`
- `call_id`
- `tool_name`
- `tool_pending`
- `tool_confirmed`
- `tool_rejected`
- `has_result`
- `diff_item_count`

前端详细工具事件日志默认关闭。需要临时打开时设置：

```bash
NEXT_PUBLIC_AI_STREAM_DEBUG=true
```

浏览器本地也可以设置：

```js
localStorage.setItem('ai_stream_debug', 'true')
```

### 后端接口 500

```bash
rg "request.failed|<request_id>" backend/logs/backend.log
```

重点字段：

- `request_id`
- `client_request_id`
- `http_method`
- `http_path`
- `http_route`
- `http_status`
- `user_id`
- `release`
- `error_type`

`request.failed` 会对敏感 query 参数脱敏，响应体也会返回相同的 `request_id`。

### 数据库慢

```bash
rg "db.query.slow|request.finished" backend/logs/backend.log
```

重点字段：

- `db_checkout_count`
- `db_checkout_ms`
- `db_query_count`
- `db_query_ms`
- `db_longest_query_ms`
- `db_longest_query_sql`

如果 `db_checkout_ms` 高，优先看连接池和数据库可用性。如果 `db_query_ms` 高，优先看 `db_longest_query_sql` 和索引。

### 面试报告生成慢或失败

```bash
rg "interview_report" backend/logs/backend.log
```

阶段顺序：

- `interview_report.requested`
- `interview_report.turns_loaded`
- `interview_report.llm.started`
- `interview_report.llm.completed`
- `interview_report.parsed`
- `interview_report.saved`

异常入口：

- `interview_report.invalid_status`
- `interview_report.invalid_json`
- `interview_report.failed`

如果只有 `llm.started` 没有 `llm.completed`，优先检查 OpenRouter。若出现 `invalid_json`，系统会保存保守 fallback 报告，不应让用户流程 500。
