# Dependency Boundary Cleanup

## 背景

当前仓库的主干分层已经比较清晰，但在前端和后端边界上仍有几处穿层依赖：

- 前端 `hooks` 和部分组件直接依赖预览组件导出的共享类型
- `JobApplicationEditor` 组件内部直接发起 OCR API 请求
- 后端 `resumes.py` 直接操作聊天记录 ORM
- 后端 `resume_agent.py` 路由层承担了较多简历读取与权限校验细节

## 目标

- 把前端共享的预览模块类型从组件层抽离到 `types` 或 `lib`
- 把组件里的 OCR API 调用下沉回 page / hook 层，恢复组件只收数据和回调
- 把聊天记录 ORM 访问下沉到 `ResumeService`
- 顺手提炼 `resume_agent.py` 的共用辅助逻辑，减少路由层样板代码

## 非目标

- 这次不重做前端页面布局或面试链路交互
- 这次不改动 API 协议本身
- 这次不做大规模目录迁移或命名重构

## 步骤

1. 抽离前端共享模块类型并替换引用 -> verify: `cd frontend && npm run type-check`
2. 下沉 `JobApplicationEditor` 的 OCR 请求并保持编辑页行为一致 -> verify: `cd frontend && npm run lint`
3. 下沉聊天记录访问到 `ResumeService`，并提炼 `resume_agent.py` 辅助函数 -> verify: `cd backend && uv run pytest`
4. 复核执行计划与改动范围，整理验证结果 -> verify: 人工检查计划状态与 git diff

## 决策日志

- 优先收敛已经明确违反架构约束的依赖，不扩大到全仓库重构
- `ResumeModule` / `ModuleConfig` 放入 `frontend/src/types/resumeLayout.ts`，`lib/resumeLayoutConfig.ts` 继续提供默认配置和转换函数
- `JobApplicationEditor` 保留文件校验、粘贴和 UI 状态，OCR 网络请求由 `useResumeEditor` 注入
- 聊天记录接口保持 API 协议不变，仅把 ORM 读写移动到 `ResumeService`

## 验证结果

- `cd frontend && npm run type-check`：通过
- `cd frontend && npm run lint`：通过，保留既有 warning
- `cd backend && uv run ruff check app/services/domain/resume_service.py app/entrypoints/http/resumes.py app/entrypoints/http/resume_agent.py`：通过
- `cd backend && uv run --extra dev python -m pytest tests/test_api_e2e.py -k 'chat_messages or confirm_tool or resume_session'`：5 passed
- `git diff --check`：通过

## 当前状态

已完成：前端共享类型、组件 API 边界、聊天记录 service 化和 Resume Agent 路由辅助逻辑均已收口。

## 下一步

- 后续如继续收边界，可进一步把 `resume_agent.py` 的流式编排抽成专门 application service
