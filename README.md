# Chat Resume

一个用 AI驱动的求职网站，具有 Agent 一键简历优化和模拟面试功能。

## 功能

- 简历上传与解析
  - 支持 `PDF`、`DOCX`、`DOC`、`TXT`
  - 后端将简历解析为结构化 JSON
- 简历编辑工作台
  - 分模块编辑个人信息、教育、工作经历、项目、技能
  - 实时预览、自动保存、模块显隐、排版控制
- Resume Agent
  - 基于当前简历内容进行分析和改写
  - 支持工具调用直接修改结构化简历
  - 支持流式输出和用户确认修改
- 模拟面试
  - 基于简历和 JD 创建面试会话
  - 动态生成问题、记录问答、生成报告
- 语音能力
  - TTS 面试问题播报
  - ASR 一次性识别和 WebSocket 实时识别
- 导出
  - 支持 `PDF`、`DOCX`、`HTML`

## AGENT 相关实现

项目的 Agent 部分不是简单聊天封装，核心实现包括：

- 通用 `AgentRuntime`
  - 负责消息构建、prompt 渲染、模型调用、工具执行和多轮循环
- `ResumeAgent`
  - 将简历优化逻辑与通用 runtime 解耦
  - 通过 prompt + tools schema + context builder 定义业务 Agent
- Tool Calling
  - 当前支持：
    - `edit_resume`
    - `update_resume_item`
    - `add_resume_item`
    - `remove_resume_item`
  - 工具直接修改结构化简历 JSON，而不是返回非结构化建议文本
- Human-in-the-loop
  - 流式返回 `tool_pending`
  - 用户确认后执行真实修改
  - 用户拒绝时保持原始简历不变
- 流式事件协议
  - SSE 同时返回文本增量、工具状态、diff 摘要和最新 `resume_content`
- 结构化数据驱动
  - 前端编辑器、Agent、导出模块共用统一简历 schema

## 技术栈

### 前端

- Next.js 14
- React 18
- TypeScript
- Tailwind CSS
- Framer Motion
- Zustand

### 后端

- FastAPI
- SQLAlchemy 2
- Pydantic v2
- httpx
- Playwright
- PyPDF2 / pdfplumber / python-docx

### AI / 语音

- OpenRouter
- MiniMax TTS
- 火山引擎 ASR

## 项目结构

```text
chat-resume/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── agents/
│   │   ├── infra/
│   │   ├── models/
│   │   ├── prompts/
│   │   ├── schemas/
│   │   └── services/
│   └── tests/
├── frontend/
│   └── src/
├── docs/
├── backend.sh
└── frontend.sh
```

## 核心目录

- `backend/app/agents/runtime/agent_runtime.py`
  - 通用 Agent Runtime
- `backend/app/agents/definitions/resume_agent.py`
  - 简历优化 Agent
- `backend/app/agents/tools/resume_tools/`
  - Agent 工具集合
- `backend/app/api/endpoints/resume_agent.py`
  - Agent 聊天与流式接口
- `frontend/src/hooks/useStreamingChat.ts`
  - 前端流式事件消费
- `frontend/src/app/resume/[id]/edit/page.tsx`
  - 简历编辑工作台
- `frontend/src/app/resume/[id]/interview/page.tsx`
  - 模拟面试页面

## 本地运行

### 环境要求

- Python 3.10+
- Node.js 18+

### 启动后端

```bash
./backend.sh
```

默认地址：

- API: `http://localhost:8000`
- Docs: `http://localhost:8000/docs`

### 启动前端

```bash
./frontend.sh
```

默认地址：

- Web: `http://localhost:3000`

## 环境变量

后端主要变量：

- `DATABASE_URL`
- `SECRET_KEY`
- `OPENROUTER_API_KEY`
- `OPENROUTER_API_BASE`
- `OPENROUTER_MODEL`
- `MINIMAX_API_KEY`
- `MINIMAX_GROUP_ID`
- `VOLCENGINE_*`
- `FRONTEND_URL`

前端主要变量：

- `NEXT_PUBLIC_API_URL`

示例文件：

- `backend/.env.example`
- `frontend/.env.example`

## 测试

当前测试主要覆盖：

- Resume schema 归一化
- Resume Agent smoke tests
- 流式确认 / 拒绝逻辑

运行：

```bash
cd backend
uv run pytest tests
```
