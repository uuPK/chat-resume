# AI 面试系统 Spec

## 1. Overview
### 1.1 项目概述
AI 面试系统是一个面向求职者的结构化面试训练产品。用户上传或选择已有简历、填写目标岗位 JD 与面试配置后，系统会自动生成一场可执行的模拟面试计划，并以逐轮问答的方式推进整场面试。

这个系统的目标不是提供一个“会聊天的面试机器人”，而是提供一个“可控、可评分、可复盘的面试引擎”。它需要像真实面试一样发问、追问、切题和结束，同时在每一轮结束后保存状态、沉淀证据，并在整场面试结束后生成结构化报告。

相比纯聊天式 AI 面试产品，这个系统的核心差异在于：面试流程由后端编排系统控制，模型负责生成内容与评估结论，而不是自由主导整个过程。这样可以显著提升稳定性、可解释性和产品可扩展性。

### 1.2 产品定位
该系统是 `Chat Resume` 的面试训练子系统，服务于“从简历优化延伸到面试训练”的求职闭环。它应与简历编辑、JD 输入、语音能力、历史记录和报告模块形成统一体验，而不是作为一个独立的随机聊天窗口存在。

## 2. Product Goal
### 2.1 核心目标
1. 帮助用户基于真实简历与目标岗位完成一场结构化模拟面试。
2. 让面试过程具备连续追问、切题、结束和评分等真实面试特征。
3. 为用户输出可解释、可执行的逐题反馈和整场复盘报告。
4. 让面试记录、评分结果和报告可持久化保存，支持后续训练和对比。
5. 在现有 `Chat Resume` 架构上平滑集成，不推翻已有简历与 AI 能力链路。

### 2.2 非目标
- 不追求首版就支持企业端招聘流程或 ATS 集成。
- 不追求首版就实现多 Agent 同时扮演多位面试官。
- 不追求首版就实现复杂数字人、摄像头分析或作弊检测。
- 不追求首版就实现全双工低延迟语音面试。
- 不追求首版覆盖所有岗位族群和所有面试题型。

## 3. Target Users
### 3.1 目标用户
- 正在准备面试的求职者，希望围绕目标岗位进行高针对性训练。
- 已经完成简历编辑，希望继续练习自我介绍、项目深挖和岗位问答的用户。
- 需要多次模拟训练并观察自己进步情况的用户。

这些用户的共同痛点是：缺少稳定的模拟面试对象，无法系统性复盘自己的表达与内容问题，也难以把“简历优化”自然延伸到“面试准备”。

### 3.2 典型使用场景
- 场景 1：用户刚完成简历优化，希望基于同一份简历和 JD 立刻开始模拟面试。
- 场景 2：用户准备明天的后端岗位面试，希望重点训练项目深挖和技术追问。
- 场景 3：用户想只练自我介绍和行为面，希望系统做高频追问和即时点评。
- 场景 4：用户已经练过多次，希望查看历史场次并识别自己重复出现的问题。

## 4. Core Product Experience
### 4.1 核心用户流程
1. 用户选择一份简历，填写目标岗位名称、公司、JD、难度和面试类型。
2. 系统解析简历与 JD，生成一份本场面试计划，明确覆盖的面试轮次与重点。
3. 用户开始面试，系统按当前轮次提出第一个问题。
4. 用户通过文本或语音回答当前问题。
5. 系统对本轮回答进行结构化评估，判断是继续追问、切换下一题，还是进入下一轮。
6. 面试持续推进，直到达到结束条件。
7. 系统生成最终报告，展示总评、逐题反馈、风险点与后续训练建议。
8. 用户可回看整场问答、评分和报告，并开始下一场训练。

### 4.2 成功体验定义
- 用户能在 1 分钟内完成一场面试的启动配置。
- 面试中的问题与追问明显围绕简历和 JD，而不是随机泛问。
- 用户能感知到系统确实“在控制流程”，而不是普通聊天。
- 每轮反馈足够具体，能指出失分原因和建议补法。
- 刷新页面或中断后，面试仍然可以恢复，不丢失当前状态。

## 5. Core Features

### Feature 1: 面试配置与启动
#### Purpose
把简历、岗位、难度和面试类型转化为一次可执行的面试 session。

#### User Stories
- 作为求职者，我希望基于某份简历和某个岗位启动面试，这样问题才有针对性。
- 作为求职者，我希望选择面试类型和难度，这样系统不会一直用单一风格发问。

#### Functional Description
系统支持用户选择简历、输入 JD、选择岗位名称、公司、面试类型、难度和语言。提交后创建一条 `InterviewSession`，并写入启动配置与初始状态。

#### Inputs
- `resume_id`
- `target_title`
- `target_company`
- `jd_text`
- `interview_type`
- `difficulty`
- `language`
- `mode`（text / voice）

#### Outputs
- 已创建的 `InterviewSession`
- 初始状态 `interview_ready`
- 面试配置快照

#### Key UX Expectations
- 配置项尽量少，但足够表达目标岗位与训练重点。
- 已在简历中填写过的岗位信息应自动带入，减少重复输入。

### Feature 2: 面试计划生成
#### Purpose
在正式对话前生成结构化面试计划，避免纯聊天式随机提问。

#### User Stories
- 作为求职者，我希望知道这场面试大致会覆盖哪些部分，这样我有预期。
- 作为系统，我需要先生成轮次计划，这样后续追问和切题才可控。

#### Functional Description
系统根据简历、JD 和面试类型生成 `InterviewPlan`。计划至少包含轮次列表、每轮目标、题目方向、预期考察点和结束条件。

#### Inputs
- 结构化简历
- JD 解析结果
- 面试配置

#### Outputs
- `InterviewPlan`
- 每轮的 `round_type`、`goal`、`focus_points`

#### Key UX Expectations
- 可在开始前向用户简要展示本场面试重点。
- 不要求一开始生成全部题目，但必须生成全局轮次计划。

### Feature 3: Session / Turn 状态编排
#### Purpose
把一场面试从自由聊天改造成有状态、有轮次、有恢复能力的流程系统。

#### User Stories
- 作为用户，我希望系统知道当前是第几题、是否还在追问、什么时候结束。
- 作为系统，我希望每轮问答都能独立保存，这样评分和报告有依据。

#### Functional Description
系统以 `InterviewSession` 表示整场面试，以 `InterviewTurn` 表示单轮问答。每一轮都经过 `asked -> answered -> evaluated -> done` 或 `followup_pending` 的状态流转。后端编排器根据当前状态决定下一步动作。

#### Inputs
- 当前 session 状态
- 当前 turn 状态
- 用户回答
- 评估结果

#### Outputs
- 新状态
- 新问题或追问
- 已持久化的 turn 记录

#### Key UX Expectations
- 页面刷新后可恢复到正确题目和正确状态。
- 前后端展示的轮次和后端状态必须一致。

### Feature 4: 动态提问与追问
#### Purpose
让面试更接近真实面试，而不是固定题库轮播。

#### User Stories
- 作为求职者，我希望系统能针对我的回答继续深挖，而不是机械跳题。
- 作为求职者，我希望当我回答已经足够完整时，系统不要没完没了追问。

#### Functional Description
系统使用规则 + LLM 的混合方式决定当前轮是继续追问还是切换下一题。规则层负责稳定性，模型层负责自然语言问题生成和追问聚焦点。

#### Inputs
- 当前问题
- 用户回答
- 预期考察点
- 回答评估结果
- 已追问次数

#### Outputs
- `action`: follow_up / next_question / end_interview
- 追问内容或下一题内容

#### Key UX Expectations
- 一次只问一个核心问题。
- 对空泛回答，应优先追问背景、动作、结果、个人贡献。
- 对已经充分回答的问题，应及时切题，避免疲劳。

### Feature 5: 结构化评估与评分
#### Purpose
让每轮回答都能落到可解释、可展示的结构化结论上。

#### User Stories
- 作为求职者，我希望知道自己具体哪里答得差，而不是只拿到一个总分。
- 作为系统，我希望评分结果能作为后续追问和最终报告的输入。

#### Functional Description
系统在每轮回答后调用评估模块输出结构化评分。评分至少覆盖沟通表达、逻辑结构、内容深度、岗位匹配度和风险点。每个维度都要有分数、证据和建议。

#### Inputs
- 当前问题
- 用户回答
- 当前轮目标
- 简历与 JD 上下文

#### Outputs
- `dimension_scores`
- `evidence`
- `gaps`
- `improvement_suggestions`
- `should_follow_up`

#### Key UX Expectations
- 同一回答在多次评估下结果波动应尽量小。
- 所有分数都应有明确证据，不可只返回结论。

### Feature 6: 面试报告与历史复盘
#### Purpose
把整场面试沉淀为可复盘、可对比、可继续训练的资产。

#### User Stories
- 作为求职者，我希望结束面试后立刻看到完整总结和训练建议。
- 作为求职者，我希望以后能回看这场面试，知道自己进步了没有。

#### Functional Description
系统在面试结束后汇总所有 turns 与评分结果，生成最终报告。报告包含总评、分维度表现、逐题摘要、主要风险点和建议训练方向。历史 session 应在面试中心可见。

#### Inputs
- 全部 turns
- 全部评估结果
- session 配置

#### Outputs
- `InterviewReport`
- `overall_score`
- `strengths`
- `weaknesses`
- `next_training_plan`

#### Key UX Expectations
- 报告应生成在同一 session 下，避免跳转到过时页面。
- 用户能快速定位到最差的一题和最值得改的一点。

### Feature 7: 语音输入输出
#### Purpose
增强面试临场感，但不让语音链路破坏主流程可控性。

#### User Stories
- 作为求职者，我希望系统能把问题播报出来，也能识别我的语音回答。
- 作为求职者，我希望语音功能出问题时还能回退到文本模式。

#### Functional Description
系统支持 TTS 播报当前问题，支持语音输入转写为回答文本。语音链路作为输入输出适配层，不直接决定面试编排逻辑。

#### Inputs
- 当前问题文本
- 用户音频

#### Outputs
- TTS 音频
- ASR 转写文本

#### Key UX Expectations
- 首版优先支持“半实时”语音，不要求全双工对话。
- 语音异常时应可无损回退到文本。

## 6. AI Opportunities

### AI Capability 1: 简历与 JD 对齐分析
#### Why It Matters
面试问题是否准确，取决于系统是否理解简历与岗位的匹配关系。

#### What It Does
提取简历强项、短板、可追问点和风险点，并与 JD 要求做映射。

#### User Trigger
用户启动面试或更新岗位信息时。

#### Expected Output
- `strength_matches`
- `gap_areas`
- `high_risk_claims`
- `recommended_focus_areas`

#### Risk / Limitation
如果简历本身信息过少，分析结果会偏泛，需要前端提醒用户补足岗位信息。

### AI Capability 2: 问题与追问生成
#### Why It Matters
真实感来自问题是否贴合用户背景，是否会顺着回答追下去。

#### What It Does
根据当前轮目标和用户回答生成自然、尖锐、聚焦的问题文本。

#### User Trigger
面试开始时或某轮回答评估完成后。

#### Expected Output
- 当前问题
- 追问文本
- 可选的提问意图标签

#### Risk / Limitation
纯 LLM 驱动容易发散，必须受 session/turn 状态和规则约束。

### AI Capability 3: 结构化评分
#### Why It Matters
结构化评分是追问决策、报告生成和长期追踪的基础。

#### What It Does
把回答转为多维评分、证据和改进建议。

#### User Trigger
用户提交当前轮回答后。

#### Expected Output
符合固定 JSON Schema 的评分卡。

#### Risk / Limitation
评分稳定性会受 prompt 和模型波动影响，需要通过 rubric 和 schema 收紧输出。

### AI Capability 4: 面试报告生成
#### Why It Matters
用户训练价值最终体现在复盘质量上。

#### What It Does
基于整场面试问答和评分汇总高价值的总结与建议。

#### User Trigger
用户结束面试时。

#### Expected Output
- 总评
- 维度总结
- 关键失分点
- 后续训练建议

#### Risk / Limitation
如果前置 turns 结构化信息不足，最终报告容易变成空泛总结。

## 7. Product Design Principles
1. **流程可控优先于聊天自然**：先保证编排稳定，再追求“像真人”。
2. **单轮闭环优先于全局炫技**：每轮必须可问、可答、可评、可存。
3. **证据优先于结论**：评分和建议必须附带依据。
4. **先文本闭环，再增强语音**：语音是体验增强，不是系统前提。
5. **状态必须可恢复**：页面刷新、中断重连后不能丢 session。
6. **AI 负责生成内容，不负责掌控流程**：流程控制权在后端编排器。
7. **先做好单面试官模型，再扩展复杂角色**：首版避免多 Agent 失控。

## 8. High-Level Technical Design
### 8.1 System Components
- 前端面试工作台
- 面试配置与计划服务
- Interview Orchestrator
- Question Generator
- Answer Evaluator
- Report Generator
- 语音适配层（ASR / TTS）
- 数据存储层

### 8.2 High-Level Architecture
- 前端负责面试配置、问答展示、评分展示、报告展示和状态恢复。
- 后端 API 负责 session 管理、turn 持久化、编排决策和模型调用。
- AI 层负责问题生成、追问生成、回答评分和报告生成。
- 数据层负责保存 session、turn、消息、评分和报告。
- 语音层负责问题播报与语音转写，不直接参与编排决策。

### 8.3 Data Flow
1. 用户提交面试配置。
2. 后端创建 `InterviewSession`，解析简历与 JD，并生成 `InterviewPlan`。
3. 编排器根据计划生成第一题并创建首个 `InterviewTurn`。
4. 用户提交回答。
5. 后端保存回答并调用评估模块生成结构化结果。
6. 编排器根据评分结果决定追问、切题或结束。
7. 后端创建下一条 turn 并把问题流式推送给前端。
8. 面试结束后，后端汇总 turns 生成 `InterviewReport`。
9. 前端渲染报告并在历史列表展示本场面试。

### 8.4 Recommended Stack
- Frontend: Next.js / React / TypeScript
- Backend: FastAPI
- Database: PostgreSQL（开发期可兼容 SQLite）
- Realtime: SSE 或 WebSocket
- AI Integration: OpenAI-compatible Responses API with structured outputs
- Storage: 本地文件或对象存储
- Cache / Recovery: Redis 或数据库状态恢复机制

### 8.5 Key Technical Constraints
- Session 和 turn 必须持久化，不能只存在前端内存里。
- AI 输出需要强结构化，便于驱动后续流程。
- 评分与报告必须可复现、可解释，不能完全依赖自由文本。
- 语音链路失败时，主流程仍能用文本模式完整运行。
- 前后端必须共享明确的状态定义与事件契约。

## 9. Artifacts and State
本系统需要显式保存以下中间产物与运行状态：

- `InterviewSession`
  保存整场面试配置、状态、当前轮次和结束信息。
- `InterviewPlan`
  保存轮次计划、重点和预期考察点。
- `InterviewTurn`
  保存每轮问题、回答、评分和状态。
- `InterviewScorecard`
  保存维度评分、证据和建议。
- `InterviewReport`
  保存整场汇总报告。
- `Stream Events`
  保存前端恢复和调试所需的关键流式事件快照。

这些 artifacts 不能只依赖模型上下文临时存在，否则页面刷新、服务重启或后续分析都会失去依据。

## 10. Orchestration Model
### 10.1 核心思路
面试编排系统采用“规则驱动流程，LLM 驱动内容”的方式：

- 规则层决定：
  - 何时开始
  - 当前是第几轮
  - 是否继续追问
  - 是否切换下一题
  - 是否结束面试
- LLM 层决定：
  - 当前问题怎么表达
  - 追问聚焦什么细节
  - 回答质量如何
  - 最终报告如何总结

### 10.2 Session State
推荐状态集合：

- `created`
- `interview_ready`
- `asking`
- `waiting_user_answer`
- `evaluating`
- `followup_decision`
- `round_finished`
- `completed`
- `report_generating`
- `report_ready`
- `failed`

### 10.3 Turn State
推荐状态集合：

- `planned`
- `asked`
- `answered`
- `evaluated`
- `followup_pending`
- `done`
- `skipped`

### 10.4 Decision Loop
每轮问答按固定循环运行：

1. 读取当前 session 和 turn。
2. 接收用户回答并持久化。
3. 调用评估器输出结构化评分。
4. 根据规则判断：
   - 如果回答不足且追问次数未达上限，生成追问。
   - 如果当前轮目标已完成，切到下一题。
   - 如果达到结束条件，结束面试。
5. 更新状态并推送前端。

### 10.5 End Conditions
系统至少应支持以下结束条件：

- 达到预设题数上限
- 所有计划轮次已覆盖
- 用户主动结束
- 多次无效回答或超时

## 11. Data Model
### 11.1 interview_sessions
关键字段建议：
- `id`
- `user_id`
- `resume_id`
- `target_title`
- `target_company`
- `jd_text`
- `interview_type`
- `difficulty`
- `language`
- `mode`
- `status`
- `current_round_index`
- `current_turn_index`
- `plan_json`
- `overall_score`
- `report_data`
- `started_at`
- `ended_at`

### 11.2 interview_turns
关键字段建议：
- `id`
- `session_id`
- `turn_index`
- `round_index`
- `question`
- `question_type`
- `intent`
- `expected_points`
- `answer`
- `evaluation`
- `score`
- `follow_up_count`
- `status`
- `asked_at`
- `answered_at`

### 11.3 interview_messages
可选扩展，用于保留更细的聊天展示记录：
- `id`
- `session_id`
- `turn_id`
- `role`
- `content`
- `message_type`
- `created_at`

### 11.4 interview_reports
如不直接复用 `report_data` 字段，可独立拆表：
- `id`
- `session_id`
- `overall_score`
- `dimension_scores`
- `strengths`
- `weaknesses`
- `risk_flags`
- `next_training_plan`
- `created_at`

## 12. API Surface
建议的核心接口如下：

- `POST /api/interviews`
  创建 session 并生成面试计划。
- `GET /api/interviews/{id}`
  获取 session、plan、当前状态和当前 turn。
- `POST /api/interviews/{id}/start`
  正式开始面试并生成第一题。
- `POST /api/interviews/{id}/answer`
  提交当前轮回答并触发评估与编排。
- `POST /api/interviews/{id}/next`
  用户主动要求下一题。
- `POST /api/interviews/{id}/end`
  主动结束面试并生成报告。
- `GET /api/interviews/{id}/report`
  获取报告。
- `GET /api/interviews`
  获取历史 session 列表。

如果继续采用 SSE，可额外提供：
- `POST /api/interviews/{id}/stream`
  统一返回问题文本、评分、状态变更和最终报告事件。

## 13. Prompt Architecture
推荐拆成 4 类 prompt：

### 13.1 Interview Planner Prompt
负责生成面试计划、轮次目标和初始题目方向。

### 13.2 Interviewer Prompt
负责根据当前轮目标和追问焦点生成自然语言问题。

### 13.3 Evaluator Prompt
负责按固定 schema 输出评分、证据、缺口和追问建议。

### 13.4 Reporter Prompt
负责基于全部 turns 和评分结果生成最终报告。

不建议把以上能力全部塞进一个巨大 system prompt 中。

## 14. MVP Scope
### 14.1 MVP 必做
1. 基于简历和 JD 创建面试 session。
2. 生成面试计划。
3. 支持文本模式逐轮问答。
4. 支持结构化评估与追问决策。
5. 支持结束面试与生成报告。
6. 支持历史 session 列表和报告回看。

### 14.2 MVP 可选
- TTS 播报问题
- ASR 单次转写回答
- 用户主动下一题 / 跳题
- 简易维度图表展示

### 14.3 MVP 不做
- 多面试官模式
- 企业端管理后台
- 视频与表情分析
- 全双工语音
- 摄像头监考或作弊检测

## 15. Risks and Open Questions
### 15.1 主要风险
- 评分波动导致用户不信任结果。
- 追问策略过强或过弱导致体验失真。
- 自由聊天入口与结构化面试入口并存，容易造成产品认知混乱。
- 旧的报告页和新面试工作流如果继续并存，会继续放大规格不一致。

### 15.2 待决问题
- 是否保留“自由聊天式面试”作为模式之一，还是完全迁移到 session/turn 编排模式。
- 报告是存在 `interview_sessions.report_data` 中，还是独立拆表。
- 前端是继续使用 SSE，还是为面试模块单独引入 WebSocket。
- 语音首版是只做 TTS，还是同时接入单次 ASR。

## 16. Implementation Phases
### Phase 1
- 补齐 session/turn 持久化
- 落地统一状态机
- 接入 planner / evaluator / reporter
- 打通文本面试闭环

### Phase 2
- 优化追问策略
- 加入历史复盘与图表
- 接入 TTS / ASR 的半实时模式

### Phase 3
- 加入岗位专项训练模式
- 加入多轮成长追踪
- 探索多角色面试与更强语音体验
