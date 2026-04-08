import asyncio
import sys
import unittest
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.ai.agent_runtime import AgentRuntime  # noqa: E402
from app.services.ai.resume_agent import ResumeAgent  # noqa: E402


class FakeChatService:
    def __init__(self, responses=None, stream_rounds=None):
        self.responses = responses or []
        self.stream_rounds = stream_rounds or []
        self.chat_calls = 0
        self.stream_calls = 0

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
        response = self.responses[self.chat_calls]
        self.chat_calls += 1
        return response

    async def chat_completion_stream_deltas(
        self,
        messages,
        temperature=0.7,
        max_tokens=None,
        tools=None,
        system_prompt=None,
    ):
        del messages, temperature, max_tokens, tools, system_prompt
        deltas = self.stream_rounds[self.stream_calls]
        self.stream_calls += 1
        for delta in deltas:
            yield delta


class ResumeAgentSmokeTests(unittest.IsolatedAsyncioTestCase):
    def _build_agent(self, chat_service):
        agent = ResumeAgent()
        agent.runtime = AgentRuntime(chat_service=chat_service)
        return agent

    def _sample_resume(self):
        return {
            "personal_info": {"name": "张三", "position": "后端开发"},
            "summary": {"text": "3年 Python 后端开发经验"},
            "work_experience": [
                {
                    "id": "work_1",
                    "company": "某科技公司",
                    "position": "Python 开发工程师",
                    "summary": "负责内部系统开发",
                    "highlights": [{"id": "hl_1", "text": "维护多个后台服务"}],
                }
            ],
            "projects": [],
            "skills": [],
            "education": [],
            "languages": [],
        }

    async def test_optimize_returns_plain_text_without_mutation(self):
        chat_service = FakeChatService(
            responses=[
                {
                    "choices": [
                        {
                            "message": {
                                "content": "我建议优先强化项目结果和量化指标。",
                            }
                        }
                    ]
                }
            ]
        )
        agent = self._build_agent(chat_service)
        resume = self._sample_resume()

        result = await agent.optimize("帮我看看这份简历怎么优化", resume)

        self.assertEqual(result["content"], "我建议优先强化项目结果和量化指标。")
        self.assertEqual(result["tool_calls"], [])
        self.assertEqual(resume["summary"]["text"], "3年 Python 后端开发经验")

    async def test_optimize_updates_resume_via_tool_call(self):
        chat_service = FakeChatService(
            responses=[
                {
                    "choices": [
                        {
                            "message": {
                                "content": "",
                                "tool_calls": [
                                    {
                                        "id": "call_1",
                                        "type": "function",
                                        "function": {
                                            "name": "update_resume_item",
                                            "arguments": (
                                                '{"section":"work_experience",'
                                                '"item_id":"work_1",'
                                                '"patch":{"summary":"负责内部系统开发与性能优化，'
                                                '推动核心接口响应时间下降 30%"}}'
                                            ),
                                        },
                                    }
                                ],
                            }
                        }
                    ]
                },
                {
                    "choices": [
                        {
                            "message": {
                                "content": "我已经把工作经历改成结果导向表达，并补了量化成果。",
                            }
                        }
                    ]
                },
            ]
        )
        agent = self._build_agent(chat_service)
        resume = self._sample_resume()

        result = await agent.optimize("优化我的工作经历", resume)

        self.assertIn("量化成果", result["content"])
        self.assertEqual(len(result["tool_calls"]), 1)
        self.assertIn("响应时间下降 30%", resume["work_experience"][0]["summary"])

    async def test_optimize_stream_applies_change_after_confirmation(self):
        chat_service = FakeChatService(
            stream_rounds=[
                [
                    {
                        "tool_calls": [
                            {
                                "index": 0,
                                "id": "call_stream_1",
                                "function": {
                                    "name": "update_resume_item",
                                    "arguments": (
                                        '{"section":"work_experience",'
                                        '"item_id":"work_1",'
                                        '"patch":{"summary":"负责核心后台系统开发，'
                                        '支撑日活 10 万用户，并完成接口性能优化"}}'
                                    ),
                                },
                            }
                        ]
                    }
                ],
                [
                    {"content": "已完成优化，"},
                    {"content": "重点突出系统规模和性能成果。"},
                ],
            ]
        )
        agent = self._build_agent(chat_service)
        resume = self._sample_resume()
        confirmation_queue = asyncio.Queue()
        confirmation_queue.put_nowait(True)

        events = []
        async for event in agent.optimize_stream(
            user_message="优化这段工作经历",
            resume_content=resume,
            conversation_history=[],
            confirmation_queue=confirmation_queue,
        ):
            events.append(event)

        self.assertTrue(any(event.get("tool_pending") for event in events))
        self.assertTrue(any(event.get("tool_confirmed") for event in events))
        self.assertEqual(
            resume["work_experience"][0]["summary"],
            "负责核心后台系统开发，支撑日活 10 万用户，并完成接口性能优化",
        )
        self.assertEqual(
            "".join(event.get("content", "") for event in events),
            "已完成优化，重点突出系统规模和性能成果。",
        )

    async def test_optimize_stream_reject_keeps_resume_unchanged(self):
        chat_service = FakeChatService(
            stream_rounds=[
                [
                    {
                        "tool_calls": [
                            {
                                "index": 0,
                                "id": "call_stream_2",
                                "function": {
                                    "name": "update_resume_item",
                                    "arguments": (
                                        '{"section":"work_experience",'
                                        '"item_id":"work_1",'
                                        '"patch":{"summary":"这是一个不应被应用的修改"}}'
                                    ),
                                },
                            }
                        ]
                    }
                ],
                [
                    {"content": "我保留了原内容，等待你提供更具体的目标岗位。"},
                ],
            ]
        )
        agent = self._build_agent(chat_service)
        resume = self._sample_resume()
        confirmation_queue = asyncio.Queue()
        confirmation_queue.put_nowait(False)

        events = []
        async for event in agent.optimize_stream(
            user_message="随便改一下工作经历",
            resume_content=resume,
            conversation_history=[],
            confirmation_queue=confirmation_queue,
        ):
            events.append(event)

        self.assertTrue(any(event.get("tool_rejected") for event in events))
        self.assertEqual(resume["work_experience"][0]["summary"], "负责内部系统开发")


if __name__ == "__main__":
    unittest.main()
