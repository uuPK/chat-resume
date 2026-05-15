"""用于集中记录 PiAgentRuntime 的诊断 trace 字段。"""

from __future__ import annotations

import logging
from collections.abc import Callable
from time import perf_counter
from typing import Any

from pi_agent_core import ToolExecutionStartEvent

from app.infra.config import settings
from app.runtime.contracts import AgentDefinition
from app.runtime.openrouter_adapter import openrouter_chat_model_name
from app.types.stream import ResumeStreamEvent

logger = logging.getLogger("app.runtime.pi_agent_runtime")


class DefaultTraceRecorder:
    """用于把 runtime 节点转换成稳定的 agent trace 日志。"""

    def __init__(self, chat_model_name: Callable[[], str] | None = None):
        """用于初始化 trace recorder 的模型名来源。"""
        self._chat_model_name = chat_model_name or openrouter_chat_model_name

    def run_started(
        self,
        agent: AgentDefinition,
        run_id: str,
        mode: str,
        user_message: str,
        conversation_history: list[dict[str, str]] | None,
    ) -> None:
        """用于记录 run 启动 trace。"""
        self.trace(
            "agent.trace.run.started",
            run_id=run_id,
            agent_name=agent.prompt_spec.name,
            mode=mode,
            user_message_preview=self.preview_text(user_message),
            history_count=len(conversation_history or []),
            tool_names=list(agent.tool_profiles.get(agent.default_tool_profile, set())),
        )

    def prompt_rendered(
        self,
        agent: AgentDefinition,
        run_id: str,
        system_prompt: str,
    ) -> None:
        """用于记录 prompt 渲染 trace。"""
        self.trace(
            "agent.trace.prompt.rendered",
            run_id=run_id,
            agent_name=agent.prompt_spec.name,
            prompt_chars=len(system_prompt),
        )

    def llm_request(
        self,
        agent: AgentDefinition,
        run_id: str,
        event: ResumeStreamEvent,
    ) -> None:
        """用于记录 LLM 请求 trace。"""
        self.trace(
            "agent.trace.llm.request",
            run_id=run_id,
            agent_name=agent.prompt_spec.name,
            model=self._chat_model_name(),
            message_count=len(event.get("messages", [])),
            tool_profile=event.get("tool_profile"),
            tool_count=event.get("tool_count"),
            prompt_chars=event.get("prompt_chars"),
            tool_names=event.get("tool_names", []),
            params=event.get("params", {}),
        )

    def llm_response(
        self,
        agent: AgentDefinition,
        run_id: str,
        event: ResumeStreamEvent,
    ) -> None:
        """用于记录 LLM 响应 trace。"""
        self.trace(
            "agent.trace.llm.response",
            run_id=run_id,
            agent_name=agent.prompt_spec.name,
            model=self._chat_model_name(),
            response_preview=self.preview_text(event.get("response_content")),
            response_chars=len(str(event.get("response_content") or "")),
            latency_ms=event.get("latency_ms"),
            first_token_latency_ms=event.get("first_token_latency_ms"),
            usage=event.get("usage"),
            confirmation_wait_ms=event.get("confirmation_wait_ms"),
        )

    def run_completed(
        self,
        agent: AgentDefinition,
        run_id: str,
        mode: str,
        state: dict[str, Any],
    ) -> None:
        """用于记录 run 完成 trace。"""
        self.trace(
            "agent.trace.run.completed",
            run_id=run_id,
            agent_name=agent.prompt_spec.name,
            mode=mode,
            latency_ms=round((perf_counter() - state["started_at"]) * 1000, 2),
        )

    def max_iterations_reached(
        self,
        agent: AgentDefinition,
        run_id: str,
        state: dict[str, Any],
    ) -> None:
        """用于记录 ReAct 循环达到最大轮次。"""
        self.trace(
            "agent.trace.run.max_iterations_reached",
            run_id=run_id,
            agent_name=agent.prompt_spec.name,
            tool_call_count=state.get("tool_call_count"),
            reason="react_loop_limit",
        )

    def tool_requested(
        self,
        agent: AgentDefinition,
        run_id: str,
        call_id: str,
        tool_name: str,
        tool_input: dict[str, Any],
        needs_confirmation: bool,
    ) -> None:
        """用于记录工具请求 trace。"""
        self.trace(
            "agent.trace.tool.requested",
            run_id=run_id,
            agent_name=agent.prompt_spec.name,
            call_id=call_id,
            tool_name=tool_name,
            tool_input=self.safe_tool_input(tool_input),
            requires_confirmation=needs_confirmation,
        )

    def tool_preview(
        self,
        agent: AgentDefinition,
        run_id: str,
        call_id: str,
        tool_name: str,
        preview_result: dict[str, Any],
    ) -> None:
        """用于记录工具预览 trace。"""
        result = preview_result.get("result", {})
        diff_items = result.get("diff_items", []) if isinstance(result, dict) else []
        self.trace(
            "agent.trace.tool.preview",
            run_id=run_id,
            agent_name=agent.prompt_spec.name,
            call_id=call_id,
            tool_name=tool_name,
            tool_display_name=preview_result["tool_name"],
            diff_summary=self.preview_text(preview_result.get("display_message")),
            diff_item_count=len(diff_items),
            result_success=self.tool_success(preview_result),
        )

    def tool_confirmation(
        self,
        agent: AgentDefinition,
        run_id: str,
        call_id: str,
        tool_name: str,
        display_name: str,
        confirmed: bool,
        confirmation_wait_ms: float,
        terminate_turn: bool,
    ) -> None:
        """用于记录工具确认 trace。"""
        self.trace(
            "agent.trace.tool.confirmation",
            run_id=run_id,
            agent_name=agent.prompt_spec.name,
            call_id=call_id,
            tool_name=tool_name,
            tool_display_name=display_name,
            confirmed=confirmed,
            confirmation_wait_ms=confirmation_wait_ms,
            terminate_turn=terminate_turn,
        )

    def tool_executed(
        self,
        agent: AgentDefinition,
        run_id: str,
        call_id: str,
        tool_name: str,
        tool_result: dict[str, Any],
        tool_started_at: float,
    ) -> None:
        """用于记录工具执行 trace。"""
        self.trace(
            "agent.trace.tool.executed",
            run_id=run_id,
            agent_name=agent.prompt_spec.name,
            call_id=call_id,
            tool_name=tool_name,
            tool_display_name=tool_result["tool_name"],
            result_success=self.tool_success(tool_result),
            display_message=self.preview_text(tool_result.get("display_message")),
            result_summary=self.result_summary(tool_result.get("result", {})),
            latency_ms=round((perf_counter() - tool_started_at) * 1000, 2),
        )

    def tool_rejected(
        self,
        agent: AgentDefinition,
        run_id: str,
        call_id: str,
        tool_name: str,
        tool_display_name: str,
        tool_started_at: float,
    ) -> None:
        """用于记录工具拒绝 trace。"""
        self.trace(
            "agent.trace.tool.rejected",
            run_id=run_id,
            agent_name=agent.prompt_spec.name,
            call_id=call_id,
            tool_name=tool_name,
            tool_display_name=tool_display_name,
            latency_ms=round((perf_counter() - tool_started_at) * 1000, 2),
        )

    def tool_call_detected(
        self,
        agent: AgentDefinition,
        run_id: str,
        event: ToolExecutionStartEvent,
        state: dict[str, Any],
    ) -> None:
        """用于记录模型发起的工具调用 trace。"""
        allowed_tool_names = {
            str(tool_name)
            for tool_name in state.get("tool_names", [])
            if isinstance(tool_name, str)
        }
        if event.tool_name not in allowed_tool_names:
            self.unexpected_tool_call(agent, run_id, event, state)
            return
        self.trace(
            "agent.trace.reasoning.tool_call_detected",
            run_id=run_id,
            agent_name=agent.prompt_spec.name,
            tool_call_count=1,
            tool_call_chunk_count=1,
            tool_names=[event.tool_name],
        )

    def extra_tool_calls_ignored(
        self,
        agent: AgentDefinition,
        run_id: str,
        tool_name: str,
        tool_call_count: int,
    ) -> None:
        """用于记录同轮多余工具调用被忽略。"""
        self.trace(
            "agent.trace.reasoning.extra_tool_calls_ignored",
            run_id=run_id,
            agent_name=agent.prompt_spec.name,
            tool_name=tool_name,
            tool_call_count=tool_call_count,
            reason="one_tool_per_react_turn",
        )

    def unexpected_tool_call(
        self,
        agent: AgentDefinition,
        run_id: str,
        event: ToolExecutionStartEvent,
        state: dict[str, Any],
    ) -> None:
        """用于记录未暴露工具被模型调用的异常 trace。"""
        logged = state.get("unexpected_tool_call_names")
        if not isinstance(logged, set):
            logged = set()
            state["unexpected_tool_call_names"] = logged
        if event.tool_name in logged:
            return
        logged.add(event.tool_name)
        self.trace(
            "agent.trace.reasoning.unexpected_tool_call",
            run_id=run_id,
            agent_name=agent.prompt_spec.name,
            tool_name=event.tool_name,
            tool_profile=str(state.get("tool_profile") or ""),
            allowed_tool_names=list(state.get("tool_names", [])),
            reason="tool_not_exposed",
        )

    def chunk(self, message: str, **fields: Any) -> None:
        """用于在需要排查流式细节时记录单个 chunk。"""
        if not settings.AGENT_TRACE_CHUNK_LOG_ENABLED:
            return
        self.trace(message, **fields)

    @staticmethod
    def trace(message: str, **fields: Any) -> None:
        """用于写入 agent trace 日志。"""
        if not settings.AGENT_TRACE_LOG_ENABLED:
            return
        logger.info(message, extra={"agent_trace": True, **fields})

    @classmethod
    def result_summary(cls, result: Any) -> dict[str, Any]:
        """用于生成工具结果摘要。"""
        if not isinstance(result, dict):
            return {"type": type(result).__name__, "preview": cls.preview_text(result)}
        summary: dict[str, Any] = {"keys": sorted(str(key) for key in result.keys())}
        if "success" in result:
            summary["success"] = result.get("success")
        if "diff_summary" in result:
            summary["diff_summary"] = cls.preview_text(result.get("diff_summary"))
        if isinstance(result.get("diff_items"), list):
            summary["diff_item_count"] = len(result["diff_items"])
        if "error" in result:
            summary["error"] = cls.preview_text(result.get("error"))
        return summary

    @classmethod
    def safe_tool_input(cls, tool_input: dict[str, Any]) -> dict[str, Any]:
        """用于去除工具输入中的长文本字段。"""
        return {
            key: cls.summarize_value(value)
            for key, value in tool_input.items()
            if key not in {"resume_content", "content"}
        }

    @classmethod
    def summarize_value(cls, value: Any) -> Any:
        """用于把任意值压缩为日志安全摘要。"""
        if isinstance(value, str):
            return cls.preview_text(value)
        if isinstance(value, (int, float, bool)) or value is None:
            return value
        if isinstance(value, list):
            return {"type": "list", "count": len(value)}
        if isinstance(value, dict):
            return {"type": "dict", "keys": sorted(str(key) for key in value.keys())[:20]}
        return {"type": type(value).__name__, "preview": cls.preview_text(value)}

    @staticmethod
    def tool_success(tool_result: dict[str, Any]) -> bool | None:
        """用于读取工具执行结果成功状态。"""
        result = tool_result.get("result")
        if isinstance(result, dict) and "success" in result:
            return bool(result["success"])
        return None

    @staticmethod
    def preview_text(value: Any, limit: int = 240) -> str:
        """用于生成单行预览文本。"""
        if value is None:
            return ""
        text = " ".join(str(value).split())
        if len(text) <= limit:
            return text
        return f"{text[:limit]}..."


__all__ = ["DefaultTraceRecorder"]
