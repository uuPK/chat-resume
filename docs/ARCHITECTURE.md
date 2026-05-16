# 架构说明

本文档记录 chat-resume 的当前系统架构、模块边界和关键数据流。

## 系统概览

- 前端：Next.js App Router + React，负责用户界面、状态管理和 API 调用。
- 后端：FastAPI，负责 HTTP API、业务服务、Agent 执行入口和数据库访问。
- Agent 运行时：`backend/app/runtime/` 封装 pi-agent-core / OpenRouter 适配、工具权限、确认队列和恢复逻辑。
- 数据库：本地默认 SQLite，生产使用 PostgreSQL，迁移由 Alembic 管理。
- 日志：请求日志、慢请求、慢 SQL 和 Agent 运行时事件由 `backend/app/infra/logging_setup.py` 与 `backend/app/main.py` 统一处理。

## 目录边界

- `backend/app/entrypoints/http/`：HTTP 路由入口，负责请求/响应适配。
- `backend/app/agents/resume/`：简历 Agent 定义、系统提示词上下文构建和流事件类型。
- `backend/app/services/agent/`：简历 Agent 的 HTTP 外业务编排，包含流式会话、恢复和工具确认。
- `backend/app/runtime/`：Agent harness、权限确认、运行时事件转换、消息转换和超时 session 清理。
- `backend/app/state/`：`AgentSessionStore`、会话事件日志、SSE cursor 回放和 session 快照，支撑确认恢复与回放。
- `backend/app/tools/resume/`：简历 Agent 可调用的业务工具。
- `backend/app/services/`：业务服务，按子域拆分为 `auth/`、`agent/`、`domain/`、`interview/`、`llm/`、`processing/`、`voice/`、`digital_human/` 等。
- `backend/app/models/`：SQLAlchemy 数据模型。
- `backend/app/schemas/`：Pydantic 请求和响应结构。
- `backend/app/infra/`：基础设施，包括 config、database、logging、security、request_context。
- `backend/app/evals/`：Agent eval 相关。
- `backend/app/prompts/`：提示词模板。
- `backend/app/types/`：共享类型定义。
- `backend/app/utils/`：通用工具函数。
- `frontend/src/app/`：页面和路由。
- `frontend/src/components/`：UI 与业务组件。
- `frontend/src/hooks/`：页面级业务 hooks，例如流式聊天、自动保存、面试 session 和分栏布局。
- `frontend/src/lib/`：前端 API、状态和工具函数。
- `frontend/src/i18n/`：国际化路由和配置。
- `frontend/src/types/`：前端共享类型定义。

## HTTP 边界

后端所有业务 API 通过 `backend/app/entrypoints/http/router.py` 聚合到 `/api`：

- `/api/auth`：邮箱密码登录、Google OAuth、Cookie 会话刷新和登出。
- `/api/resumes`：简历列表、详情、创建、更新、删除、布局保存和聊天记录。
- `/api/resumes/{id}/export`：简历导出（生成下载 token）和下载（HMAC token 验签）。
- `/api/upload`：简历后台解析任务与 JD 图片 OCR。
- `/api/ai`：简历 Agent SSE 对话、工具确认和暂停 session 恢复。
- `/api/interviews`：结构化面试 session 的创建、读取、消息持久化、结束和删除。
- `/api/digital-human`：语音/数字人供应商会话创建和 WebSocket 代理。
- `/api/tts`：文本转语音。
- `/api/asr`：语音转文本。
- `/api/billing`：PayPal 订阅状态、checkout 和 webhook。
- `/api/users`：用户信息。

`backend/app/main.py` 的鉴权中间件会在进入受保护 API 前统一校验 Bearer token 或 HttpOnly access-token Cookie。`/api/resumes/download` 和 `/api/billing/paypal/webhook` 是显式豁免路径。

## 认证与会话

- 登录和刷新由 `backend/app/entrypoints/http/auth.py` 签发 access token，并通过 `RefreshSessionService` 在数据库保存 refresh session。
- 浏览器侧 `frontend/src/lib/auth.tsx` 缓存当前用户到 `localStorage`，真实鉴权凭据仍依赖后端设置的 HttpOnly Cookie。
- 前端路由保护由 `frontend/src/proxy.ts` 处理，受保护页面包括 `/dashboard`、`/settings`、`/interviews`、`/resume` 和 `/resumes`。公开页面包括 `/login`、`/register`、`/` 和 `/resume/print`。鉴权校验通过后端 `/api/auth/me` 验证 token 真伪。
- 后端受保护 API 不信任前端状态，统一在中间件中把当前用户写入 `request.state.current_user`。

## 简历主链路

1. 前端通过 `ResumeAPI.uploadResume()` 调用 `/api/upload/resume`。
2. 后端创建 `ResumeUploadJob`，后台任务 `process_resume_upload_job()` 负责抽取文本、调用 `ResumeParser`、写入 `Resume`。
3. 前端轮询 `/api/upload/resume-jobs/{job_id}`，完成后进入 `/resume/{id}/edit`。
4. 编辑页通过 `useResumeEditor()` 管理结构化表单，通过 `useResumeAutoSave()` 保存内容。
5. 预览与导出依赖 `frontend/src/components/preview/` 和 `/api/resumes/{id}/export`。

## 简历 Agent 链路

简历 Agent 当前只服务简历优化，不再承载面试聊天入口。`ResumeAgentStreamService.ensure_stream_supported()` 会拒绝 `agent_type=interview` 或 `is_interview=true` 的旧调用，并提示使用 `/api/interviews`。

一次简历 Agent 流式会话的真实路径是：

1. `POST /api/ai/chat/stream` 进入 `chat_with_resume_stream()`。
2. `ResumeAgentStreamService.stream_events()` 读取当前用户简历，并按 `visible_modules` 裁剪传给 Agent 的上下文。
3. `AgentHarness.create_resume_session()` 在 `AgentSessionStore` 中创建 session，随后 `run_resume_stream()` 驱动 `ResumeAgent`（定义在 `backend/app/agents/resume/`）和 `backend/app/tools/resume/` 工具。
4. 所有公开 SSE 事件会通过 `AgentSessionStore.append_stream_event()` 写入 `agent_events`，并分配 `event_id={session_id}:{sequence}`。
5. 工具需要用户确认时，运行时通过 `confirmation_manager` 暂停等待，前端调用 `/api/ai/chat/confirm-tool` 确认或拒绝。
6. 如果确认到达时原 SSE 连接已结束，后端把 session 标记为 `paused`，前端可调用 `/api/ai/chat/resume-session` 恢复。
7. 流结束后，服务只在简历内容确实变化时调用 `ResumeService.update()` 落库。

SSE 断点续传由同一个 `/api/ai/chat/stream` 入口处理：请求头带 `Last-Event-ID` 时，后端不新建 Agent 运行，而是校验 session 归属并回放该 cursor 之后的 `stream_event`。

## 面试链路

面试主链路已经拆成结构化 session 和供应商语音代理：

- `/api/interviews` 负责本地面试 session、轮次、最终文本和结束状态。
- `/api/digital-human/conversations` 根据 `DIGITAL_HUMAN_PROVIDER` 创建供应商会话。当前 `volcengine` 分支返回本地 interview session id 作为语音会话 id。
- `/api/digital-human/voice-session/{session_id}` 是前端语音房间使用的 WebSocket 代理，前端页面位于 `frontend/src/app/[locale]/resume/[id]/interview/page.tsx`。
- 前端 `useInterviewSession()` 是创建或加载面试 session 的稳定入口。

## 支付与权限

- 订阅由 `backend/app/entrypoints/http/billing.py` 和 `backend/app/services/paypal_billing_service.py` 管理。
- 需要付费权限的接口使用 `require_active_subscription`，目前覆盖简历上传和创建面试/数字人会话等高成本动作。
- PayPal webhook 是鉴权豁免路径，但需要用 PayPal webhook id/签名配置完成供应商侧验证。

## 部署与运行

- 本地启动入口是根目录 `./restart.sh`，单独启动可用 `./backend.sh` 和 `./frontend.sh`。
- 后端数据库迁移使用 `cd backend && uv run alembic upgrade head`。
- Railway 部署由后端启动命令处理数据库迁移，FastAPI 应用本身不在 `startup` 里跑迁移。
- `backend/app/state/replay.py` 负责把持久化事件还原成历史列表，`snapshot.py` 负责把事件历史归约成轻量 session 快照。
- 前端通过 `NEXT_PUBLIC_API_URL` 指向后端 API；后端 CORS 通过 `BACKEND_CORS_ORIGINS` 和 `FRONTEND_URL` 共同决定有效 origin。
