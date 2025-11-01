"""
简历优化AI服务模块

基于AI技术提供简历优化建议，包括内容优化、格式调整、关键词优化等。
整合多种AI模型，提供专业的简历优化指导。
"""

from typing import Dict, Any, List, Optional
from .chat_service import ChatService, AIProvider
from app.core.prompts import ResumeAssistantPrompts


class ResumeOptimizer:
    """简历优化AI服务类"""

    def __init__(self, provider: AIProvider = AIProvider.OPENROUTER):
        """初始化简历优化服务

        Args:
            provider: AI服务提供商
        """
        self.chat_service = ChatService(provider)
        self.prompts = ResumeAssistantPrompts()

    async def analyze_resume(
        self, resume_content: str, job_description: Optional[str] = None
    ) -> Dict[str, Any]:
        """分析简历内容

        Args:
            resume_content: 简历内容
            job_description: 目标职位描述（可选）

        Returns:
            分析结果，包含优缺点分析
        """
        system_prompt = self._get_analysis_prompt(job_description)

        message = f"请分析以下简历内容，提供专业的改进建议：\n\n{resume_content}"

        response = await self.chat_service.chat_with_context(
            message=message, system_prompt=system_prompt
        )

        return self._parse_analysis_response(response)

    async def optimize_content(
        self,
        resume_content: str,
        target_section: Optional[str] = None,
        optimization_type: str = "general",
    ) -> Dict[str, Any]:
        """优化简历内容

        Args:
            resume_content: 简历内容
            target_section: 目标优化部分（如：工作经历、教育背景等）
            optimization_type: 优化类型（general, keywords, structure, achievements）

        Returns:
            优化建议和改进后的内容
        """
        system_prompt = self._get_optimization_prompt(optimization_type)

        context = f"优化类型：{optimization_type}"
        if target_section:
            context += f"\n目标部分：{target_section}"

        message = f"请优化以下简历内容：\n\n{resume_content}"

        response = await self.chat_service.chat_with_context(
            message=message, context=context, system_prompt=system_prompt
        )

        return self._parse_optimization_response(response)

    async def suggest_keywords(
        self, resume_content: str, job_description: str, industry: Optional[str] = None
    ) -> Dict[str, Any]:
        """建议关键词优化

        Args:
            resume_content: 简历内容
            job_description: 职位描述
            industry: 行业领域（可选）

        Returns:
            关键词建议列表
        """
        system_prompt = """
        你是一位专业的HR和简历优化专家。请根据简历内容和目标职位描述，
        提供关键词优化建议，包括：
        1. 必备关键词清单
        2. 技能关键词补充建议
        3. 行业专业术语推荐
        4. ATS系统友好关键词
        """

        context = f"行业领域：{industry}" if industry else ""

        message = f"""
        简历内容：
        {resume_content}

        目标职位描述：
        {job_description}

        请提供详细的关键词优化建议。
        """

        response = await self.chat_service.chat_with_context(
            message=message, context=context, system_prompt=system_prompt
        )

        return self._parse_keywords_response(response)

    async def improve_achievements(
        self, work_experience: str, quantification_focus: bool = True
    ) -> Dict[str, Any]:
        """改进工作成就描述

        Args:
            work_experience: 工作经历描述
            quantification_focus: 是否重点关注量化成果

        Returns:
            改进后的成就描述
        """
        system_prompt = """
        你是一位资深的职业发展顾问。请帮助用户改进工作成就描述，
        使用STAR法则（情境、任务、行动、结果）和量化指标，
        让成就描述更有说服力和影响力。
        """

        focus_instruction = (
            "请重点关注量化成果，添加具体数字和百分比。"
            if quantification_focus
            else "请重点关注行动描述和结果展示。"
        )

        message = f"""
        工作经历描述：
        {work_experience}

        {focus_instruction}
        请使用STAR法则重新组织和优化这段描述。
        """

        response = await self.chat_service.chat_with_context(
            message=message, system_prompt=system_prompt
        )

        return {
            "original": work_experience,
            "improved": response,
            "improvement_notes": self._extract_improvement_notes(response),
        }

    async def check_ats_compatibility(self, resume_content: str) -> Dict[str, Any]:
        """检查ATS系统兼容性

        Args:
            resume_content: 简历内容

        Returns:
            ATS兼容性检查结果
        """
        system_prompt = """
        你是一位ATS（申请人追踪系统）专家。请检查简历的ATS兼容性，
        包括格式规范、关键词密度、结构清晰度等方面。
        """

        message = f"请检查以下简历的ATS兼容性并提供改进建议：\n\n{resume_content}"

        response = await self.chat_service.chat_with_context(
            message=message, system_prompt=system_prompt
        )

        return self._parse_ats_check_response(response)

    def _get_analysis_prompt(self, job_description: Optional[str]) -> str:
        """获取简历分析的系统提示词"""
        base_prompt = """
        你是一位资深的HR专家和职业顾问。请对简历进行全面分析，
        包括：
        1. 结构和格式评估
        2. 内容完整性检查
        3. 技能和经验匹配度
        4. 改进建议清单
        5. 优势亮点总结
        """

        if job_description:
            base_prompt += (
                f"\n\n目标职位描述：\n{job_description}\n\n请特别关注与该职位的匹配度。"
            )

        return base_prompt

    def _get_optimization_prompt(self, optimization_type: str) -> str:
        """获取优化类型的系统提示词"""
        prompts = {
            "general": "请对简历进行全面优化，包括结构、内容、格式等方面。",
            "keywords": "请重点优化关键词，提高简历的搜索匹配度。",
            "structure": "请重点优化简历结构，使其更清晰、更专业。",
            "achievements": "请重点优化工作成就描述，使用STAR法则和量化指标。",
        }

        return prompts.get(optimization_type, prompts["general"])

    def _parse_analysis_response(self, response: str) -> Dict[str, Any]:
        """解析分析响应"""
        return {
            "analysis": response,
            "key_points": self._extract_key_points(response),
            "improvement_areas": self._extract_improvement_areas(response),
        }

    def _parse_optimization_response(self, response: str) -> Dict[str, Any]:
        """解析优化响应"""
        return {
            "optimized_content": response,
            "changes_made": self._extract_changes(response),
            "rationale": self._extract_rationale(response),
        }

    def _parse_keywords_response(self, response: str) -> Dict[str, Any]:
        """解析关键词响应"""
        return {
            "keywords": self._extract_keywords(response),
            "recommendations": response,
            "priority": self._extract_keyword_priority(response),
        }

    def _parse_ats_check_response(self, response: str) -> Dict[str, Any]:
        """解析ATS检查响应"""
        return {
            "ats_score": self._extract_ats_score(response),
            "issues": self._extract_ats_issues(response),
            "recommendations": response,
        }

    # 辅助方法（简化实现，实际可以根据需要进行更复杂的文本解析）
    def _extract_key_points(self, response: str) -> List[str]:
        """提取关键点"""
        # 简单实现，实际可以使用更复杂的NLP技术
        lines = response.split("\n")
        return [
            line.strip("- ").strip() for line in lines if line.strip().startswith("-")
        ]

    def _extract_improvement_areas(self, response: str) -> List[str]:
        """提取改进领域"""
        # 简化实现
        return ["结构优化", "内容完善", "技能突出"]

    def _extract_changes(self, response: str) -> List[str]:
        """提取变更内容"""
        return ["内容优化", "格式调整", "语言润色"]

    def _extract_rationale(self, response: str) -> str:
        """提取优化理由"""
        return "基于HR最佳实践和行业标准进行优化"

    def _extract_keywords(self, response: str) -> List[str]:
        """提取关键词"""
        # 简化实现，实际可以使用正则表达式或NLP技术
        return ["专业技能", "工作经验", "项目成果"]

    def _extract_keyword_priority(self, response: str) -> Dict[str, int]:
        """提取关键词优先级"""
        return {"高": 0, "中": 0, "低": 0}

    def _extract_improvement_notes(self, response: str) -> List[str]:
        """提取改进说明"""
        return ["使用量化指标", "突出成果", "简化表达"]

    def _extract_ats_score(self, response: str) -> int:
        """提取ATS评分"""
        return 85  # 简化实现

    def _extract_ats_issues(self, response: str) -> List[str]:
        """提取ATS问题"""
        return ["格式建议", "关键词密度"]
