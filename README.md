# Chat Resume

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

- Python 3.10+
- Node.js 18+
- `uv`

启动后端：

```bash
./backend.sh
```

默认地址：

- API: `http://localhost:8000`
- Docs: `http://localhost:8000/docs`

启动前端：

```bash
./frontend.sh
```

默认地址：

- Web: `http://localhost:3000`

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
- 前端
  - `NEXT_PUBLIC_API_URL`

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
