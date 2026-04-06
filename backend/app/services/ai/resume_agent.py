"""
简历优化 Agent

保留简历领域规则，通用执行逻辑由 AgentRuntime 负责。
"""

from typing import Any, Dict, List, Optional
import json
from .agent_runtime import AgentDefinition, AgentRuntime
from .resume_tools import ResumeTools
from app.prompts import load_prompt


class ResumeAgent:
    """简历优化 Agent，负责定义 prompt、工具和结果映射。"""

    def __init__(self):
        self.tools = ResumeTools()
        self.prompt_spec = load_prompt("resume_agent")
        self.runtime = AgentRuntime()
        self.definition = AgentDefinition(
            prompt_spec=self.prompt_spec,
            tools_schema=self.tools.get_tools_schema(),
            tool_executor=self._run_tool,
            prompt_context_builder=self._build_prompt_context,
            max_iterations=6,
        )

    async def optimize(
        self,
        user_message: str,
        resume_content: Dict[str, Any],
        conversation_history: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        """执行一次简历优化循环。"""
        runtime_result = await self.runtime.run(
            agent=self.definition,
            user_message=user_message,
            context={"resume_content": resume_content},
            conversation_history=conversation_history,
        )
        return {
            "content": runtime_result["content"],
            "qr_images": self._collect_qr_images(runtime_result["tool_calls"]),
            "tool_calls": runtime_result["tool_calls"],
            "resume_content": resume_content,
        }

    async def optimize_stream(
        self,
        user_message: str,
        resume_content: Dict[str, Any],
        conversation_history: Optional[List[Dict[str, str]]] = None,
    ):
        """按阶段流式输出 Agent 执行过程。"""
        async for event in self.runtime.run_stream(
            agent=self.definition,
            user_message=user_message,
            context={"resume_content": resume_content},
            conversation_history=conversation_history,
        ):
            yield {
                "content": event["content"],
                "qr_images": event.get("qr_images", []),
                "tool_calls": event["tool_calls"],
                "resume_content": resume_content if event.get("context") is not None else None,
                "done": event["done"],
            }

    def _build_prompt_context(self, context: Dict[str, Any]) -> Dict[str, Any]:
        resume_content = context["resume_content"]
        return {
            "resume_json": json.dumps(resume_content, ensure_ascii=False, indent=2)
        }

    def _run_tool(
        self, tool_call: Dict[str, Any], context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """执行单个工具调用并返回结构化结果"""
        resume_content = context["resume_content"]
        tool_name = tool_call["function"]["name"]
        tool_args = json.loads(tool_call["function"]["arguments"])
        result = self.tools.execute_tool(
            tool_name=tool_name, resume_content=resume_content, **tool_args
        )
        return {
            "tool_name": tool_name,
            "result": result,
            "display_message": (
                result.get("diff_summary") or result.get("message")
                if isinstance(result, dict)
                else None
            ),
            "qr_image": result.get("image_base64") if isinstance(result, dict) else None,
            "updated_section_name": self._get_section_name(
                result.get("updated_section") if isinstance(result, dict) else None
            ),
        }

    def _collect_qr_images(self, tool_calls: List[Dict[str, Any]]) -> List[str]:
        """兼容旧返回结构，目前简历工具没有稳定产出二维码。"""
        return []

    def _get_section_name(self, section_key: Optional[str]) -> Optional[str]:
        """将板块键转成中文名称。"""
        section_names = {
            "personal_info": "个人信息",
            "education": "教育经历",
            "work_experience": "工作经历",
            "skills": "技能专长",
            "projects": "项目经历",
            "summary": "个人总结",
            "languages": "语言能力",
        }
        if not section_key:
            return None
        return section_names.get(section_key, section_key)
