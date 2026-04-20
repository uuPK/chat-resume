"""用于封装结构化面试 Agent 的业务入口。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.prompts import load_prompt
from app.runtime.loop import AgentDefinition, AgentRuntime

from .prompt_context import build_interviewer_prompt_context

INTERVIEW_TOOLS_SCHEMA: list[dict[str, Any]] = []


class InterviewerAgent:
    """用于组合面试提示词和运行时，生成结构化追问。"""

    def __init__(self):
        """用于初始化面试 Agent 的固定配置。"""
        self.prompt_spec = load_prompt("interviewer_agent")
        self.runtime = AgentRuntime()
        self.definition = AgentDefinition(
            prompt_spec=self.prompt_spec,
            tools_schema=INTERVIEW_TOOLS_SCHEMA,
            tool_executor=self._run_tool,
            prompt_context_builder=build_interviewer_prompt_context,
            max_iterations=1,
            max_history_messages=40,
        )

    async def chat(
        self,
        user_message: str,
        resume_content: Dict[str, Any],
        conversation_history: Optional[List[Dict[str, str]]] = None,
        event_callback=None,
    ) -> Dict[str, Any]:
        """用于执行一次非流式面试官回复。"""
        runtime_result = await self.runtime.run(
            agent=self.definition,
            user_message=user_message,
            context={"resume_content": resume_content},
            conversation_history=conversation_history,
            event_callback=event_callback,
        )
        return {
            "content": runtime_result["content"],
            "tool_calls": [],
            "resume_content": resume_content,
        }

    async def chat_stream(
        self,
        user_message: str,
        resume_content: Dict[str, Any],
        conversation_history: Optional[List[Dict[str, str]]] = None,
        event_callback=None,
    ):
        """用于执行一次流式面试官回复。"""
        async for event in self.runtime.run_stream(
            agent=self.definition,
            user_message=user_message,
            context={"resume_content": resume_content},
            conversation_history=conversation_history,
            event_callback=event_callback,
        ):
            yield {
                "content": event.get("content", ""),
                "tool_calls": [],
                "resume_content": None,
                "done": event.get("done", False),
            }

    def _build_prompt_context(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """用于生成面试提示词渲染所需的上下文。"""
        return build_interviewer_prompt_context(context)

    def _run_tool(
        self, tool_call: Dict[str, Any], context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """用于显式拒绝面试 Agent 不支持的工具调用。"""
        del tool_call, context
        raise RuntimeError("InterviewerAgent does not support tool calls")


__all__ = ["InterviewerAgent"]
