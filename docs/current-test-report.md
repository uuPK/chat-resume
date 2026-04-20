# 当前测试现状报告（2026-04-21）

## 1. 报告目标

这份报告用于回答 3 个问题：

1. 当前项目到底有哪些测试资产。
2. 这些测试现在能不能跑通。
3. 测试覆盖了哪些核心链路，还缺哪些高风险场景。

本次报告以“先盘点，再执行，再给结论”为原则，不只按文件名做静态判断。

## 2. 结论摘要

- 后端当前共有 `12` 个测试文件，`168` 个 `pytest` 用例，实测全部通过。
- 前端当前共有 `2` 个 Playwright E2E 文件，`19` 个测试用例，实测全部通过。
- 前端 TypeScript 类型检查通过。
- 现有测试总量不算少，主力集中在后端接口、简历 Agent、简历解析和认证流程。
- 前端测试目前明显偏向“登录/仪表板/新建简历”主链路，缺少更细粒度的组件测试和对 AI/面试工作台的 E2E 覆盖。
- 仓库中未发现自动执行测试的 GitHub Actions workflow，当前 CI 主要是 Claude 相关流程，不承担测试守门责任。

## 3. 本次实际执行结果

### 3.1 执行命令

```bash
cd backend
uv sync --extra dev
uv run pytest tests --collect-only -q
uv run pytest tests -q

cd ../frontend
npm run type-check
npx playwright test --list
npm run e2e
```

### 3.2 实测结果

| 项目 | 命令 | 结果 |
| --- | --- | --- |
| 后端依赖 | `uv sync --extra dev` | 成功，同步开发依赖后补齐 `pytest` |
| 后端收集 | `uv run pytest tests --collect-only -q` | `168 tests collected in 8.07s` |
| 后端执行 | `uv run pytest tests -q` | `168 passed, 3 warnings in 59.82s` |
| 前端类型检查 | `npm run type-check` | 通过 |
| 前端用例枚举 | `npx playwright test --list` | `19 tests in 2 files` |
| 前端 E2E | `npm run e2e` | `19 passed (1.5m)` |

### 3.3 测试执行时的环境前提

- Playwright 配置中没有 `webServer` 自动拉起逻辑，依赖本地已有前端服务。
- 本次执行时，`http://localhost:3000` 可访问，因此前端 E2E 得以直接运行。
- 后端 pytest 主要依赖 `FastAPI TestClient + SQLite 内存库`，不依赖本地 PostgreSQL。

## 4. 测试资产盘点

### 4.1 后端测试分布

| 文件 | 用例数 | 主要覆盖内容 |
| --- | ---: | --- |
| `backend/tests/test_api_e2e.py` | 65 | 认证、简历 CRUD、聊天记录、权限隔离、JD OCR、面试 session、负向场景 |
| `backend/tests/test_resume_parser.py` | 47 | 简历文本基础信息提取、JSON 清洗、解析容错、解析质量评分 |
| `backend/tests/test_resume_agent_smoke.py` | 25 | Resume Agent 工具调用、确认流、恢复逻辑、错误恢复 |
| `backend/tests/test_resume_agent.py` | 9 | Resume Agent prompt/context/schema 约束 |
| `backend/tests/test_resume_schema_normalization.py` | 6 | 简历结构标准化 |
| `backend/tests/test_observability_setup.py` | 4 | 日志/Sentry/Langfuse 观测配置 |
| `backend/tests/test_resume_tool_executor.py` | 4 | 工具执行器和 user memory |
| `backend/tests/test_agent_harness.py` | 2 | Agent harness 事件与确认应用 |
| `backend/tests/test_agent_session_store.py` | 2 | Agent session 存储和观测上下文 |
| `backend/tests/test_interviewer_agent.py` | 2 | Interview Agent 文本输出与 prompt context |
| `backend/tests/test_export_service.py` | 1 | 导出 PDF 服务 |
| `backend/tests/test_user_memory_service.py` | 1 | 用户记忆读写隔离 |

### 4.2 前端测试分布

| 文件 | 用例数 | 主要覆盖内容 |
| --- | ---: | --- |
| `frontend/e2e/auth.spec.ts` | 11 | 注册、登录、错误密码、表单校验、受保护路由鉴权 |
| `frontend/e2e/dashboard.spec.ts` | 8 | 仪表板加载、空状态、新建简历、编辑后返回列表 |

### 4.3 测试代码规模

本次统计到的测试相关代码总计约 `3802` 行：

- 后端测试：`3496` 行
- 前端 E2E：`306` 行

这说明当前测试重心明显偏后端。

## 5. 当前覆盖面判断

### 5.1 已覆盖较好的部分

#### 后端

- 认证链路覆盖较完整：注册、登录、`/me`、刷新 token、登出、失效 token、失活用户。
- 简历 CRUD 与权限隔离覆盖较完整：创建、列表、详情、更新、删除、跨用户访问限制。
- 面试主链路已覆盖到 session 创建、开始、回答、流式回答、提示请求、结束和列表摘要。
- Resume Agent 的核心风险点已覆盖：工具调用、确认/拒绝、可恢复错误、隐藏 section 拒绝、流式事件。
- 简历解析链路覆盖面较好：文本提取、JSON 清洗、容错解析、评分算法。
- 基础设施侧有最低限度守护：日志格式、Langfuse、Sentry、导出服务。

#### 前端

- 账号进入系统的主路径是通的。
- 仪表板到新建简历到编辑页再返回列表的主路径是通的。
- 受保护页面的重定向逻辑已有 E2E 保护。

### 5.2 覆盖相对薄弱的部分

- 前端没有组件级测试，也没有 hook 级测试。
- 前端 E2E 尚未覆盖简历上传的真实文件流程，只验证了“上传按钮存在”。
- 前端 E2E 尚未覆盖 AI 流式聊天、diff 确认、工具确认/拒绝交互。
- 前端 E2E 尚未覆盖面试工作台 `/resume/[id]/interview` 的真实交互。
- 前端 E2E 尚未覆盖导出动作的真实结果，只验证了编辑页存在“导出 PDF”按钮。
- 后端 API E2E 没有看到“真实简历文件上传并解析”的接口级测试，目前只覆盖了 JD OCR 上传。
- 后端集成测试依赖内存 SQLite，不能替代 PostgreSQL/Alembic/真实事务行为验证。
- 没有看到覆盖率统计或最低 coverage 阈值配置。

## 6. 当前风险与观察

### 6.1 结构性风险

- 测试结构明显“后端强、前端弱”，前端复杂页面目前主要依赖 Playwright 兜底。
- Playwright 没有自动启动应用，意味着本地或 CI 环境必须先准备好运行中的服务，否则测试会直接失效。
- 仓库里未发现负责测试的 GitHub Actions workflow，说明当前缺少稳定的自动化回归门禁。

### 6.2 本次执行观察到的 warning / 噪声

- `passlib` 依赖触发 `crypt` 弃用 warning，未来 Python 3.13 需要关注兼容性。
- `FastAPI` 的 `@app.on_event("shutdown")` 已进入弃用路径，建议迁移到 lifespan 事件。
- 后端 pytest 跑完后出现 Sentry 后台线程向已关闭输出流写日志的噪声：
  - 测试结果本身是通过的。
  - 但这会污染测试输出，也说明测试环境下的观测组件关闭动作还不够干净。

## 7. CI 现状

当前 `.github/workflows/` 下仅发现：

- `claude.yml`
- `claude-code-review.yml`

这两个 workflow 都不是测试执行流水线。也就是说，当前仓库虽然有不少测试，但没有看到对应的自动化测试守门配置。

## 8. 优先级建议

### P0：先把测试纳入自动化门禁

- 增加 GitHub Actions 流水线，至少执行：
  - `cd backend && uv sync --extra dev && uv run pytest tests -q`
  - `cd frontend && npm ci && npm run type-check`
  - `cd frontend && npm run e2e`

### P1：补前端高价值 E2E 缺口

- 新增简历上传并解析成功/失败场景。
- 新增 Resume Agent 流式聊天与 diff 确认/拒绝场景。
- 新增面试工作台完整会话场景。
- 新增导出 PDF 的真实结果校验场景。

### P1：补后端真实环境集成验证

- 增加基于 PostgreSQL 的一组最小集成测试。
- 至少覆盖迁移、事务、JSON 字段、权限查询等与 SQLite 行为不完全一致的部分。

### P2：降低前端测试成本

- 为复杂 hook 和关键状态逻辑补单元测试。
- 将 Playwright 留给真正跨页面、跨服务的主流程验证，避免把所有细节都堆进 E2E。

### P2：清理测试噪声

- 在测试环境关闭或 mock Sentry 实际发送。
- 把 `on_event` 迁移到 lifespan。
- 评估 `passlib` 相关依赖的升级路径。

## 9. 最终判断

如果只看“有没有测试”，当前项目测试基础已经不弱，尤其后端。

如果看“测试结构是否均衡、是否足够支撑持续迭代”，当前状态仍有明显短板：

- 后端测试相对扎实。
- 前端测试偏少且集中在浅层主链路。
- 自动化门禁缺失。
- 若后续继续重构编辑页、面试页、Agent 交互，前端回归风险会高于后端。

整体判断：当前测试体系处于“后端中上、前端中等偏弱、自动化不足”的状态，适合进入下一阶段补齐前端关键链路和 CI 守门。
