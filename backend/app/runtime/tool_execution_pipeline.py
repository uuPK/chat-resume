"""用于集中处理 PiAgentRuntime 的工具构造和执行流水线。"""

from __future__ import annotations

import asyncio
import json
from copy import deepcopy
from time import perf_counter
from typing import Any

from pi_agent_core import AgentTool, AgentToolResult, AgentToolSchema, TextContent

from app.runtime.contracts import AgentDefinition, RuntimeEventCallback
from app.runtime.runtime_event_adapter import RuntimeEventPublisher
from app.runtime.tool_confirmation import ToolConfirmationPolicy
from app.runtime.trace_recorder import DefaultTraceRecorder


class ToolExecutionPipeline:
    """用于封装工具 schema 构造、确认等待、执行和结果事件。"""

    def __init__(
        self,
        *,
        confirmation_policy: ToolConfirmationPolicy | None = None,
        event_publisher: RuntimeEventPublisher | None = None,
        trace_recorder: DefaultTraceRecorder | None = None,
    ):
        """用于初始化工具执行流水线依赖。"""
        self.confirmation_policy = confirmation_policy or ToolConfirmationPolicy()
        self.event_publisher = event_publisher or RuntimeEventPublisher()
        self.trace_recorder = trace_recorder or DefaultTraceRecorder()

    def build_tools(
        self,
        *,
        agent: AgentDefinition,
        tools_schema: list[dict[str, Any]],
        context: dict[str, Any],
        confirmation_queue: asyncio.Queue | None,
        event_queue: asyncio.Queue[Any] | None,
        event_callback: RuntimeEventCallback | None,
        run_id: str,
        executed_tools: list[dict[str, Any]],
        stream_state: dict[str, Any],
    ) -> list[AgentTool]:
        """用于根据工具 schema 构建 pi-agent-core 可执行工具。"""
        tools: list[AgentTool] = []
        lock = asyncio.Lock()
        for schema in tools_schema:
            function = schema.get("function", {})
            tool_name = function.get("name")
            if not isinstance(tool_name, str) or not tool_name:
                continue
            tools.append(
                self._build_tool(
                    agent=agent,
                    tool_name=tool_name,
                    function=function,
                    context=context,
                    confirmation_queue=confirmation_queue,
                    event_queue=event_queue,
                    event_callback=event_callback,
                    run_id=run_id,
                    executed_tools=executed_tools,
                    lock=lock,
                    stream_state=stream_state,
                )
            )
        return tools

    async def execute_tool_result(
        self,
        *,
        agent: AgentDefinition,
        run_id: str,
        call_id: str,
        tool_name: str,
        tool_input: dict[str, Any],
        context: dict[str, Any],
        confirmation_queue: asyncio.Queue | None,
        event_queue: asyncio.Queue[Any] | None,
        event_callback: RuntimeEventCallback | None,
        executed_tools: list[dict[str, Any]],
        stream_state: dict[str, Any],
    ) -> AgentToolResult:
        """用于执行工具并转换为 pi-agent-core ToolResult。"""
        output = await self._execute_tool(
            agent=agent,
            run_id=run_id,
            call_id=call_id,
            tool_name=tool_name,
            tool_input=tool_input,
            context=context,
            confirmation_queue=confirmation_queue,
            event_queue=event_queue,
            event_callback=event_callback,
            executed_tools=executed_tools,
            stream_state=stream_state,
        )
        return AgentToolResult(content=[TextContent(text=output)], details=output)

    @staticmethod
    def tool_profile(agent: AgentDefinition, context: dict[str, Any]) -> str:
        """用于选择当前轮次实际使用的工具 profile。"""
        requested = context.get("tool_profile")
        if isinstance(requested, str) and requested in agent.tool_profiles:
            return requested
        return agent.default_tool_profile

    @staticmethod
    def profiled_tool_schemas(
        agent: AgentDefinition,
        tool_profile: str,
    ) -> list[dict[str, Any]]:
        """用于按工具 profile 过滤暴露给模型的工具 schema。"""
        allowed = agent.tool_profiles.get(tool_profile)
        if allowed is None:
            allowed = agent.tool_profiles.get(agent.default_tool_profile)
        if not allowed:
            return []
        return [
            schema
            for schema in agent.tools_schema
            if schema.get("function", {}).get("name") in allowed
        ]

    @staticmethod
    def tool_names_from_schemas(schemas: list[dict[str, Any]]) -> list[str]:
        """用于从工具 schema 列表读取工具名。"""
        names: list[str] = []
        for schema in schemas:
            name = schema.get("function", {}).get("name")
            if isinstance(name, str) and name:
                names.append(name)
        return names

    def _build_tool(
        self,
        *,
        agent: AgentDefinition,
        tool_name: str,
        function: dict[str, Any],
        context: dict[str, Any],
        confirmation_queue: asyncio.Queue | None,
        event_queue: asyncio.Queue[Any] | None,
        event_callback: RuntimeEventCallback | None,
        run_id: str,
        executed_tools: list[dict[str, Any]],
        lock: asyncio.Lock,
        stream_state: dict[str, Any],
    ) -> AgentTool:
        """用于构建单个工具并绑定执行上下文。"""

        async def execute(
            tool_call_id: str,
            params: dict[str, Any],
            *_args: Any,
        ) -> AgentToolResult:
            """用于执行一次业务工具调用。"""
            if tool_name in agent.auto_execute_tool_names:
                return await self.execute_tool_result(
                    agent=agent,
                    run_id=run_id,
                    call_id=tool_call_id,
                    tool_name=tool_name,
                    tool_input=params,
                    context=context,
                    confirmation_queue=confirmation_queue,
                    event_queue=event_queue,
                    event_callback=event_callback,
                    executed_tools=executed_tools,
                    stream_state=stream_state,
                )
            async with lock:
                return await self.execute_tool_result(
                    agent=agent,
                    run_id=run_id,
                    call_id=tool_call_id,
                    tool_name=tool_name,
                    tool_input=params,
                    context=context,
                    confirmation_queue=confirmation_queue,
                    event_queue=event_queue,
                    event_callback=event_callback,
                    executed_tools=executed_tools,
                    stream_state=stream_state,
                )

        return AgentTool(
            name=tool_name,
            description=str(function.get("description", "")),
            parameters=self.tool_schema(function.get("parameters")),
            execute=execute,
        )

    async def _execute_tool(
        self,
        *,
        agent: AgentDefinition,
        run_id: str,
        call_id: str,
        tool_name: str,
        tool_input: dict[str, Any],
        context: dict[str, Any],
        confirmation_queue: asyncio.Queue | None,
        event_queue: asyncio.Queue[Any] | None,
        event_callback: RuntimeEventCallback | None,
        executed_tools: list[dict[str, Any]],
        stream_state: dict[str, Any],
    ) -> str:
        """用于执行工具确认、预览和最终执行流程。"""
        tool_started_at = perf_counter()
        confirmation_decision = self.confirmation_policy.before_tool_call(
            confirmation_queue=confirmation_queue,
            tool_name=tool_name,
            auto_execute_tool_names=agent.auto_execute_tool_names,
        )
        needs_confirmation = confirmation_decision.requires_confirmation
        tool_call = self.tool_call_payload(call_id, tool_name, tool_input)
        await self._publish_visible_tool_call(
            call_id=call_id,
            tool_name=tool_name,
            tool_input=tool_input,
            event_queue=event_queue,
            event_callback=event_callback,
        )
        self.trace_recorder.tool_requested(
            agent,
            run_id,
            call_id,
            tool_name,
            tool_input,
            needs_confirmation,
        )
        preview = await self._maybe_confirm_tool(
            agent=agent,
            run_id=run_id,
            call_id=call_id,
            tool_name=tool_name,
            tool_input=tool_input,
            tool_call=tool_call,
            context=context,
            confirmation_queue=confirmation_queue,
            event_queue=event_queue,
            event_callback=event_callback,
            executed_tools=executed_tools,
            needs_confirmation=needs_confirmation,
            tool_started_at=tool_started_at,
            stream_state=stream_state,
        )
        if isinstance(preview, str):
            return preview
        return await self._run_confirmed_tool(
            agent=agent,
            run_id=run_id,
            call_id=call_id,
            tool_name=tool_name,
            tool_call=tool_call,
            context=context,
            event_queue=event_queue,
            event_callback=event_callback,
            executed_tools=executed_tools,
            needs_confirmation=needs_confirmation,
            tool_started_at=tool_started_at,
            stream_state=stream_state,
        )

    async def _maybe_confirm_tool(
        self,
        *,
        agent: AgentDefinition,
        run_id: str,
        call_id: str,
        tool_name: str,
        tool_input: dict[str, Any],
        tool_call: dict[str, Any],
        context: dict[str, Any],
        confirmation_queue: asyncio.Queue | None,
        event_queue: asyncio.Queue[Any] | None,
        event_callback: RuntimeEventCallback | None,
        executed_tools: list[dict[str, Any]],
        needs_confirmation: bool,
        tool_started_at: float,
        stream_state: dict[str, Any],
    ) -> dict[str, Any] | str | None:
        """用于处理工具预览和用户确认。"""
        if not needs_confirmation:
            return None
        assert confirmation_queue is not None
        preview_context = {"resume_content": deepcopy(context.get("resume_content"))}
        preview_result = self._call_tool_executor(
            agent=agent,
            tool_call=tool_call,
            context=preview_context,
            tool_name=tool_name,
        )
        if self.is_tool_failure(preview_result):
            return await self._publish_failed_preview(
                agent=agent,
                run_id=run_id,
                call_id=call_id,
                tool_name=tool_name,
                preview_result=preview_result,
                event_queue=event_queue,
                event_callback=event_callback,
                executed_tools=executed_tools,
                tool_started_at=tool_started_at,
            )
        diff_summary = preview_result.get("display_message") or "执行完成"
        result = preview_result.get("result", {})
        diff_items = result.get("diff_items", []) if isinstance(result, dict) else []
        self.trace_recorder.tool_preview(agent, run_id, call_id, tool_name, preview_result)
        await self.event_publisher.publish(
            event_queue=event_queue,
            event_callback=event_callback,
            event=self.event_publisher.tool_pending(
                call_id=call_id,
                tool_name=tool_name,
                tool_call=tool_call,
                tool_display_name=preview_result["tool_name"],
                tool_input=tool_input,
                diff_summary=diff_summary,
                diff_items=diff_items,
                tool_calls=executed_tools,
            ),
        )
        wait_started_at = perf_counter()
        confirmed = await self.confirmation_policy.wait_for_decision(confirmation_queue)
        confirmation_wait_ms = round((perf_counter() - wait_started_at) * 1000, 2)
        stream_state["confirmation_wait_ms"] += confirmation_wait_ms
        confirmation_result = self.confirmation_policy.after_tool_decision(
            confirmed=confirmed,
        )
        self.trace_recorder.tool_confirmation(
            agent,
            run_id,
            call_id,
            tool_name,
            preview_result["tool_name"],
            confirmed,
            confirmation_wait_ms,
            confirmation_result.terminate_turn,
        )
        if confirmed:
            return preview_result
        rejected = {"success": False, "error": "用户拒绝了此修改"}
        await self._publish_rejected_tool(
            agent=agent,
            run_id=run_id,
            call_id=call_id,
            tool_name=tool_name,
            tool_display_name=preview_result["tool_name"],
            diff_summary=diff_summary,
            diff_items=diff_items,
            result=rejected,
            event_queue=event_queue,
            event_callback=event_callback,
            executed_tools=executed_tools,
            tool_started_at=tool_started_at,
        )
        await self._publish_terminal_text(
            agent=agent,
            run_id=run_id,
            stream_state=stream_state,
            event_queue=event_queue,
            event_callback=event_callback,
            content="已取消这处修改。",
        )
        return json.dumps(rejected, ensure_ascii=False)

    async def _run_confirmed_tool(
        self,
        *,
        agent: AgentDefinition,
        run_id: str,
        call_id: str,
        tool_name: str,
        tool_call: dict[str, Any],
        context: dict[str, Any],
        event_queue: asyncio.Queue[Any] | None,
        event_callback: RuntimeEventCallback | None,
        executed_tools: list[dict[str, Any]],
        needs_confirmation: bool,
        tool_started_at: float,
        stream_state: dict[str, Any],
    ) -> str:
        """用于执行已确认或无需确认的工具。"""
        tool_result = self._call_tool_executor(
            agent=agent,
            tool_call=tool_call,
            context=context,
            tool_name=tool_name,
        )
        result = tool_result.get("result", {})
        if needs_confirmation:
            self.remember_confirmed_diff_items(stream_state, result)
        display_message = tool_result.get("display_message")
        self.trace_recorder.tool_executed(
            agent,
            run_id,
            call_id,
            tool_name,
            tool_result,
            tool_started_at,
        )
        executed_tools.append(self.executed_tool_summary(tool_result, result))
        await self._publish_tool_result(
            call_id=call_id,
            tool_name=tool_name,
            tool_result=tool_result,
            result=result,
            display_message=display_message if isinstance(display_message, str) else None,
            event_queue=event_queue,
            event_callback=event_callback,
            executed_tools=executed_tools,
            context=context,
            needs_confirmation=needs_confirmation,
        )
        return json.dumps(result, ensure_ascii=False)

    async def _publish_failed_preview(
        self,
        *,
        agent: AgentDefinition,
        run_id: str,
        call_id: str,
        tool_name: str,
        preview_result: dict[str, Any],
        event_queue: asyncio.Queue[Any] | None,
        event_callback: RuntimeEventCallback | None,
        executed_tools: list[dict[str, Any]],
        tool_started_at: float,
    ) -> str:
        """用于把预览阶段失败转换为工具失败事件。"""
        result = preview_result.get("result", {})
        self.trace_recorder.tool_executed(
            agent,
            run_id,
            call_id,
            tool_name,
            preview_result,
            tool_started_at,
        )
        executed_tools.append(self.executed_tool_summary(preview_result, result))
        await self._publish_tool_result(
            call_id=call_id,
            tool_name=tool_name,
            tool_result=preview_result,
            result=result,
            display_message=preview_result.get("display_message"),
            event_queue=event_queue,
            event_callback=event_callback,
            executed_tools=executed_tools,
            context={},
            needs_confirmation=False,
        )
        return json.dumps(result, ensure_ascii=False)

    async def _publish_terminal_text(
        self,
        *,
        agent: AgentDefinition,
        run_id: str,
        stream_state: dict[str, Any],
        event_queue: asyncio.Queue[Any] | None,
        event_callback: RuntimeEventCallback | None,
        content: str,
    ) -> None:
        """用于在确认后发布确定性文本，避免再次调用模型。"""
        stream_state["chunk_index"] += 1
        stream_state["response_parts"].append(content)
        self.trace_recorder.chunk(
            "agent.trace.intermediate.chunk",
            run_id=run_id,
            agent_name=agent.prompt_spec.name,
            chunk_index=stream_state["chunk_index"],
            content_preview=DefaultTraceRecorder.preview_text(content),
            content_chars=len(content),
        )
        await self.event_publisher.publish(
            event_queue=event_queue,
            event_callback=event_callback,
            event=self.event_publisher.text_delta(content),
        )

    async def _publish_visible_tool_call(
        self,
        *,
        call_id: str,
        tool_name: str,
        tool_input: dict[str, Any],
        event_queue: asyncio.Queue[Any] | None,
        event_callback: RuntimeEventCallback | None,
    ) -> None:
        """用于发布模型请求工具调用的可见事件。"""
        tool_call = self.tool_call_payload(call_id, tool_name, tool_input)
        await self.event_publisher.publish(
            event_queue=event_queue,
            event_callback=event_callback,
            event=self.event_publisher.tool_call_started(
                call_id=call_id,
                tool_name=tool_name,
                tool_call=tool_call,
                tool_input=tool_call["function"]["arguments"],
            ),
        )

    async def _publish_tool_result(
        self,
        *,
        call_id: str,
        tool_name: str,
        tool_result: dict[str, Any],
        result: Any,
        display_message: str | None,
        event_queue: asyncio.Queue[Any] | None,
        event_callback: RuntimeEventCallback | None,
        executed_tools: list[dict[str, Any]],
        context: dict[str, Any],
        needs_confirmation: bool,
    ) -> None:
        """用于根据工具结果发布 confirmed/result/failed 事件。"""
        if self.is_tool_failure(tool_result):
            event = self.event_publisher.tool_call_failed(
                call_id=call_id,
                tool_name=tool_name,
                tool_display_name=tool_result["tool_name"],
                tool_calls=executed_tools,
                result=result,
                display_message=display_message,
            )
        elif needs_confirmation:
            event = self.event_publisher.tool_confirmed(
                call_id=call_id,
                tool_name=tool_name,
                tool_display_name=tool_result["tool_name"],
                tool_calls=executed_tools,
                qr_images=[tool_result["qr_image"]] if tool_result.get("qr_image") else [],
                result=result,
                display_message=display_message,
                diff_summary=result.get("diff_summary") if isinstance(result, dict) else None,
                diff_items=result.get("diff_items", []) if isinstance(result, dict) else [],
                context=context,
            )
        else:
            event = self.event_publisher.tool_result(
                call_id=call_id,
                tool_name=tool_name,
                tool_display_name=tool_result["tool_name"],
                tool_calls=executed_tools,
                result=result,
                display_message=display_message,
                context=context,
            )
        await self.event_publisher.publish(
            event_queue=event_queue,
            event_callback=event_callback,
            event=event,
        )

    async def _publish_rejected_tool(
        self,
        *,
        agent: AgentDefinition,
        run_id: str,
        call_id: str,
        tool_name: str,
        tool_display_name: str,
        diff_summary: str,
        diff_items: Any,
        result: dict[str, Any],
        event_queue: asyncio.Queue[Any] | None,
        event_callback: RuntimeEventCallback | None,
        executed_tools: list[dict[str, Any]],
        tool_started_at: float,
    ) -> None:
        """用于发布用户拒绝工具结果。"""
        self.trace_recorder.tool_rejected(
            agent,
            run_id,
            call_id,
            tool_name,
            tool_display_name,
            tool_started_at,
        )
        await self.event_publisher.publish(
            event_queue=event_queue,
            event_callback=event_callback,
            event=self.event_publisher.tool_rejected(
                call_id=call_id,
                tool_name=tool_name,
                tool_display_name=tool_display_name,
                diff_summary=diff_summary,
                diff_items=diff_items,
                result=result,
                tool_calls=executed_tools,
            ),
        )

    def _call_tool_executor(
        self,
        *,
        agent: AgentDefinition,
        tool_call: dict[str, Any],
        context: dict[str, Any],
        tool_name: str,
    ) -> dict[str, Any]:
        """用于调用业务工具并把异常或坏 schema 降级为失败结果。"""
        try:
            raw_result = agent.tool_executor(tool_call, context)
        except Exception as exc:
            return self._failure_result(tool_name, f"{type(exc).__name__}: {exc}")
        return self._normalize_tool_result(raw_result, tool_name)

    def _normalize_tool_result(
        self,
        raw_result: Any,
        tool_name: str,
    ) -> dict[str, Any]:
        """用于把工具返回值规整成 runtime 可消费结构。"""
        if not isinstance(raw_result, dict):
            return self._failure_result(
                tool_name,
                f"工具返回值必须是 dict，实际收到 {type(raw_result).__name__}",
            )
        result = raw_result.get("result")
        if not isinstance(result, dict):
            return self._failure_result(tool_name, "工具 result 字段必须是 dict")
        normalized = dict(raw_result)
        if not isinstance(normalized.get("tool_name"), str):
            normalized["tool_name"] = tool_name
        return normalized

    @staticmethod
    def _failure_result(tool_name: str, error: str) -> dict[str, Any]:
        """用于生成工具失败结果。"""
        return {
            "tool_name": tool_name,
            "display_message": error,
            "result": {"success": False, "error": error},
        }

    @staticmethod
    def tool_schema(value: Any) -> AgentToolSchema:
        """用于把 OpenAI-style parameters 转成 pi-agent-core schema。"""
        if not isinstance(value, dict):
            return AgentToolSchema()
        properties = value.get("properties")
        required = value.get("required")
        return AgentToolSchema(
            type=str(value.get("type") or "object"),
            properties=properties if isinstance(properties, dict) else {},
            required=required if isinstance(required, list) else [],
        )

    @staticmethod
    def tool_call_payload(
        call_id: str,
        tool_name: str,
        tool_input: dict[str, Any],
    ) -> dict[str, Any]:
        """用于生成工具调用 payload。"""
        return {
            "id": call_id,
            "type": "function",
            "function": {"name": tool_name, "arguments": tool_input},
        }

    @staticmethod
    def executed_tool_summary(
        tool_result: dict[str, Any],
        result: Any,
    ) -> dict[str, Any]:
        """用于生成已执行工具摘要。"""
        return {
            "name": tool_result["tool_name"],
            "result": result.get("diff_summary") if isinstance(result, dict) else tool_result.get("display_message"),
            "success": result.get("success") if isinstance(result, dict) else None,
        }

    @staticmethod
    def remember_confirmed_diff_items(
        stream_state: dict[str, Any],
        result: Any,
    ) -> None:
        """用于把已确认工具产生的 diff 提供给后续只读摘要工具。"""
        if not isinstance(result, dict) or result.get("success") is False:
            return
        diff_items = result.get("diff_items")
        if not isinstance(diff_items, list):
            return
        confirmed = stream_state.get("confirmed_diff_items")
        if isinstance(confirmed, list):
            confirmed.extend(item for item in diff_items if isinstance(item, dict))

    @staticmethod
    def is_tool_failure(tool_result: dict[str, Any]) -> bool:
        """用于判断工具结果是否表示失败。"""
        result = tool_result.get("result")
        return isinstance(result, dict) and result.get("success") is False


__all__ = ["ToolExecutionPipeline"]
