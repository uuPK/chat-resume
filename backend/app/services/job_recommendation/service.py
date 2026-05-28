"""
智能岗位推荐与匹配分析服务

封装对 LLM 的调用以及相关的数据库存取。
"""

import json
import logging
from typing import Any

from sqlalchemy.orm import Session

from app.models.job import JobMatchReport, JobRecommendation
from app.models.resume import Resume
from app.services.llm.chat_service import ChatService
from app.services.job_recommendation.prompts import (
    _MATCH_REPORT_SYSTEM_PROMPT,
    _RECOMMENDATION_SYSTEM_PROMPT,
)

logger = logging.getLogger(__name__)


class JobRecommendationService:
    def __init__(self, db: Session):
        self.db = db

    async def generate_recommendations(self, resume_id: int) -> JobRecommendation:
        """为特定简历生成并保存岗位推荐列表。"""
        resume = self.db.query(Resume).filter(Resume.id == resume_id).first()
        if not resume:
            raise ValueError(f"Resume {resume_id} not found")

        resume_content_str = json.dumps(resume.content, ensure_ascii=False)

        # 调用大模型生成推荐
        async with ChatService() as chat:
            response = await chat.chat_completion(
                messages=[
                    {
                        "role": "user",
                        "content": f"以下是候选人的完整简历内容：\n{resume_content_str}",
                    }
                ],
                system_prompt=_RECOMMENDATION_SYSTEM_PROMPT,
                temperature=0.6,
            )

        content = response.get("choices", [{}])[0].get("message", {}).get("content", "")
        
        # 尝试提取 JSON (防御模型可能多嘴输出的前后内容)
        content = content.strip()
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()

        try:
            recommendations_data = json.loads(content)
            if not isinstance(recommendations_data, list):
                raise ValueError("JSON must be a list of job recommendations")
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse job recommendations: {content}")
            raise RuntimeError("LLM返回格式错误") from e

        # 保存到数据库
        job_recommendation = JobRecommendation(
            resume_id=resume_id,
            recommendations=recommendations_data
        )
        self.db.add(job_recommendation)
        self.db.commit()
        self.db.refresh(job_recommendation)
        
        return job_recommendation

    def get_latest_recommendations(self, resume_id: int) -> JobRecommendation | None:
        """获取最新的岗位推荐历史"""
        return (
            self.db.query(JobRecommendation)
            .filter(JobRecommendation.resume_id == resume_id)
            .order_by(JobRecommendation.id.desc())
            .first()
        )

    async def generate_match_report(self, resume_id: int, target_jd: str) -> JobMatchReport:
        """为特定简历和 JD 生成并保存深度匹配报告。"""
        resume = self.db.query(Resume).filter(Resume.id == resume_id).first()
        if not resume:
            raise ValueError(f"Resume {resume_id} not found")

        resume_content_str = json.dumps(resume.content, ensure_ascii=False)

        # 调用大模型生成深度匹配报告
        async with ChatService() as chat:
            response = await chat.chat_completion(
                messages=[
                    {
                        "role": "user",
                        "content": f"【目标职位描述（JD）】:\n{target_jd}\n\n【候选人简历】:\n{resume_content_str}",
                    }
                ],
                system_prompt=_MATCH_REPORT_SYSTEM_PROMPT,
                temperature=0.6,
            )

        content = response.get("choices", [{}])[0].get("message", {}).get("content", "")
        
        content = content.strip()
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()

        try:
            report_data = json.loads(content)
            if not isinstance(report_data, dict):
                raise ValueError("JSON must be a dictionary")
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse match report: {content}")
            raise RuntimeError("LLM返回格式错误") from e

        # 保存到数据库
        match_report = JobMatchReport(
            resume_id=resume_id,
            target_jd=target_jd,
            analysis_result=report_data
        )
        self.db.add(match_report)
        self.db.commit()
        self.db.refresh(match_report)
        
        return match_report
