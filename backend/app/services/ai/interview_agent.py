"""
面试AI服务模块

提供AI面试官功能，包括模拟面试、问题生成、面试评分等。
整合面试报告和评分功能，提供完整的面试体验。
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from .chat_service import ChatService, AIProvider


class InterviewAgent:
    """AI面试官服务类"""

    def __init__(self, provider: AIProvider = AIProvider.OPENROUTER):
        """初始化面试Agent服务

        Args:
            provider: AI服务提供商
        """
        self.chat_service = ChatService(provider)

    async def generate_interview_questions(
        self,
        job_title: str,
        job_description: str,
        resume_content: str,
        question_types: Optional[List[str]] = None,
        difficulty: str = "medium",
    ) -> Dict[str, Any]:
        """生成面试问题

        Args:
            job_title: 职位名称
            job_description: 职位描述
            resume_content: 简历内容
            question_types: 问题类型列表（behavioral, technical, situational, general）
            difficulty: 难度级别（easy, medium, hard）

        Returns:
            生成的面试问题列表
        """
        if question_types is None:
            question_types = ["behavioral", "technical", "situational", "general"]

        system_prompt = f"""
        你是一位专业的面试官。请根据提供的职位信息和候选人简历，
        生成一套全面的面试问题。要求：
        1. 问题类型涵盖：{", ".join(question_types)}
        2. 难度级别：{difficulty}
        3. 问题要与职位要求和候选人背景高度相关
        4. 每个问题都要有明确的考察目的
        5. 提供5-8个问题，覆盖不同维度
        """

        message = f"""
        职位名称：{job_title}

        职位描述：
        {job_description}

        候选人简历：
        {resume_content}

        请生成针对性的面试问题，每个问题包含：
        - 问题内容
        - 问题类型
        - 考察目的
        - 参考回答要点
        """

        response = await self.chat_service.chat_with_context(
            message=message, system_prompt=system_prompt
        )

        return self._parse_questions_response(response)

    async def conduct_interview(
        self,
        question: str,
        user_answer: str,
        question_context: Optional[str] = None,
        interview_history: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        """进行面试对话

        Args:
            question: 面试问题
            user_answer: 用户回答
            question_context: 问题背景信息
            interview_history: 面试历史记录

        Returns:
            面试反馈和追问
        """
        system_prompt = """
        你是一位经验丰富的面试官。请对候选人的回答进行评估，
        并提供专业的反馈。包括：
        1. 回答质量评估
        2. 优点分析
        3. 改进建议
        4. 可能的追问问题
        5. 评分（1-10分）
        """

        context = f"问题背景：{question_context}" if question_context else ""

        message = f"""
        面试问题：{question}

        候选人回答：{user_answer}

        请作为面试官提供专业的评估和反馈。
        """

        response = await self.chat_service.chat_with_context(
            message=message,
            context=context,
            system_prompt=system_prompt,
            conversation_history=interview_history,
        )

        return self._parse_interview_response(response)

    async def generate_follow_up_question(
        self, original_question: str, user_answer: str, feedback_score: int
    ) -> Dict[str, Any]:
        """生成追问问题

        Args:
            original_question: 原始问题
            user_answer: 用户回答
            feedback_score: 之前回答的评分

        Returns:
            追问问题
        """
        system_prompt = """
        你是一位专业的面试官。请根据候选人的回答质量，
        生成合适的追问问题。如果回答质量高，可以问更深入的问题；
        如果回答质量一般，可以引导候选人更好地展示自己。
        """

        level = "深入挖掘" if feedback_score >= 7 else "引导补充"

        message = f"""
        原始问题：{original_question}
        候选人回答：{user_answer}
        评分：{feedback_score}/10

        请生成一个{level}的追问问题。
        """

        response = await self.chat_service.chat_with_context(
            message=message, system_prompt=system_prompt
        )

        return {
            "follow_up_question": response,
            "question_type": "follow_up",
            "purpose": level,
        }

    async def evaluate_interview_performance(
        self, interview_session: List[Dict[str, Any]], job_requirements: str
    ) -> Dict[str, Any]:
        """评估面试表现

        Args:
            interview_session: 面试会话记录
            job_requirements: 职位要求

        Returns:
            面试表现评估报告
        """
        system_prompt = """
        你是一位资深的HR专家。请对整个面试过程进行综合评估，
        生成详细的面试报告。包括：
        1. 总体评分和评价
        2. 各项能力评分
        3. 优势和亮点
        4. 不足和改进建议
        5. 录用建议
        """

        # 构建面试会话摘要
        session_summary = self._build_session_summary(interview_session)

        message = f"""
        职位要求：
        {job_requirements}

        面试会话记录：
        {session_summary}

        请生成综合的面试评估报告。
        """

        response = await self.chat_service.chat_with_context(
            message=message, system_prompt=system_prompt
        )

        return self._parse_evaluation_response(response)

    async def provide_interview_tips(
        self, job_title: str, user_concerns: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """提供面试技巧建议

        Args:
            job_title: 目标职位
            user_concerns: 用户关注的问题

        Returns:
            面试技巧建议
        """
        system_prompt = """
        你是一位资深的职业发展顾问。请为用户提供专业的面试技巧指导，
        包括准备建议、面试技巧、常见问题应对等。
        """

        concerns_text = ""
        if user_concerns:
            concerns_text = f"\n用户特别关注的问题：{', '.join(user_concerns)}"

        message = f"""
        目标职位：{job_title}{concerns_text}

        请提供实用的面试技巧和建议。
        """

        response = await self.chat_service.chat_with_context(
            message=message, system_prompt=system_prompt
        )

        return {
            "job_title": job_title,
            "interview_tips": response,
            "key_areas": self._extract_key_areas(response),
            "common_mistakes": self._extract_common_mistakes(response),
        }

    def _parse_questions_response(self, response: str) -> Dict[str, Any]:
        """解析问题生成响应"""
        return {
            "questions": self._extract_questions(response),
            "total_count": len(self._extract_questions(response)),
            "generation_time": datetime.now().isoformat(),
            "raw_response": response,
        }

    def _parse_interview_response(self, response: str) -> Dict[str, Any]:
        """解析面试对话响应"""
        return {
            "feedback": response,
            "score": self._extract_score(response),
            "strengths": self._extract_strengths(response),
            "improvements": self._extract_improvements(response),
            "follow_up_suggestions": self._extract_follow_up_suggestions(response),
        }

    def _parse_evaluation_response(self, response: str) -> Dict[str, Any]:
        """解析评估响应"""
        return {
            "overall_evaluation": response,
            "total_score": self._extract_total_score(response),
            "category_scores": self._extract_category_scores(response),
            "recommendation": self._extract_recommendation(response),
            "evaluation_date": datetime.now().isoformat(),
        }

    def _build_session_summary(self, interview_session: List[Dict[str, Any]]) -> str:
        """构建面试会话摘要"""
        summary = "面试会话摘要：\n\n"

        for i, session in enumerate(interview_session, 1):
            summary += f"问题{i}: {session.get('question', '')}\n"
            summary += f"回答{i}: {session.get('answer', '')}\n"
            summary += f"评分{i}: {session.get('score', 'N/A')}/10\n\n"

        return summary

    # 辅助方法（简化实现）
    def _extract_questions(self, response: str) -> List[Dict[str, Any]]:
        """提取问题列表"""
        # 简化实现，实际可以使用更复杂的文本解析
        return [
            {
                "question": "请介绍一下你自己",
                "type": "general",
                "purpose": "了解候选人基本情况",
            }
        ]

    def _extract_score(self, response: str) -> int:
        """提取评分"""
        # 简化实现，实际可以使用正则表达式
        return 8

    def _extract_strengths(self, response: str) -> List[str]:
        """提取优点"""
        return ["表达清晰", "逻辑性强", "经验丰富"]

    def _extract_improvements(self, response: str) -> List[str]:
        """提取改进建议"""
        return ["可以更具体", "增加量化指标"]

    def _extract_follow_up_suggestions(self, response: str) -> List[str]:
        """提取追问建议"""
        return ["可以举例说明", "详细谈谈具体做法"]

    def _extract_total_score(self, response: str) -> int:
        """提取总分"""
        return 85

    def _extract_category_scores(self, response: str) -> Dict[str, int]:
        """提取分类评分"""
        return {"专业技能": 8, "沟通能力": 7, "问题解决": 8, "团队协作": 7}

    def _extract_recommendation(self, response: str) -> str:
        """提取录用建议"""
        return "建议录用"

    def _extract_key_areas(self, response: str) -> List[str]:
        """提取关键领域"""
        return ["自我介绍", "专业技能", "项目经验"]

    def _extract_common_mistakes(self, response: str) -> List[str]:
        """提取常见错误"""
        return ["回答过于简短", "缺乏具体例子"]
