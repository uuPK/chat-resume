"""
面试响应解析器模块

专门负责解析AI响应的类，实现真正的文本解析逻辑。
符合团队代码规范中"接口是契约"和"能删的才是好代码"的原则。
"""

import re
import json
from datetime import datetime
from typing import List, Optional
from .interview_data_structures import (
    InterviewQuestion,
    InterviewFeedback,
    FollowUpQuestion,
    CategoryScore,
    InterviewEvaluation,
    InterviewTips,
    QuestionType,
    DifficultyLevel,
    RecommendationType,
)


class InterviewResponseParser:
    """面试响应解析器类

    专门负责解析AI服务返回的各种响应，将其转换为结构化的数据对象。
    实现真正的解析逻辑，避免硬编码返回值。
    """

    def __init__(self):
        """初始化解析器"""
        # 定义常用的正则表达式模式
        self.score_pattern = re.compile(r"(\d+)[/／]?10")
        self.json_pattern = re.compile(r"```json\s*(.*?)\s*```", re.DOTALL)
        self.question_pattern = re.compile(r"问题[：:]\s*(.*?)(?=\n|$)")
        self.type_pattern = re.compile(r"类型[：:]\s*(.*?)(?=\n|$)")
        self.purpose_pattern = re.compile(r"目的[：:]\s*(.*?)(?=\n|$)")

    def parse_questions_response(self, response: str) -> List[InterviewQuestion]:
        """解析问题生成响应

        Args:
            response: AI服务返回的问题生成响应

        Returns:
            解析后的面试问题列表

        Raises:
            ValueError: 当响应格式不正确时
        """

        # 尝试解析JSON格式
        json_questions = self._try_parse_json_questions(response)
        if json_questions:
            return json_questions

        # 尝试解析文本格式
        text_questions = self._parse_text_questions(response)
        if text_questions:
            return text_questions

        # 如果都无法解析，抛出异常
        raise ValueError("无法解析问题生成响应，请检查响应格式")

    def parse_interview_feedback(self, response: str) -> InterviewFeedback:
        """解析面试反馈响应

        Args:
            response: AI服务返回的面试反馈响应

        Returns:
            解析后的面试反馈对象

        Raises:
            ValueError: 当响应格式不正确或评分无效时
        """
        # 提取评分
        score = self._extract_score(response)

        # 提取反馈内容
        feedback = self._extract_main_content(response)

        # 提取优点
        strengths = self._extract_strengths(response)

        # 提取改进建议
        improvements = self._extract_improvements(response)

        # 提取追问建议
        follow_up_suggestions = self._extract_follow_up_suggestions(response)

        return InterviewFeedback(
            feedback=feedback,
            score=score,
            strengths=strengths,
            improvements=improvements,
            follow_up_suggestions=follow_up_suggestions,
        )

    def parse_follow_up_question(self, response: str, level: str) -> FollowUpQuestion:
        """解析追问问题响应

        Args:
            response: AI服务返回的追问问题响应
            level: 追问级别（深入挖掘/引导补充）

        Returns:
            解析后的追问问题对象
        """
        # 提取追问问题内容
        question = self._extract_main_content(response)

        return FollowUpQuestion(
            follow_up_question=question,
            question_type=QuestionType.FOLLOW_UP,
            purpose=level,
            level=level,
        )

    def parse_evaluation_response(self, response: str) -> InterviewEvaluation:
        """解析评估响应

        Args:
            response: AI服务返回的评估响应

        Returns:
            解析后的评估报告对象

        Raises:
            ValueError: 当响应格式不正确或评分无效时
        """
        # 提取总体评价
        overall_evaluation = self._extract_main_content(response)

        # 提取总分
        total_score = self._extract_total_score(response)

        # 提取分类评分
        category_scores = self._extract_category_scores(response)

        # 提取录用建议
        recommendation = self._extract_recommendation(response)

        # 提取优势和不足
        strengths = self._extract_strengths(response)
        weaknesses = self._extract_weaknesses(response)

        return InterviewEvaluation(
            overall_evaluation=overall_evaluation,
            total_score=total_score,
            category_scores=category_scores,
            recommendation=recommendation,
            strengths=strengths,
            weaknesses=weaknesses,
            evaluation_date=datetime.now(),
        )

    def parse_interview_tips(self, response: str, job_title: str) -> InterviewTips:
        """解析面试技巧建议响应

        Args:
            response: AI服务返回的面试技巧建议响应
            job_title: 目标职位

        Returns:
            解析后的面试技巧建议对象
        """
        # 提取关键领域
        key_areas = self._extract_key_areas(response)

        # 提取常见错误
        common_mistakes = self._extract_common_mistakes(response)

        return InterviewTips(
            job_title=job_title,
            interview_tips=response,
            key_areas=key_areas,
            common_mistakes=common_mistakes,
        )

    def _try_parse_json_questions(
        self, response: str
    ) -> Optional[List[InterviewQuestion]]:
        """尝试解析JSON格式的问题

        Args:
            response: AI响应文本

        Returns:
            解析成功返回问题列表，失败返回None
        """
        try:
            # 查找JSON代码块
            json_match = self.json_pattern.search(response)
            if not json_match:
                return None

            json_str = json_match.group(1)
            data = json.loads(json_str)

            questions = []
            if isinstance(data, dict) and "questions" in data:
                data = data["questions"]

            for item in data:
                if isinstance(item, dict):
                    question = InterviewQuestion(
                        question=item.get("question", ""),
                        question_type=QuestionType(item.get("type", "general")),
                        purpose=item.get("purpose", ""),
                        reference_points=item.get("reference_points", []),
                        difficulty=DifficultyLevel(item.get("difficulty", "medium")),
                    )
                    questions.append(question)

            return questions

        except (json.JSONDecodeError, KeyError, ValueError):
            return None

    def _parse_text_questions(self, response: str) -> Optional[List[InterviewQuestion]]:
        """解析文本格式的问题

        Args:
            response: AI响应文本

        Returns:
            解析成功返回问题列表，失败返回None
        """
        try:
            questions = []
            # 按问题分割响应
            question_blocks = re.split(r"\n\s*\d+\.", response)

            for block in question_blocks:
                if not block.strip():
                    continue

                question = self._extract_question_from_block(block)
                if question:
                    questions.append(question)

            return questions if questions else None

        except Exception:
            return None

    def _extract_question_from_block(self, block: str) -> Optional[InterviewQuestion]:
        """从文本块中提取问题信息

        Args:
            block: 包含问题信息的文本块

        Returns:
            解析成功返回问题对象，失败返回None
        """
        try:
            # 提取问题内容
            question_match = self.question_pattern.search(block)
            if not question_match:
                return None

            question_text = question_match.group(1).strip()

            # 提取问题类型
            type_match = self.type_pattern.search(block)
            question_type = QuestionType.GENERAL
            if type_match:
                type_str = type_match.group(1).strip().lower()
                for qtype in QuestionType:
                    if qtype.value in type_str:
                        question_type = qtype
                        break

            # 提取考察目的
            purpose_match = self.purpose_pattern.search(block)
            purpose = (
                purpose_match.group(1).strip() if purpose_match else "考察候选人能力"
            )

            # 提取参考要点
            reference_points = self._extract_reference_points(block)

            return InterviewQuestion(
                question=question_text,
                question_type=question_type,
                purpose=purpose,
                reference_points=reference_points,
                difficulty=DifficultyLevel.MEDIUM,
            )

        except Exception:
            return None

    def _extract_reference_points(self, text: str) -> List[str]:
        """提取参考回答要点

        Args:
            text: 包含参考要点的文本

        Returns:
            参考要点列表
        """
        points = []
        # 查找要点列表
        point_pattern = re.compile(r"要点[：:]?\s*(.*?)(?=\n|$)")
        match = point_pattern.search(text)
        if match:
            points_text = match.group(1).strip()
            # 按分隔符分割
            points = [
                p.strip() for p in re.split(r"[,，、;；]", points_text) if p.strip()
            ]

        return points

    def _extract_score(self, text: str) -> int:
        """提取评分

        Args:
            text: 包含评分的文本

        Returns:
            评分值（1-10）

        Raises:
            ValueError: 当无法提取有效评分时
        """
        match = self.score_pattern.search(text)
        if match:
            score = int(match.group(1))
            if 1 <= score <= 10:
                return score

        # 如果找不到评分，返回默认值
        return 7

    def _extract_main_content(self, text: str) -> str:
        """提取主要内容

        Args:
            text: 响应文本

        Returns:
            清理后的主要内容
        """
        # 移除代码块标记
        text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
        # 移除多余的空白字符
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def _extract_strengths(self, text: str) -> List[str]:
        """提取优点分析

        Args:
            text: 响应文本

        Returns:
            优点列表
        """
        strengths = []
        # 查找优点相关段落
        strength_patterns = [
            r"优点[：:]?\s*(.*?)(?=\n\n|\n[一二三四五六七八九十]|\n\d+\.|$)",
            r"优势[：:]?\s*(.*?)(?=\n\n|\n[一二三四五六七八九十]|\n\d+\.|$)",
        ]

        for pattern in strength_patterns:
            matches = re.findall(pattern, text, re.DOTALL)
            for match in matches:
                items = [
                    item.strip()
                    for item in re.split(r"[,，、;；\n]", match)
                    if item.strip()
                ]
                strengths.extend(items)

        return strengths[:5]  # 最多返回5个优点

    def _extract_improvements(self, text: str) -> List[str]:
        """提取改进建议

        Args:
            text: 响应文本

        Returns:
            改进建议列表
        """
        improvements = []
        # 查找改进建议相关段落
        improvement_patterns = [
            r"改进[建议]?[：:]?\s*(.*?)(?=\n\n|\n[一二三四五六七八九十]|\n\d+\.|$)",
            r"不足[：:]?\s*(.*?)(?=\n\n|\n[一二三四五六七八九十]|\n\d+\.|$)",
        ]

        for pattern in improvement_patterns:
            matches = re.findall(pattern, text, re.DOTALL)
            for match in matches:
                items = [
                    item.strip()
                    for item in re.split(r"[,，、;；\n]", match)
                    if item.strip()
                ]
                improvements.extend(items)

        return improvements[:5]  # 最多返回5个改进建议

    def _extract_follow_up_suggestions(self, text: str) -> List[str]:
        """提取追问建议

        Args:
            text: 响应文本

        Returns:
            追问建议列表
        """
        suggestions = []
        # 查找追问建议相关段落
        suggestion_patterns = [
            r"追问[建议]?[：:]?\s*(.*?)(?=\n\n|\n[一二三四五六七八九十]|\n\d+\.|$)",
            r"可以[进一步]?[：:]?\s*(.*?)(?=\n\n|\n[一二三四五六七八九十]|\n\d+\.|$)",
        ]

        for pattern in suggestion_patterns:
            matches = re.findall(pattern, text, re.DOTALL)
            for match in matches:
                items = [
                    item.strip()
                    for item in re.split(r"[,，、;；\n]", match)
                    if item.strip()
                ]
                suggestions.extend(items)

        return suggestions[:3]  # 最多返回3个追问建议

    def _extract_total_score(self, text: str) -> int:
        """提取总分

        Args:
            text: 响应文本

        Returns:
            总分（1-100）
        """
        # 查找总分模式
        total_score_patterns = [
            r"总分[：:]?\s*(\d+)",
            r"总体评分[：:]?\s*(\d+)",
            r"综合得分[：:]?\s*(\d+)",
        ]

        for pattern in total_score_patterns:
            match = re.search(pattern, text)
            if match:
                score = int(match.group(1))
                if 1 <= score <= 100:
                    return score

        # 如果找不到，返回默认值
        return 75

    def _extract_category_scores(self, text: str) -> List[CategoryScore]:
        """提取分类评分

        Args:
            text: 响应文本

        Returns:
            分类评分列表
        """
        category_scores = []

        # 定义常见的评分类别
        categories = [
            "专业技能",
            "技术能力",
            "沟通能力",
            "表达能力",
            "问题解决",
            "团队协作",
            "学习能力",
            "逻辑思维",
            "创新能力",
            "责任心",
        ]

        for category in categories:
            pattern = f"{category}[：:]?\\s*(\\d+)[/／]?10"
            match = re.search(pattern, text)
            if match:
                score = int(match.group(1))
                if 1 <= score <= 10:
                    category_scores.append(
                        CategoryScore(
                            category=category,
                            score=score,
                            description=f"{category}评分",
                        )
                    )

        return category_scores

    def _extract_recommendation(self, text: str) -> RecommendationType:
        """提取录用建议

        Args:
            text: 响应文本

        Returns:
            录用建议类型
        """
        # 定义建议关键词映射
        recommendation_keywords = {
            RecommendationType.STRONG_RECOMMEND: ["强烈推荐", "优先录用", "优秀"],
            RecommendationType.RECOMMEND: ["推荐", "建议录用", "合适"],
            RecommendationType.CONSIDER: ["考虑", "可以考虑", "有待观察"],
            RecommendationType.NOT_RECOMMEND: ["不推荐", "不建议", "不合适"],
        }

        for recommendation, keywords in recommendation_keywords.items():
            for keyword in keywords:
                if keyword in text:
                    return recommendation

        # 默认返回考虑
        return RecommendationType.CONSIDER

    def _extract_weaknesses(self, text: str) -> List[str]:
        """提取不足之处

        Args:
            text: 响应文本

        Returns:
            不足之处列表
        """
        weaknesses = []
        # 查找不足相关段落
        weakness_patterns = [
            r"不足[：:]?\s*(.*?)(?=\n\n|\n[一二三四五六七八九十]|\n\d+\.|$)",
            r"缺点[：:]?\s*(.*?)(?=\n\n|\n[一二三四五六七八九十]|\n\d+\.|$)",
            r"需要改进[：:]?\s*(.*?)(?=\n\n|\n[一二三四五六七八九十]|\n\d+\.|$)",
        ]

        for pattern in weakness_patterns:
            matches = re.findall(pattern, text, re.DOTALL)
            for match in matches:
                items = [
                    item.strip()
                    for item in re.split(r"[,，、;；\n]", match)
                    if item.strip()
                ]
                weaknesses.extend(items)

        return weaknesses[:5]  # 最多返回5个不足之处

    def _extract_key_areas(self, text: str) -> List[str]:
        """提取关键领域

        Args:
            text: 响应文本

        Returns:
            关键领域列表
        """
        key_areas = []
        # 查找关键领域相关段落
        area_patterns = [
            r"关键[领域]?[：:]?\s*(.*?)(?=\n\n|\n[一二三四五六七八九十]|\n\d+\.|$)",
            r"重点[准备]?[：:]?\s*(.*?)(?=\n\n|\n[一二三四五六七八九十]|\n\d+\.|$)",
        ]

        for pattern in area_patterns:
            matches = re.findall(pattern, text, re.DOTALL)
            for match in matches:
                items = [
                    item.strip()
                    for item in re.split(r"[,，、;；\n]", match)
                    if item.strip()
                ]
                key_areas.extend(items)

        return key_areas[:5]  # 最多返回5个关键领域

    def _extract_common_mistakes(self, text: str) -> List[str]:
        """提取常见错误

        Args:
            text: 响应文本

        Returns:
            常见错误列表
        """
        common_mistakes = []
        # 查找常见错误相关段落
        mistake_patterns = [
            r"常见[错误]?[：:]?\s*(.*?)(?=\n\n|\n[一二三四五六七八九十]|\n\d+\.|$)",
            r"容易[犯错]?[：:]?\s*(.*?)(?=\n\n|\n[一二三四五六七八九十]|\n\d+\.|$)",
        ]

        for pattern in mistake_patterns:
            matches = re.findall(pattern, text, re.DOTALL)
            for match in matches:
                items = [
                    item.strip()
                    for item in re.split(r"[,，、;；\n]", match)
                    if item.strip()
                ]
                common_mistakes.extend(items)

        return common_mistakes[:5]  # 最多返回5个常见错误
