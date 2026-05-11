# Chat Resume

[![zread](https://img.shields.io/badge/Ask_Zread-_.svg?style=flat&color=00b0aa&labelColor=000000&logo=data%3Aimage%2Fsvg%2Bxml%3Bbase64%2CPHN2ZyB3aWR0aD0iMTYiIGhlaWdodD0iMTYiIHZpZXdCb3g9IjAgMCAxNiAxNiIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KPHBhdGggZD0iTTQuOTYxNTYgMS42MDAxSDIuMjQxNTZDMS44ODgxIDEuNjAwMSAxLjYwMTU2IDEuODg2NjQgMS42MDE1NiAyLjI0MDFWNC45NjAxQzEuNjAxNTYgNS4zMTM1NiAxLjg4ODEgNS42MDAxIDIuMjQxNTYgNS42MDAxSDQuOTYxNTZDNS4zMTUwMiA1LjYwMDEgNS42MDE1NiA1LjMxMzU2IDUuNjAxNTYgNC45NjAxVjIuMjQwMUM1LjYwMTU2IDEuODg2NjQgNS4zMTUwMiAxLjYwMDEgNC45NjE1NiAxLjYwMDFaIiBmaWxsPSIjZmZmIi8%2BCjxwYXRoIGQ9Ik00Ljk2MTU2IDEwLjM5OTlIMi4yNDE1NkMxLjg4ODEgMTAuMzk5OSAxLjYwMTU2IDEwLjY4NjQgMS42MDE1NiAxMS4wMzk5VjEzLjc1OTlDMS42MDE1NiAxNC4xMTM0IDEuODg4MSAxNC4zOTk5IDIuMjQxNTYgMTQuMzk5OUg0Ljk2MTU2QzUuMzE1MDIgMTQuMzk5OSA1LjYwMTU2IDE0LjExMzQgNS42MDE1NiAxMy43NTk5VjExLjAzOTlDNS42MDE1NiAxMC42ODY0IDUuMzE1MDIgMTAuMzk5OSA0Ljk2MTU2IDEwLjM5OTlaIiBmaWxsPSIjZmZmIi8%2BCjxwYXRoIGQ9Ik0xMy43NTg0IDEuNjAwMUgxMS4wMzg0QzEwLjY4NSAxLjYwMDEgMTAuMzk4NCAxLjg4NjY0IDEwLjM5ODQgMi4yNDAxVjQuOTYwMUMxMC4zOTg0IDUuMzEzNTYgMTAuNjg1IDUuNjAwMSAxMS4wMzg0IDUuNjAwMUgxMy43NTg0QzE0LjExMTkgNS42MDAxIDE0LjM5ODQgNS4zMTM1NiAxNC4zOTg0IDQuOTYwMVYyLjI0MDFDMTQuMzk4NCAxLjg4NjY0IDE0LjExMTkgMS42MDAxIDEzLjc1ODQgMS42MDAxWiIgZmlsbD0iI2ZmZiIvPgo8cGF0aCBkPSJNNCAxMkwxMiA0TDQgMTJaIiBmaWxsPSIjZmZmIi8%2BCjxwYXRoIGQ9Ik00IDEyTDEyIDQiIHN0cm9rZT0iI2ZmZiIgc3Ryb2tlLXdpZHRoPSIxLjUiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIvPgo8L3N2Zz4K&logoColor=ffffff)](https://zread.ai/849261680/chat-resume)

Chat Resume 是一个围绕「结构化简历优化 + AI Agent 改写 + 语音模拟面试」的求职应用。

当前主链路是：

1. 上传或创建结构化简历。
2. 在编辑工作台维护岗位、个人信息、教育、工作、项目、技能等模块。
3. Resume Agent 基于 Deep Agents 调用简历工具，生成可确认的 diff。
4. 用户确认后写回结构化简历，并导出 PDF / DOCX / HTML。
5. 基于简历创建实时语音模拟面试，沉淀面试记录和报告。

## 功能状态

- 账号系统
  - 邮箱注册、登录、刷新会话
  - Google OAuth 登录
  - Cookie 鉴权保护简历、面试、AI、语音、账单等 API
- 简历管理
  - 上传解析 `PDF`、`DOC`、`DOCX`、`TXT`
  - 结构化编辑与实时预览
  - 自动保存、布局控制、一页适配
  - 导出 `PDF`、`DOCX`、`HTML`
- Resume Agent
  - Deep Agents 是当前唯一主执行内核
  - SSE 流式输出
  - 显示工具调用状态
  - 支持 `read_resume`、`update_bullet`、`add_bullet`、`remove_bullet`、`update_overview`
  - 工具改动先生成 diff，用户确认后落库
  - 使用官方 Deep Agents memory 文件 `/memories/AGENTS.md` 保存用户偏好和简历策略
- 模拟面试
  - 面试中心管理 session
  - 实时语音面试页面
  - 火山引擎端到端实时语音对话
  - 面试官问题和候选人回答写入 `interview_turns`
  - 支持结束面试并生成报告数据
- 账单
  - PayPal Plus 订阅创建、状态查询、Webhook 同步
  - 本地持久化 `billing_subscriptions` 与 webhook 事件
- 评测与观测
  - `eval/` 下有离线 eval case、schema 校验、打分、趋势对比和证据报告脚本
  - LangSmith / Langfuse / Sentry 配置入口
  - Resume Agent eval 可输出 trace artifacts

## 技术栈

- 前端：Next.js 16、React 18、TypeScript、Tailwind CSS、Framer Motion、Playwright
- 后端：FastAPI、SQLAlchemy 2、Pydantic v2、Alembic、uv
- Agent：Deep Agents、LangChain OpenAI、OpenRouter
- 语音：火山引擎实时语音对话、火山引擎 ASR、MiniMax TTS
- 支付：PayPal Subscriptions
- 观测：Sentry、Langfuse、LangSmith

## 目录结构

```text
chat-resume/
├── backend/
│   ├── alembic/                  # 数据库迁移
│   ├── app/
│   │   ├── agents/               # Resume / Interview agent 业务入口
│   │   ├── entrypoints/http/      # FastAPI HTTP 路由
│   │   ├── evals/                # 后端 eval 任务定义
│   │   ├── infra/                # 配置、数据库、日志、观测
│   │   ├── models/               # SQLAlchemy models
│   │   ├── prompts/              # Agent prompts
│   │   ├── runtime/              # Deep Agents runtime adapter
│   │   ├── schemas/              # Pydantic schemas
│   │   ├── services/             # 认证、账单、面试、LLM、解析、语音服务
│   │   ├── state/                # Agent 状态快照和回放
│   │   ├── tools/                # 简历工具
│   │   └── types/                # 运行时/流式事件类型
│   ├── scripts/
│   └── tests/
├── frontend/
│   ├── e2e/                      # Playwright 用例
│   ├── scripts/
│   └── src/
│       ├── app/                  # Next.js App Router 页面
│       ├── components/
│       ├── hooks/
│       ├── lib/
│       └── types/
├── eval/                         # Agent eval CLI、case、gate 配置
├── docs/
│   └── architecture.html
├── DESIGN.md                     # Coinbase 风格设计规范
├── backend.sh
├── frontend.sh
├── restart.sh
├── railway.json                  # 后端部署配置
└── frontend/vercel.json          # 前端部署配置
```

## 关键页面

- `/`：产品首页
- `/login`、`/register`：账号入口
- `/dashboard`：登录后的概览入口
- `/resumes`：简历中心
- `/resume/[id]/edit`：简历编辑与 Agent 优化工作台
- `/resume/print`：简历打印/导出页面
- `/interviews`：面试中心
- `/resume/[id]/interview`：实时语音模拟面试
- `/settings`：账号设置与套餐选择

## 本地开发

环境要求：

- Python 3.11+
- Node.js 18+
- `uv`
- `npm`

首次启动推荐直接用根目录脚本：

```bash
./restart.sh
```

默认地址：

- API: `http://localhost:8000`
- API Docs: `http://localhost:8000/docs`
- Web: `http://localhost:3000`

`restart.sh` 会同时启动前后端，并把完整日志写入：

- `backend.log`
- `frontend.log`

需要完整终端日志时：

```bash
VERBOSE=1 ./restart.sh
```

也可以单独启动：

```bash
./backend.sh
./frontend.sh
```

脚本支持端口覆盖：

```bash
BACKEND_PORT=8010 FRONTEND_PORT=3010 ./restart.sh
```

## 数据库

本地默认使用 SQLite：

```bash
backend/chat_resume.db
```

迁移命令：

```bash
cd backend
uv run alembic upgrade head
```

## 环境变量

示例文件：

- `backend/.env.example`
- `frontend/.env.example`

本地脚本会在缺失时复制为：

- `backend/.env`
- `frontend/.env.local`

### 后端常用配置

```bash
DATABASE_URL=sqlite:///./chat_resume.db
SECRET_KEY=your-secret-key-here
FRONTEND_URL=http://localhost:3000
BACKEND_CORS_ORIGINS=http://localhost:3000,https://localhost:3000
AUTH_COOKIE_SECURE=false
AUTH_COOKIE_SAMESITE=lax
AUTH_COOKIE_DOMAIN=
```

### OpenRouter / Agent

```bash
OPENROUTER_API_KEY=
OPENROUTER_API_BASE=https://openrouter.ai/api/v1
OPENROUTER_MODEL=google/gemini-2.5-flash
OPENROUTER_VISION_MODEL=qwen/qwen2.5-vl-72b-instruct
OPENROUTER_VISION_FALLBACK_MODELS=google/gemini-2.5-flash
OPENROUTER_RESUME_PARSER_MODEL=deepseek/deepseek-v4-flash
```

### Google 登录

Google 登录采用后端授权码流程。前端跳转到后端启动端点，不处理 Google token。

```bash
GOOGLE_OAUTH_CLIENT_ID=
GOOGLE_OAUTH_CLIENT_SECRET=
GOOGLE_OAUTH_REDIRECT_URI=http://localhost:8000/api/auth/google/callback
```

Google Cloud Console 的 OAuth Client 类型选择 `Web application`。本地 Authorized redirect URI：

```text
http://localhost:8000/api/auth/google/callback
```

生产环境必须和 `GOOGLE_OAUTH_REDIRECT_URI` 完全一致：

```text
https://<BACKEND_PUBLIC_HOST>/api/auth/google/callback
```

常见错误：

- `redirect_uri_mismatch`：Google Console 的 redirect URI 与 `GOOGLE_OAUTH_REDIRECT_URI` 不一致。
- `config_missing`：后端缺少 `GOOGLE_OAUTH_CLIENT_ID`、`GOOGLE_OAUTH_CLIENT_SECRET` 或 `GOOGLE_OAUTH_REDIRECT_URI`。
- 登录后无登录态：检查 `NEXT_PUBLIC_API_URL`、`BACKEND_CORS_ORIGINS`、Cookie `Secure` / `SameSite` / `Domain`。

### PayPal 订阅

```bash
PAYPAL_CLIENT_ID=
PAYPAL_CLIENT_SECRET=
PAYPAL_PLAN_ID=
PAYPAL_WEBHOOK_ID=
PAYPAL_API_BASE=https://api-m.sandbox.paypal.com
```

本地/沙箱默认使用 PayPal sandbox。生产环境把 `PAYPAL_API_BASE` 改成：

```bash
PAYPAL_API_BASE=https://api-m.paypal.com
```

后端暴露的账单接口包括：

- `GET /api/billing/status`
- `GET /api/billing/paypal/plan`
- `POST /api/billing/paypal/subscriptions`
- `GET /api/billing/paypal/subscriptions/{subscription_id}/sync`
- `POST /api/billing/paypal/subscriptions/{subscription_id}/cancel`
- `POST /api/billing/paypal/webhook`

`/api/billing/paypal/webhook` 是鉴权豁免路径，但仍会做 PayPal webhook 签名校验。

### 语音与数字人

```bash
DIGITAL_HUMAN_PROVIDER=volcengine
VOLCENGINE_DIALOGUE_APP_ID=
VOLCENGINE_DIALOGUE_ACCESS_KEY=
VOLCENGINE_DIALOGUE_RESOURCE_ID=volc.speech.dialog
VOLCENGINE_DIALOGUE_SPEAKER_ID=
VOLCENGINE_DIALOGUE_WS_URL=wss://openspeech.bytedance.com/api/v3/realtime/dialogue
```

其他可选语音/数字人配置：

- `MINIMAX_API_KEY`、`MINIMAX_GROUP_ID`
- `VOLCENGINE_APP_KEY`、`VOLCENGINE_ACCESS_TOKEN`
- `VOLCENGINE_ASR_API_KEY`、`VOLCENGINE_ASR_APP_ID`
- `VOLCENGINE_TTS_API_KEY`、`VOLCENGINE_TTS_APP_ID`
- `TAVUS_*`
- `LIVEAVATAR_*`

### 前端配置

```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_APP_ENV=development
NEXT_PUBLIC_APP_NAME=Chat Resume
NEXT_PUBLIC_APP_DESCRIPTION=AI驱动的智能简历优化平台
```

## 生产模式本地运行

后端：

```bash
cd backend
uv sync --extra dev
uv run alembic upgrade head
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

前端：

```bash
cd frontend
npm install
npm run build
npm run start
```

## 测试与验证

后端测试：

```bash
cd backend
uv run --extra dev python -m pytest tests
```

前端类型检查：

```bash
cd frontend
npm run type-check
```

前端构建：

```bash
cd frontend
npm run build
```

Playwright E2E：

```bash
cd frontend
npm run e2e
```

E2E 需要前端和后端服务同时可用，默认使用：

- `http://localhost:3000`
- `http://localhost:8000`

## Eval 工作流

`eval/` 是当前 Agent 评测入口，包含 case、gate、分析、打分和趋势对比。

常用命令：

```bash
cd backend
uv run python ../eval/validate_cases.py
uv run python -m pytest \
  tests/test_eval_analyzer.py \
  tests/test_eval_case_validation.py \
  tests/test_eval_score.py \
  tests/test_eval_trend_comparison.py \
  tests/test_evidence_report.py
```

真实模型 eval 依赖 `backend/.env` 中的 `OPENROUTER_API_KEY`：

```bash
cd backend
uv run python ../eval/run_eval.py
```

分析已有结果：

```bash
python eval/analyze_results.py \
  --results eval/eval_results.json \
  --cases eval/test_cases.json \
  --output eval/analysis.json \
  --markdown-output eval/analysis.md
```

## 性能测速

项目自带一份生产模式测速脚本：

```bash
cd frontend
npm run perf:prod -- \
  --frontend-url http://localhost:3000 \
  --api-url http://localhost:8000 \
  --runs 3 \
  --output perf-report.json
```

它会准备测试账号、简历和面试 session，并输出：

- API 探针耗时
- 浏览器页面导航耗时
- 平均值、P95、最大值

## 设计规范

前端界面以 `DESIGN.md` 为准。当前设计系统采用 Coinbase 风格：

- 主色：`#0052ff`
- 文本：`#0a0b0d`
- 次级文字：`#5b616e`
- 次级表面：`#eef0f3`
- CTA 使用 56px pill 圆角
- 蓝色只用于主要可执行操作
