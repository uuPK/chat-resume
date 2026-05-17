# Chat Resume

[![zread](https://img.shields.io/badge/Ask_Zread-_.svg?style=flat&color=00b0aa&labelColor=000000&logo=data%3Aimage%2Fsvg%2Bxml%3Bbase64%2CPHN2ZyB3aWR0aD0iMTYiIGhlaWdodD0iMTYiIHZpZXdCb3g9IjAgMCAxNiAxNiIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KPHBhdGggZD0iTTQuOTYxNTYgMS42MDAxSDIuMjQxNTZDMS44ODgxIDEuNjAwMSAxLjYwMTU2IDEuODg2NjQgMS42MDE1NiAyLjI0MDFWNC45NjAxQzEuNjAxNTYgNS4zMTM1NiAxLjg4ODEgNS42MDAxIDIuMjQxNTYgNS42MDAxSDQuOTYxNTZDNS4zMTUwMiA1LjYwMDEgNS42MDE1NiA1LjMxMzU2IDUuNjAxNTYgNC45NjAxVjIuMjQwMUM1LjYwMTU2IDEuODg2NjQgNS4zMTUwMiAxLjYwMDEgNC45NjE1NiAxLjYwMDFaIiBmaWxsPSIjZmZmIi8%2BCjxwYXRoIGQ9Ik00Ljk2MTU2IDEwLjM5OTlIMi4yNDE1NkMxLjg4ODEgMTAuMzk5OSAxLjYwMTU2IDEwLjY4NjQgMS42MDE1NiAxMS4wMzk5VjEzLjc1OTlDMS42MDE1NiAxNC4xMTM0IDEuODg4MSAxNC4zOTk5IDIuMjQxNTYgMTQuMzk5OUg0Ljk2MTU2QzUuMzE1MDIgMTQuMzk5OSA1LjYwMTU2IDE0LjExMzQgNS42MDE1NiAxMy43NTk5VjExLjAzOTlDNS42MDE1NiAxMC42ODY0IDUuMzE1MDIgMTAuMzk5OSA0Ljk2MTU2IDEwLjM5OTlaIiBmaWxsPSIjZmZmIi8%2BCjxwYXRoIGQ9Ik0xMy43NTg0IDEuNjAwMUgxMS4wMzg0QzEwLjY4NSAxLjYwMDEgMTAuMzk4NCAxLjg4NjY0IDEwLjM5ODQgMi4yNDAxVjQuOTYwMUMxMC4zOTg0IDUuMzEzNTYgMTAuNjg1IDUuNjAwMSAxMS4wMzg0IDUuNjAwMUgxMy43NTg0QzE0LjExMTkgNS42MDAxIDE0LjM5ODQgNS4zMTM1NiAxNC4zOTg0IDQuOTYwMVYyLjI0MDFDMTQuMzk4NCAxLjg4NjY0IDE0LjExMTkgMS42MDAxIDEzLjc1ODQgMS42MDAxWiIgZmlsbD0iI2ZmZiIvPgo8cGF0aCBkPSJNNCAxMkwxMiA0TDQgMTJaIiBmaWxsPSIjZmZmIi8%2BCjxwYXRoIGQ9Ik00IDEyTDEyIDQiIHN0cm9rZT0iI2ZmZiIgc3Ryb2tlLXdpZHRoPSIxLjUiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIvPgo8L3N2Zz4K&logoColor=ffffff)](https://zread.ai/849261680/chat-resume)

Chat Resume 不是普通简历编辑器，而是一个 AI 求职工作台。它的核心是 Human-in-the-loop Resume Optimization Agent：从上传简历到分析目标 JD，再到结构化工具调用、用户确认式改写、导出和模拟面试，串成一条完整求职闭环。

它重点展示的 Agent 工程能力是：自定义 ReAct runtime、结构化工具、SSE 实时可观测、diff confirmation gate、防编造边界和 Agent eval。

## Demo

> TODO: 放 3 分钟演示视频或 GIF：上传简历 -> 粘贴 JD -> 工具调用 -> Top gaps -> 确认 diff -> 简历更新。

建议演示链路：

1. 上传或创建一份简历。
2. 粘贴目标岗位 JD，或上传 JD 截图识别文字。
3. Resume Agent 分析简历和 JD 的匹配情况。
4. Agent 调用 `generate_job_match_summary` 生成岗位匹配摘要。
5. Agent 生成结构化简历修改 diff。
6. 用户确认或拒绝修改。
7. 简历实时更新，并继续导出或进入模拟面试。

## 核心能力

- 简历上传解析：支持 PDF、DOC、DOCX、TXT，后台解析后生成结构化简历。
- 简历编辑工作台：结构化编辑、实时预览、自动保存、布局配置、一页适配和导出。
- JD 管理：保存目标公司、目标岗位和 JD 文本，支持 JD 图片 OCR。
- Resume Agent：基于当前简历、目标 JD 和对话上下文进行 ReAct 式工具调用。
- 用户确认式改写：所有修改类工具先展示 diff，用户确认后才写入简历。
- JD 匹配摘要：同一个工具返回命中关键词、缺失关键词、已确认改动、待补充事实提示和优先补强 Top gaps。
- 模拟面试：基于简历和目标岗位创建语音面试 session，保存问答并生成报告。
- Agent eval：提供评估用例和评分脚本，用于检查关键词提升、工具调用正确性和决策规则。

## 主要用户流程

```text
上传/创建简历
  -> 结构化编辑
  -> 填写或识别 JD
  -> Resume Agent 分析匹配
  -> 工具调用生成匹配摘要 / Top gaps / 修改 diff
  -> 用户确认后应用修改
  -> 预览、一页适配、导出
  -> 基于简历进入模拟面试
```

## 为什么这是 Agent 系统

Chat Resume 不是固定表单，也不是简单关键词检查器。Resume Agent 运行在 `PiAgentRuntime` 上，通过 pi-agent-core 和 OpenRouter 完成 ReAct loop：

- Observe：读取当前简历、JD、聊天历史和已确认改动。
- Reason：判断用户想要咨询、匹配分析，还是实际修改简历。
- Act：调用结构化工具读取、分析或修改简历。
- Confirm：修改类工具暂停并展示 diff，等待用户确认后继续。
- Resume：如果 SSE 连接中断，确认结果可以通过 session 恢复链路继续处理。

Agent 的输出不是“自然语言声称已修改”，只有真实工具调用成功并通过确认门后，简历内容才会被写入。

## Agent 工具

当前 Resume Agent 的工具分为只读分析和写入修改两类。

只读工具会自动执行：

- `generate_job_match_summary`：生成岗位匹配摘要，返回 `matched_keywords`、`missing_keywords`、`resume_changes`、`fact_gaps` 和 `top_gaps`。

修改工具需要用户确认：

- `update_overview`：更新项目简介。
- `update_bullet`：更新已有 bullet。
- `add_bullet`：新增 bullet。
- `remove_bullet`：删除 bullet。

每个修改工具都会返回结构化 diff，包括修改前、修改后和修改原因。前端展示确认卡，用户接受后才应用到简历。

## JD 匹配能力边界

当前 JD 匹配是轻量关键词、证据链和能力缺口归并，不是完整语义匹配模型。

它会：

- 从 JD 中提取中英文关键词。
- 排除 JD 字段后，在简历正文中判断命中和缺失。
- 汇总本轮已确认 diff，说明已经补强了哪些表达。
- 把零散缺失关键词归并成 2-3 个能力缺口，例如 RAG 落地经验、Agent 工具调用与工作流编排、工程基础设施经验。
- 为每个 Top gap 返回 JD 证据、建议写入位置、优先级原因、建议补强方向和风险类型。

它当前不会：

- 对 JD 做完整语义匹配。
- 证明用户真实做过某项缺失能力。
- 编造简历里没有证据支撑的经历。

## 系统架构

```text
Frontend (Next.js / React)
  -> FastAPI HTTP API
  -> ResumeAgentStreamService
  -> PiAgentRuntime
  -> Resume Tools
  -> Tool Confirmation Gate
  -> ResumeService / AgentSessionStore
  -> Database
```

关键模块：

- `frontend/src/app/[locale]/resumes/page.tsx`：简历中心，上传、创建、列表和缩略预览。
- `frontend/src/app/[locale]/resume/[id]/edit/page.tsx`：编辑、预览、Agent 对话和导出主页面。
- `frontend/src/app/[locale]/resume/[id]/interview/page.tsx`：语音模拟面试页面。
- `backend/app/entrypoints/http/upload.py`：简历上传后台任务和 JD OCR。
- `backend/app/entrypoints/http/resume_agent.py`：Resume Agent SSE、工具确认和 session 恢复入口。
- `backend/app/agents/resume/`：Agent 定义、提示词上下文和工具执行。
- `backend/app/runtime/`：pi-agent-core 适配、流事件、确认策略和恢复逻辑。
- `backend/app/tools/resume/`：结构化简历工具。
- `backend/app/services/agent/job_match_summary.py`：JD 匹配摘要和 Top gaps 逻辑。
- `backend/app/entrypoints/http/interviews.py`：模拟面试 session API。
- `eval/`：Agent eval 用例、评分和趋势分析脚本。

## 技术栈

- 前端：Next.js 16.2、React 18、TypeScript、Tailwind CSS、next-intl
- 后端：FastAPI、SQLAlchemy 2、Pydantic v2、Alembic、uv
- Agent：pi-agent-core、OpenRouter、自定义 runtime adapter
- 语音：火山引擎实时语音对话、ASR、MiniMax TTS
- 支付：PayPal Subscription
- 测试：pytest、Playwright

## 主要目录

```text
backend/app/entrypoints/http/  # FastAPI 路由
backend/app/agents/resume/     # 简历 Agent 定义和提示词上下文
backend/app/runtime/           # pi-agent-core 运行时适配、确认和恢复
backend/app/tools/resume/      # 简历工具
backend/app/services/          # 业务服务
backend/app/state/             # Agent session 存储和 SSE 回放
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
