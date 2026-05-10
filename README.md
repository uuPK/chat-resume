# Chat Resume

[![zread](https://img.shields.io/badge/Ask_Zread-_.svg?style=flat&color=00b0aa&labelColor=000000&logo=data%3Aimage%2Fsvg%2Bxml%3Bbase64%2CPHN2ZyB3aWR0aD0iMTYiIGhlaWdodD0iMTYiIHZpZXdCb3g9IjAgMCAxNiAxNiIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KPHBhdGggZD0iTTQuOTYxNTYgMS42MDAxSDIuMjQxNTZDMS44ODgxIDEuNjAwMSAxLjYwMTU2IDEuODg2NjQgMS42MDE1NiAyLjI0MDFWNC45NjAxQzEuNjAxNTYgNS4zMTM1NiAxLjg4ODEgNS42MDAxIDIuMjQxNTYgNS42MDAxSDQuOTYxNTZDNS4zMTUwMiA1LjYwMDEgNS42MDE1NiA1LjMxMzU2IDUuNjAxNTYgNC45NjAxVjIuMjQwMUM1LjYwMTU2IDEuODg2NjQgNS4zMTUwMiAxLjYwMDEgNC45NjE1NiAxLjYwMDFaIiBmaWxsPSIjZmZmIi8%2BCjxwYXRoIGQ9Ik00Ljk2MTU2IDEwLjM5OTlIMi4yNDE1NkMxLjg4ODEgMTAuMzk5OSAxLjYwMTU2IDEwLjY4NjQgMS42MDE1NiAxMS4wMzk5VjEzLjc1OTlDMS42MDE1NiAxNC4xMTM0IDEuODg4MSAxNC4zOTk5IDIuMjQxNTYgMTQuMzk5OUg0Ljk2MTU2QzUuMzE1MDIgMTQuMzk5OSA1LjYwMTU2IDE0LjExMzQgNS42MDE1NiAxMy43NTk5VjExLjAzOTlDNS42MDE1NiAxMC42ODY0IDUuMzE1MDIgMTAuMzk5OSA0Ljk2MTU2IDEwLjM5OTlaIiBmaWxsPSIjZmZmIi8%2BCjxwYXRoIGQ9Ik0xMy43NTg0IDEuNjAwMUgxMS4wMzg0QzEwLjY4NSAxLjYwMDEgMTAuMzk4NCAxLjg4NjY0IDEwLjM5ODQgMi4yNDAxVjQuOTYwMUMxMC4zOTg0IDUuMzEzNTYgMTAuNjg1IDUuNjAwMSAxMS4wMzg0IDUuNjAwMUgxMy43NTg0QzE0LjExMTkgNS42MDAxIDE0LjM5ODQgNS4zMTM1NiAxNC4zOTg0IDQuOTYwMVYyLjI0MDFDMTQuMzk4NCAxLjg4NjY0IDE0LjExMTkgMS42MDAxIDEzLjc1ODQgMS42MDAxWiIgZmlsbD0iI2ZmZiIvPgo8cGF0aCBkPSJNNCAxMkwxMiA0TDQgMTJaIiBmaWxsPSIjZmZmIi8%2BCjxwYXRoIGQ9Ik00IDEyTDEyIDQiIHN0cm9rZT0iI2ZmZiIgc3Ryb2tlLXdpZHRoPSIxLjUiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIvPgo8L3N2Zz4K&logoColor=ffffff)](https://zread.ai/849261680/chat-resume)

一个围绕「简历优化 + 模拟面试」的 AI 求职应用。

前端是 Next.js 14，后端是 FastAPI。当前主流程已经收敛为一套：结构化简历编辑、Agent 流式改写、工具级 diff 确认、模拟面试与报告。

## 当前功能

- 账号注册、登录、刷新登录态
- 简历上传与解析
  - 支持 `PDF`、`DOC`、`DOCX`、`TXT`
  - 后端统一归一化为结构化简历 JSON
- 简历工作台
  - 模块化编辑：岗位、个人信息、教育、工作、项目、技能
  - 自动保存
  - 实时预览
  - 布局控制与一页适配
  - 导出 `PDF`、`DOCX`、`HTML`
- Resume Agent
  - SSE 流式输出
  - 工具调用直接修改结构化简历
  - 修改前先展示 diff，用户确认后才落库
- 模拟面试
  - 基于简历创建 session
  - 追问、阶段推进、结束报告
  - 面试中心查看记录
- 语音能力
  - TTS 播报
  - ASR 文件识别与流式识别接口

## 技术栈

- 前端：Next.js 14、React 18、TypeScript、Tailwind CSS、Framer Motion
- 后端：FastAPI、SQLAlchemy 2、Pydantic v2、Alembic
- AI / 语音：OpenRouter、MiniMax TTS、火山引擎 ASR
- 测试：pytest、Playwright

## 目录

```text
chat-resume/
├── backend/
│   ├── alembic/
│   ├── app/
│   │   ├── api/
│   │   ├── agents/
│   │   ├── infra/
│   │   ├── models/
│   │   ├── schemas/
│   │   └── services/
│   └── tests/
├── frontend/
│   ├── e2e/
│   ├── scripts/
│   └── src/
├── restart.sh
├── backend.sh
├── frontend.sh
└── railway.json
```

## 关键页面

- `/resumes`：简历中心
- `/resume/[id]/edit`：简历编辑工作台
- `/interviews`：面试中心
- `/resume/[id]/interview`：模拟面试工作台

## 本地开发

环境要求：

- Python 3.11+
- Node.js 18+
- `uv`

一键重启前后端：

```bash
./restart.sh
```

终端默认显示精简日志，完整日志会写入 `backend.log` 和 `frontend.log`。需要看完整输出时：

```bash
VERBOSE=1 ./restart.sh
```

默认地址：

- API: `http://localhost:8000`
- Docs: `http://localhost:8000/docs`
- Web: `http://localhost:3000`

也可以单独启动某一端：

```bash
./backend.sh
./frontend.sh
```

## 生产模式本地运行

后端：

```bash
cd backend
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

前端：

```bash
cd frontend
npm run build
npm run start
```

## 环境变量

示例文件：

- `backend/.env.example`
- `frontend/.env.example`

常用变量：

- 后端
  - `DATABASE_URL`
  - `SECRET_KEY`
  - `BACKEND_CORS_ORIGINS`
  - `OPENROUTER_API_KEY`
  - `OPENROUTER_MODEL`
  - `MINIMAX_*`
  - `VOLCENGINE_*`
  - `DIGITAL_HUMAN_PROVIDER=volcengine`
  - `VOLCENGINE_DIALOGUE_APP_KEY`
  - `VOLCENGINE_DIALOGUE_ACCESS_KEY`
- 前端
  - `NEXT_PUBLIC_API_URL`

### Google 登录 OAuth 配置

Google 登录采用后端授权码流程。前端只跳转到后端启动端点，不处理或保存 Google token。

本地开发默认值：

```bash
# backend/.env
GOOGLE_OAUTH_CLIENT_ID=
GOOGLE_OAUTH_CLIENT_SECRET=
GOOGLE_OAUTH_REDIRECT_URI=http://localhost:8000/api/auth/google/callback
FRONTEND_URL=http://localhost:3000
BACKEND_CORS_ORIGINS=http://localhost:3000,https://localhost:3000
AUTH_COOKIE_SECURE=false
AUTH_COOKIE_SAMESITE=lax
AUTH_COOKIE_DOMAIN=

# frontend/.env.local
NEXT_PUBLIC_API_URL=http://localhost:8000
```

Google Cloud Console 中创建 OAuth Client 时选择 `Web application`。Authorized redirect URIs 本地填：

```text
http://localhost:8000/api/auth/google/callback
```

生产环境填真实后端域名，并且必须与 `GOOGLE_OAUTH_REDIRECT_URI` 完全一致：

```text
https://<BACKEND_PUBLIC_HOST>/api/auth/google/callback
```

如果控制台要求 Authorized JavaScript origins，可填前端来源：

```text
http://localhost:3000
https://<FRONTEND_PUBLIC_HOST>
```

生产环境同站点或同父域部署时，Cookie 与 CORS 推荐：

```bash
FRONTEND_URL=https://<FRONTEND_PUBLIC_HOST>
NEXT_PUBLIC_API_URL=https://<BACKEND_PUBLIC_HOST>
BACKEND_CORS_ORIGINS=https://<FRONTEND_PUBLIC_HOST>
AUTH_COOKIE_SECURE=true
AUTH_COOKIE_SAMESITE=lax
AUTH_COOKIE_DOMAIN=<可选父域名>
```

生产环境前后端跨站点部署时，浏览器要求跨站 Cookie 使用 `Secure` 和 `SameSite=None`：

```bash
BACKEND_CORS_ORIGINS=https://<FRONTEND_PUBLIC_HOST>
AUTH_COOKIE_SECURE=true
AUTH_COOKIE_SAMESITE=none
AUTH_COOKIE_DOMAIN=<后端 Cookie 可用域名>
```

常见配置错误：

- Google 回调返回 `redirect_uri_mismatch`：Google Cloud Console 的 Authorized redirect URI 与 `GOOGLE_OAUTH_REDIRECT_URI` 不完全一致，包括协议、域名、端口和路径。
- 点击“使用 Google 继续”后访问不到后端：检查 `NEXT_PUBLIC_API_URL` 是否指向后端公开地址，本地默认是 `http://localhost:8000`。
- 登录成功后没有登录态：检查前端 API 请求是否携带 Cookie、`BACKEND_CORS_ORIGINS` 是否包含前端来源，以及生产环境是否设置了正确的 `AUTH_COOKIE_SECURE`、`AUTH_COOKIE_SAMESITE` 和 `AUTH_COOKIE_DOMAIN`。
- 后端返回 `config_missing`：检查后端是否设置了 `GOOGLE_OAUTH_CLIENT_ID`、`GOOGLE_OAUTH_CLIENT_SECRET` 和 `GOOGLE_OAUTH_REDIRECT_URI`。

## 测试

后端：

```bash
cd backend
uv run --extra dev python -m pytest tests
```

前端类型检查：

```bash
cd frontend
npm run type-check
```

前端 E2E：

```bash
cd frontend
npm run e2e
```

## 生产性能测速

项目自带一份生产模式测速脚本：

```bash
cd frontend
npm run perf:prod -- \
  --frontend-url http://localhost:3000 \
  --api-url http://localhost:8000 \
  --runs 3 \
  --output perf-report.json
```

它会自动准备测试账号、简历和面试 session，并输出：

- API 探针耗时
- 浏览器页面导航耗时
- 平均值、P95、最大值

脚本文件：

- `frontend/scripts/measure-production.mjs`
