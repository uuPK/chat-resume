# -*- coding: utf-8 -*-
"""简历优化智能代理核心实现

将现有"一键生成报告"的工具，升级为一个交互式的、有状态的、具备引导能力
的"AI 职业顾问"。它不再是冰冷的工具，而是用户的智能伙伴，通过对话帮助
用户深度优化简历，并在此过程中提升用户的简历撰写能力。
"""

from typing import Dict, Any, List, AsyncIterator, Optional
import json
import re
from app.core.prompts import RESUME_OPTIMIZER_PROMPTS
from app.services.openrouter_service import OpenRouterService


class ResumeOptimizerAgent:
    """
    简历优化智能代理核心逻辑。
    负责管理对话状态、选择并格式化 Prompt、与大模型交互。
    """
    
    def __init__(self, resume_data: Dict[str, Any], target_job: Optional[str] = None):
        """初始化简历优化代理
        
        Args:
            resume_data: 用户简历数据
            target_job: 目标岗位，可选
        """
        self.resume_data = resume_data
        self.target_job = target_job
        self.llm = OpenRouterService()

    async def stream_response(self, history: List[Dict[str, str]]) -> AsyncIterator[str]:
        """
        根据对话历史生成流式响应的核心方法。
        
        Args:
            history: 对话历史 [{"role": "user/assistant", "content": "..."}]
            
        Yields:
            str: 响应内容片段
        """
        # 1. 决策：判断当前对话处于哪个阶段/状态
        state = self._determine_conversation_state(history)
        
        # 2. 选剧本：根据状态获取对应的 Prompt 模板
        prompt_template = RESUME_OPTIMIZER_PROMPTS.get(state, RESUME_OPTIMIZER_PROMPTS["GENERAL_CONVERSATION"])
        
        # 3. 准备材料：格式化最终的 Prompt
        system_prompt = prompt_template.format(
            resume_data=self._format_resume_for_prompt(self.resume_data),
            target_job=self.target_job or "未设定",
            history=self._format_history_for_prompt(history)
        )
        
        # 4. 构建消息列表
        messages = [{"role": "system", "content": system_prompt}]
        
        # 添加对话历史（最近5轮，避免context过长）
        recent_history = history[-10:] if len(history) > 10 else history
        for msg in recent_history:
            if msg.get("role") in ["user", "assistant"]:
                messages.append({
                    "role": msg["role"], 
                    "content": msg["content"]
                })
        
        # 5. 调用 AI 并返回响应流
        async for chunk in self.llm.chat_completion_stream(messages, temperature=0.8):
            yield chunk

    def _determine_conversation_state(self, history: List[Dict[str, str]]) -> str:
        """
        简化的状态机，用于决定使用哪个 Prompt。
        这是 Agent 的"思考"过程。
        
        Args:
            history: 对话历史
            
        Returns:
            str: 当前对话状态
        """
        if not history:
            return "GREETING"  # 首次交互
        
        # 获取最后几条消息用于状态判断
        recent_messages = history[-3:] if len(history) >= 3 else history
        
        # 检查是否正在等待目标岗位
        for msg in recent_messages:
            if msg.get("role") == "assistant":
                content = msg.get("content", "").lower()
                if any(keyword in content for keyword in ["目标岗位", "求职目标", "应聘职位", "目标职位"]):
                    return "AWAITING_GOAL"
        
        # 检查是否已经设定了目标但尚未确认
        if not self.target_job:
            for msg in recent_messages:
                if msg.get("role") == "user":
                    content = msg.get("content", "").lower()
                    # 简单检测是否包含岗位相关词汇
                    job_keywords = ["工程师", "开发", "设计师", "经理", "专员", "主管", "总监", "分析师", "顾问"]
                    if any(keyword in content for keyword in job_keywords):
                        return "GOAL_CONFIRMATION"
        
        # 检查是否在讨论特定简历模块
        last_assistant_msg = ""
        for msg in reversed(history):
            if msg.get("role") == "assistant":
                last_assistant_msg = msg.get("content", "").lower()
                break
        
        # 根据关键词判断当前讨论的模块
        if any(keyword in last_assistant_msg for keyword in ["工作经历", "工作经验", "职业经历"]):
            return "WORK_EXPERIENCE_FOCUS"
        elif any(keyword in last_assistant_msg for keyword in ["项目经验", "项目经历", "项目"]):
            return "PROJECT_FOCUS"
        elif any(keyword in last_assistant_msg for keyword in ["教育背景", "学历", "教育经历"]):
            return "EDUCATION_FOCUS"
        elif any(keyword in last_assistant_msg for keyword in ["技能", "专业技能", "核心技能"]):
            return "SKILLS_FOCUS"
        
        # 检查是否在生成具体建议
        if "建议" in last_assistant_msg or "优化" in last_assistant_msg or "改为" in last_assistant_msg:
            return "SUGGESTION_GENERATION"
        
        return "GENERAL_CONVERSATION"  # 默认的持续对话状态

    def _format_resume_for_prompt(self, resume_data: Dict[str, Any]) -> str:
        """格式化简历数据用于Prompt"""
        formatted_sections = []
        
        # 个人信息
        if personal_info := resume_data.get("personal_info"):
            info_items = []
            if personal_info.get("name"):
                info_items.append(f"姓名：{personal_info['name']}")
            if personal_info.get("position"):
                info_items.append(f"求职意向：{personal_info['position']}")
            if personal_info.get("email"):
                info_items.append(f"邮箱：{personal_info['email']}")
            if personal_info.get("phone"):
                info_items.append(f"电话：{personal_info['phone']}")
            if info_items:
                formatted_sections.append(f"【个人信息】\n" + "\n".join(info_items))
        
        # 工作经历
        if work_exp := resume_data.get("work_experience"):
            work_items = []
            for i, exp in enumerate(work_exp, 1):
                exp_text = f"{i}. {exp.get('company', '')} - {exp.get('position', '')}"
                if exp.get("duration"):
                    exp_text += f" ({exp['duration']})"
                if exp.get("description"):
                    exp_text += f"\n   {exp['description']}"
                work_items.append(exp_text)
            if work_items:
                formatted_sections.append(f"【工作经历】\n" + "\n".join(work_items))
        
        # 项目经验
        if projects := resume_data.get("projects"):
            project_items = []
            for i, proj in enumerate(projects, 1):
                proj_text = f"{i}. {proj.get('name', '')}"
                if proj.get("description"):
                    proj_text += f"\n   {proj['description']}"
                if proj.get("technologies"):
                    proj_text += f"\n   技术栈：{', '.join(proj['technologies'])}"
                project_items.append(proj_text)
            if project_items:
                formatted_sections.append(f"【项目经验】\n" + "\n".join(project_items))
        
        # 教育背景
        if education := resume_data.get("education"):
            edu_items = []
            for i, edu in enumerate(education, 1):
                edu_text = f"{i}. {edu.get('school', '')} - {edu.get('major', '')}"
                if edu.get("degree"):
                    edu_text += f" ({edu['degree']})"
                if edu.get("duration"):
                    edu_text += f" {edu['duration']}"
                edu_items.append(edu_text)
            if edu_items:
                formatted_sections.append(f"【教育背景】\n" + "\n".join(edu_items))
        
        # 技能
        if skills := resume_data.get("skills"):
            skills_text = "【技能清单】\n"
            # skills是一个数组，每个元素包含name, level, category等字段
            if isinstance(skills, list):
                # 按category分组
                skills_by_category = {}
                for skill in skills:
                    if isinstance(skill, dict):
                        category = skill.get("category", "其他")
                        name = skill.get("name", "")
                        level = skill.get("level", "")
                        if name:
                            skill_text = name
                            if level:
                                skill_text += f"({level})"
                            if category not in skills_by_category:
                                skills_by_category[category] = []
                            skills_by_category[category].append(skill_text)
                
                # 格式化输出
                for category, skill_list in skills_by_category.items():
                    if skill_list:
                        skills_text += f"- {category}：{', '.join(skill_list)}\n"
            
            if len(skills_text) > 10:  # 有实际内容
                formatted_sections.append(skills_text.strip())
        
        return "\n\n".join(formatted_sections) if formatted_sections else "暂无简历信息"

    def _format_history_for_prompt(self, history: List[Dict[str, str]]) -> str:
        """格式化对话历史用于Prompt"""
        if not history:
            return "暂无对话历史"
        
        formatted_history = []
        for msg in history[-6:]:  # 只取最近6条消息
            role = "用户" if msg.get("role") == "user" else "助手"
            content = msg.get("content", "")
            formatted_history.append(f"{role}：{content}")
        
        return "\n".join(formatted_history)

    def extract_suggestions_from_response(self, response_content: str) -> List[Dict[str, Any]]:
        """从AI响应中提取可应用的建议
        
        Args:
            response_content: AI的响应内容
            
        Returns:
            List[Dict]: 建议列表，每个建议包含section, original, suggested等字段
        """
        suggestions = []
        
        # 使用正则表达式匹配建议格式
        # 匹配类似 "原文：...改为：..." 的模式
        suggestion_pattern = r'【?原文?】?[：:]\s*(.+?)\s*【?改?为?】?[：:]\s*(.+?)(?=\n|$)'
        matches = re.findall(suggestion_pattern, response_content, re.DOTALL | re.IGNORECASE)
        
        for original, suggested in matches:
            suggestions.append({
                "type": "content_change",
                "section": self._infer_section_from_content(original.strip()),
                "original_content": original.strip(),
                "suggested_content": suggested.strip(),
                "reasoning": "AI建议优化"
            })
        
        return suggestions

    def _infer_section_from_content(self, content: str) -> str:
        """根据内容推断属于哪个简历模块"""
        content_lower = content.lower()
        
        if any(keyword in content_lower for keyword in ["公司", "职位", "工作", "负责", "主导"]):
            return "work_experience"
        elif any(keyword in content_lower for keyword in ["项目", "开发", "设计", "实现"]):
            return "projects"
        elif any(keyword in content_lower for keyword in ["大学", "学院", "专业", "学历"]):
            return "education"
        elif any(keyword in content_lower for keyword in ["技能", "掌握", "熟练"]):
            return "skills"
        else:
            return "general"