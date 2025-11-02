"""
简历优化提示词模块

包含简历分析、优化建议、岗位匹配等相关的提示词管理。
"""

import logging

logger = logging.getLogger(__name__)


class ResumePrompts:
    """简历优化提示词管理类"""

    # 核心系统提示词（不包含用户数据）
    SYSTEM_PROMPT = """# AI简历优化师 - 系统提示词

## 角色定位
你是一位拥有15年招聘经验的AI简历优化专家。你的特点：
- **犀利但温暖**：一针见血指出问题，但总能给出建设性方案
- **实战派**：只关注能帮求职者拿到面试的优化，拒绝花架子

对话方式：自然，简洁，建议具体。

## 格式要求
- 回复内容不要有多余的空格和缩进
- 列表项直接从行首开始，不要前置空格

## 当你需要给出具体优化时，按以下格式回复：
优化内容：
优化前：
优化后：

## 禁忌清单
- ❌ 长篇大论的理论分析
- ❌ 一次给出5个以上建议
- ❌ 使用专业术语不解释
- ❌ 给出模糊的建议
- ❌ 编造经历或数据
- ❌ 在回复中使用多余的空格和缩进
"""

    # 简历上下文提示词模板
    RESUME_CONTEXT_TEMPLATE = """
## 用户简历信息

以下是用户的简历信息，请基于此信息回答用户的问题：

### 基本信息
- 姓名：{name}
- 邮箱：{email}
- 电话：{phone}
- 求职岗位：{position}

### 技能清单
{skills_text}

### 工作经历
{experience_text}

### 项目经历
{projects_text}

### 教育背景
{education_text}

---

请基于以上简历信息，专业地回答用户的问题。"""

    # 简历-岗位匹配分析提示词
    JD_MATCHING_PROMPT = """请分析以下简历与岗位描述的匹配度，并提供优化建议。

请按以下格式返回分析结果：
1. 匹配度评分（0-100分）
2. 匹配的技能和经验
3. 缺失的关键技能
4. 简历优化建议（具体的修改建议）
5. 关键词优化建议

请用中文回答，并提供具体、可操作的建议。"""

    @staticmethod
    def format_resume_context(resume_content: dict) -> str:
        """格式化简历上下文信息"""

        # 提取基本信息
        personal_info = resume_content.get("personal_info", {})
        name = personal_info.get("name", "未提供")
        email = personal_info.get("email", "未提供")
        phone = personal_info.get("phone", "未提供")
        position = personal_info.get("position", "未提供")

        # 格式化技能信息
        skills = resume_content.get("skills", [])
        if skills:
            skills_text = "\n".join(
                [
                    f"- {skill.get('name', '未知技能')} ({skill.get('level', '未知水平')})"
                    for skill in skills
                ]
            )
        else:
            skills_text = "暂无技能信息"

        # 格式化工作经历
        experience = resume_content.get("work_experience", [])
        if experience:
            experience_text = "\n".join(
                [
                    f"- {exp.get('company', '未知公司')} - {exp.get('position', '未知职位')} ({exp.get('duration', '未知时间')})"
                    for exp in experience
                ]
            )
        else:
            experience_text = "暂无工作经历"

        # 格式化项目经历
        projects = resume_content.get("projects", [])
        if projects:
            projects_text = "\n".join(
                [
                    f"- {proj.get('name', '未知项目')}：{proj.get('description', '无描述')}"
                    for proj in projects
                ]
            )
        else:
            projects_text = "暂无项目经历"

        # 格式化教育背景
        education = resume_content.get("education", [])
        if education:
            education_text = "\n".join(
                [
                    f"- {edu.get('school', '未知学校')} - {edu.get('major', '未知专业')} ({edu.get('degree', '未知学位')})"
                    for edu in education
                ]
            )
        else:
            education_text = "暂无教育背景"

        return ResumePrompts.RESUME_CONTEXT_TEMPLATE.format(
            name=name,
            email=email,
            phone=phone,
            position=position,
            skills_text=skills_text,
            experience_text=experience_text,
            projects_text=projects_text,
            education_text=education_text,
        )

    @staticmethod
    def build_chat_messages(
        user_message: str, resume_content: dict, chat_history: list | None = None
    ) -> list:
        """构建简历优化聊天消息列表，支持对话历史"""

        # 系统提示词
        system_message = {
            "role": "system",
            "content": ResumePrompts.SYSTEM_PROMPT,
        }

        # 简历上下文信息
        resume_context = ResumePrompts.format_resume_context(resume_content)
        context_message = {"role": "user", "content": resume_context}

        # 构建消息列表
        messages = [system_message, context_message]

        # 添加聊天历史（如果有的话）
        if chat_history:
            for msg in chat_history:
                if msg.get("type") == "user":
                    messages.append({"role": "user", "content": msg.get("content", "")})
                elif msg.get("type") == "ai":
                    messages.append(
                        {"role": "assistant", "content": msg.get("content", "")}
                    )

        # 添加当前用户消息
        user_question = {"role": "user", "content": user_message}
        messages.append(user_question)

        # 调试：打印完整的消息结构
        logger.debug("\n" + "=" * 80)
        logger.debug("发送给大模型的完整消息:")
        logger.debug("=" * 80)
        for i, message in enumerate(messages):
            logger.debug(f"消息 {i + 1} - Role: {message['role']}")
            logger.debug("-" * 40)
            logger.debug(message["content"])
            logger.debug("-" * 40)
        logger.debug("=" * 80 + "\n")

        return messages

    @staticmethod
    def build_analysis_messages(resume_content: dict, jd_content: str) -> list:
        """构建简历-岗位匹配分析消息"""

        system_message = {
            "role": "system",
            "content": "你是一个专业的HR顾问和简历优化专家，擅长分析简历与岗位要求的匹配度并提供优化建议。",
        }

        resume_context = ResumePrompts.format_resume_context(resume_content)

        analysis_prompt = f"""{ResumePrompts.JD_MATCHING_PROMPT}

简历内容：
{resume_context}

岗位描述：
{jd_content}"""

        user_message = {"role": "user", "content": analysis_prompt}

        return [system_message, user_message]