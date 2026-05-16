# Chat Resume

[![zread](https://img.shields.io/badge/Ask_Zread-_.svg?style=flat&color=00b0aa&labelColor=000000&logo=data%3Aimage%2Fsvg%2Bxml%3Bbase64%2CPHN2ZyB3aWR0aD0iMTYiIGhlaWdodD0iMTYiIHZpZXdCb3g9IjAgMCAxNiAxNiIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KPHBhdGggZD0iTTQuOTYxNTYgMS42MDAxSDIuMjQxNTZDMS44ODgxIDEuNjAwMSAxLjYwMTU2IDEuODg2NjQgMS42MDE1NiAyLjI0MDFWNC45NjAxQzEuNjAxNTYgNS4zMTM1NiAxLjg4ODEgNS42MDAxIDIuMjQxNTYgNS42MDAxSDQuOTYxNTZDNS4zMTUwMiA1LjYwMDEgNS42MDE1NiA1LjMxMzU2IDUuNjAxNTYgNC45NjAxVjIuMjQwMUM1LjYwMTU2IDEuODg2NjQgNS4zMTUwMiAxLjYwMDEgNC45NjE1NiAxLjYwMDFaIiBmaWxsPSIjZmZmIi8%2BCjxwYXRoIGQ9Ik00Ljk2MTU2IDEwLjM5OTlIMi4yNDE1NkMxLjg4ODEgMTAuMzk5OSAxLjYwMTU2IDEwLjY4NjQgMS42MDE1NiAxMS4wMzk5VjEzLjc1OTlDMS42MDE1NiAxNC4xMTM0IDEuODg4MSAxNC4zOTk5IDIuMjQxNTYgMTQuMzk5OUg0Ljk2MTU2QzUuMzE1MDIgMTQuMzk5OSA1LjYwMTU2IDE0LjExMzQgNS42MDE1NiAxMy43NTk5VjExLjAzOTlDNS42MDE1NiAxMC42ODY0IDUuMzE1MDIgMTAuMzk5OSA0Ljk2MTU2IDEwLjM5OTlaIiBmaWxsPSIjZmZmIi8%2BCjxwYXRoIGQ9Ik0xMy43NTg0IDEuNjAwMUgxMS4wMzg0QzEwLjY4NSAxLjYwMDEgMTAuMzk4NCAxLjg4NjY0IDEwLjM5ODQgMi4yNDAxVjQuOTYwMUMxMC4zOTg0IDUuMzEzNTYgMTAuNjg1IDUuNjAwMSAxMS4wMzg0IDUuNjAwMUgxMy43NTg0QzE0LjExMTkgNS42MDAxIDE0LjM5ODQgNS4zMTM1NiAxNC4zOTg0IDQuOTYwMVYyLjI0MDFDMTQuMzk4NCAxLjg4NjY0IDE0LjExMTkgMS42MDAxIDEzLjc1ODQgMS42MDAxWiIgZmlsbD0iI2ZmZiIvPgo8cGF0aCBkPSJNNCAxMkwxMiA0TDQgMTJaIiBmaWxsPSIjZmZmIi8%2BCjxwYXRoIGQ9Ik00IDEyTDEyIDQiIHN0cm9rZT0iI2ZmZiIgc3Ryb2tlLXdpZHRoPSIxLjUiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIvPgo8L3N2Zz4K&logoColor=ffffff)](https://zread.ai/849261680/chat-resume)

Chat Resume 是一个 AI 求职应用，核心流程是：上传简历 -> 上传 JD -> Agent 优化 -> 确认修改 -> 导出简历 -> 模拟面试。

## 核心功能

- 简历上传解析：支持 `PDF`、`DOC`、`DOCX`、`TXT`
- 简历编辑工作台：结构化编辑、实时预览、自动保存、一页适配
- Resume Agent：AGENT根据JD定向优化简历
- 模拟面试：基于简历创建语音面试 session，保存问答记录和报告


## 技术栈

- 前端：Next.js 16.2、React 18、TypeScript、Tailwind CSS、next-intl
- 后端：FastAPI、SQLAlchemy 2、Pydantic v2、Alembic、uv
- AI：pi-agent-core、OpenRouter
- 语音：火山引擎实时语音对话、ASR、MiniMax TTS
- 测试：pytest、Playwright

## 主要目录

```text
backend/app/entrypoints/http/  # FastAPI 路由
backend/app/agents/resume/     # 简历 Agent 定义和提示词
backend/app/runtime/           # pi-agent-core 运行时适配
backend/app/tools/resume/      # 简历工具
backend/app/services/          # 业务服务（auth、agent、domain、interview、llm、processing、voice）
backend/app/state/             # Agent session 存储和回放
frontend/src/app/              # Next.js 页面
frontend/src/components/       # 前端组件
frontend/src/hooks/            # 页面级业务 hooks
frontend/src/i18n/             # 国际化配置
frontend/locales/              # 中英文翻译文件
eval/                          # Agent eval 脚本和用例
```

## 本地启动

要求：

- Python 3.11+
- Node.js 18+
- uv
- npm

启动前后端：

```bash
./restart.sh
```

默认地址：

- Web: `http://localhost:3000`
- API: `http://localhost:8000`
- API Docs: `http://localhost:8000/docs`

路由：

- `/login` / `/register`：登录注册
- `/dashboard`：工作台
- `/resumes`：简历中心
- `/resume/{id}/edit`：简历编辑、预览、Agent 优化和导出
- `/resume/{id}/interview`：语音面试
- `/interviews`：面试记录
- `/pricing`：套餐价格
- `/settings`：账户设置

单独启动：

```bash
./backend.sh
./frontend.sh
```

## 环境变量

示例文件：

- `backend/.env.example`
- `frontend/.env.example`

本地最少需要：

```bash
# backend/.env
DATABASE_URL=sqlite:///./chat_resume.db
SECRET_KEY=your-secret-key-here
OPENROUTER_API_KEY=
OPENROUTER_RESUME_PARSER_MODEL=deepseek/deepseek-v4-flash
FRONTEND_URL=http://localhost:3000
BACKEND_CORS_ORIGINS=http://localhost:3000,https://localhost:3000

# frontend/.env.local
NEXT_PUBLIC_API_URL=http://localhost:8000
```

可选能力按需配置：

- Google 登录：`GOOGLE_OAUTH_CLIENT_ID`、`GOOGLE_OAUTH_CLIENT_SECRET`、`GOOGLE_OAUTH_REDIRECT_URI`
- PayPal 订阅：`PAYPAL_CLIENT_ID`、`PAYPAL_CLIENT_SECRET`、`PAYPAL_PLAN_ID`、`PAYPAL_WEBHOOK_ID`
- 语音面试：`DIGITAL_HUMAN_PROVIDER=volcengine` 和 `VOLCENGINE_DIALOGUE_*`
- ASR/TTS：`VOLCENGINE_APP_KEY`、`VOLCENGINE_ACCESS_TOKEN`、`MINIMAX_API_KEY`

## 数据库

```bash
cd backend
uv run alembic upgrade head
```

## 测试

```bash
# 后端
cd backend
uv run --extra dev python -m pytest tests

# 前端类型检查
cd frontend
npm run type-check

# 前端构建
npm run build

# E2E
npm run e2e
```

## 设计

前端设计规范见 [DESIGN.md](./DESIGN.md)。
