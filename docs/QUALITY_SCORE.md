# 质量评分

本文档记录 chat-resume 的质量评分维度、当前基线和下一步改进重点。评分基于当前仓库代码、项目文档和本地验证命令，重点服务回归控制，而不是给项目做静态宣传。

## 评分维度

| 维度 | 权重 | 当前评分 | 判断依据 |
| --- | ---: | ---: | --- |
| 功能正确性 | 25% | 8/10 | 核心上传、简历编辑、Resume Agent、面试、订阅链路都有明确路由和测试覆盖；语音供应商链路仍依赖外部环境验证 |
| 回归风险 | 20% | 7/10 | 关键链路有后端单测和部分 e2e；编辑页、SSE、语音、支付仍是高耦合回归面 |
| 测试覆盖 | 20% | 7/10 | 后端测试覆盖 Agent、认证、账单、上传、评估等领域；前端主要依赖 type-check/build/e2e，组件级覆盖较少 |
| 用户体验 | 15% | 7/10 | 简历编辑工作台、结构化预览、Agent 确认流已成型；上传、导出、语音异常态仍需要更多真实浏览器验证 |
| 可维护性 | 10% | 7/10 | 后端模块边界已拆分为 entrypoints/services/runtime/state/tools；编辑页仍是前端最大复杂页面 |
| 日志诊断 | 10% | 7/10 | 已有 request id、错误日志、慢请求、慢 SQL 和 Agent 运行日志；已移除外部观测栈，后续重点是日志检索和保留策略 |

加权总分：`7.4 / 10`

## 当前状态

基线时间：2026-05-15 Asia/Shanghai。

当前主干核心能力：

- 上传简历后异步解析为结构化内容。
- 编辑页支持结构化编辑、自动保存、分页预览、导出和 Resume Agent 优化。
- Resume Agent 支持工具确认、暂停恢复、SSE cursor 回放和外部模型故障降级。
- 面试链路已拆成本地结构化 session 和数字人/语音供应商代理。
- 订阅能力由 PayPal checkout、status、webhook 和 `require_active_subscription()` 保护高成本入口。
- 日志覆盖请求日志、慢请求、错误 request id、数据库耗时和 Agent 运行事件。

## 验证基线

| 检查项 | 命令 | 结果 |
| --- | --- | --- |
| 后端测试 | `cd backend && uv run --extra dev python -m pytest tests -q` | 通过：358 passed，7 warnings，3 subtests passed，用时 72.43s |
| 后端类型检查 | `cd backend && uv run basedpyright` | 通过：0 errors，0 warnings，0 notes |
| 前端类型检查 | `cd frontend && npm run type-check` | 通过：`tsc --noEmit -p tsconfig.typecheck.json` |
| 前端生产构建 | `cd frontend && npm run build` | 通过：Next.js 16.2.6 Turbopack build 成功，生成 18 个静态页面 |

## 已知风险

- `frontend/src/app/[locale]/resume/[id]/edit/page.tsx` 是当前最大页面，集成了加载、保存、预览、聊天、SSE、导出和选择工具条，后续改动需要更小切片和浏览器 smoke。
- SSE 与工具确认跨越 `backend/app/types/stream.py`、`ResumeAgentStreamService`、`useStreamingChat()`、编辑页渲染和历史消息兼容，新增事件必须双端验证。
- 语音面试依赖外部供应商 WebSocket、麦克风权限、订阅状态和本地 interview session，纯单测不能证明真实可用。
- PayPal webhook 正确性依赖供应商验签、幂等事件和本地订阅状态机，生产环境必须用真实 sandbox/live webhook 验证。
- 上传和 JD OCR 会把用户简历/JD 发送给模型或 OCR 供应商，隐私说明、供应商数据保留和日志采样仍需产品层确认。
- `docs/SECURITY.md` 记录了当前安全缺口：用户自助删除/导出、生产数据保留周期、供应商侧数据处理策略仍未实现。

## 改进优先级

1. 对编辑页主流程补一条稳定 e2e：登录、进入已有简历、触发 Agent 工具确认、保存、导出。
2. 对语音面试补真实浏览器 smoke 脚本，至少验证 session 创建、供应商会话创建、WebSocket 认证失败和成功路径。
3. 给 PayPal webhook 状态机补更多乱序、重复、签名失败、plan 不匹配测试。
4. 建立上传任务、Agent event、导出文件、过期 refresh session 的生产清理策略。
5. 把安全配置检查做成部署前 checklist，覆盖 `SECRET_KEY`、Cookie、CORS、OAuth redirect、PayPal API base、日志脱敏开关。

## 验证命令

后端最小回归：

```bash
cd backend
uv run --extra dev python -m pytest tests -q
```

后端类型检查：

```bash
cd backend
uv run basedpyright
```

前端最小回归：

```bash
cd frontend
npm run type-check
npm run build
```

前端端到端：

```bash
cd frontend
npm run e2e
```

本仓库默认不使用 Ruff、Black 或通用 lint 作为质量门禁。
