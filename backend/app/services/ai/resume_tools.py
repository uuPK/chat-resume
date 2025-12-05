"""
简历优化工具集合

提供简历分析和优化的各种工具函数
"""

from typing import Dict, Any, List
import json


class ResumeTools:
    """简历优化工具类"""

    @staticmethod
    def analyze_job_matching(resume_content: Dict[str, Any], job_description: str) -> Dict[str, Any]:
        """分析简历与职位描述的匹配度

        Args:
            resume_content: 简历内容
            job_description: 职位描述

        Returns:
            匹配度分析结果
        """
        # 提取关键信息
        skills = resume_content.get("skills", [])
        experience = resume_content.get("experience", [])

        return {
            "tool": "analyze_job_matching",
            "resume_skills": skills,
            "experience_count": len(experience),
            "job_description": job_description[:200] + "..." if len(job_description) > 200 else job_description,
            "message": "已获取简历技能和经验信息，等待AI分析匹配度"
        }

    @staticmethod
    def optimize_section(resume_content: Dict[str, Any], section_name: str, context: str = "") -> Dict[str, Any]:
        """优化简历特定章节

        Args:
            resume_content: 简历内容
            section_name: 章节名称（experience/education/skills/projects）
            context: 优化上下文（如目标职位）

        Returns:
            章节内容和优化建议
        """
        section_data = resume_content.get(section_name, [])

        return {
            "tool": "optimize_section",
            "section_name": section_name,
            "current_content": section_data,
            "context": context,
            "message": f"已获取{section_name}章节内容，等待AI提供优化建议"
        }

    @staticmethod
    def generate_keywords(job_description: str, industry: str = "") -> Dict[str, Any]:
        """生成行业关键词

        Args:
            job_description: 职位描述
            industry: 行业领域

        Returns:
            关键词列表
        """
        return {
            "tool": "generate_keywords",
            "job_description": job_description[:200] + "..." if len(job_description) > 200 else job_description,
            "industry": industry,
            "message": "已获取职位描述，等待AI生成关键词建议"
        }

    @staticmethod
    def score_resume(resume_content: Dict[str, Any], criteria: str = "comprehensive") -> Dict[str, Any]:
        """对简历进行评分

        Args:
            resume_content: 简历内容
            criteria: 评分标准（comprehensive/technical/presentation）

        Returns:
            评分结果
        """
        # 统计基本信息
        has_experience = len(resume_content.get("experience", [])) > 0
        has_education = len(resume_content.get("education", [])) > 0
        has_skills = len(resume_content.get("skills", [])) > 0
        has_projects = len(resume_content.get("projects", [])) > 0

        return {
            "tool": "score_resume",
            "criteria": criteria,
            "completeness": {
                "has_experience": has_experience,
                "has_education": has_education,
                "has_skills": has_skills,
                "has_projects": has_projects,
            },
            "message": "已分析简历完整性，等待AI进行详细评分"
        }

    @staticmethod
    def suggest_improvements(resume_content: Dict[str, Any], focus_area: str = "all") -> Dict[str, Any]:
        """生成改进建议

        Args:
            resume_content: 简历内容
            focus_area: 关注领域（all/content/format/keywords）

        Returns:
            改进建议
        """
        return {
            "tool": "suggest_improvements",
            "focus_area": focus_area,
            "resume_sections": list(resume_content.keys()),
            "message": f"已识别简历章节，等待AI针对{focus_area}提供改进建议"
        }

    @classmethod
    def get_tools_schema(cls) -> List[Dict[str, Any]]:
        """获取工具的 JSON Schema 定义，用于 Function Calling"""
        return [
            {
                "type": "function",
                "function": {
                    "name": "analyze_job_matching",
                    "description": "分析简历与职位描述的匹配度，评估技能和经验的契合程度",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "job_description": {
                                "type": "string",
                                "description": "职位描述内容"
                            }
                        },
                        "required": ["job_description"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "optimize_section",
                    "description": "优化简历的特定章节，提供具体的改进建议",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "section_name": {
                                "type": "string",
                                "enum": ["experience", "education", "skills", "projects", "summary"],
                                "description": "要优化的章节名称"
                            },
                            "context": {
                                "type": "string",
                                "description": "优化的上下文信息，如目标职位或行业"
                            }
                        },
                        "required": ["section_name"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "generate_keywords",
                    "description": "根据职位描述生成简历应该包含的关键词",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "job_description": {
                                "type": "string",
                                "description": "职位描述内容"
                            },
                            "industry": {
                                "type": "string",
                                "description": "行业领域"
                            }
                        },
                        "required": ["job_description"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "score_resume",
                    "description": "对简历进行综合评分，分析优缺点",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "criteria": {
                                "type": "string",
                                "enum": ["comprehensive", "technical", "presentation"],
                                "description": "评分标准：comprehensive-综合评估，technical-技术能力，presentation-展示效果"
                            }
                        },
                        "required": []
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "suggest_improvements",
                    "description": "生成具体的简历改进建议",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "focus_area": {
                                "type": "string",
                                "enum": ["all", "content", "format", "keywords"],
                                "description": "关注的改进领域"
                            }
                        },
                        "required": []
                    }
                }
            }
        ]

    @classmethod
    def execute_tool(cls, tool_name: str, resume_content: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """执行指定的工具

        Args:
            tool_name: 工具名称
            resume_content: 简历内容
            **kwargs: 工具参数

        Returns:
            工具执行结果
        """
        tool_map = {
            "analyze_job_matching": cls.analyze_job_matching,
            "optimize_section": cls.optimize_section,
            "generate_keywords": cls.generate_keywords,
            "score_resume": cls.score_resume,
            "suggest_improvements": cls.suggest_improvements,
        }

        if tool_name not in tool_map:
            return {"error": f"Unknown tool: {tool_name}"}

        tool_func = tool_map[tool_name]

        # 根据工具调整参数
        if tool_name in ["analyze_job_matching", "generate_keywords"]:
            return tool_func(resume_content, **kwargs)
        elif tool_name == "optimize_section":
            return tool_func(resume_content, kwargs.get("section_name", ""), kwargs.get("context", ""))
        elif tool_name == "score_resume":
            return tool_func(resume_content, kwargs.get("criteria", "comprehensive"))
        elif tool_name == "suggest_improvements":
            return tool_func(resume_content, kwargs.get("focus_area", "all"))

        return {"error": "Invalid tool parameters"}
