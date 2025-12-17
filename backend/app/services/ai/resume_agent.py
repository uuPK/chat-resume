"""
简历优化 Agent

使用 Function Calling 实现智能简历优化助手
"""

from typing import Dict, Any, List, Optional
import json
from .chat_service import ChatService
from .resume_tools import ResumeTools


class ResumeAgent:
    """简历优化 Agent，支持工具调用"""

    def __init__(self):
        self.chat_service = ChatService()
        self.tools = ResumeTools()
        self.max_iterations = 5  # 最大迭代次数，防止无限循环

    async def optimize(
        self,
        user_message: str,
        resume_content: Dict[str, Any],
        conversation_history: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        """执行简历优化对话

        Args:
            user_message: 用户消息
            resume_content: 简历内容
            conversation_history: 对话历史

        Returns:
            AI 回复
        """
        # 构建系统提示词
        system_prompt = self._build_system_prompt(resume_content)

        # 构建消息列表
        messages = []
        if conversation_history:
            messages.extend(conversation_history)
        messages.append({"role": "user", "content": user_message})

        extra_display: List[str] = []
        qr_images: List[str] = []
        executed_tools: List[Dict[str, Any]] = []

        # 迭代执行，支持多轮工具调用
        for iteration in range(self.max_iterations):
            # 调用 AI，支持 function calling
            response = await self.chat_service.chat_completion(
                messages=messages,
                system_prompt=system_prompt,
                tools=self.tools.get_tools_schema(),
                stream=False,
            )

            # 检查是否需要调用工具
            if self._has_tool_calls(response):
                # 执行工具调用
                tool_results = self._execute_tool_calls(response, resume_content)

                # 将工具结果添加到消息历史
                messages.append(response)
                for tool_result in tool_results:
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_result["tool_call_id"],
                            "content": json.dumps(
                                tool_result["result"], ensure_ascii=False
                            ),
                        }
                    )
                    display = tool_result.get("display_message")
                    if display:
                        extra_display.append(display)
                    qr_image = tool_result.get("qr_image")
                    if qr_image:
                        qr_images.append(qr_image)

                    # 记录工具调用的简要信息，供前端展示
                    tool_call_id = tool_result["tool_call_id"]
                    tool_name = "unknown"
                    # 从 response 中找到对应的 tool name
                    resp_tool_calls = response["choices"][0]["message"].get(
                        "tool_calls", []
                    )
                    for tc in resp_tool_calls:
                        if tc["id"] == tool_call_id:
                            tool_name = tc["function"]["name"]
                            break

                    # 构建精简的自然语言描述
                    tool_desc = f"调用工具 {tool_name}"
                    tool_res_str = str(display) if display else "执行完成"

                    executed_tools.append({"name": tool_name, "result": tool_res_str})

                # 继续下一轮对话
                continue
            else:
                # 没有工具调用，返回最终结果
                final_text = self._extract_content(response)

                return {
                    "content": final_text,
                    "qr_images": qr_images,
                    "tool_calls": executed_tools,
                }

        # 达到最大迭代次数
        timeout_message = "抱歉，优化过程超时，请重新尝试。"
        return {
            "content": timeout_message,
            "qr_images": qr_images,
            "tool_calls": executed_tools,
        }

    def _build_system_prompt(self, resume_content: Dict[str, Any]) -> str:
        """构建系统提示词"""
        return f"""你是一位专业的简历优化专家。你可以使用各种工具来分析和优化用户的简历。

当前简历概况：
- 工作经历：{len(resume_content.get("experience", []))} 条
- 教育背景：{len(resume_content.get("education", []))} 条
- 技能：{len(resume_content.get("skills", []))} 项
- 项目经验：{len(resume_content.get("projects", []))} 个

你的职责：
1. 理解用户的需求（如：匹配特定职位、优化某个章节、提升整体质量）
2. 主动使用工具分析简历
3. 基于工具结果提供专业的优化建议
4. 给出具体的修改方案

可用工具：
- score_resume: 对简历进行不同维度的评分
- login_full_auto: 自动生成二维码并监控Boss直聘扫码
- login_start_interactive: 交互式引导Boss直聘扫码登录
- get_login_info: 查询Boss直聘登录状态
- get_recommend_jobs: 获取Boss直聘职位推荐
- send_greeting: 向Boss直聘职位发送打招呼

请根据用户的问题，主动选择合适的工具进行分析，然后给出专业建议。"""

    def _has_tool_calls(self, response: Dict[str, Any]) -> bool:
        """检查响应中是否包含工具调用"""
        # 检查 OpenAI 格式
        if "choices" in response:
            message = response["choices"][0].get("message", {})
            return "tool_calls" in message and message["tool_calls"]

        # 检查其他格式
        return False

    def _execute_tool_calls(
        self, response: Dict[str, Any], resume_content: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """执行工具调用"""
        results = []

        # 获取工具调用列表
        tool_calls = response["choices"][0]["message"].get("tool_calls", [])

        for tool_call in tool_calls:
            tool_name = tool_call["function"]["name"]
            tool_args = json.loads(tool_call["function"]["arguments"])

            # 执行工具
            result = self.tools.execute_tool(
                tool_name=tool_name, resume_content=resume_content, **tool_args
            )

            display_message = None
            qr_image = None
            if isinstance(result, dict):
                display_message = result.get("message")
                qr_image = result.get("image_base64")
            results.append(
                {
                    "tool_call_id": tool_call["id"],
                    "result": result,
                    "display_message": display_message,
                    "qr_image": qr_image,
                }
            )

        return results

    def _extract_content(self, response: Dict[str, Any]) -> str:
        """从响应中提取内容"""
        if "choices" in response:
            return response["choices"][0]["message"]["content"]

        return "无法获取响应内容"
