"""
面试AI服务模块

提供AI面试官功能，包括模拟面试、问题生成、面试评分等。
整合面试报告和评分功能，提供完整的面试体验。
符合团队代码编写规范的所有要求。
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from .chat_service import ChatService, AIProvider
from .interview_data_structures import (
    FollowUpQuestion,
    InterviewEvaluation,
    InterviewTips,
    QuestionGenerationResult,
    InterviewConversationResult,
    DifficultyLevel,
)
from .interview_response_parser import InterviewResponseParser


class InterviewAgent:
    """AI面试官服务类

    提供完整的AI面试功能，包括问题生成、面试对话、评估报告等。
    使用依赖注入和明确的接口设计，确保代码可测试、可复用。
    """

    def __init__(
        self,
        provider: AIProvider = AIProvider.OPENROUTER,
        response_parser: Optional[InterviewResponseParser] = None,
    ):
        """初始化面试Agent服务

        Args:
            provider: AI服务提供商
            response_parser: 响应解析器，用于依赖注入
        """
        self.chat_service = ChatService(provider)
        self.response_parser = response_parser or InterviewResponseParser()

    async def generate_interview_questions(
        self,
        job_title: str,
        job_description: str,
        resume_content: str,
        question_types: Optional[List[str]] = None,
        difficulty: str = "medium",
    ) -> QuestionGenerationResult:
        """生成面试问题

        Args:
            job_title: 职位名称
            job_description: 职位描述
            resume_content: 简历内容
            question_types: 问题类型列表（behavioral, technical, situational, general）
            difficulty: 难度级别（easy, medium, hard）

        Returns:
            生成的问题结果对象

        Raises:
            ValueError: 当输入参数无效时
        """
        # 参数校验
        self._validate_generate_questions_params(
            job_title, job_description, resume_content, difficulty
        )

        if question_types is None:
            question_types = ["behavioral", "technical", "situational", "general"]

        # 构建系统提示词
        system_prompt = self._build_question_generation_prompt(
            question_types, difficulty
        )

        # 构建用户消息
        message = self._build_question_generation_message(
            job_title, job_description, resume_content
        )

        try:
            # 调用AI服务
            response = await self.chat_service.chat_with_context(
                message=message, system_prompt=system_prompt
            )

            # 解析响应
            questions = self.response_parser.parse_questions_response(response)

            # 构建结果对象
            return QuestionGenerationResult(
                questions=questions,
                total_count=len(questions),
                generation_time=datetime.now(),
                job_title=job_title,
                difficulty=DifficultyLevel(difficulty),
                raw_response=response,
            )

        except Exception as e:
            raise Exception(f"生成面试问题失败: {str(e)}")

    async def conduct_interview(
        self,
        question: str,
        user_answer: str,
        question_context: Optional[str] = None,
        interview_history: Optional[List[Dict[str, str]]] = None,
    ) -> InterviewConversationResult:
        """进行面试对话

        Args:
            question: 面试问题
            user_answer: 用户回答
            question_context: 问题背景信息
            interview_history: 面试历史记录

        Returns:
            面试对话结果对象

        Raises:
            ValueError: 当输入参数无效时
        """
        # 参数校验
        self._validate_conduct_interview_params(question, user_answer)

        # 构建系统提示词
        system_prompt = self._build_interview_feedback_prompt()

        # 构建上下文
        context = self._build_interview_context(question_context)

        # 构建用户消息
        message = self._build_interview_message(question, user_answer)

        try:
            # 调用AI服务
            response = await self.chat_service.chat_with_context(
                message=message,
                context=context,
                system_prompt=system_prompt,
                conversation_history=interview_history,
            )

            # 解析反馈
            feedback = self.response_parser.parse_interview_feedback(response)

            # 构建对话历史
            conversation_history = interview_history or []
            conversation_history.extend(
                [
                    {"role": "assistant", "content": question},
                    {"role": "user", "content": user_answer},
                    {"role": "assistant", "content": feedback.feedback},
                ]
            )

            return InterviewConversationResult(
                feedback=feedback, conversation_history=conversation_history
            )

        except Exception as e:
            raise Exception(f"面试对话失败: {str(e)}")

    async def generate_follow_up_question(
        self, original_question: str, user_answer: str, feedback_score: int
    ) -> FollowUpQuestion:
        """生成追问问题

        Args:
            original_question: 原始问题
            user_answer: 用户回答
            feedback_score: 之前回答的评分

        Returns:
            追问问题对象

        Raises:
            ValueError: 当输入参数无效时
        """
        # 参数校验
        self._validate_follow_up_params(original_question, user_answer, feedback_score)

        # 构建系统提示词
        system_prompt = self._build_follow_up_prompt()

        # 确定追问级别
        level = "深入挖掘" if feedback_score >= 7 else "引导补充"

        # 构建用户消息
        message = self._build_follow_up_message(
            original_question, user_answer, feedback_score, level
        )

        try:
            # 调用AI服务
            response = await self.chat_service.chat_with_context(
                message=message, system_prompt=system_prompt
            )

            # 解析追问问题
            return self.response_parser.parse_follow_up_question(response, level)

        except Exception as e:
            raise Exception(f"生成追问问题失败: {str(e)}")

    async def evaluate_interview_performance(
        self, interview_session: List[Dict[str, Any]], job_requirements: str
    ) -> InterviewEvaluation:
        """评估面试表现

        Args:
            interview_session: 面试会话记录
            job_requirements: 职位要求

        Returns:
            面试评估报告对象

        Raises:
            ValueError: 当输入参数无效时
        """
        # 参数校验
        self._validate_evaluation_params(interview_session, job_requirements)

        # 构建系统提示词
        system_prompt = self._build_evaluation_prompt()

        # 构建面试会话摘要
        session_summary = self._build_session_summary(interview_session)

        # 构建用户消息
        message = self._build_evaluation_message(job_requirements, session_summary)

        try:
            # 调用AI服务
            response = await self.chat_service.chat_with_context(
                message=message, system_prompt=system_prompt
            )

            # 解析评估结果
            return self.response_parser.parse_evaluation_response(response)

        except Exception as e:
            raise Exception(f"评估面试表现失败: {str(e)}")

    async def provide_interview_tips(
        self, job_title: str, user_concerns: Optional[List[str]] = None
    ) -> InterviewTips:
        """提供面试技巧建议

        Args:
            job_title: 目标职位
            user_concerns: 用户关注的问题

        Returns:
            面试技巧建议对象

        Raises:
            ValueError: 当输入参数无效时
        """
        # 参数校验
        self._validate_tips_params(job_title)

        # 构建系统提示词
        system_prompt = self._build_tips_prompt()

        # 构建用户消息
        message = self._build_tips_message(job_title, user_concerns)

        try:
            # 调用AI服务
            response = await self.chat_service.chat_with_context(
                message=message, system_prompt=system_prompt
            )

            # 解析面试技巧
            return self.response_parser.parse_interview_tips(response, job_title)

        except Exception as e:
            raise Exception(f"提供面试技巧失败: {str(e)}")

    def _validate_generate_questions_params(
        self, job_title: str, job_description: str, resume_content: str, difficulty: str
    ) -> None:
        """验证生成问题参数"""
        if not job_title or not job_title.strip():
            raise ValueError("职位名称不能为空")
        if not job_description or not job_description.strip():
            raise ValueError("职位描述不能为空")
        if not resume_content or not resume_content.strip():
            raise ValueError("简历内容不能为空")
        if difficulty not in ["easy", "medium", "hard"]:
            raise ValueError(f"无效的难度级别: {difficulty}")

    def _validate_conduct_interview_params(
        self, question: str, user_answer: str
    ) -> None:
        """验证面试对话参数"""
        if not question or not question.strip():
            raise ValueError("面试问题不能为空")
        if not user_answer or not user_answer.strip():
            raise ValueError("用户回答不能为空")

    def _validate_follow_up_params(
        self, original_question: str, user_answer: str, feedback_score: int
    ) -> None:
        """验证追问参数"""
        if not original_question or not original_question.strip():
            raise ValueError("原始问题不能为空")
        if not user_answer or not user_answer.strip():
            raise ValueError("用户回答不能为空")
        if not 1 <= feedback_score <= 10:
            raise ValueError(f"评分必须在1-10之间，当前值: {feedback_score}")

    def _validate_evaluation_params(
        self, interview_session: List[Dict[str, Any]], job_requirements: str
    ) -> None:
        """验证评估参数"""
        if not interview_session:
            raise ValueError("面试会话记录不能为空")
        if not job_requirements or not job_requirements.strip():
            raise ValueError("职位要求不能为空")

    def _validate_tips_params(self, job_title: str) -> None:
        """验证技巧参数"""
        if not job_title or not job_title.strip():
            raise ValueError("职位名称不能为空")

    def _build_question_generation_prompt(
        self, question_types: List[str], difficulty: str
    ) -> str:
        """构建问题生成系统提示词"""
        return f"""
        你是一位专业的面试官。请根据提供的职位信息和候选人简历，
        生成一套全面的面试问题。要求：
        1. 问题类型涵盖：{", ".join(question_types)}
        2. 难度级别：{difficulty}
        3. 问题要与职位要求和候选人背景高度相关
        4. 每个问题都要有明确的考察目的
        5. 提供5-8个问题，覆盖不同维度
        
        请按以下JSON格式返回：
        {{
            "questions": [
                {{
                    "question": "问题内容",
                    "type": "问题类型",
                    "purpose": "考察目的",
                    "reference_points": ["参考要点1", "参考要点2"],
                    "difficulty": "难度级别"
                }}
            ]
        }}
        """

    def _build_question_generation_message(
        self, job_title: str, job_description: str, resume_content: str
    ) -> str:
        """构建问题生成用户消息"""
        return f"""
        职位名称：{job_title}

        职位描述：
        {job_description}

        候选人简历：
        {resume_content}

        请生成针对性的面试问题。
        """

    def _build_interview_feedback_prompt(self) -> str:
        """构建面试反馈系统提示词"""
        return """
        你是一位经验丰富的面试官。请对候选人的回答进行评估，
        并提供专业的反馈。包括：
        1. 回答质量评估
        2. 优点分析
        3. 改进建议
        4. 可能的追问问题
        5. 评分（1-10分）
        """

    def _build_interview_context(self, question_context: Optional[str]) -> str:
        """构建面试上下文"""
        return f"问题背景：{question_context}" if question_context else ""

    def _build_interview_message(self, question: str, user_answer: str) -> str:
        """构建面试对话用户消息"""
        return f"""
        面试问题：{question}

        候选人回答：{user_answer}

        请作为面试官提供专业的评估和反馈。
        """

    def _build_follow_up_prompt(self) -> str:
        """构建追问系统提示词"""
        return """
        你是一位专业的面试官。请根据候选人的回答质量，
        生成合适的追问问题。如果回答质量高，可以问更深入的问题；
        如果回答质量一般，可以引导候选人更好地展示自己。
        """

    def _build_follow_up_message(
        self, original_question: str, user_answer: str, feedback_score: int, level: str
    ) -> str:
        """构建追问用户消息"""
        return f"""
        原始问题：{original_question}
        候选人回答：{user_answer}
        评分：{feedback_score}/10

        请生成一个{level}的追问问题。
        """

    def _build_evaluation_prompt(self) -> str:
        """构建评估系统提示词"""
        return """
        你是一位资深的HR专家。请对整个面试过程进行综合评估，
        生成详细的面试报告。包括：
        1. 总体评分和评价
        2. 各项能力评分
        3. 优势和亮点
        4. 不足和改进建议
        5. 录用建议
        """

    def _build_session_summary(self, interview_session: List[Dict[str, Any]]) -> str:
        """构建面试会话摘要"""
        summary = "面试会话摘要：\n\n"

        for i, session in enumerate(interview_session, 1):
            summary += f"问题{i}: {session.get('question', '')}\n"
            summary += f"回答{i}: {session.get('answer', '')}\n"
            score = session.get("score", "N/A")
            summary += f"评分{i}: {score}/10\n\n"

        return summary

    def _build_evaluation_message(
        self, job_requirements: str, session_summary: str
    ) -> str:
        """构建评估用户消息"""
        return f"""
        职位要求：
        {job_requirements}

        {session_summary}

        请生成综合的面试评估报告。
        """

    def _build_tips_prompt(self) -> str:
        """构建技巧系统提示词"""
        return """
        你是一位资深的职业发展顾问。请为用户提供专业的面试技巧指导，
        包括准备建议、面试技巧、常见问题应对等。
        """

    def _build_tips_message(
        self, job_title: str, user_concerns: Optional[List[str]]
    ) -> str:
        """构建技巧用户消息"""
        concerns_text = ""
        if user_concerns:
            concerns_text = f"\n用户特别关注的问题：{', '.join(user_concerns)}"

        return f"""
        目标职位：{job_title}{concerns_text}

        请提供实用的面试技巧和建议。
        """
