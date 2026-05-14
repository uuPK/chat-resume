# Pi Agent 示例实现与当前接入对比报告

## 结论

`example/pi` 里的 Pi Agent 不是一个单纯的 LLM 循环示例，而是一套完整的 Agent Harness：底层 `agentLoop` 只负责回合、工具和事件协议；上层 `Agent` 维护可变 transcript、队列、模型和工具状态；再上层 `AgentSession` 负责持久化、系统提示词重建、扩展、压缩、重试、模型/思考等级切换和会话分支。

当前项目已经把 Pi 的核心循环接入到了简历优化链路，但接入方式更像“业务薄适配器”：每次 HTTP/SSE 请求临时构造一个 `AgentContext`，渲染完整系统提示词，暴露整套简历工具，然后把 Pi 事件翻译成简历 UI 事件和 DB session 事件。这个方案更贴合当前产品，但没有复用 Pi 示例里最有价值的会话层、上下文治理层和工具编排层。

如果目标是改善当前 Agent 性能与可恢复性，优先不应继续扩大提示词或继续在工具执行器里堆逻辑，而应借鉴 Pi 的三点：动态工具集、显式消息转换边界、可持久恢复的 AgentSession。

## 架构对照

| 维度 | Pi Agent 示例 | 当前项目 |
| --- | --- | --- |
| 核心循环 | `agentLoop` 只处理 turns、LLM stream、tool calls、事件和终止条件。见 `example/pi/packages/agent/src/agent-loop.ts:31`、`:155`。 | `PiAgentRuntime` 直接调用 `agent_loop`，同时负责提示词、工具包装、确认、trace、SSE 事件翻译。见 `backend/app/runtime/pi_agent_runtime.py:123`、`:230`。 |
| Agent 状态 | `Agent` 拥有 transcript、工具、模型、thinking level、pending queues，并暴露 `steer`/`followUp`。见 `example/pi/packages/agent/src/agent.ts:156`。 | 每次请求临时生成 `AgentContext`；历史只取 `conversation_history` 最近若干条，运行态在 `stream_state` dict 中。见 `backend/app/runtime/pi_agent_runtime.py:230`、`:870`、`:899`。 |
| 会话持久化 | `SessionManager` 记录 session header、message、model/thinking 变更、compaction、branch summary、自定义 entry，能重建上下文。见 `example/pi/packages/coding-agent/src/core/session-manager.ts:27`、`:50`、`:66`、`:161`。 | `AgentSessionStore` 记录业务 session 状态和事件，主要用于确认、回放和审计；不等价于 Pi 的通用 transcript/session tree。见 `backend/app/state/store.py:16`、`:80`、`:172`。 |
| 系统提示词 | `AgentSession` 从 resource loader、skills、context files、选中工具和工具片段重建 prompt。见 `example/pi/packages/coding-agent/src/core/agent-session.ts:918`。 | `ResumeAgent` 用固定 prompt spec，`build_resume_prompt_context` 每轮把 JD 和简历 JSON 放进系统提示词。见 `backend/app/agents/resume/agent.py:103`、`backend/app/agents/resume/prompt_context.py:23`。 |
| 工具暴露 | SDK 默认只启用 `read/bash/edit/write`，支持 `tools` allowlist 和 `noTools`；会话中还能切换 active tools。见 `example/pi/packages/coding-agent/src/core/sdk.ts:271`、`example/pi/packages/coding-agent/src/core/tools/index.ts:138`。 | `ResumeAgent` 把 `RESUME_TOOLS_SCHEMA` 全量交给 runtime，只把部分工具设为 auto-execute。见 `backend/app/agents/resume/agent.py:108`。 |
| 工具执行 | Pi 支持全局 sequential/parallel、单工具 sequential、参数 prepare/validate、`beforeToolCall`、`afterToolCall`、`terminate`。见 `example/pi/packages/agent/src/agent-loop.ts:373`、`:552`、`:641`。 | OpenRouter 请求禁用 parallel tool calls；runtime 对非 auto 工具加 `asyncio.Lock` 串行执行，并用业务逻辑限制首轮只展示一个可确认修改。见 `backend/app/runtime/pi_agent_openrouter.py:278`、`backend/app/runtime/pi_agent_runtime.py:277`、`:389`。 |
| 用户确认 | Pi 的通用扩展点是 `beforeToolCall`/`afterToolCall` 和 `terminate`。 | 当前把确认预览、等待用户、实际执行、终止文本都放在工具包装层。见 `backend/app/runtime/pi_agent_runtime.py:508`、`:587`、`:648`。 |
| 上下文压缩 | `AgentSession` 在手动、阈值、overflow 三种场景压缩并可自动重试。见 `example/pi/packages/coding-agent/src/core/agent-session.ts:1610`、`:1766`。 | 当前只有历史条数裁剪和字段精简，没有 token/usage 驱动的压缩。见 `backend/app/runtime/contracts.py:24`、`backend/app/runtime/pi_agent_runtime.py:870`、`backend/app/agents/resume/prompt_context.py:12`。 |
| Provider 层 | `createAgentSession` 通过 model registry、auth、retry settings、payload/response hooks 和 transport 适配 provider。见 `example/pi/packages/coding-agent/src/core/sdk.ts:320`。 | `stream_openrouter` 直接构造 OpenRouter 请求体和消息格式，模型来自 `settings.OPENROUTER_MODEL`。见 `backend/app/runtime/pi_agent_openrouter.py:278`、`backend/app/runtime/pi_agent_runtime.py:853`。 |
| 可观测性 | Pi 示例把 usage、cost、context usage 放进 session stats，并在 provider hooks 前后可插入扩展。见 `example/pi/packages/coding-agent/src/core/agent-session.ts:208`、`example/pi/packages/coding-agent/src/core/sdk.ts:347`。 | 当前项目有本地日志、Prometheus、Tempo、Langfuse/LangSmith 和 runtime trace；观测链路已经更产品化。见 `docs/OBSERVABILITY.md:3`、`backend/app/services/agent/resume_agent_stream_service.py:85`。 |

## 关键差异分析

### 1. 我们接入的是 Pi loop，不是 Pi AgentSession

Pi 示例的分层很清楚：`agentLoop` 是无 UI、无业务的协议循环；`Agent` 才开始持有长期状态；`AgentSession` 再把文件系统会话、资源加载、工具注册、扩展、压缩和模型管理组合起来。当前项目直接在 `PiAgentRuntime` 里构造 `AgentContext` 并调用 `agent_loop`，因此我们获得了 Pi 的流式事件和工具循环，但没有获得它的长期会话能力。

这解释了当前实现里很多逻辑为什么集中在 `PiAgentRuntime`：工具确认、首轮工具限制、事件翻译、trace、终止文本都在一个类里完成。它可以工作，但后续继续扩功能会让 runtime 变成“业务运行时 + UI 协议 + 权限层 + provider 层”的混合体。

### 2. Pi 的消息边界更强，我们的消息边界偏薄

Pi 明确区分 `AgentMessage` 和 LLM `Message`，只在调用模型前用 `convertToLlm` 转换；coding-agent 还把 bash、custom、branch summary、compaction summary 等自定义消息映射成 LLM 可消费格式。当前项目的 `AgentLoopConfig` 使用 `convert_to_llm=lambda messages: messages`，实际依赖 `stream_openrouter` 再把 Pi message 转 OpenAI-compatible message。

这不是立即错误，但会让 UI/internal 事件、业务事件、摘要消息、确认消息以后更难纳入上下文治理。若后续要支持摘要、恢复、用户插话、内部观察结果，应该把 `convert_to_llm` 变成明确边界，而不是继续默认透传。

### 3. 当前性能压力主要来自“每轮全量输入”

当前每次请求都会渲染系统提示词，并把 JD 文本与精简后的简历 JSON 放入系统提示词；同时 runtime 将所有 resume tools 暴露给模型。虽然 `strip_redundant_fields` 去掉了一些冗余字段，`max_history_messages` 限制了聊天历史，但这仍是“全量简历 + 全量工具 + 最近历史”的模式。

Pi 示例对应的治理手段是两类：一是 active tools，只把当前模式需要的工具暴露出去；二是 compaction，根据 token 使用、上下文窗口和 overflow 进行压缩。对我们来说，active tools 会比 compaction 更先见效，因为它能同时减少 prompt schema 体积、降低工具误选概率，并缩短模型做工具选择前的思考路径。

### 4. 当前确认流程是产品可用的，但抽象层级偏低

当前确认流程有一个好的产品约束：先 preview，用户确认后才修改简历，并且确认后用确定性文本结束当前轮次，避免模型再补一轮。这一点符合简历编辑场景。

问题在于它被实现为工具执行包装逻辑，而 Pi 示例已经有更通用的 hook 位：`beforeToolCall` 可阻断或等待权限，`afterToolCall` 可改写结果和设置 `terminate`。如果把确认迁到 hook 语义上，runtime 可以少知道业务细节，确认、权限、审计、回放会更容易测试。

### 5. 我们的可观测性比 Pi 示例更贴近线上产品

当前项目已有本地 Loki/Prometheus/Tempo、Langfuse/LangSmith observer、runtime trace 和可由 agent 查询的日志/指标工具。这部分不需要照搬 Pi。真正需要补的是把 Pi 示例中的 usage/context/cost 统计也接入现有观测事件，尤其是记录每轮输入 token、工具 schema 数、系统提示词长度、首次 token 延迟、工具等待确认耗时。

## 建议路线

### P0：先做动态工具集

按用户意图把工具分成至少四档：只读问答、简历编辑、JD 匹配、观测诊断。默认不要把所有 resume tools 暴露给每一轮模型。当前 `AgentDefinition` 已经有 `tools_schema`，可以先在 `ResumeAgent` 或 `PiAgentRuntime._build_loop_inputs` 前增加一个小型 tool profile 选择器，产出本轮 tools。

预期收益：降低首包前模型决策成本、减少错误工具调用、减少 OpenRouter 请求体大小。这个改动范围最小，也最符合 Pi 的 active tool 设计。

### P1：引入业务版 AgentSession

不要直接搬 Pi coding-agent 的完整 `AgentSession`，它包含 CLI、bash、扩展、文件会话、分支等很多对简历产品过重的能力。建议做一个业务版 `ResumeAgentSession`，只持久化这些内容：LLM transcript、当前工具 profile、模型配置、确认中的 tool call、摘要边界、最后一次 usage。

它应复用现有 `AgentSessionStore` 的 DB 事件能力，但不要只存 UI stream event；要能重建下一轮 LLM 上下文。

### P1：把确认流程改造成 hook 语义

保留现有 preview/confirm UX，但把“是否需要确认、如何 preview、确认后是否 terminate”从 `_execute_tool` 中拆出来，映射到 Pi 风格的 `beforeToolCall`/`afterToolCall`。短期即使 Python 版 pi core 没暴露同名接口，也可以在我们自己的 runtime 层先建立等价概念。

### P2：建立显式 `convert_to_llm`

把当前 `lambda messages: messages` 改成业务转换函数，明确哪些消息进入 LLM，哪些只用于 UI/审计。后续 compaction summary、resume snapshot、observability result、confirmation result 都通过这个边界进入上下文，而不是散落在 prompt 或 tool result 中。

### P2：补 token/usage 驱动的上下文治理

短期先记录每轮 `prompt_chars`、tool 数、message 数和 OpenRouter usage；中期做简历专用摘要，例如“当前简历结构摘要 + 本轮已确认 diff summary + 最近 N 条对话”。不要优先照搬 Pi 的完整分支压缩，先解决当前产品的全量简历输入问题。

### P3：整理 provider 层

OpenRouter 适配目前可用，但 provider、auth、retry、reasoning/thinking 配置都写在 runtime/openrouter 边界。可以参考 Pi 的 `createAgentSession`，把模型选择、认证、重试、payload/response hook 从业务 runtime 中拆出，便于以后切换 provider 或做模型降级。

## 不建议直接照搬的部分

- 不建议引入 Pi coding-agent 的 bash/edit/write/read 工具体系；它面向代码编辑，不符合简历产品的权限和数据边界。
- 不建议一次性搬扩展系统、skills、slash command、session tree 和 branch summary；这些会显著增加复杂度。
- 不建议把当前 DB session 全部替换成文件 JSONL session；我们的产品已经依赖用户、简历、SSE replay 和确认恢复，DB 事件层应保留。

## 推荐下一步

最有价值的下一步是做一个小切片：给 `ResumeAgent` 增加 tool profile 选择，只在“编辑意图”时暴露修改类工具，在普通问答时只暴露 `read_resume` 或不暴露工具，在观测问题时只暴露 LogQL/PromQL 工具。这个切片能直接验证 Pi active tools 思路对当前性能和工具误触发的影响，且不需要先重构完整 session 层。

验收指标建议：

- 同一条只读问题的 OpenRouter 请求体工具数量下降。
- `agent.trace.llm.request` 增加 tool profile 字段。
- 首次 token 延迟和总延迟可用现有观测栈对比。
- 现有工具确认与简历保存行为不回归。

## 证据索引

- Pi core loop：`example/pi/packages/agent/src/agent-loop.ts:31`、`:155`、`:373`、`:552`、`:641`
- Pi Agent wrapper：`example/pi/packages/agent/src/agent.ts:28`、`:156`、`:197`
- Pi coding session：`example/pi/packages/coding-agent/src/core/agent-session.ts:1`、`:918`、`:967`、`:1610`、`:1766`
- Pi SDK/session 构造：`example/pi/packages/coding-agent/src/core/sdk.ts:193`、`:271`、`:320`
- Pi session manager：`example/pi/packages/coding-agent/src/core/session-manager.ts:27`、`:50`、`:66`、`:161`
- Pi custom message conversion：`example/pi/packages/coding-agent/src/core/messages.ts:140`
- 当前简历 Agent：`backend/app/agents/resume/agent.py:100`
- 当前 Pi runtime：`backend/app/runtime/pi_agent_runtime.py:123`、`:230`、`:277`、`:508`、`:587`
- 当前 OpenRouter adapter：`backend/app/runtime/pi_agent_openrouter.py:278`
- 当前会话和回放：`backend/app/runtime/harness.py:19`、`backend/app/state/store.py:16`
- 当前应用层 SSE 编排：`backend/app/services/agent/resume_agent_stream_service.py:72`
- 当前可观测性：`docs/OBSERVABILITY.md:3`
