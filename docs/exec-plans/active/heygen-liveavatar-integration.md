# HeyGen LiveAvatar Integration

## 背景与目标

当前 Tavus 数字人受 conversational credits 限制，面试页需要切换到 HeyGen LiveAvatar。目标是先完成 Full mode 最小闭环：后端安全创建 LiveAvatar session token，前端在面试视频区域启动真实 LiveAvatar 会话。

## 非目标

- 本阶段不接自研 ASR/TTS/LLM 编排。
- 本阶段不把右侧 Copilot Answers 与 LiveAvatar 对话事件双向同步。
- 本阶段不迁移已有 Tavus 代码，只新增可替换供应商能力。

## 分步骤计划

1. 后端新增 HeyGen/LiveAvatar 配置与服务。
   - verify: `cd backend && uv run ruff check app`
2. 后端数字人 API 支持 provider，并返回 LiveAvatar session token。
   - verify: `cd backend && uv run ruff check app/entrypoints/http/digital_human.py app/services/digital_human`
3. 前端接入 `@heygen/liveavatar-web-sdk`，在视频区启动/停止 LiveAvatar。
   - verify: `cd frontend && npm run type-check`
4. 更新页面错误与关闭逻辑。
   - verify: `cd frontend && npm run lint -- --file 'src/app/resume/[id]/interview/page.tsx'`

## 决策日志

- 采用 HeyGen LiveAvatar Full mode 作为首版，因为它托管 LLM/TTS/ASR，能最快替换 Tavus 自主对话体验。
- 后端只暴露短期 session token，不向浏览器暴露 `LIVEAVATAR_API_KEY`。

## 当前状态 / 下一步

- 状态：最小闭环代码已完成，等待配置 LiveAvatar 环境变量后联调真实会话。
- 下一步：配置 `LIVEAVATAR_API_KEY`、`LIVEAVATAR_AVATAR_ID`、`LIVEAVATAR_VOICE_ID`、`LIVEAVATAR_CONTEXT_ID` 并重启后端。
