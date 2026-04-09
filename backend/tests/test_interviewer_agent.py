import sys
import unittest
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.ai.agent_runtime import AgentRuntime  # noqa: E402
from app.services.ai.interviewer_agent import InterviewerAgent  # noqa: E402


class FakeChatService:
    def __init__(self, response: str):
        self.response = response

    async def chat_completion(
        self,
        messages,
        temperature=0.7,
        max_tokens=None,
        stream=False,
        tools=None,
        system_prompt=None,
    ):
        del messages, temperature, max_tokens, stream, tools, system_prompt
        return {
            "choices": [
                {
                    "message": {"role": "assistant", "content": self.response},
                    "finish_reason": "stop",
                }
            ]
        }


class InterviewerAgentTests(unittest.IsolatedAsyncioTestCase):
    async def test_chat_returns_plain_text_without_tool_calls(self):
        agent = InterviewerAgent()
        agent.runtime = AgentRuntime(chat_service=FakeChatService("请你先用两分钟介绍一下你最近的核心项目。"))

        result = await agent.chat(
            user_message="开始面试",
            resume_content={
                "job_application": {
                    "target_title": "后端工程师",
                    "target_company": "示例公司",
                },
                "work_experience": [],
            },
            conversation_history=[],
        )

        self.assertEqual(result["content"], "请你先用两分钟介绍一下你最近的核心项目。")
        self.assertEqual(result["tool_calls"], [])

    def test_prompt_context_includes_job_application(self):
        agent = InterviewerAgent()
        context = agent._build_prompt_context(
            {
                "resume_content": {
                    "job_application": {
                        "target_title": "后端工程师",
                        "target_company": "示例公司",
                        "jd_text": "负责高并发 API 与稳定性建设",
                    },
                    "projects": [],
                }
            }
        )

        self.assertEqual(context["target_title"], "后端工程师")
        self.assertEqual(context["target_company"], "示例公司")
        self.assertIn("高并发 API", context["jd_text"])
        self.assertIn('"job_application"', context["resume_json"])
