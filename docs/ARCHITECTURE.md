# 架构说明

本文档记录 chat-resume 的当前系统架构、模块边界和关键数据流。

## 系统概览

- 前端：Next.js App Router + React，负责用户界面、状态管理和 API 调用。
- 后端：FastAPI，负责 HTTP API、业务服务、Agent 执行入口和数据库访问。
- Agent 运行时：pi-agent-core 相关适配和运行时契约位于 `backend/app/runtime/`。
- 数据库：本地默认 SQLite，生产使用 PostgreSQL，迁移由 Alembic 管理。

## 目录边界

- `backend/app/entrypoints/http/`：HTTP 路由入口，负责请求/响应适配。
- `backend/app/runtime/`：Agent 运行时、权限和工具执行契约。
- `backend/app/tools/`：Agent 可调用的业务工具。
- `backend/app/services/`：业务服务、外部 API 集成和领域逻辑。
- `backend/app/models/`：SQLAlchemy 数据模型。
- `backend/app/schemas/`：Pydantic 请求和响应结构。
- `frontend/src/app/`：页面和路由。
- `frontend/src/components/`：UI 与业务组件。
- `frontend/src/lib/`：前端 API、状态和工具函数。

## 待补充

- 认证与会话数据流
- 简历上传与解析数据流
- Agent 工具调用与确认流程
- 支付与权限边界
- 部署拓扑
