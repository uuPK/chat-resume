# 可靠性说明

本文档记录系统可靠性目标、已知风险和故障处理策略。

## 关键链路

- 登录与刷新：后端 HttpOnly Cookie + 数据库 refresh session，前端只缓存用户快照。
- 简历上传解析：`/api/upload/resume` 返回后台 job，解析结果通过 `/api/upload/resume-jobs/{job_id}` 查询。
- 简历编辑保存：结构化内容和布局配置分别走 `/api/resumes/{id}` 与 `/api/resumes/{id}/layout`。
- 简历 Agent：`/api/ai/chat/stream` SSE 流、`/api/ai/chat/confirm-tool` 工具确认、`/api/ai/chat/resume-session` 暂停恢复。
- 语音面试：`/api/interviews` 管本地 session，`/api/digital-human` 管供应商会话和 WebSocket。
- 支付权限：高成本动作通过 `require_active_subscription` 阻断，PayPal webhook 独立豁免鉴权。

## 失败模式与处理

- 401/403：先区分页面保护和 API 鉴权。页面保护看 `frontend/src/proxy.ts`，API 鉴权看 `backend/app/main.py` 的 `authenticate_protected_api_requests()`。
- 404/422 出现在简历编辑页：优先检查路由参数是否被解析成非法 ID，避免 `/api/resumes/NaN` 这类请求进入后端。
- 简历上传卡住：查 `ResumeUploadJob.status`，再查 `resume_upload.job.failed`、`resume_upload.completed` 和当前 job id。
- JD OCR 失败：供应商 403/TOS 会被压缩成固定错误文案，先检查 `OPENROUTER_VISION_MODEL` 是否支持图片输入。
- Agent 输出中断：前端应带 `Last-Event-ID` 回放，后端从 `agent_events` 中的 `stream_event` 读取 cursor 之后的事件。
- 工具确认冲突：409 通常表示 call id 已过期、session 不在 `waiting_confirmation`，或 pending 事件和前端按钮不匹配。
- 确认后连接已断：后端返回 `resumable` 时不要重复确认同一个工具，应调用 resume-session。
- 面试无声音或无回复：先区分 `/api/interviews` session 是否正常、`/api/digital-human/conversations` 是否返回 session id、WebSocket 是否连接成功。
- 导出失败：先验证编辑页保存是否成功，再看导出接口、打印路由和浏览器控制台。

## SSE cursor 可靠性约定

当前 SSE 断点续传是“事件日志回放”，不是“重新运行 Agent”。

- 服务端在公开事件发给浏览器前调用 `AgentSessionStore.append_stream_event()`，事件序号来自 `AgentEvent.sequence`。
- SSE 文本块包含 `id: {session_id}:{sequence}`，JSON payload 也包含同一个 `event_id`。
- `Last-Event-ID` 只能回放同一用户拥有的 session；session 不存在或不属于当前用户时返回 404。
- 回放时会移除 `observability` 字段，避免把内部观察数据暴露给前端。
- 前端只尝试一次 cursor 回放，避免网络抖动时进入无限重连循环。

修改这条链路时，至少覆盖：

```bash
cd backend
uv run --extra dev python -m pytest tests/test_agent_session_store.py tests/test_resume_agent_sse_cursor.py -q
```

## 降级策略

- OpenRouter 未配置：`/api/ai/status` 返回 mock/not_configured，前端应展示不可用状态，不应伪造成功优化。
- Resume Agent 异常：SSE 返回 `error` 事件，后端记录 `Resume agent stream failed`。
- 外部语音供应商不可用：`digital_human.py` 返回 502/503，面试 session 仍保留在本地，可重试创建供应商会话。
- PayPal 不可用：订阅 checkout/status 失败不应影响已登录用户查看已有简历。
- 可观测性后端未启动：业务 API 仍应运行；本地排障时再启动 `docker-compose.observability.yml`。

## 日志与追踪

- 所有 HTTP 请求都会获得 `X-Request-ID`。
- 未处理异常会记录 `request.failed`，响应体包含相同 `request_id`。
- 慢请求和错误请求会记录 `request.finished`，包含 DB checkout/query 次数和耗时。
- Agent 流式会话通过 `log_context()` 绑定 `request_id` 和 `session_id`。
- Langfuse/LangSmith observer 在 `ResumeAgentStreamService` 中按 run id 记录简历 Agent 运行。
- Prometheus 指标从 `/metrics` 暴露，本地 Grafana/Loki/Tempo 入口见 `docs/OBSERVABILITY.md`。

## 验证命令

后端最小回归：

```bash
cd backend
uv run --extra dev python -m pytest tests -q
```

后端类型检查：

```bash
cd backend
uv run basedpyright
```

前端最小回归：

```bash
cd frontend
npm run type-check
npm run build
```

端到端：

```bash
cd frontend
npm run e2e
```

不要用 Ruff、Black 或通用 lint 作为本仓库默认质量门禁。
