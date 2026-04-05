"""
简历优化 Agent

使用 ReAct (推理+行动) 循环：模型自主决定是否调用工具、调用几次、何时停止。
相比原来固定的 3 阶段流水线，减少了 LLM 调用次数，响应更快，决策更灵活。
"""

import asyncio
from typing import Any, Dict, List, Optional
import json
from .chat_service import ChatService
from .resume_tools import ResumeTools
from app.prompts import load_prompt


class ResumeAgent:
    """简历优化 Agent，基于 ReAct 循环自主执行"""

    def __init__(self):
        self.chat_service = ChatService()
        self.tools = ResumeTools()
        self.max_iterations = 6  # 防止无限循环
        self.prompt_spec = load_prompt("resume_agent")

    async def optimize(
        self,
        user_message: str,
        resume_content: Dict[str, Any],
        conversation_history: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        """ReAct 循环：思考 → 行动(可选) → 观察 → 思考 → ... → 最终回复"""
        messages = self._build_messages(user_message, conversation_history)

        executed_tools: List[Dict[str, Any]] = []
        qr_images: List[str] = []
        final_text = ""

        defaults = self.prompt_spec.model_defaults
        for _ in range(self.max_iterations):
            system_prompt = self.prompt_spec.render(
                resume_json=json.dumps(resume_content, ensure_ascii=False, indent=2)
            )
            response = await self.chat_service.chat_completion(
                messages=messages,
                system_prompt=system_prompt,
                tools=self.tools.get_tools_schema(),
                temperature=defaults.get("temperature", 0.3),
                max_tokens=defaults.get("max_tokens", 1500),
                stream=False,
            )

            message = response["choices"][0]["message"]
            messages.append(message)

            # 没有工具调用 → 模型已给出最终回复，循环结束
            if not message.get("tool_calls"):
                final_text = message.get("content") or "已完成处理。"
                break

            # 执行所有工具调用，将结果反馈给模型（Observe 阶段）
            for tool_call in message["tool_calls"]:
                tool_result = self._run_tool(tool_call, resume_content)
                executed_tools.append({
                    "name": tool_result["tool_name"],
                    "result": tool_result["display_message"] or "执行完成",
                })
                if tool_result["qr_image"]:
                    qr_images.append(tool_result["qr_image"])
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call["id"],
                    "content": json.dumps(tool_result["result"], ensure_ascii=False),
                })

        return {
            "content": final_text,
            "qr_images": qr_images,
            "tool_calls": executed_tools,
            "resume_content": resume_content,
        }

    async def optimize_stream(
        self,
        user_message: str,
        resume_content: Dict[str, Any],
        conversation_history: Optional[List[Dict[str, str]]] = None,
    ):
        """按阶段流式输出 Agent 执行过程。"""
        messages = self._build_messages(user_message, conversation_history)

        executed_tools: List[Dict[str, Any]] = []
        qr_images: List[str] = []

        defaults = self.prompt_spec.model_defaults
        for iteration in range(self.max_iterations):
            system_prompt = self.prompt_spec.render(
                resume_json=json.dumps(resume_content, ensure_ascii=False, indent=2)
            )
            response = await self.chat_service.chat_completion(
                messages=messages,
                system_prompt=system_prompt,
                tools=self.tools.get_tools_schema(),
                temperature=defaults.get("temperature", 0.3),
                max_tokens=defaults.get("max_tokens", 1500),
                stream=False,
            )

            message = response["choices"][0]["message"]
            messages.append(message)

            if not message.get("tool_calls"):
                final_text = message.get("content") or "已完成处理。"
                async for chunk in self._stream_text(final_text):
                    yield {
                        "content": chunk,
                        "qr_images": [],
                        "tool_calls": executed_tools,
                        "resume_content": None,
                        "done": False,
                    }
                break

            for tool_call in message["tool_calls"]:
                tool_result = self._run_tool(tool_call, resume_content)
                executed_tools.append(
                    {
                        "name": tool_result["tool_name"],
                        "result": tool_result["display_message"] or "执行完成",
                    }
                )
                if tool_result["qr_image"]:
                    qr_images.append(tool_result["qr_image"])

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call["id"],
                        "content": json.dumps(tool_result["result"], ensure_ascii=False),
                    }
                )

                yield {
                    "content": "",
                    "qr_images": [tool_result["qr_image"]] if tool_result["qr_image"] else [],
                    "tool_calls": executed_tools,
                    "resume_content": resume_content,
                    "done": False,
                }

    def _build_messages(
        self,
        user_message: str,
        conversation_history: Optional[List[Dict[str, str]]],
    ) -> List[Dict[str, Any]]:
        """构建消息列表"""
        messages: List[Dict[str, Any]] = []
        if conversation_history:
            messages.extend(conversation_history[-6:])
        messages.append({"role": "user", "content": user_message})
        return messages

    def _run_tool(
        self, tool_call: Dict[str, Any], resume_content: Dict[str, Any]
    ) -> Dict[str, Any]:
        """执行单个工具调用并返回结构化结果"""
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

    async def _stream_text(self, text: str, chunk_size: int = 24):
        """将最终回复切成小块，提升前端感知流式体验。"""
        for i in range(0, len(text), chunk_size):
            yield text[i : i + chunk_size]
            await asyncio.sleep(0.02)

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
