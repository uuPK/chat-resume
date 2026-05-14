# 前端说明

本文档记录前端应用结构、状态管理、API 约定和页面实现规范。

## 技术栈

- Next.js 16 App Router
- React 18
- TypeScript
- Tailwind CSS
- next-intl
- npm

## 关键目录

- `frontend/src/app/`：页面、布局和路由。
- `frontend/src/components/`：可复用组件和业务组件。
- `frontend/src/lib/`：API 客户端、状态和工具函数。
- `frontend/src/hooks/`：页面级业务 hooks。
- `frontend/src/types/`：共享类型定义。
- `frontend/locales/`：中英文翻译 namespace。
- `frontend/tests/`：Playwright e2e 测试。

## 路由结构

- `frontend/src/app/[locale]/page.tsx`：本地化首页。
- `frontend/src/app/[locale]/dashboard/page.tsx`：登录后的工作台。
- `frontend/src/app/[locale]/resumes/page.tsx`：简历中心。
- `frontend/src/app/[locale]/resume/[id]/edit/page.tsx`：简历编辑、预览、Agent 优化和导出主页面。
- `frontend/src/app/[locale]/resume/[id]/interview/page.tsx`：实时语音面试页面。
- `frontend/src/app/[locale]/interviews/page.tsx`：面试记录和创建入口。
- `frontend/src/app/[locale]/settings/page.tsx`：账户和订阅设置。
- `frontend/src/app/(print)/resume/print/page.tsx`：打印/导出专用页面。

`frontend/src/proxy.ts` 负责 locale 归一化和页面级登录保护。不要只依赖页面组件判断登录态。

## API 约定

- `frontend/src/lib/httpClient.ts` 是普通 REST 请求的底层封装。
- `frontend/src/lib/api.ts` 暴露 `ResumeAPI` 等页面使用的业务 API。
- 认证请求默认走 Cookie，`AuthProvider` 在 `frontend/src/lib/auth.tsx` 中保存当前用户快照到 `localStorage`。
- 后端错误响应优先读取 `detail`；无法解析时再使用前端本地化兜底文案。
- `NEXT_PUBLIC_API_URL` 决定浏览器请求的后端基址，本地默认是 `http://localhost:8000`。

## 简历编辑页

`frontend/src/app/[locale]/resume/[id]/edit/page.tsx` 是当前最重的页面，主要依赖这些 hooks 和组件：

- `useResumeEditor()`：加载简历、更新局部表单状态，并暴露保存入口。
- `useResumeAutoSave()`：对结构化内容和布局配置做自动保存。
- `usePanelLayout()`：维护左侧编辑、中间预览、右侧聊天面板的宽度。
- `useResumeChatPanel()`：加载和保存简历下的聊天记录。
- `useStreamingChat()`：驱动 `/api/ai/chat/stream` SSE 流、工具确认和断点续传。
- `PaginatedResumePreview` / `ResumeLayoutControls`：预览分页和布局控制。
- `DiffReviewCard`：渲染 Agent 工具调用产生的结构化 diff 和确认按钮。

编辑页从路由参数读取简历 ID 时必须先验证是数字字符串。非法 ID 应回到 dashboard，不能请求 `/api/resumes/NaN` 或 `/api/resumes/NaN/chat-messages`。

## SSE 与工具确认

`useStreamingChat()` 使用 `fetch()` 读取 SSE 文本流，不使用浏览器 `EventSource`，因为当前接口需要 `POST` 请求体和 Cookie。

当前流式协议要点：

- SSE `id:` 和 JSON payload 的 `event_id` 都使用 `{session_id}:{sequence}`。
- 前端用 `lastEventIdRef` 记录最后处理的事件。
- 如果一次读取结束且已有 cursor，前端会用 `Last-Event-ID` header 对同一个 `/api/ai/chat/stream` 发起一次回放请求。
- 后端回放只返回 cursor 之后已经持久化的公开事件，不重新执行 Agent。
- `tool_pending` 事件会在 UI 中显示确认/拒绝；确认结果通过 `/api/ai/chat/confirm-tool` 提交。
- 如果后端返回 `resumable`，说明确认结果已记录但原连接不可继续，页面应走 resume-session 路径。

新增或调整流事件时，需要同时检查：

- `backend/app/types/stream.py`
- `backend/app/services/agent/resume_agent_stream_service.py`
- `frontend/src/hooks/useStreamingChat.ts`
- `frontend/src/app/[locale]/resume/[id]/edit/page.tsx`
- 保存历史消息的 `stream_events` 字段渲染兼容性。

## 面试页面

面试 UI 当前围绕 `useInterviewSession()` 和 `frontend/src/app/[locale]/resume/[id]/interview/page.tsx`：

- 先创建或加载 `/api/interviews` session。
- 再调用 `/api/digital-human/conversations` 获得供应商会话信息。
- `volcengine` 模式下使用 WebSocket `/api/digital-human/voice-session/{session_id}` 传输麦克风音频和实时文本。
- 最终文本通过 `ResumeAPI.recordInterviewMessage()` 写回本地 interview session。

面试体验相关改动应尽量保持 `useInterviewSession()` 这个生命周期边界稳定。

## I18N

- `frontend/src/i18n/request.ts` 加载 `common`、`auth`、`dashboard`、`interview`、`resume` namespace。
- 新增可见文案必须同步维护 `frontend/locales/zh/*.json` 和 `frontend/locales/en/*.json`。
- 页面里不要硬编码能被用户看到的中英文业务文案，除非该文案本身就是数据。

## 验证命令

```bash
cd frontend
npm run type-check
npm run build
npm run e2e
```

前端改动如果触及主交互页，至少用浏览器打开对应路由做一次 smoke 检查。涉及 SSE 或语音时，还要看后端日志中的 `request_id`、`session_id` 和 WebSocket 错误。
