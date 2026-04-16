# Chat Resume 产品规格说明书（Spec）

## 1. 文档目的

本文档基于当前仓库实现编写，目标是把 `Chat Resume` 的产品边界、核心流程、数据结构、接口契约和后续演进方向收敛为一份可执行的规格说明。

这不是营销介绍，也不是理想化 PRD。本文优先描述“代码已经实现了什么”，并明确“当前实现与目标产品之间还缺什么”。

## 2. 产品定义

`Chat Resume` 是一个以简历为中心的 AI 求职辅助系统，包含三条主链路：

1. 简历导入与结构化
2. 简历编辑、预览、导出与 AI 优化
3. 基于简历内容的模拟面试与面试报告

系统形态为前后端分离：

- 前端：Next.js 14 App Router
- 后端：FastAPI
- 存储：SQLAlchemy + PostgreSQL/SQLite 兼容模型
- AI：OpenRouter 驱动简历解析、简历优化、面试问答与评估
- 语音：ASR/TTS 接入火山引擎/MiniMax

## 3. 目标用户

### 3.1 核心用户

- 正在投递岗位的求职者
- 需要快速整理和优化中文简历的用户
- 希望围绕目标岗位进行面试训练的用户

### 3.2 核心使用场景

- 上传已有 PDF/Word/TXT 简历，自动转成结构化内容
- 手动编辑简历并实时预览排版结果
- 围绕岗位 JD 与 AI 对话，让 AI 提出或执行简历改写
- 导出 PDF 简历
- 针对某份简历开启模拟面试，获取逐题反馈与整体报告

## 4. 产品范围

### 4.1 当前已实现范围

- 用户注册、登录、个人信息读取与更新
- 简历上传、AI 解析、CRUD
- 结构化简历编辑器
- 简历实时预览与布局配置
- 简历 AI 对话优化
- 提案记录、应用、拒绝
- 简历聊天历史持久化
- 简历 PDF/HTML/DOCX 导出
- 模拟面试会话创建、继续、结束、删除
- 面试聊天、逐题问答接口、整体评分补算
- 面试报告生成与缓存
- TTS/ASR 后端能力接口

### 4.2 当前不在稳定范围内

- 多用户协作
- 简历版本回滚
- 多模板主题体系
- 支付、订阅、配额管理
- 企业端职位管理
- 真实招聘平台深度集成

## 5. 信息架构

前端主要页面如下：

- `/`：Landing 页
- `/login`、`/register`：认证页
- `/dashboard`：简历列表页，支持上传、新建、删除
- `/resume/[id]/edit`：核心工作台，包含编辑器、预览、AI 助手
- `/resume/[id]/interview`：单份简历的模拟面试页
- `/interviews`：面试记录中心
- `/interviews/[id]/report?resume_id=...`：面试报告页
- `/settings`：设置页
- `/resume/print`：前端打印页，供后端 PDF 导出调用

## 6. 核心用户流程

### 6.1 简历导入流程

1. 用户在 `/dashboard` 上传 PDF / DOC / DOCX / TXT 文件
2. 前端调用 `POST /api/upload/resume`
3. 后端保存原文件，提取纯文本
4. `ResumeParser` 调用 OpenRouter 生成结构化 JSON
5. `ResumeService` 将结果标准化为 `ResumeContent` schema 后落库
6. 前端提示解析质量，并刷新简历列表

成功标准：

- 返回一份可编辑的结构化简历
- 即使 AI 解析失败，也能回退为基础结构，允许手动补全

### 6.2 空白简历创建流程

1. 用户在 `/dashboard` 点击新建简历
2. 前端构造最小内容结构并调用 `POST /api/resumes/`
3. 后端规范化存储
4. 前端跳转到 `/resume/[id]/edit`

### 6.3 简历编辑流程

1. 编辑页加载 `GET /api/resumes/{id}`
2. 用户在各分区编辑结构化字段
3. 前端本地维护 `resume.content`
4. 自动保存逻辑调用 `PUT /api/resumes/{id}`
5. 右侧预览区域即时渲染分页简历
6. 布局配置单独存储在前端本地

编辑分区包括：

- 求职目标
- 个人信息
- 教育经历
- 工作经历
- 技能
- 项目经历

### 6.4 AI 简历优化流程

当前系统以流式链路作为主规格：`POST /api/ai/chat/stream`。

流式交互流程：

1. 用户在编辑页输入优化指令
2. 前端携带 `resume_id`、消息文本、聊天历史请求 SSE
3. 后端加载真实简历内容并交给 `ResumeAgent`
4. `ResumeAgent` 通过 `ResumeTools` 执行读/改简历工具
5. 工具执行前后可进入逐工具确认流程
6. SSE 持续返回文本片段、工具状态、diff 摘要、最终简历内容
7. 若最终内容已变化，后端直接更新 `Resume.content`
8. 前端刷新预览，并把聊天记录与工具确认事件存入 `ResumeChatMessage`

当前统一语义如下：

- AI 输出默认被视为“准备执行的修改”，不是仅供参考的自由文本建议
- 工具调用进入 `tool_pending` 时，前端展示 diff 摘要
- 用户确认后，该工具修改立即应用到最新的 `Resume.content`
- 用户拒绝后，该次工具调用不生效，事件写入会话历史
- 系统不再维护 proposal-first 的 apply/reject 双阶段主链路

对用户而言，唯一需要理解的规则是：

- `确认 = 生效并保存`
- `拒绝 = 不生效`
- 聊天记录和工具事件承担历史留痕职责，而不是单独的 proposal 实体

该规则是当前产品的唯一真相，前后端和文档都应围绕它保持一致。

### 6.5 工具确认与恢复流程

1. 前端收到 `tool_pending` 事件后展示 diff 与确认按钮
2. 用户调用 `POST /api/ai/chat/confirm-tool` 表示确认或拒绝
3. 若流式连接仍活跃，后端继续执行当前 session
4. 若流式连接已结束，后端记录确认结果，并允许通过 `POST /api/ai/chat/resume-session` 恢复执行
5. 若工具被确认且产生实际变更，最新简历内容会直接落库到 `Resume.content`

### 6.6 简历导出流程

1. 用户在编辑页点击导出
2. 前端调用 `POST /api/resumes/{id}/export`
3. 后端按格式选择导出器：
   - `pdf`：使用 Playwright 打开前端打印页后输出 PDF
   - `docx`：服务端生成 Word 文档
   - `html`：服务端生成 HTML 文件
4. 返回下载地址和文件名
5. 用户通过 `/api/resumes/download/{filename}` 下载

### 6.7 模拟面试流程

1. 用户在面试中心选择简历、填写岗位名称/JD
2. 前端调用 `POST /api/resumes/{resume_id}/interview/start`
3. 后端创建 `InterviewSession`
4. 面试页通过 `useInterview` 进入聊天模式
5. 首轮由前端注入欢迎语，提示用户做自我介绍
6. 用户发送回答，前端调用 `POST /api/resumes/{resume_id}/interview/{session_id}/chat`
7. 后端调用 `InterviewAgent.chat` 返回 AI 面试官回复
8. 用户可持续多轮对话，直到结束面试
9. 结束时调用 `POST /api/resumes/{resume_id}/interview/{session_id}/end`
10. 后端生成整体评分并标记会话为 `completed`

注意：

- 当前前端主面试页实际走的是“自由聊天式面试”
- 后端同时还实现了“按问题获取下一题 + 提交答案评分”的结构化接口
- 这两套面试交互模型并存，但前端主流程未完全使用结构化接口

这也是当前系统最重要的规格不一致之一。

### 6.8 面试报告流程

1. 用户从面试中心进入报告页
2. 前端调用 `GET /api/resumes/{resume_id}/interview/{session_id}/report`
3. 后端若已有 `report_data` 且未请求重算，则直接返回缓存
4. 否则调用 `InterviewAgent` 生成报告 JSON
5. 报告写回 `InterviewSession.report_data`
6. 前端展示总分、雷达图、亮点、改进建议等

## 7. 领域模型

### 7.1 User

关键字段：

- `id`
- `email`
- `hashed_password`
- `full_name`
- `is_active`
- `is_superuser`

关系：

- 一个用户拥有多份 `Resume`

### 7.2 Resume

关键字段：

- `id`
- `title`
- `content`：JSON 结构化简历正文
- `original_filename`
- `file_path`
- `owner_id`

关系：

- `optimization_records`
- `interview_sessions`
- `chat_messages`

### 7.3 ResumeContent

当前稳定 schema 由后端 `ResumeContent` Pydantic 模型约束，核心结构包括：

- `meta`
- `parsing_quality`
- `parsing_method`
- `job_application`
- `personal_info`
- `summary`
- `education[]`
- `work_experience[]`
- `skills[]`
- `projects[]`
- `languages[]`
- `custom_sections[]`

设计特征：

- 为数组项生成稳定 `id`
- 兼容旧字段 `description` / `achievements`
- 支持字符串 JSON 自动反序列化
- 对技能、项目、经历做弱结构兼容

### 7.4 ResumeChatMessage

用途：

- 存储用户与 AI 在某份简历上的历史消息
- 记录工具确认事件流，作为 AI 修改留痕的一部分

关键字段：

- `role`
- `content`
- `stream_events`

### 7.6 InterviewSession

关键字段：

- `resume_id`
- `job_position`
- `interview_mode`
- `jd_content`
- `questions`
- `answers`
- `feedback`
- `report_data`
- `status`
- `overall_score`

说明：

- `questions/answers/feedback` 均为 JSON 字段
- 当前前端自由聊天模式对 `questions/answers` 的依赖较弱
- 结构化问答接口仍然把这些字段作为主存储

## 8. 功能规格

### 8.1 认证

必须支持：

- 注册
- 登录
- 获取当前用户
- 更新当前用户信息

约束：

- 基于 Bearer Token
- 当前为单 access token 模式
- 默认有效期 8 天

### 8.2 简历管理

必须支持：

- 列表查询
- 单条详情
- 新建
- 更新
- 删除

约束：

- 用户只能访问自己的简历
- 更新请求允许部分字段更新
- `content` 落库前必须经过 `ResumeContent` 规范化

### 8.3 文件上传与解析

支持格式：

- `.pdf`
- `.docx`
- `.doc`
- `.txt`

行为要求：

- 上传失败应返回明确错误信息
- AI 解析失败时不应阻断用户继续编辑
- 返回结果必须包含解析质量或回退标识，供前端提示

### 8.4 简历编辑器

目标行为：

- 表单编辑和预览联动
- 自动保存
- 支持多分区编辑
- 支持局部模块排序/布局控制

当前现实：

- 已具备基本编辑和自动保存
- 布局配置主要保存在前端本地，不在服务端持久化

### 8.5 AI 优化代理

目标行为：

- 基于当前简历 JSON 和对话历史进行建议或改写
- 支持工具级确认
- 返回结构化 diff，让用户理解改了什么
- 保留操作记录，便于回溯

当前实现细节：

- Agent 提示词在 `backend/app/prompts/resume_agent/`
- 工具由 `ResumeTools` 提供
- 变更摘要由后端 patch builder 生成
- 流式接口可回传 `tool_pending/tool_confirmed/tool_rejected/diff_summary`

建议收敛规格：

- 统一为“工具级 diff 确认后立即落库”
- 聊天记录和 agent session 负责历史留痕与恢复，而不是单独的 proposal 实体

### 8.6 面试系统

产品目标应二选一，不应长期混用：

方案 A：自由聊天式面试

- AI 作为连续对话型面试官
- 每轮根据上下文追问
- 更自然，但评分结构化较弱

方案 B：结构化问答式面试

- 明确题目、题号、逐题答案、逐题评分
- 更利于报告和量化分析

当前实现是 A 为主、B 为辅：

- 前端面试页主要使用 A
- 后端同时保留 B 的题目/评分/报告接口

建议目标规格：

- 对外产品主链路以一种模式为准
- 若保留两种模式，需要在 UI 和数据结构上显式区分

### 8.7 面试报告

目标行为：

- 可重复生成
- 支持缓存
- 支持从会话数据重建
- 能输出总分、维度分、亮点、改进项、逐题分析

当前风险：

- 报告页前端需要的字段多于后端当前稳定返回字段
- 报告数据结构目前依赖 LLM 自由生成 JSON，缺少严格 schema 校验

这意味着报告页与后端返回之间存在潜在契约漂移。

### 8.8 语音能力

范围：

- ASR：语音转文本
- TTS：文本转语音

当前状态：

- 后端服务已接入
- 前端面试页已出现语音输入/播放相关组件
- 是否已完整打通面试主流程，需要进一步联调验证

因此本模块当前应定义为“实验性增强能力”，不是主规格阻塞项。

## 9. 核心接口规格

### 9.1 Auth

- `POST /api/auth/register`
- `POST /api/auth/login`
- `GET /api/auth/me`
- `PUT /api/auth/me`

### 9.2 Resume

- `GET /api/resumes/`
- `POST /api/resumes/`
- `GET /api/resumes/{resume_id}`
- `PUT /api/resumes/{resume_id}`
- `DELETE /api/resumes/{resume_id}`

### 9.3 Upload

- `POST /api/upload/resume`

### 9.4 Resume AI

- `POST /api/ai/chat/stream`
- `POST /api/ai/chat/confirm-tool`
- `POST /api/ai/chat/resume-session`
- `GET /api/ai/status`

### 9.5 Chat History

- `GET /api/resumes/{resume_id}/chat-messages`
- `POST /api/resumes/{resume_id}/chat-messages`
- `DELETE /api/resumes/{resume_id}/chat-messages`

### 9.6 Export

- `POST /api/resumes/{resume_id}/export`
- `GET /api/resumes/download/{filename}`

### 9.7 Interview

- `POST /api/resumes/{resume_id}/interview/start`
- `GET /api/resumes/{resume_id}/interview/{session_id}/question`
- `POST /api/resumes/{resume_id}/interview/{session_id}/answer`
- `POST /api/resumes/{resume_id}/interview/{session_id}/end`
- `GET /api/resumes/{resume_id}/interview/sessions`
- `DELETE /api/resumes/{resume_id}/interview/{session_id}`
- `POST /api/resumes/{resume_id}/interview/calculate-scores`
- `POST /api/resumes/{resume_id}/interview/cleanup-duplicate`
- `GET /api/resumes/{resume_id}/interview/{session_id}/report`
- `POST /api/resumes/{resume_id}/interview/{session_id}/chat`
- `GET /api/interviews/`
- `GET /api/interviews/stats`

## 10. 非功能要求

### 10.1 安全

- 所有业务接口默认要求登录
- 资源按 `owner_id` 做权限校验
- 禁止访问他人简历、面试、聊天记录和 agent session
- 生产环境必须收敛 CORS 白名单
- `SECRET_KEY` 和第三方 API Key 必须由环境变量注入

### 10.2 可用性

- 上传、AI、导出等长耗时操作必须给前端明确状态反馈
- AI 失败时要保底，不得导致已有简历数据丢失
- 自动保存失败需要可见提示

### 10.3 可观测性

- 关键请求需要日志
- AI 调用、导出、上传、面试报告生成应可追踪
- 不应在生产中继续依赖 `print()`

### 10.4 数据一致性

- `Resume.content` 必须经过 schema 正规化
- 删除简历时要级联清理面试、聊天记录和相关 agent 状态
- 面试完成后需清理旧报告缓存

## 11. 当前实现中的主要规格偏差

### 11.1 AI 修改链路需持续保持单语义

当前产品已经确定采用方案 A：

- 工具级 diff 确认
- 用户确认后立即落库
- 不再维护 proposal-first 主链路

当前剩余工作不再是“选哪种方案”，而是继续清理旧文档、旧接口残留，并保证 UI 提示与该规则一致。

### 11.2 面试模型并存

- 前端主面试流程是自由聊天模式
- 后端保留结构化题目/答案/评分模式

建议：

- 决定主模式
- 另一模式若保留，需作为独立面试类型显式暴露

### 11.3 报告契约不稳定

- 报告页期望的数据字段较丰富
- 后端当前依赖 LLM 文本转 JSON，缺少强校验

建议：

- 为报告定义严格 Pydantic schema
- 后端统一补齐缺省字段
- 前端按稳定 schema 消费

### 11.4 前后端需要持续清理旧残留

若仓库里仍存在指向废弃优化接口的代码或文档，说明系统仍有旧方案残留。

建议：

- 删除未使用 Hook、接口和页面依赖
- 保证所有 AI 优化入口都走 `chat/stream + confirm-tool + resume-session`

## 12. 推荐的下一版收敛方案

### 12.1 V1 稳定版产品定义

建议将系统定义为：

- 一个以“结构化简历”为单一数据真源的求职助手
- 简历优化采用“工具级 diff 确认，确认即落库”模式
- 面试采用“自由聊天式主链路 + 报告摘要”模式

原因：

- 与现有前端交互更贴近
- 能减少结构化问答与自由聊天双轨并存的复杂度
- 更适合先把编辑体验和 AI 可控性做稳

### 12.2 V1.1 再增强的方向

- 把面试改造成可选模式：
  - 自由聊天面试
  - 结构化问答面试
- 服务端持久化简历布局配置
- 报告 schema 标准化
- 引入简历版本历史

## 13. 验收标准

产品达到“可对外演示”的最低标准应满足：

1. 用户可以注册登录，并只看到自己的数据
2. 上传简历后，能稳定进入编辑态
3. 编辑页自动保存可用，预览正确更新
4. AI 优化可以稳定返回结果，且用户清楚知道“确认即生效”
5. 导出 PDF 成功率可接受
6. 能从简历进入面试、完成一次面试、生成报告
7. 面试记录中心能查看、继续、删除会话

## 14. 开放问题

以下问题需要产品和工程共同拍板：

1. 是否需要在“确认即落库”之外增加版本历史或撤销能力？
2. 面试主链路到底是自由聊天还是结构化问答？
3. 报告需要固定字段模板，还是允许 LLM 自由发挥？
4. 语音能力是主功能还是增强功能？
5. 简历布局配置是否需要跨设备同步？

## 15. 建议的后续文档拆分

如果要继续完善文档体系，建议从本 Spec 拆出三份子文档：

- `resume-domain-spec.md`：只描述简历 schema 与编辑规则
- `interview-spec.md`：只描述面试状态机、评分与报告
- `api-contract.md`：只描述请求/响应体与错误码
