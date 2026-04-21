# ARCHITECTURE.md

## 1. 分层（必须遵守）

本项目是一个前后端分离的 AI 求职应用，主链路包含：认证、简历解析与编辑、Resume Agent 流式改写、结构化模拟面试、导出与语音能力。

### 1.1 总体分层

#### 前端分层

1. 页面层：`frontend/src/app`
   - 负责路由、页面装配、鉴权跳转、页面级状态拼装。
   - 不直接写底层 `fetch` 细节，不直接持有复杂业务协议解析逻辑。

2. 交互编排层：`frontend/src/hooks`
   - 负责把页面行为组织成可复用业务 Hook。
   - 例如：简历加载与自动保存、Agent 聊天流、结构化面试 session 生命周期。

3. 组件层：`frontend/src/components`
   - 负责界面展示和局部交互。
   - 组件优先接收数据和回调，不自己承担跨页面业务编排。

4. 数据访问层：`frontend/src/lib`
   - 负责 API 调用、鉴权上下文、TTS/ASR 封装、布局配置持久化。
   - 页面和 Hook 统一通过这里访问后端。

5. 类型层：`frontend/src/types`
   - 负责前端领域对象类型定义，保证编辑器、预览、Agent 面板使用同一份数据结构。

#### 后端分层

1. 接入层：`backend/app/main.py`、`backend/app/entrypoints/http`
   - 负责 FastAPI 启动、中间件、路由注册、鉴权接入、请求参数校验、响应组装。
   - 不承载复杂业务规则。

2. 应用服务层：`backend/app/services`
   - 负责具体业务编排。
   - 包含简历 CRUD、文件处理、解析、导出、面试 session 推进、语音服务、LLM 调用等。

3. Agent 层：`backend/app/agents`、`backend/app/runtime`、`backend/app/tools`、`backend/app/prompts`
   - 负责 Prompt 构造、运行时循环、工具调用、流式事件输出、人工确认和恢复机制。
   - Resume Agent 与 Interview Agent 共用运行时抽象，但业务策略不同。

4. 状态持久化层：`backend/app/state`
   - 负责 Agent session、事件日志、快照与回放。
   - 为“工具 diff 确认后继续执行”提供持久化基础。

5. 领域模型与协议层：`backend/app/models`、`backend/app/schemas`、`backend/app/types`
   - `models` 负责数据库表结构。
   - `schemas` 负责 API 输入输出和结构化简历协议。
   - `types` 负责 Agent/runtime 事件与会话类型。

6. 基础设施层：`backend/app/infra`
   - 负责配置、数据库、日志、Sentry、Langfuse、安全、请求上下文。
   - 为其余各层提供技术能力，不承载业务决策。

### 1.2 依赖规则

必须遵守以下依赖方向：

1. 前端页面层只能依赖 Hook、组件、`lib`、`types`。
2. 前端组件层不直接访问后端 API，统一经由页面或 Hook 注入数据。
3. 后端 `entrypoints/http` 只能向下依赖 `schemas`、`services`、`state`、`infra`，不能反向依赖前端概念。
4. 后端 `services` 不依赖 FastAPI 路由对象，不直接处理 HTTP 细节。
5. 后端 `agents` 通过 `runtime` 和 `tools` 完成执行，不直接操作 HTTP 请求响应。
6. 后端 `state` 只负责 Agent 执行状态持久化，不写页面或业务展示逻辑。
7. `infra` 为最外层公共能力，可被其他层依赖，但不能反向依赖业务层。

### 1.3 当前落地结构

```text
Frontend
app -> hooks -> lib -> backend API
app -> components
components -> types

Backend
main -> entrypoints/http -> services -> models
                         -> services -> agents/runtime/tools -> state
                         -> schemas
all layers -> infra
```

## 2. 模块职责

### 2.1 前端模块

| 模块 | 职责 |
| --- | --- |
| `frontend/src/app/resumes/page.tsx` | 简历中心，负责展示简历列表、上传入口、创建入口。 |
| `frontend/src/app/resume/[id]/edit/page.tsx` | 简历编辑工作台，组装编辑器、预览、Resume Agent、结构化面试面板。 |
| `frontend/src/app/interviews/page.tsx` | 面试中心，负责新建面试、读取历史面试记录、删除 session。 |
| `frontend/src/app/resume/[id]/interview/page.tsx` | 面试工作台，负责承接结构化问答与简历/JD 辅助视图。 |
| `frontend/src/hooks/useResumeEditor.ts` | 管理简历加载、布局配置、自动保存、导出、一页适配。 |
| `frontend/src/hooks/useResumeChatPanel.ts` | 管理简历 Agent 面板的消息状态、历史记录、发送与清空。 |
| `frontend/src/hooks/useStreamingChat.ts` | 解析后端 SSE，处理流式文本、`tool_pending`、确认结果和简历回写。 |
| `frontend/src/hooks/useInterviewSession.ts` | 管理结构化面试 session 的创建、启动、答题、提示、结束和评估轮询。 |
| `frontend/src/lib/api.ts` | 前端统一 API 门面，封装简历、聊天、面试、导出、OCR 等请求。 |
| `frontend/src/lib/auth.tsx` | 管理前端登录态、当前用户信息和鉴权上下文。 |
| `frontend/src/components/editor/*` | 结构化简历各模块编辑器。 |
| `frontend/src/components/preview/*` | 简历预览、分页渲染、布局控制。 |
| `frontend/src/components/interview/StructuredInterviewPanel.tsx` | 面试 UI 展示层，负责题目、回答、提示、评估的界面呈现。 |

### 2.2 后端接入层

| 模块 | 职责 |
| --- | --- |
| `backend/app/main.py` | 应用入口，负责中间件、CORS、受保护 API 鉴权、健康检查、路由挂载。 |
| `backend/app/entrypoints/http/router.py` | 聚合全部 HTTP 路由。 |
| `backend/app/entrypoints/http/auth.py` | 注册、登录、刷新、登出、当前用户信息。 |
| `backend/app/entrypoints/http/resumes.py` | 简历 CRUD、布局配置保存、聊天记录接口。 |
| `backend/app/entrypoints/http/upload.py` | 简历文件上传解析、JD 图片 OCR。 |
| `backend/app/entrypoints/http/resume_agent.py` | Resume Agent SSE 流式入口、工具确认入口、session 恢复入口。 |
| `backend/app/entrypoints/http/interviews.py` | 结构化面试的创建、启动、回答、流式回答、提示、报告。 |
| `backend/app/entrypoints/http/export.py` | 导出 PDF/DOCX/HTML 等文件。 |
| `backend/app/entrypoints/http/tts.py` / `asr.py` | 语音播放与语音识别入口。 |
| `backend/app/entrypoints/http/deps.py` | 统一数据库依赖和当前用户解析逻辑。 |

### 2.3 后端服务层

| 模块 | 职责 |
| --- | --- |
| `backend/app/services/domain/resume_service.py` | 简历持久化、内容序列化、删除关联数据。 |
| `backend/app/services/domain/file_service.py` | 上传文件保存、文本提取、文件清理。 |
| `backend/app/services/domain/user_service.py` | 用户查询、注册、认证、更新。 |
| `backend/app/services/domain/refresh_session_service.py` | 刷新令牌 session 生命周期管理。 |
| `backend/app/services/processing/resume_parser.py` | 将上传文本解析为结构化简历 JSON。 |
| `backend/app/services/processing/export_service.py` | 把结构化简历渲染为导出产物。 |
| `backend/app/services/processing/jd_ocr_service.py` | 从 JD 图片中提取文字。 |
| `backend/app/services/interview/session_service.py` | 结构化面试主编排，负责创建 session、出题、收答、结束、流式返回。 |
| `backend/app/services/interview/planning_service.py` | 为面试构造轮次计划、提示词片段和追问策略。 |
| `backend/app/services/interview/evaluation_service.py` | 生成问题、评估回答、沉淀报告。 |
| `backend/app/services/interview/serializer.py` | 把面试 ORM 对象转换为前端稳定响应结构。 |
| `backend/app/services/llm/chat_service.py` | 对接大模型聊天能力。 |
| `backend/app/services/voice/*.py` | TTS 与 ASR 的供应商适配。 |
| `backend/app/services/memory/user_memory_service.py` | 为 Agent 读写用户长期偏好和记忆。 |

### 2.4 Agent 与运行时模块

| 模块 | 职责 |
| --- | --- |
| `backend/app/agents/resume/agent.py` | 简历优化 Agent 入口，组合 Prompt、运行时和工具执行器。 |
| `backend/app/agents/resume/executor.py` | 执行简历修改工具并生成 diff、错误结果和回写结果。 |
| `backend/app/agents/resume/prompt_context.py` | 裁剪和构造简历 Agent 的提示词上下文。 |
| `backend/app/agents/interview/agent.py` | 面试官 Agent 入口，负责追问和提示生成。 |
| `backend/app/runtime/loop.py` | 通用 Agent 运行时循环，处理 prompt、模型调用、工具迭代和流式事件。 |
| `backend/app/runtime/harness.py` | 把 Resume Agent 执行和 `state` 持久化编排到一起。 |
| `backend/app/runtime/recovery.py` | 从已落库的 session / event 恢复 Agent 执行。 |
| `backend/app/runtime/permissions.py` | 约束运行时可执行动作。 |
| `backend/app/tools/resume/*` | 对结构化简历的细粒度读取和编辑工具，如读取简历、更新亮点、写用户记忆。 |
| `backend/app/prompts/resume_agent` / `interviewer_agent` | Agent Prompt 模板与配置。 |

### 2.5 状态、模型与基础设施模块

| 模块 | 职责 |
| --- | --- |
| `backend/app/state/models.py` | 定义 `agent_sessions`、`agent_events` 表。 |
| `backend/app/state/store.py` | 提供 Agent session / event 的统一读写接口。 |
| `backend/app/state/snapshot.py` / `replay.py` | 为恢复和重放提供快照/回放能力。 |
| `backend/app/models/resume.py` | 定义简历、优化记录、聊天消息表。 |
| `backend/app/models/interview.py` | 定义面试 session / turn 表。 |
| `backend/app/models/user.py` / `refresh_session.py` | 定义用户与刷新会话表。 |
| `backend/app/schemas/resume.py` | 统一结构化简历协议、前后端序列化与导出字段。 |
| `backend/app/schemas/auth.py` / `export.py` | 认证与导出接口协议。 |
| `backend/app/infra/config.py` | 统一配置来源。 |
| `backend/app/infra/database.py` | SQLAlchemy Engine、Session、Base。 |
| `backend/app/infra/security.py` | JWT、密码哈希等安全能力。 |
| `backend/app/infra/logging_setup.py` / `request_context.py` | 请求日志和 request/session/tool call 上下文。 |
| `backend/app/infra/sentry_setup.py` / `langfuse_*` | 错误监控与 Agent 观测。 |

## 3. 数据流

### 3.1 登录鉴权流

1. 前端登录页调用 `POST /api/auth/login`。
2. `auth.py` 校验邮箱密码，并通过 `RefreshSessionService` 创建刷新会话。
3. 后端把 access token 和 refresh token 写入 HttpOnly Cookie。
4. 前端后续通过 `credentials: 'include'` 访问 API。
5. `main.py` 的鉴权中间件和 `deps.py` 从 Header/Cookie 解析令牌，并把当前用户写入 `request.state`。

### 3.2 简历上传与解析流

1. 前端在简历中心上传文件，`frontend/src/lib/api.ts` 调用 `POST /api/upload/resume`。
2. `upload.py` 校验扩展名，调用 `FileService` 保存临时文件并提取文本。
3. `ResumeParser` 把原始文本转换为结构化简历 JSON。
4. `ResumeService` 将结果写入 `resumes.content`。
5. 前端跳转到编辑页，后续全部围绕结构化 JSON 编辑，而不是继续编辑原始文件。

### 3.3 简历编辑与自动保存流

1. 编辑页 `page.tsx` 通过 `useResumeEditor` 拉取 `GET /api/resumes/{id}`。
2. 用户在各编辑组件中修改字段，更新本地 `resume.content` 草稿。
3. `useResumeAutoSave` 负责脏状态跟踪和防抖保存。
4. 前端调用 `PUT /api/resumes/{id}` 或 `PUT /api/resumes/{id}/layout`。
5. `resumes.py` 做权限校验，`ResumeService` 更新数据库。
6. 预览组件基于同一份结构化内容实时重渲染。

### 3.4 Resume Agent 流式改写流

1. 用户在编辑页 Agent 面板输入问题，`useResumeChatPanel` 会先触发自动保存，再调用 `useStreamingChat`。
2. 前端向 `POST /api/ai/chat/stream` 发送当前消息、聊天历史、`resume_id` 和当前可见模块。
3. `resume_agent.py` 读取目标简历，按可见模块裁剪上下文，创建 `session_id` 和确认队列。
4. `AgentHarness.create_resume_session()` 在 `agent_sessions` / `agent_events` 中写入会话起点。
5. `ResumeAgent.optimize_stream()` 通过 `AgentRuntime` 驱动模型推理。
6. 当模型调用工具时，`backend/app/tools/resume/*` 先产出 diff 预览，而不是直接静默落库。
7. 运行时发出 `tool_pending` 事件，前端展示 diff 卡片并等待用户确认。
8. 前端点击确认/拒绝后，调用 `POST /api/ai/chat/confirm-tool`。
9. 后端把确认结果写入 `agent_events`，运行时继续执行；若确认通过，则最新 `resume_content` 继续沿 SSE 返回。
10. 流结束后，若简历内容发生变化，`ResumeService.update()` 将最终结构化内容落库。
11. 前端收到最终 `resume_content` 后刷新预览，并把完整消息及工具事件写入聊天历史。

### 3.5 结构化面试流

1. 面试中心或编辑页调用 `POST /api/interviews/` 创建 session。
2. `session_service.create_interview_session()` 从简历中的 `job_application` 和结构化内容构造面试计划 `plan_json`。
3. 前端调用 `POST /api/interviews/{id}/start` 获取第一题。
4. 用户回答后，前端调用 `POST /api/interviews/{id}/answer/stream`。
5. `session_service` 读取简历、历史轮次和计划，调用 `InterviewerAgent` 生成下一题或追问。
6. 回答评估结果与下一题分阶段返回给前端；必要时进入评估轮询补全。
7. 面试结束后，服务层写入 `report_data`，前端通过 `GET /api/interviews/{id}/report` 或最终 session 结果展示报告。

### 3.6 导出与语音流

#### 导出流

1. 编辑页触发导出。
2. 前端调用导出接口。
3. `export.py` -> `processing/export_service.py` 把结构化简历生成 PDF/DOCX/HTML。
4. 后端返回下载地址，前端直接下载文件。

#### 语音流

1. 前端通过 `frontend/src/lib/tts.ts`、`asr.ts` 调用语音接口。
2. 后端 `tts.py` / `asr.py` 转给 `services/voice` 中的供应商适配实现。
3. 语音结果回到前端，作为面试或朗读能力的辅助输入输出。

### 3.7 当前系统的核心事实

1. 系统的唯一业务真源是结构化简历 JSON，而不是原始上传文件。
2. Resume Agent 的核心能力不是“生成一段建议文本”，而是“基于工具直接修改结构化简历，并在用户确认后落库”。
3. 面试模块已经从旧聊天式入口迁移到 `/api/interviews` 结构化链路。
4. 认证主路径依赖 HttpOnly Cookie，因此前端所有受保护请求都必须携带 `credentials: 'include'`。
5. Agent 可观测性依赖 request_id、session_id、tool_call_id 在日志、Langfuse 和 state 事件中的贯通。
