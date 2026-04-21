# 项目结构文档

## 总览

```text
chat-resume/
├── backend/                  # FastAPI 后端
├── frontend/                 # Next.js 前端
├── docs/                     # 项目文档
├── eval/                     # 评测脚本与样例
├── example/                  # 参考/实验目录
├── .github/workflows/        # GitHub 工作流
├── backend.sh                # 后端启动脚本
├── frontend.sh               # 前端启动脚本
├── railway.json              # Railway 部署配置
└── README.md                 # 项目说明
```

## 后端

```text
backend/
├── app/
│   ├── main.py               # 应用入口
│   ├── entrypoints/          # HTTP/API 入口
│   ├── services/             # 业务服务
│   ├── agents/               # Resume / Interview Agent
│   ├── runtime/              # Agent 运行时
│   ├── tools/                # Agent 工具
│   ├── state/                # 会话状态
│   ├── models/               # ORM 模型
│   ├── schemas/              # API Schema
│   ├── prompts/              # Prompt 模板
│   └── infra/                # 配置、数据库、日志、观测
├── alembic/                  # 数据库迁移
├── tests/                    # pytest 测试
├── scripts/                  # 独立脚本
└── uploads/                  # 上传与导出产物
```

关键入口：

- `backend/app/main.py`
- `backend/app/entrypoints/http/router.py`
- `backend/app/entrypoints/http/resumes.py`
- `backend/app/entrypoints/http/resume_agent.py`
- `backend/app/entrypoints/http/interviews.py`

## 前端

```text
frontend/
├── src/
│   ├── app/                  # 页面路由
│   ├── components/           # UI 与业务组件
│   ├── hooks/                # 页面状态与交互逻辑
│   ├── lib/                  # API、鉴权、TTS/ASR 封装
│   ├── styles/               # 样式
│   └── types/                # 类型定义
├── e2e/                      # Playwright 测试
├── public/                   # 静态资源
├── scripts/                  # 脚本
├── middleware.ts             # 前端鉴权中间件
└── package.json              # 前端脚本与依赖
```

关键页面：

- `frontend/src/app/resumes/page.tsx`
- `frontend/src/app/resume/[id]/edit/page.tsx`
- `frontend/src/app/interviews/page.tsx`
- `frontend/src/app/resume/[id]/interview/page.tsx`

## 其他目录

- `docs/`：文档
- `eval/`：评测脚本与测试样例
- `example/`：参考项目或实验目录
- `.github/workflows/`：仓库自动化流程

## 建议阅读顺序

1. `README.md`
2. `frontend/src/app/resumes/page.tsx`
3. `frontend/src/app/resume/[id]/edit/page.tsx`
4. `backend/app/main.py`
5. `backend/app/entrypoints/http/router.py`
6. `backend/app/services/`

## 一句话总结

这是一个以前端工作台为入口、以后端服务和 Agent 运行时为核心的前后端分离项目。
