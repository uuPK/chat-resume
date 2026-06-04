"""用于封装简历优化 Agent 的业务入口（基于 LangGraph 重构）。"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, AsyncGenerator, Dict, List, Optional

from langchain_core.messages import HumanMessage, AIMessage

from app.agents.resume.graph import build_graph
from app.types.stream import ResumeStreamEvent

logger = logging.getLogger(__name__)


class ResumeAgent:
    """基于 LangGraph 和 MCP 重构的全新简历优化 Agent。"""

    def __init__(self):
        """初始化编译好的 LangGraph 状态机。"""
        self.graph = build_graph()

    async def optimize(
        self,
        user_message: str,
        resume_content: Dict[str, Any],
        conversation_history: Optional[List[Dict[str, str]]] = None,
        allowed_sections: Optional[set[str]] = None,
        user_id: Optional[int] = None,
        resume_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """用于执行一次非流式简历优化请求。"""
        messages = self._convert_history(conversation_history)
        messages.append(HumanMessage(content=user_message))
        
        # 组装初始的 LangGraph State
        initial_state = {
            "messages": messages,
            "resume_content": resume_content,
            "user_memory": {},  # 真实环境中可以根据 user_id 从数据库动态加载
            "is_valid": True,
            "feedback": None
        }
        
        # 触发图结构运行 (核心入口)
        result = await self.graph.ainvoke(initial_state)
        
        # 提取最后一条大模型回复给前端
        final_message = result["messages"][-1] if result["messages"] else AIMessage(content="处理完成")
        content = final_message.content if isinstance(final_message, AIMessage) else str(final_message)
        
        return {
            "content": content,
            "qr_images": [],
            "tool_calls": [], # 因为已经剥离到 MCP Server 执行，无需再发给前端执行
            "resume_content": result.get("resume_content", resume_content),
        }

    async def optimize_stream(
        self,
        user_message: str,
        resume_content: Dict[str, Any],
        conversation_history: Optional[List[Dict[str, str]]] = None,
        confirmation_queue: Optional[asyncio.Queue] = None,
        allowed_sections: Optional[set[str]] = None,
        event_callback=None,
        user_id: Optional[int] = None,
        resume_id: Optional[int] = None,
        user_preferences: Optional[dict] = None,
    ) -> AsyncGenerator[ResumeStreamEvent, None]:
        """用于执行一次流式简历优化请求（向下兼容旧版的 SSE 格式）。"""
        messages = self._convert_history(conversation_history)
        messages.append(HumanMessage(content=user_message))
        
        initial_state = {
            "messages": messages,
            "resume_content": resume_content,
            "user_memory": user_preferences or {},
            "is_valid": True,
            "feedback": None,
            "user_id": user_id,
            "resume_id": resume_id,
            "confirmation_queue": confirmation_queue
        }
        
        class DSMLStreamFilter:
            def __init__(self):
                self.buffer = ""
                self.in_dsml = False
            def push(self, text: str) -> str:
                self.buffer += text
                out = ""
                while True:
                    if not self.in_dsml:
                        dsml_start = "<｜｜DSML｜｜tool_calls>"
                        idx = self.buffer.find(dsml_start)
                        if idx != -1:
                            out += self.buffer[:idx]
                            self.buffer = self.buffer[idx + len(dsml_start):]
                            self.in_dsml = True
                            continue
                        partial_match = False
                        for i in range(1, len(dsml_start)):
                            if self.buffer.endswith(dsml_start[:i]):
                                out += self.buffer[:-i]
                                self.buffer = self.buffer[-i:]
                                partial_match = True
                                break
                        if not partial_match:
                            out += self.buffer
                            self.buffer = ""
                        break
                    else:
                        dsml_end = "</｜｜DSML｜｜tool_calls>"
                        idx = self.buffer.find(dsml_end)
                        if idx != -1:
                            self.buffer = self.buffer[idx + len(dsml_end):]
                            self.in_dsml = False
                            continue
                        break
                return out

        dsml_filter = DSMLStreamFilter()
        
        # 立即输出一个占位符，满足 3 秒内极速响应要求
        yield {"event_type": "text_delta", "content": "💡 正在为您分析并优化...\n\n"}
        
        # 使用 LangGraph v2 的事件流 API，拦截模型的 chunk 转化给前端，并且支持 on_custom_event
        async for event in self.graph.astream_events(initial_state, version="v2"):
            kind = event["event"]
            if kind == "on_chat_model_stream":
                chunk = event["data"]["chunk"]
                if chunk.content:
                    clean_text = dsml_filter.push(chunk.content)
                    if clean_text:
                        yield {"event_type": "text_delta", "content": clean_text}
            elif kind == "on_tool_start":
                run_id = event.get("run_id", "")
                yield {"event_type": "tool_call", "call_id": run_id, "tool_name": event["name"]}
            elif kind == "on_tool_end":
                run_id = event.get("run_id", "")
                yield {"event_type": "tool_result", "call_id": run_id, "tool_name": event["name"], "result": event.get("data", {}).get("output")}
            elif kind == "on_custom_event":
                name = event.get("name")
                data = event.get("data", {})
                if name == "manual_tool_start":
                    yield {"event_type": "tool_call", "call_id": data.get("run_id", ""), "tool_name": data.get("name", "")}
                elif name == "manual_tool_end":
                    yield {"event_type": "tool_result", "call_id": data.get("run_id", ""), "tool_name": data.get("name", ""), "result": data.get("output", "")}
                    yield {"event_type": "text_delta", "content": "\n\n> ✅ 已成功保存修改到简历。\n"}
                elif name == "manual_tool_pending":
                    import json
                    args_dict = data.get('args', {})
                    # 过滤内部参数
                    display_args = {k: v for k, v in args_dict.items() if not k.startswith('_')}
                    tool_name = data.get("name", "")
                    
                    diff_items = []
                    if tool_name == "update_bullet":
                        section = display_args.get("section", "")
                        text = display_args.get("text", "")
                        diff_summary = f"正在修改 [{section}] 的内容..."
                        diff_items.append({
                            "type": "modify",
                            "path": f"{section}",
                            "new_value": text
                        })
                    else:
                        diff_summary = f"准备执行工具 [{tool_name}]："
                        for k, v in display_args.items():
                            diff_items.append({
                                "type": "modify",
                                "path": k,
                                "new_value": str(v)
                            })
                            
                    yield {
                        "event_type": "tool_pending", 
                        "tool_pending": True,
                        "call_id": data.get("run_id", ""), 
                        "tool_name": tool_name,
                        "diff_summary": diff_summary,
                        "diff_items": diff_items
                    }
                elif name == "manual_tool_confirmed":
                    yield {
                        "event_type": "tool_confirmed",
                        "tool_confirmed": True,
                        "call_id": data.get("run_id", ""), 
                        "tool_name": data.get("name", "")
                    }
                elif name == "manual_tool_rejected":
                    yield {
                        "event_type": "tool_rejected",
                        "tool_rejected": True,
                        "call_id": data.get("run_id", ""), 
                        "tool_name": data.get("name", "")
                    }
                
        # 告诉前端流结束了
        # flush anything left in buffer if not in DSML
        if not dsml_filter.in_dsml and dsml_filter.buffer:
            yield {"event_type": "text_delta", "content": dsml_filter.buffer}
            
        yield {
            "event_type": "done",
            "resume_content": initial_state.get("resume_content")
        }

    def _convert_history(self, history: Optional[List[Dict[str, str]]]) -> list:
        """转换前端传来的历史消息为 LangChain 标准 Message。"""
        messages = []
        if not history:
            return messages
        for msg in history:
            if msg.get("role") == "user":
                messages.append(HumanMessage(content=msg.get("content", "")))
            elif msg.get("role") == "assistant":
                messages.append(AIMessage(content=msg.get("content", "")))
        return messages


__all__ = ["ResumeAgent"]
