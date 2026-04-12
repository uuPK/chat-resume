"""
面试官聊天 Agent

复用通用 AgentRuntime，但不暴露任何工具。
"""

import json
from typing import Any, Dict, List, Optional

from app.prompts import load_prompt
from app.schemas.resume import dump_resume_content_for_frontend

from app.agents.runtime.agent_runtime import AgentDefinition, AgentRuntime


class InterviewerAgent:
    """基于简历上下文进行模拟面试对话的无工具 Agent。"""

    def __init__(self):
        self.prompt_spec = load_prompt("interviewer_agent")
        self.runtime = AgentRuntime()
        self.definition = AgentDefinition(
            prompt_spec=self.prompt_spec,
            tools_schema=[],
            tool_executor=self._run_tool,
            prompt_context_builder=self._build_prompt_context,
            max_iterations=1,
        )

    async def chat(
        self,
        user_message: str,
        resume_content: Dict[str, Any],
        conversation_history: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        runtime_result = await self.runtime.run(
            agent=self.definition,
            user_message=user_message,
            context={"resume_content": resume_content},
            conversation_history=conversation_history,
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
    ):
        async for event in self.runtime.run_stream(
            agent=self.definition,
            user_message=user_message,
            context={"resume_content": resume_content},
            conversation_history=conversation_history,
        ):
            yield {
                "content": event.get("content", ""),
                "tool_calls": [],
                "resume_content": None,
                "done": event.get("done", False),
            }

    def _build_prompt_context(self, context: Dict[str, Any]) -> Dict[str, Any]:
        resume_content = dump_resume_content_for_frontend(context["resume_content"])
        job_application = resume_content.get("job_application", {})
        return {
            "target_title": str(job_application.get("target_title", "") or ""),
            "target_company": str(job_application.get("target_company", "") or ""),
            "jd_text": str(job_application.get("jd_text", "") or ""),
            "resume_json": json.dumps(resume_content, ensure_ascii=False, indent=2),
        }

    def _run_tool(self, tool_call: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        del tool_call, context
        raise RuntimeError("InterviewerAgent does not support tool calls")
