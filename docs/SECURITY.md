# 安全说明

本文档记录 chat-resume 的安全边界、敏感配置、认证授权模型、数据保留策略和第三方服务要求。当前内容基于仓库代码与 `backend/.env.example`、`frontend/.env.example`、`backend/app/infra/config.py`、`backend/app/main.py`、`backend/app/entrypoints/http/deps.py` 的实现。

## 基本原则

- 不在代码、文档、日志或测试夹具中提交真实密钥、令牌、生产密码、OAuth secret、支付 secret。
- 用户简历、JD、面试文本、Agent 对话、导出文件和供应商 trace 都按敏感数据处理。
- 后端受保护 API 不能信任前端登录态；必须依赖服务端 JWT、HttpOnly Cookie、数据库用户状态和资源归属校验。
- 高成本能力必须经过订阅权限检查，不能只靠前端隐藏入口。
- Webhook 和外部回调必须验签、幂等处理，并记录足够的非敏感审计信息。
- 生产环境必须使用非默认 `SECRET_KEY`。`APP_ENV` 不属于 development/dev/local/test/testing 时，默认密钥会阻止应用启动。

## 配置清单

### 必填基础配置

| 配置项 | 位置 | 用途 | 安全要求 |
| --- | --- | --- | --- |
| `APP_ENV` | backend | 区分本地、测试、生产行为 | 生产必须使用明确环境名，避免误走 development 分支 |
| `DATABASE_URL` | backend | SQLAlchemy 主数据库 | 生产使用托管数据库连接串，不能提交凭据 |
| `SECRET_KEY` | backend | JWT、下载链接 HMAC 签名 | 生产必须高熵、非默认、仅服务端保存 |
| `FRONTEND_URL` | backend | OAuth、PayPal、导出回调和 CORS 候选 | 必须是当前前端正式域名 |
| `BACKEND_CORS_ORIGINS` | backend | Cookie 跨域请求白名单 | 生产只列真实前端 origin，禁止使用通配 |
| `NEXT_PUBLIC_API_URL` | frontend | 浏览器访问后端 API 的公开地址 | 只能放公开 URL，不能放 secret |

### 认证与 Cookie

| 配置项 | 用途 | 生产要求 |
| --- | --- | --- |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | access token 有效期，默认 8 天 | 按产品风险评估缩短或配合刷新会话审计 |
| `REFRESH_SESSION_EXPIRE_DAYS` | 服务端 refresh session 有效期，默认 30 天 | 保持可吊销、可轮换 |
| `ACCESS_TOKEN_COOKIE_NAME` / `REFRESH_TOKEN_COOKIE_NAME` | HttpOnly Cookie 名称 | 不需要暴露给前端 JS |
| `AUTH_COOKIE_SECURE` | Cookie 是否只允许 HTTPS | 生产必须为 `true` |
| `AUTH_COOKIE_SAMESITE` | Cookie SameSite 策略 | 同站部署用 `lax`；跨站 Cookie 必须配合 HTTPS 使用 `none` |
| `AUTH_COOKIE_DOMAIN` | Cookie domain | 只在需要跨子域共享登录态时设置 |

### 第三方能力

| 能力 | 关键配置 | 安全要求 |
| --- | --- | --- |
| Google OAuth | `GOOGLE_OAUTH_CLIENT_ID`、`GOOGLE_OAUTH_CLIENT_SECRET`、`GOOGLE_OAUTH_REDIRECT_URI` | redirect URI 必须和 Google Console、后端回调、正式域名一致；secret 只在后端保存 |
| PayPal 订阅 | `PAYPAL_CLIENT_ID`、`PAYPAL_CLIENT_SECRET`、`PAYPAL_PLAN_ID`、`PAYPAL_WEBHOOK_ID`、`PAYPAL_API_BASE` | 生产使用 `https://api-m.paypal.com`；webhook 必须经过 PayPal 签名校验后才更新本地订阅 |
| OpenRouter | `OPENROUTER_API_KEY`、`OPENROUTER_API_BASE`、模型和超时/重试配置 | API key 只在后端保存；上传简历、JD、Agent 上下文会发给模型供应商 |
| 火山引擎语音 | `DIGITAL_HUMAN_PROVIDER`、`VOLCENGINE_*`、`VOLCENGINE_DIALOGUE_*` | access key/token 只在后端保存；WebSocket 入口必须验证当前用户和订阅 |
| MiniMax / Tavus / LiveAvatar | `MINIMAX_*`、`TAVUS_*`、`LIVEAVATAR_*` | 未启用供应商不要配置生产 key；开启前补充对应隐私和数据处理说明 |
| 可观测性 | `SENTRY_*`、`LANGFUSE_*`、`LANGSMITH_*`、`OTEL_*`、`LOKI_BASE_URL`、`PROMETHEUS_BASE_URL` | 生产默认关闭 PII 上报；trace 和日志必须经过脱敏策略 |

### 上传与 Agent 控制

| 配置项 | 用途 | 安全要求 |
| --- | --- | --- |
| `UPLOAD_DIR` | 保存上传文件 | 目录不能公开暴露；删除简历时同步清理文件 |
| `MAX_FILE_SIZE` | 简历上传大小限制 | 和前端提示保持一致，避免大文件拖垮解析 |
| `JD_OCR_MAX_FILE_SIZE` | JD 图片 OCR 大小限制 | 控制视觉模型成本和滥用面 |
| `AGENT_SESSION_CONFIRMATION_TIMEOUT_SECONDS` | 工具确认暂停 session 超时 | 防止重启或断连后长期保留待确认状态 |
| `OPENROUTER_CIRCUIT_BREAKER_*` | 供应商故障快速失败 | 防止外部模型持续超时拖垮请求池 |

## 认证与授权模型

### 登录与会话

- 邮箱密码登录使用 bcrypt 哈希校验，成功后签发 access token，并创建服务端 `RefreshSession`。
- Google OAuth 使用 state 防 CSRF，回调成功后通过本地用户或 `ProviderIdentity` 绑定签发同一套 Cookie 会话。
- access token 是 HS256 JWT，`sub` 保存用户 ID，服务端用 `SECRET_KEY` 解码。
- refresh token 原文只进入 HttpOnly Cookie 和响应过程，数据库只保存 SHA-256 摘要。
- refresh 成功会 `touch` 当前 session 并轮换新 session；旧 session 会被标记为 revoked。
- logout 会吊销当前 refresh session 并删除 access/refresh Cookie。

### API 保护

`backend/app/main.py` 的认证中间件会在进入以下 API 前统一鉴权：

- `/api/resumes`
- `/api/interviews`
- `/api/upload`
- `/api/ai`
- `/api/users`
- `/api/tts`
- `/api/asr`
- `/api/digital-human`
- `/api/billing`

显式豁免路径：

- `/api/resumes/download`：依赖短时 HMAC 下载 token。
- `/api/billing/paypal/webhook`：依赖 PayPal webhook 验签。

路由级依赖仍会通过 `get_current_user()` 或 `get_current_user_claims()` 获取当前用户。改动受保护 API 时，不要绕过这些依赖。

### 资源归属

- 简历读取、更新、删除、聊天记录、导出都会校验 `resume.owner_id == current_user["id"]`。
- 面试 session 读取、删除和语音会话会校验 `session.user_id == current_user["id"]`。
- Agent session 恢复和 SSE cursor 回放会校验 `session.user_id == request.user_id`。
- 高成本入口使用 `require_active_subscription()`，当前覆盖上传、创建面试和数字人会话等路径。
- `is_superuser` 字段存在，但当前没有独立管理后台授权模型；新增管理入口前必须定义管理员路由、审计和权限测试。

## 数据与保留策略

### 存储的数据

| 数据 | 存储位置 | 当前保留行为 |
| --- | --- | --- |
| 用户账号 | `users` | 未实现自助删除账号 |
| 第三方身份 | `provider_identities` | 用户删除时数据库外键级联 |
| refresh session | `refresh_sessions` | 过期和吊销状态保留，用于审计和失效判断 |
| 简历结构化内容 | `resumes.content` | 删除简历时删除该记录 |
| 原始上传文件 | `UPLOAD_DIR` / `Resume.file_path` | 删除简历时调用文件删除 |
| 上传任务 | `resume_upload_jobs` | 保留任务状态和错误信息 |
| 简历聊天记录 | `resume_chat_messages` | 删除简历时由服务层清理 |
| Agent session/event | `agent_sessions` / `agent_events` | 删除简历时清理关联 session 和 event；paused session 有超时清理 |
| 面试记录 | `interview_sessions` / `interview_turns` | 删除面试 session 时级联 turns |
| 订阅与 webhook | `billing_subscriptions` / `billing_webhook_events` | 保留供应商订阅状态和幂等事件记录 |
| 导出文件 | 导出服务临时文件路径 | 下载链接短时签名，文件清理依赖导出服务实现 |

### 当前缺口

- 未实现用户自助数据导出或账号删除流程。
- 未定义生产数据保留期限，例如上传任务、聊天记录、Agent event、导出文件的过期清理周期。
- 未定义供应商侧数据处理和保留策略，需要结合 OpenRouter、Langfuse、LangSmith、Sentry、语音供应商的实际配置补充。
- 未对所有历史日志做自动 PII 扫描；当前依赖日志脱敏和谨慎记录。

## 日志、追踪与脱敏

- HTTP 请求统一生成 `X-Request-ID`，错误响应会返回同一个 `request_id`。
- 查询参数中的 `authorization`、`key`、`token`、`secret`、`password`、`cookie` 等敏感字段会记录为 `[REDACTED]`。
- 结构化日志会通过 `backend/app/infra/logging_setup.py` 对敏感 key 做脱敏。
- `SENTRY_SEND_DEFAULT_PII` 默认是 `false`，生产不得随意打开。
- Agent trace 可能包含简历和 JD 内容；生产开启 `LANGFUSE_*`、`LANGSMITH_*`、`OTEL_TRACES_ENABLED` 前，需要明确采样率、访问权限和供应商数据保留政策。

## 第三方服务安全要求

- Google OAuth：必须保留 state 校验；新增 OAuth provider 时也要有 state/nonce 类防护。
- PayPal：webhook 必须调用供应商验签接口，处理前记录幂等事件 id，旧事件不能覆盖较新的本地订阅状态。
- OpenRouter：模型请求失败应走超时、重试和 circuit breaker；错误响应不能把 API key 或完整敏感 payload 返回给前端。
- 语音供应商：WebSocket 必须先通过 Cookie access token 鉴权，再校验订阅和 session 归属。
- 可观测性供应商：生产 key 不写入前端；默认不发送 PII；trace 示例不能包含真实简历。

## 变更检查清单

修改认证、支付、上传、Agent、导出或语音链路时，至少检查：

- 是否仍通过认证中间件或 `get_current_user()` 保护。
- 是否校验当前用户和资源归属。
- 是否需要 `require_active_subscription()`。
- 是否会把简历、JD、token、secret、Cookie、支付 payload 写入日志或 trace。
- 是否需要更新 `backend/.env.example`、`README.md` 和本文档。
- 是否有针对 401、403、404、签名失败、跨用户访问的回归测试。
