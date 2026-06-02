"""
个性化成长路线生成服务

基于简历变更或面试结果，调用大模型生成带有历史记忆上下文的 4 周学习规划。
"""

import json
import logging
import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.services.errors import ServiceError
from app.models.interview import InterviewSession
from app.models.learning_path import LearningPathVersion
from app.models.resume import Resume
from app.services.llm.chat_service import ChatService
from app.services.domain.learning_service import LearningService

logger = logging.getLogger(__name__)

_PLAN_SYSTEM_PROMPT = """
你是一位顶尖的大厂技术教练兼职业发展导师。你的任务是根据候选人的当前状态（简历或刚刚结束的面试表现），为其量身定制一份极度专业、可落地的“4周突破性成长规划（Learning Path）”。

【极其重要的上下文记忆与对比机制】
上下文中可能会提供“历史成长路线版本（Previous Plan）”以及“过去面试表现（past_interview_reports）”和“本次面试表现（interview_report）”。
更重要的是，上下文中还可能提供候选人“已加入的高校优选课程（enrolled_courses）”。
你必须仔细分析并综合生成路线：
1. 如果候选人加入了某些优选课程，你的路线必须将这些课程的内容（大纲、知识点）完美融入到接下来的4周计划中，让这4周既能补足短板，又能覆盖课程的学习目标。
2. 相比上次规划和过去面试表现，候选人这次面试的表现有什么实质变化？是取得了进步，还是暴露了新的短板？
3. 必须明确结合【之前面试表现和这次面试表现的差别】（如果有）来指导规划重点。
4. 在新规划中，要顺着上次的基础进行【进阶突破】，或者对新暴露的严重短板进行【专项恶补】。
5. 请在 summary 中一句话点出这次版本的核心进阶逻辑（若有课程加入，必须提及已将课程内容融入路线规划中）。

【输出格式约束】
你只能输出合法的 JSON，禁止使用 Markdown (如 ```json) 包装，也不要输出任何解释性废话。
JSON 的格式必须严格如下：
{
  "summary": "一句话概括本次路线版本的核心侧重点（如：‘针对本次面试暴露的高并发短板，在上一版基础上补充Redis源码级特训’）",
  "weeks": [
    {
      "week_number": 1,
      "theme": "本周主题",
      "goal": "本周核心目标",
      "tasks": [
        {
          "name": "任务名称",
          "description": "具体怎么做，细到代码级或架构级要求",
          "resource_links": ["推荐文档/书籍名称/博客链接"]
        }
      ],
      "passing_criteria": "达标的客观判断标准（如：能手写出XX算法）"
    }
  ]
}
注意：必须严格输出 4 个 week。
"""

async def generate_learning_path(
    db: Session,
    resume_id: int,
    trigger_type: str,
    interview_session_id: int | None = None
) -> LearningPathVersion:
    """生成或更新个性化学习路线版本。"""
    
    resume = db.scalar(select(Resume).where(Resume.id == resume_id))
    if not resume:
        raise ServiceError("Resume not found")

    # 获取最新的一份历史规划作为 Context
    previous_plan_model = db.scalar(
        select(LearningPathVersion)
        .where(LearningPathVersion.resume_id == resume_id)
        .order_by(LearningPathVersion.created_at.desc())
        .limit(1)
    )

    context_payload = {
        "trigger": trigger_type,
        "resume": resume.content,
        "previous_plan": previous_plan_model.plan_data if previous_plan_model else None,
    }

    # 获取用户已加入的课程
    learning_svc = LearningService(db)
    enrolled_courses = learning_svc.get_user_plan(resume.owner_id)
    if enrolled_courses:
        context_payload["enrolled_courses"] = [
            {
                "title": c.title,
                "description": c.description,
                "target_skills": c.target_skills,
                "outline": json.loads(c.outline) if c.outline else {}
            } for c in enrolled_courses
        ]

    # 如果有面试，附加上面试报告及历史面试报告
    if interview_session_id:
        interview = db.scalar(
            select(InterviewSession).where(InterviewSession.id == interview_session_id)
        )
        if interview and interview.report_data:
            context_payload["interview_report"] = interview.report_data
            context_payload["target_title"] = interview.target_title

        past_interviews = db.scalars(
            select(InterviewSession)
            .where(InterviewSession.resume_id == resume_id)
            .where(InterviewSession.status == "completed")
            .where(InterviewSession.id != interview_session_id)
            .order_by(InterviewSession.created_at.desc())
            .limit(3)
        ).all()
        
        past_reports = [pi.report_data for pi in past_interviews if pi.report_data]
        if past_reports:
            context_payload["past_interview_reports"] = past_reports

    logger.info(
        "learning_path.generate.started",
        extra={
            "resume_id": resume_id,
            "trigger_type": trigger_type,
            "has_previous_plan": bool(previous_plan_model),
        },
    )

    try:
        async with ChatService() as chat:
            response = await chat.chat_completion(
                messages=[
                    {
                        "role": "user",
                        "content": json.dumps(context_payload, ensure_ascii=False),
                    }
                ],
                temperature=0.4, # 稍微多一点创造性
                max_tokens=3000,
                system_prompt=_PLAN_SYSTEM_PROMPT,
            )
    except Exception as exc:
        raise ServiceError(f"Learning path generation failed: {exc}") from exc

    raw_content = response.get("choices", [{}])[0].get("message", {}).get("content", "")
    
    # 清理潜在的 markdown 包装
    raw_content = raw_content.strip()
    if raw_content.startswith("```json"):
        raw_content = re.sub(r"^```json\n", "", raw_content)
        raw_content = re.sub(r"\n```$", "", raw_content)
    elif raw_content.startswith("```"):
        raw_content = re.sub(r"^```\n", "", raw_content)
        raw_content = re.sub(r"\n```$", "", raw_content)

    try:
        plan_data = json.loads(raw_content)
    except json.JSONDecodeError as exc:
        logger.error(f"Failed to parse learning path JSON: {raw_content}")
        raise ServiceError("LLM returned invalid JSON for learning path") from exc

    new_version = LearningPathVersion(
        resume_id=resume_id,
        interview_session_id=interview_session_id,
        trigger_type=trigger_type,
        plan_data=plan_data
    )
    db.add(new_version)
    db.commit()
    db.refresh(new_version)

    return new_version
