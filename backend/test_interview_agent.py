"""
面试Agent测试模块

测试优化后的InterviewAgent类和相关组件。
符合团队代码编写规范，确保代码质量和功能正确性。
"""

import pytest
from unittest.mock import Mock, AsyncMock
from app.services.ai import InterviewAgent, InterviewResponseParser
from app.services.ai.chat_service import AIProvider
from app.services.ai.interview_data_structures import (
    InterviewQuestion,
    InterviewFeedback,
    QuestionType,
    DifficultyLevel,
)


class TestInterviewAgent:
    """面试Agent测试类"""

    @pytest.fixture
    def mock_chat_service(self):
        """模拟聊天服务"""
        mock_service = Mock()
        mock_service.chat_with_context = AsyncMock()
        return mock_service

    @pytest.fixture
    def mock_response_parser(self):
        """模拟响应解析器"""
        mock_parser = Mock(spec=InterviewResponseParser)
        mock_parser.parse_questions_response.return_value = [
            InterviewQuestion(
                question="请介绍一下你自己",
                question_type=QuestionType.GENERAL,
                purpose="了解候选人基本情况",
                reference_points=["个人背景", "工作经验", "技能特长"],
                difficulty=DifficultyLevel.MEDIUM,
            )
        ]
        mock_parser.parse_interview_feedback.return_value = InterviewFeedback(
            feedback="回答很好，表达清晰",
            score=8,
            strengths=["表达清晰", "逻辑性强"],
            improvements=["可以更具体"],
            follow_up_suggestions=["可以举例说明"],
        )
        return mock_parser

    @pytest.fixture
    def interview_agent(self, mock_chat_service, mock_response_parser):
        """创建面试Agent实例"""
        agent = InterviewAgent(AIProvider.OPENROUTER, mock_response_parser)
        agent.chat_service = mock_chat_service
        return agent

    @pytest.mark.asyncio
    async def test_generate_interview_questions_success(
        self, interview_agent, mock_chat_service, mock_response_parser
    ):
        """测试生成面试问题成功场景"""
        # 准备测试数据
        mock_chat_service.chat_with_context.return_value = "模拟AI响应"

        # 执行测试
        result = await interview_agent.generate_interview_questions(
            job_title="软件工程师",
            job_description="负责后端开发",
            resume_content="5年Python开发经验",
            question_types=["technical", "behavioral"],
            difficulty="medium",
        )

        # 验证结果
        assert result.total_count == 1
        assert len(result.questions) == 1
        assert result.questions[0].question == "请介绍一下你自己"
        assert result.questions[0].question_type == QuestionType.GENERAL
        assert result.job_title == "软件工程师"
        assert result.difficulty == DifficultyLevel.MEDIUM

        # 验证调用
        mock_chat_service.chat_with_context.assert_called_once()
        mock_response_parser.parse_questions_response.assert_called_once_with(
            "模拟AI响应"
        )

    @pytest.mark.asyncio
    async def test_generate_interview_questions_invalid_params(self, interview_agent):
        """测试生成面试问题参数验证"""
        # 测试空职位名称
        with pytest.raises(ValueError, match="职位名称不能为空"):
            await interview_agent.generate_interview_questions(
                job_title="", job_description="测试描述", resume_content="测试内容"
            )

        # 测试空职位描述
        with pytest.raises(ValueError, match="职位描述不能为空"):
            await interview_agent.generate_interview_questions(
                job_title="测试职位", job_description="", resume_content="测试内容"
            )

        # 测试空简历内容
        with pytest.raises(ValueError, match="简历内容不能为空"):
            await interview_agent.generate_interview_questions(
                job_title="测试职位", job_description="测试描述", resume_content=""
            )

        # 测试无效难度级别
        with pytest.raises(ValueError, match="无效的难度级别"):
            await interview_agent.generate_interview_questions(
                job_title="测试职位",
                job_description="测试描述",
                resume_content="测试内容",
                difficulty="invalid",
            )

    @pytest.mark.asyncio
    async def test_conduct_interview_success(
        self, interview_agent, mock_chat_service, mock_response_parser
    ):
        """测试进行面试对话成功场景"""
        # 准备测试数据
        mock_chat_service.chat_with_context.return_value = "模拟反馈响应"

        # 执行测试
        result = await interview_agent.conduct_interview(
            question="请介绍一下你的项目经验",
            user_answer="我参与了多个项目的开发",
            question_context="技术面试",
            interview_history=[{"role": "user", "content": "你好"}],
        )

        # 验证结果
        assert result.feedback.feedback == "回答很好，表达清晰"
        assert result.feedback.score == 8
        assert len(result.feedback.strengths) == 2
        assert len(result.feedback.improvements) == 1
        assert len(result.conversation_history) == 4  # 原有1个 + 新增3个

        # 验证调用
        mock_chat_service.chat_with_context.assert_called_once()
        mock_response_parser.parse_interview_feedback.assert_called_once_with(
            "模拟反馈响应"
        )

    @pytest.mark.asyncio
    async def test_conduct_interview_invalid_params(self, interview_agent):
        """测试进行面试对话参数验证"""
        # 测试空问题
        with pytest.raises(ValueError, match="面试问题不能为空"):
            await interview_agent.conduct_interview(question="", user_answer="测试回答")

        # 测试空回答
        with pytest.raises(ValueError, match="用户回答不能为空"):
            await interview_agent.conduct_interview(question="测试问题", user_answer="")

    @pytest.mark.asyncio
    async def test_generate_follow_up_question_success(
        self, interview_agent, mock_chat_service, mock_response_parser
    ):
        """测试生成追问问题成功场景"""
        # 准备测试数据
        mock_chat_service.chat_with_context.return_value = "模拟追问响应"
        mock_response_parser.parse_follow_up_question.return_value = Mock(
            follow_up_question="能详细说说你在这个项目中的具体贡献吗？",
            question_type=QuestionType.FOLLOW_UP,
            purpose="深入挖掘",
            level="深入挖掘",
        )

        # 执行测试
        result = await interview_agent.generate_follow_up_question(
            original_question="请介绍你的项目经验",
            user_answer="我参与了多个项目",
            feedback_score=8,
        )

        # 验证结果
        assert result.follow_up_question == "能详细说说你在这个项目中的具体贡献吗？"
        assert result.question_type == QuestionType.FOLLOW_UP
        assert result.purpose == "深入挖掘"

        # 验证调用
        mock_chat_service.chat_with_context.assert_called_once()
        mock_response_parser.parse_follow_up_question.assert_called_once_with(
            "模拟追问响应", "深入挖掘"
        )

    @pytest.mark.asyncio
    async def test_generate_follow_up_question_invalid_params(self, interview_agent):
        """测试生成追问问题参数验证"""
        # 测试空原始问题
        with pytest.raises(ValueError, match="原始问题不能为空"):
            await interview_agent.generate_follow_up_question(
                original_question="", user_answer="测试回答", feedback_score=8
            )

        # 测试空用户回答
        with pytest.raises(ValueError, match="用户回答不能为空"):
            await interview_agent.generate_follow_up_question(
                original_question="测试问题", user_answer="", feedback_score=8
            )

        # 测试无效评分
        with pytest.raises(ValueError, match="评分必须在1-10之间"):
            await interview_agent.generate_follow_up_question(
                original_question="测试问题", user_answer="测试回答", feedback_score=15
            )

    def test_validate_generate_questions_params(self, interview_agent):
        """测试生成问题参数验证方法"""
        # 测试有效参数不抛出异常
        interview_agent._validate_generate_questions_params(
            job_title="测试职位",
            job_description="测试描述",
            resume_content="测试内容",
            difficulty="medium",
        )

        # 测试无效参数抛出异常
        with pytest.raises(ValueError):
            interview_agent._validate_generate_questions_params(
                job_title="",
                job_description="测试描述",
                resume_content="测试内容",
                difficulty="medium",
            )

    def test_build_question_generation_prompt(self, interview_agent):
        """测试构建问题生成提示词"""
        prompt = interview_agent._build_question_generation_prompt(
            question_types=["technical", "behavioral"], difficulty="medium"
        )

        assert "technical" in prompt
        assert "behavioral" in prompt
        assert "medium" in prompt
        assert "JSON格式" in prompt

    def test_build_interview_feedback_prompt(self, interview_agent):
        """测试构建面试反馈提示词"""
        prompt = interview_agent._build_interview_feedback_prompt()

        assert "面试官" in prompt
        assert "评估" in prompt
        assert "评分" in prompt
        assert "1-10分" in prompt


class TestInterviewResponseParser:
    """面试响应解析器测试类"""

    @pytest.fixture
    def parser(self):
        """创建解析器实例"""
        return InterviewResponseParser()

    def test_extract_score_success(self, parser):
        """测试提取评分成功"""
        # 测试不同格式的评分
        assert parser._extract_score("评分：8/10") == 8
        assert parser._extract_score("评分：8／10") == 8
        assert parser._extract_score("评分：8") == 8
        assert parser._extract_score("没有评分") == 7  # 默认值

    def test_extract_main_content(self, parser):
        """测试提取主要内容"""
        # 测试清理内容
        content_with_code = """
        这是主要内容
        ```python
        print("代码块")
        ```
        继续内容
        """
        result = parser._extract_main_content(content_with_code)
        assert "这是主要内容" in result
        assert "print" not in result
        assert "继续内容" in result

    def test_extract_strengths(self, parser):
        """测试提取优点"""
        text = """
        优点：表达清晰，逻辑性强，经验丰富
        优势：沟通能力好，学习能力强
        """
        strengths = parser._extract_strengths(text)
        assert len(strengths) > 0
        assert any("表达清晰" in s for s in strengths)

    def test_extract_improvements(self, parser):
        """测试提取改进建议"""
        text = """
        改进建议：可以更具体，增加量化指标
        不足：缺乏具体例子
        """
        improvements = parser._extract_improvements(text)
        assert len(improvements) > 0
        assert any("更具体" in s for s in improvements)

    def test_extract_total_score(self, parser):
        """测试提取总分"""
        text = "总分：85分，总体评分：90，综合得分：88"
        score = parser._extract_total_score(text)
        assert score == 85  # 应该返回第一个匹配的分数

    def test_extract_category_scores(self, parser):
        """测试提取分类评分"""
        text = """
        专业技能：8/10
        沟通能力：7/10
        团队协作：8/10
        """
        scores = parser._extract_category_scores(text)
        assert len(scores) >= 3
        assert any(s.category == "专业技能" and s.score == 8 for s in scores)

    def test_extract_recommendation(self, parser):
        """测试提取录用建议"""
        # 测试强烈推荐
        text1 = "强烈推荐录用该候选人"
        rec1 = parser._extract_recommendation(text1)
        assert rec1.value == "strong_recommend"

        # 测试不推荐
        text2 = "不建议录用该候选人"
        rec2 = parser._extract_recommendation(text2)
        assert rec2.value == "not_recommend"


if __name__ == "__main__":
    # 运行测试
    pytest.main([__file__, "-v"])
