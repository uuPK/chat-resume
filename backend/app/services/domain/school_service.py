import json
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.models.school import AICourse
from app.models.enterprise import EnterpriseJob
from app.models.resume import Resume
from app.services.llm.chat_service import ChatService
import logging
import re

logger = logging.getLogger(__name__)

class SchoolService:
    def __init__(self, db: Session):
        self.db = db

    async def calculate_market_gaps(self) -> dict:
        # 1. 抓取所有企业要求的技能
        jobs = self.db.execute(select(EnterpriseJob)).scalars().all()
        job_skills = []
        for job in jobs:
            if isinstance(job.skills_required, list):
                job_skills.extend(job.skills_required)

        # 2. 抓取所有求职者具备的技能
        resumes = self.db.execute(select(Resume)).scalars().all()
        candidate_skills = []
        for resume in resumes:
            skills = resume.content.get("skills", [])
            for skill_category in skills:
                candidate_skills.extend(skill_category.get("keywords", []))

        # 去重并统一大小写统计频率 (简化处理，这里直接传给 LLM)
        payload = {
            "enterprise_required_skills": job_skills,
            "candidate_current_skills": candidate_skills
        }

        system_prompt = """
你是一位资深的人才市场数据分析专家。
我将提供两组数据给你：
1. "enterprise_required_skills"：目前企业岗位需求中高频出现的技能。
2. "candidate_current_skills"：目前平台内求职者简历中实际具备的技能。

请你进行深度 Gap Analysis（缺口分析），并严格输出以下 JSON 格式：
{
  "top_missing_skills": ["技能1", "技能2", "技能3", "技能4", "技能5"],
  "analysis": "基于企业需求与求职者现状的深度趋势分析（200-300字）。如果数据不足，请结合当前(2026年)前沿科技领域(如AI/大模型/现代前端)的常识进行合理推测。"
}

不要输出任何 Markdown 标记（例如 ```json），只输出纯合法的 JSON 字符串。
"""
        
        logger.info("calculate_market_gaps.llm.started")
        try:
            async with ChatService() as chat:
                response = await chat.chat_completion(
                    messages=[
                        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}
                    ],
                    temperature=0.7,
                    max_tokens=1000,
                    system_prompt=system_prompt
                )
        except Exception as exc:
            logger.error(f"Failed to generate market gaps: {exc}")
            # Fallback
            return {
                "top_missing_skills": ["大模型微调", "Agent 编排", "RAG 检索增强", "React 服务端组件", "Next.js App Router"],
                "analysis": "由于服务异常，暂时返回预测数据。企业越来越渴望候选人具备实战型的 AI 工程化能力以及现代化的 React 框架开发经验。"
            }
            
        raw_content = response.get("choices", [{}])[0].get("message", {}).get("content", "")
        raw_content = raw_content.strip()
        if raw_content.startswith("```json"):
            raw_content = re.sub(r"^```json\n", "", raw_content)
            raw_content = re.sub(r"\n```$", "", raw_content)
        elif raw_content.startswith("```"):
            raw_content = re.sub(r"^```\n", "", raw_content)
            raw_content = re.sub(r"\n```$", "", raw_content)
            
        try:
            result = json.loads(raw_content)
            return result
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON from LLM: {raw_content}")
            return {
                "top_missing_skills": ["未知技能分析失败"],
                "analysis": f"解析大模型返回结果失败: {raw_content}"
            }

    def generate_course(self, target_skills: list[str]) -> AICourse:
        skills_str = ", ".join(target_skills)
        title = f"{skills_str} 极速实战营"
        description = f"这是一门高强度的实战课程，旨在帮助学员快速弥补在 {skills_str} 领域的技能空白。"
        
        # Mock outline generation with more detailed syllabus
        outline = {
            "weeks": [
                {
                    "week_number": 1,
                    "theme": f"{target_skills[0] if target_skills else '前沿技术'} 核心概念与环境搭建",
                    "goal": "掌握核心底层原理、配置开发环境并完成首个 Demo",
                    "tasks": [
                        {"name": "开发环境准备", "description": "配置本地开发环境，安装必要的 SDK 与依赖库", "resource_links": []},
                        {"name": "核心理论学习", "description": "深入理解架构设计理念与核心工作流", "resource_links": []},
                        {"name": "Hello World 实战", "description": "基于官方文档，动手完成第一个基础演示程序", "resource_links": []}
                    ],
                    "passing_criteria": "成功运行 Demo 并通过随堂知识测验 (80分及格)"
                },
                {
                    "week_number": 2,
                    "theme": "进阶核心功能开发",
                    "goal": "能够独立使用高级特性完成复杂业务需求",
                    "tasks": [
                        {"name": "组件化与模块化设计", "description": "学习如何进行代码拆分与高内聚设计", "resource_links": []},
                        {"name": "状态管理与数据流", "description": "掌握复杂状态同步及数据传递的最佳实践", "resource_links": []},
                        {"name": "API 交互实战", "description": "与后端服务或第三方 API 进行数据交互与异常处理", "resource_links": []}
                    ],
                    "passing_criteria": "完成阶段性作业，实现一个具备完整数据流的模块"
                },
                {
                    "week_number": 3,
                    "theme": "性能优化与工程化",
                    "goal": "掌握线上部署标准、工程化规范及性能调优",
                    "tasks": [
                        {"name": "性能分析与调优", "description": "使用 Profiler 工具找出性能瓶颈并进行优化", "resource_links": []},
                        {"name": "自动化测试", "description": "编写单元测试与端到端测试，保证代码质量", "resource_links": []},
                        {"name": "CI/CD 基础", "description": "配置自动化构建与部署流水线", "resource_links": []}
                    ],
                    "passing_criteria": "测试覆盖率达到 70% 以上，并成功通过 CI 检查"
                },
                {
                    "week_number": 4,
                    "theme": "企业级项目实战与答辩",
                    "goal": "从零到一构建并上线一个完整的企业级项目",
                    "tasks": [
                        {"name": "需求分析与架构设计", "description": "完成毕业项目的技术选型与数据库设计", "resource_links": []},
                        {"name": "全栈开发实战", "description": "独立开发整个项目，并处理边缘情况与安全问题", "resource_links": []},
                        {"name": "上线部署与总结", "description": "将项目部署至云服务器，并准备结课答辩", "resource_links": []}
                    ],
                    "passing_criteria": "通过导师代码评审 (Code Review) 及最终答辩"
                }
            ]
        }
        
        course = AICourse(
            title=title,
            description=description,
            target_skills=skills_str,
            outline=json.dumps(outline),
            published=False
        )
        self.db.add(course)
        self.db.commit()
        self.db.refresh(course)
        return course

    def get_course(self, course_id: int) -> AICourse | None:
        return self.db.query(AICourse).filter(AICourse.id == course_id).first()

    def get_published_courses(self) -> list[AICourse]:
        return self.db.query(AICourse).filter(AICourse.published == True).all()

    def publish_course(self, course_id: int) -> AICourse | None:
        course = self.get_course(course_id)
        if course:
            course.published = True
            self.db.commit()
            self.db.refresh(course)
        return course
