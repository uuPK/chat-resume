"""
简历优化 Agent

保留简历领域规则，通用执行逻辑由 AgentRuntime 负责。
"""

import asyncio
from typing import Any, Dict, List, Optional
import json
import logging
from app.agents.runtime.agent_runtime import AgentDefinition, AgentRuntime
from app.agents.tools.resume_tool_executor import (
    ResumeToolExecutor,
    TOOL_REQUIRED_ARGS,
)
from app.agents.tools.resume_tools import ResumeTools
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
        self.tool_executor = ResumeToolExecutor(self.tools)
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
                "tool_call_failed": event.get("tool_call_failed"),
                "call_id": event.get("call_id"),
                "tool_call": event.get("tool_call"),
                "tool_name": event.get("tool_name"),
                "diff_summary": event.get("diff_summary"),
                "result": event.get("result"),
                "display_message": event.get("display_message"),
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

    def _prepare_tool_args(
        self, tool_name: str, raw_args: Any
    ) -> tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
        try:
            tool_args = _parse_tool_arguments(raw_args)
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            return None, self.tool_executor.error_result(
                tool_name,
                "invalid_arguments_json",
                f"工具参数不是合法 JSON，无法执行 {tool_name}: {exc}",
                recoverable=True,
                expected_arguments=sorted(TOOL_REQUIRED_ARGS.get(tool_name, set())),
            )

        if not isinstance(tool_args, dict):
            return None, self.tool_executor.error_result(
                tool_name,
                "invalid_arguments_type",
                f"工具参数必须是对象，实际收到 {type(tool_args).__name__}",
                recoverable=True,
                expected_arguments=sorted(TOOL_REQUIRED_ARGS.get(tool_name, set())),
            )

        if tool_name == "update_overview" and not tool_args.get("section"):
            tool_args["section"] = "projects"

        required = TOOL_REQUIRED_ARGS.get(tool_name)
        if required is None and tool_name != "read_resume":
            return None, self.tool_executor.error_result(
                tool_name,
                "unknown_tool",
                f"Unknown tool: {tool_name}",
                recoverable=False,
            )

        if required:
            missing = sorted(key for key in required if not tool_args.get(key))
            if missing:
                return None, self.tool_executor.error_result(
                    tool_name,
                    "missing_required_argument",
                    f"{tool_name} 缺少必填参数: {', '.join(missing)}",
                    recoverable=True,
                    expected_arguments=sorted(required),
                    updated_section=tool_args.get("section"),
                )

        return tool_args, None

    def _run_tool(
        self, tool_call: Dict[str, Any], context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """执行单个工具调用并返回结构化结果"""
        tool_name = tool_call["function"]["name"]
        raw_args = tool_call["function"]["arguments"]
        logger.debug(f"[tool_call] {tool_name} raw_args={raw_args!r}")
        tool_args, error_result = self._prepare_tool_args(tool_name, raw_args)
        if error_result is not None:
            return error_result
        assert tool_args is not None
        return self.tool_executor.execute(
            tool_name=tool_name,
            tool_input=tool_args,
            context=context,
        )

    def _collect_qr_images(self, tool_calls: List[Dict[str, Any]]) -> List[str]:
        """兼容旧返回结构，目前简历工具没有稳定产出二维码。"""
        return []
