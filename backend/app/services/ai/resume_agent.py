"""
简历优化 Agent

保留简历领域规则，通用执行逻辑由 AgentRuntime 负责。
"""

import asyncio
from typing import Any, Dict, List, Optional
import json
import logging
from .agent_runtime import AgentDefinition, AgentRuntime
from .resume_tools import ResumeTools
from app.prompts import load_prompt
from app.schemas.resume import dump_resume_content_for_frontend

logger = logging.getLogger(__name__)


def _parse_tool_arguments(raw: Any) -> Dict[str, Any]:
    """解析工具参数，兼容 Gemini/OpenRouter 流式返回的各种格式。"""
    # 已经是 dict（部分模型不走字符串路径）
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, str):
        raise ValueError(f"无法解析工具参数类型: {type(raw)}, value={raw!r}")
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        logger.warning(f"json.loads 失败，尝试修复: {e}, raw={raw!r}")
        # 尝试提取第一个完整 JSON 对象（应对尾部多余字符）
        import re
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        raise


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
        allowed_sections: Optional[set[str]] = None,
    ) -> Dict[str, Any]:
        """执行一次简历优化循环。"""
        runtime_result = await self.runtime.run(
            agent=self.definition,
            user_message=user_message,
            context={
                "resume_content": resume_content,
                "allowed_sections": allowed_sections,
            },
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
        confirmation_queue: Optional[asyncio.Queue] = None,
        allowed_sections: Optional[set[str]] = None,
    ):
        """按阶段流式输出 Agent 执行过程。"""
        context = {
            "resume_content": resume_content,
            "allowed_sections": allowed_sections,
        }
        async for event in self.runtime.run_stream(
            agent=self.definition,
            user_message=user_message,
            context=context,
            conversation_history=conversation_history,
            confirmation_queue=confirmation_queue,
        ):
            yield {
                "content": event.get("content", ""),
                "qr_images": event.get("qr_images", []),
                "tool_calls": event.get("tool_calls", []),
                # 从 context 读取最新 resume_content，避免工具被拒绝回滚后引用陈旧数据
                "resume_content": context.get("resume_content") if event.get("context") is not None else None,
                # 工具确认相关字段透传
                "tool_pending": event.get("tool_pending"),
                "tool_confirmed": event.get("tool_confirmed"),
                "tool_rejected": event.get("tool_rejected"),
                "call_id": event.get("call_id"),
                "tool_name": event.get("tool_name"),
                "diff_summary": event.get("diff_summary"),
                "done": event.get("done", False),
            }

    def _build_prompt_context(self, context: Dict[str, Any]) -> Dict[str, Any]:
        resume_content = context["resume_content"]
        return {
            "resume_json": json.dumps(
                self._strip_redundant_fields(resume_content),
                ensure_ascii=False,
                indent=2,
            )
        }

    @staticmethod
    def _strip_redundant_fields(resume_content: Dict[str, Any]) -> Dict[str, Any]:
        """移除发给 Agent 的简历 JSON 中的冗余字段，避免 Agent 重复修改同一数据。
        - achievements 与 highlights 内容相同，只保留 highlights。
        - 空的 summary 会误导 Agent 以为用户缺少“个人总结”模块，因此不传。
        """
        import copy
        content = dump_resume_content_for_frontend(copy.deepcopy(resume_content))
        for section in ("work_experience", "projects"):
            items = content.get(section)
            if isinstance(items, list):
                for item in items:
                    item.pop("achievements", None)
        return content

    # 工具名 -> 用户可见的中文名称
    _TOOL_DISPLAY_NAMES = {
        "edit_resume": "编辑简历板块",
        "update_resume_item": "更新条目",
        "add_resume_item": "新增条目",
        "remove_resume_item": "删除条目",
        "read_resume": "读取简历",
    }

    def _run_tool(
        self, tool_call: Dict[str, Any], context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """执行单个工具调用并返回结构化结果"""
        resume_content = context["resume_content"]
        tool_name = tool_call["function"]["name"]
        raw_args = tool_call["function"]["arguments"]
        logger.debug(f"[tool_call] {tool_name} raw_args={raw_args!r}")
        tool_args = _parse_tool_arguments(raw_args)
        allowed_sections = context.get("allowed_sections")
        target_section = tool_args.get("section")
        if (
            allowed_sections is not None
            and target_section
            and target_section not in allowed_sections
        ):
            return {
                "tool_name": self._TOOL_DISPLAY_NAMES.get(tool_name, tool_name),
                "result": {
                    "success": False,
                    "message": f"板块 {target_section} 当前已隐藏，禁止修改",
                    "updated_section": target_section,
                },
                "display_message": f"板块 {target_section} 当前已隐藏，禁止修改",
                "qr_image": None,
                "updated_section_name": self._get_section_name(target_section),
            }
        result = self.tools.execute_tool(
            tool_name=tool_name, resume_content=resume_content, **tool_args
        )
        return {
            "tool_name": self._TOOL_DISPLAY_NAMES.get(tool_name, tool_name),
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
