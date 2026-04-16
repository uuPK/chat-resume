import asyncio
import sys
import unittest
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.agents.definitions.resume_agent import ResumeAgent  # noqa: E402
from app.agents.runtime.agent_runtime import AgentRuntime  # noqa: E402
from app.services.llm.chat_service import ChatService  # noqa: E402


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
            "projects": [
                {
                    "id": "proj_1",
                    "name": "Chat Resume",
                    "role": "开发者",
                    "duration": "2025",
                    "overview": "AI 求职辅导平台",
                    "highlights": [{"id": "proj_hl_1", "text": "支持流式简历优化"}],
                }
            ],
            "skills": [],
            "education": [],
            "languages": [],
        }

    def test_strip_redundant_fields_removes_empty_summary(self):
        cleaned = ResumeAgent._strip_redundant_fields(
            {
                "personal_info": {"name": "张三"},
                "summary": {"text": "   "},
                "projects": [],
                "work_experience": [],
            }
        )

        self.assertNotIn("summary", cleaned)

    def test_strip_redundant_fields_drops_summary_even_when_non_empty(self):
        cleaned = ResumeAgent._strip_redundant_fields(
            {
                "personal_info": {"name": "张三"},
                "summary": {"text": "有 3 年后端开发经验"},
                "projects": [],
                "work_experience": [],
            }
        )

        self.assertNotIn("summary", cleaned)

    def test_run_tool_rejects_hidden_section(self):
        agent = ResumeAgent()
        result = agent._run_tool(
            {
                "function": {
                    "name": "add_highlight",
                    "arguments": {
                        "section": "skills",
                        "item_id": "skill_1",
                        "text": "不应被允许",
                    },
                }
            },
            {
                "resume_content": self._sample_resume(),
                "allowed_sections": {"personal_info", "work_experience"},
            },
        )

        self.assertIn("禁止修改", result["display_message"])
        self.assertEqual(result["updated_section_name"], "技能专长")

    def test_update_overview_tool_updates_project_overview(self):
        agent = ResumeAgent()
        resume = self._sample_resume()

        result = agent._run_tool(
            {
                "function": {
                    "name": "update_overview",
                    "arguments": {
                        "section": "projects",
                        "item_id": "proj_1",
                        "overview": "支持结构化简历编辑、Agent 改写和模拟面试。",
                    },
                }
            },
            {"resume_content": resume},
        )

        self.assertTrue(result["result"]["success"])
        self.assertEqual(
            resume["projects"][0]["overview"],
            "支持结构化简历编辑、Agent 改写和模拟面试。",
        )

    def test_update_overview_defaults_missing_section_to_projects(self):
        agent = ResumeAgent()
        resume = self._sample_resume()

        result = agent._run_tool(
            {
                "function": {
                    "name": "update_overview",
                    "arguments": {
                        "item_id": "proj_1",
                        "overview": "默认补全 projects 后完成更新。",
                    },
                }
            },
            {"resume_content": resume},
        )

        self.assertTrue(result["result"]["success"])
        self.assertEqual(
            resume["projects"][0]["overview"],
            "默认补全 projects 后完成更新。",
        )

    def test_update_overview_missing_item_id_returns_recoverable_error(self):
        agent = ResumeAgent()
        resume = self._sample_resume()

        result = agent._run_tool(
            {
                "function": {
                    "name": "update_overview",
                    "arguments": {
                        "section": "projects",
                        "overview": "缺少 item_id 时不应抛出 TypeError。",
                    },
                }
            },
            {"resume_content": resume},
        )

        self.assertFalse(result["result"]["success"])
        self.assertEqual(
            result["result"]["error"]["type"],
            "missing_required_argument",
        )
        self.assertTrue(result["result"]["error"]["recoverable"])
        self.assertIn("item_id", result["display_message"])

    def test_invalid_tool_arguments_json_returns_recoverable_error(self):
        agent = ResumeAgent()
        resume = self._sample_resume()

        result = agent._run_tool(
            {
                "function": {
                    "name": "update_highlight",
                    "arguments": '{"section":"projects",',
                }
            },
            {"resume_content": resume},
        )

        self.assertFalse(result["result"]["success"])
        self.assertEqual(
            result["result"]["error"]["type"],
            "invalid_arguments_json",
        )
        self.assertTrue(result["result"]["error"]["recoverable"])

    def test_update_highlight_tool_updates_single_highlight(self):
        agent = ResumeAgent()
        resume = self._sample_resume()

        result = agent._run_tool(
            {
                "function": {
                    "name": "update_highlight",
                    "arguments": {
                        "section": "work_experience",
                        "item_id": "work_1",
                        "highlight_id": "hl_1",
                        "text": "维护多个后台服务并推动关键接口性能优化",
                    },
                }
            },
            {"resume_content": resume},
        )

        self.assertTrue(result["result"]["success"])
        self.assertEqual(
            resume["work_experience"][0]["highlights"][0]["text"],
            "维护多个后台服务并推动关键接口性能优化",
        )

    def test_add_highlight_tool_appends_highlight(self):
        agent = ResumeAgent()
        resume = self._sample_resume()

        result = agent._run_tool(
            {
                "function": {
                    "name": "add_highlight",
                    "arguments": {
                        "section": "projects",
                        "item_id": "proj_1",
                        "text": "支持工具调用后的人机确认流程",
                    },
                }
            },
            {"resume_content": resume},
        )

        self.assertTrue(result["result"]["success"])
        self.assertEqual(len(resume["projects"][0]["highlights"]), 2)
        self.assertEqual(
            resume["projects"][0]["highlights"][-1]["text"],
            "支持工具调用后的人机确认流程",
        )

    def test_remove_highlight_tool_deletes_highlight(self):
        agent = ResumeAgent()
        resume = self._sample_resume()

        result = agent._run_tool(
            {
                "function": {
                    "name": "remove_highlight",
                    "arguments": {
                        "section": "projects",
                        "item_id": "proj_1",
                        "highlight_id": "proj_hl_1",
                    },
                }
            },
            {"resume_content": resume},
        )

        self.assertTrue(result["result"]["success"])
        self.assertEqual(resume["projects"][0]["highlights"], [])

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
                                            "name": "update_highlight",
                                            "arguments": (
                                                '{"section":"work_experience",'
                                                '"item_id":"work_1",'
                                                '"highlight_id":"hl_1",'
                                                '"text":"维护多个后台服务，并推动核心接口响应时间下降 30%"}'
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
        self.assertIn(
            "响应时间下降 30%",
            resume["work_experience"][0]["highlights"][0]["text"],
        )

    async def test_optimize_executes_only_first_tool_call_per_round(self):
        chat_service = FakeChatService(
            responses=[
                {
                    "choices": [
                        {
                            "message": {
                                "content": "",
                                "tool_calls": [
                                    {
                                        "id": "call_first",
                                        "type": "function",
                                        "function": {
                                            "name": "update_overview",
                                            "arguments": (
                                                '{"section":"projects",'
                                                '"item_id":"proj_1",'
                                                '"overview":"新的项目简介"}'
                                            ),
                                        },
                                    },
                                    {
                                        "id": "call_second",
                                        "type": "function",
                                        "function": {
                                            "name": "add_highlight",
                                            "arguments": (
                                                '{"section":"projects",'
                                                '"item_id":"proj_1",'
                                                '"text":"这条不应在同一轮被执行"}'
                                            ),
                                        },
                                    },
                                ],
                            }
                        }
                    ]
                },
                {
                    "choices": [
                        {
                            "message": {
                                "content": "已先完成第一步修改。",
                            }
                        }
                    ]
                },
            ]
        )
        agent = self._build_agent(chat_service)
        resume = self._sample_resume()

        result = await agent.optimize("优化项目内容", resume)

        self.assertEqual(result["content"], "已先完成第一步修改。")
        self.assertEqual(len(result["tool_calls"]), 1)
        self.assertEqual(resume["projects"][0]["overview"], "新的项目简介")
        self.assertEqual(len(resume["projects"][0]["highlights"]), 1)

    async def test_optimize_retries_recoverable_tool_error(self):
        chat_service = FakeChatService(
            responses=[
                {
                    "choices": [
                        {
                            "message": {
                                "content": "",
                                "tool_calls": [
                                    {
                                        "id": "call_bad",
                                        "type": "function",
                                        "function": {
                                            "name": "update_overview",
                                            "arguments": (
                                                '{"section":"projects",'
                                                '"overview":"缺少 item_id"}'
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
                                "content": "",
                                "tool_calls": [
                                    {
                                        "id": "call_fixed",
                                        "type": "function",
                                        "function": {
                                            "name": "update_overview",
                                            "arguments": (
                                                '{"section":"projects",'
                                                '"item_id":"proj_1",'
                                                '"overview":"重试后写入的简介"}'
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
                                "content": "已根据工具错误修正参数并完成修改。",
                            }
                        }
                    ]
                },
            ]
        )
        agent = self._build_agent(chat_service)
        resume = self._sample_resume()

        result = await agent.optimize("优化项目简介", resume)

        self.assertEqual(chat_service.chat_calls, 3)
        self.assertEqual(resume["projects"][0]["overview"], "重试后写入的简介")
        self.assertIn("修正参数", result["content"])

    async def test_optimize_stops_after_recoverable_tool_error_limit(self):
        responses = []
        for idx in range(3):
            responses.append(
                {
                    "choices": [
                        {
                            "message": {
                                "content": "",
                                "tool_calls": [
                                    {
                                        "id": f"call_bad_{idx}",
                                        "type": "function",
                                        "function": {
                                            "name": "update_overview",
                                            "arguments": '{"section":"projects","overview":"仍然缺少 item_id"}',
                                        },
                                    }
                                ],
                            }
                        }
                    ]
                }
            )
        chat_service = FakeChatService(responses=responses)
        agent = self._build_agent(chat_service)
        resume = self._sample_resume()

        result = await agent.optimize("优化项目简介", resume)

        self.assertEqual(chat_service.chat_calls, 3)
        self.assertIn("已停止自动重试", result["content"])
        self.assertEqual(resume["projects"][0]["overview"], "AI 求职辅导平台")

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
                                    "name": "update_highlight",
                                    "arguments": (
                                        '{"section":"work_experience",'
                                        '"item_id":"work_1",'
                                        '"highlight_id":"hl_1",'
                                        '"text":"维护多个后台服务，支撑日活 10 万用户，并完成接口性能优化"}'
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
            resume["work_experience"][0]["highlights"][0]["text"],
            "维护多个后台服务，支撑日活 10 万用户，并完成接口性能优化",
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
                                    "name": "update_highlight",
                                    "arguments": (
                                        '{"section":"work_experience",'
                                        '"item_id":"work_1",'
                                        '"highlight_id":"hl_1",'
                                        '"text":"这是一个不应被应用的修改"}'
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
        self.assertEqual(
            resume["work_experience"][0]["highlights"][0]["text"],
            "维护多个后台服务",
        )

    async def test_optimize_stream_emits_tool_call_failed_then_recovers(self):
        chat_service = FakeChatService(
            stream_rounds=[
                [
                    {
                        "tool_calls": [
                            {
                                "index": 0,
                                "id": "call_stream_bad",
                                "function": {
                                    "name": "update_overview",
                                    "arguments": '{"section":"projects","overview":"缺少 item_id"}',
                                },
                            }
                        ]
                    }
                ],
                [
                    {
                        "tool_calls": [
                            {
                                "index": 0,
                                "id": "call_stream_fixed",
                                "function": {
                                    "name": "update_overview",
                                    "arguments": (
                                        '{"section":"projects",'
                                        '"item_id":"proj_1",'
                                        '"overview":"流式重试后的简介"}'
                                    ),
                                },
                            }
                        ]
                    }
                ],
                [
                    {"content": "已完成流式重试。"},
                ],
            ]
        )
        agent = self._build_agent(chat_service)
        resume = self._sample_resume()

        events = []
        async for event in agent.optimize_stream(
            user_message="优化项目简介",
            resume_content=resume,
            conversation_history=[],
            confirmation_queue=None,
        ):
            events.append(event)

        self.assertTrue(any(event.get("tool_call_failed") for event in events))
        self.assertEqual(resume["projects"][0]["overview"], "流式重试后的简介")
        self.assertEqual(
            "".join(event.get("content", "") for event in events),
            "已完成流式重试。",
        )


class ChatServiceChunkParsingTests(unittest.TestCase):
    def test_extract_sse_data_accepts_data_prefix_without_space(self):
        self.assertEqual(
            ChatService._extract_sse_data('data:{"choices":[{"text":"ok"}]}'),
            '{"choices":[{"text":"ok"}]}',
        )

    def test_extract_stream_delta_accepts_message_content(self):
        chunk = {
            "choices": [
                {
                    "message": {
                        "content": '{"question":"请介绍你最熟悉的 Agent 项目","question_type":"experience","intent":"评估项目经验"}'
                    }
                }
            ]
        }

        self.assertEqual(
            ChatService._extract_stream_delta(chunk),
            {
                "content": '{"question":"请介绍你最熟悉的 Agent 项目","question_type":"experience","intent":"评估项目经验"}'
            },
        )

    def test_extract_stream_delta_flattens_content_parts(self):
        chunk = {
            "choices": [
                {
                    "message": {
                        "content": [
                            {"type": "text", "text": '{"question":"请介绍你的系统设计思路",'},
                            {"type": "text", "text": '"question_type":"technical","intent":"评估架构能力"}'},
                        ]
                    }
                }
            ]
        }

        self.assertEqual(
            ChatService._extract_stream_delta(chunk),
            {
                "content": '{"question":"请介绍你的系统设计思路","question_type":"technical","intent":"评估架构能力"}'
            },
        )


class AgentRuntimeResponseHandlingTests(unittest.IsolatedAsyncioTestCase):
    async def test_next_message_retries_when_length_truncated_and_content_empty(self):
        chat_service = FakeChatService(
            responses=[
                {
                    "choices": [
                        {
                            "finish_reason": "length",
                            "message": {
                                "content": "",
                            },
                        }
                    ]
                },
                {
                    "choices": [
                        {
                            "finish_reason": "stop",
                            "message": {
                                "content": '{"question":"请介绍你主导的项目","question_type":"experience","intent":"评估项目 ownership"}',
                            },
                        }
                    ]
                },
            ]
        )
        runtime = AgentRuntime(chat_service=chat_service)
        agent = ResumeAgent().definition

        message = await runtime._next_message(
            agent=agent,
            messages=[{"role": "user", "content": "test"}],
            context={"resume_content": {}},
        )

        self.assertEqual(chat_service.chat_calls, 2)
        self.assertEqual(
            message["content"],
            '{"question":"请介绍你主导的项目","question_type":"experience","intent":"评估项目 ownership"}',
        )

    async def test_next_message_normalizes_non_stream_content_parts(self):
        chat_service = FakeChatService(
            responses=[
                {
                    "choices": [
                        {
                            "finish_reason": "stop",
                            "message": {
                                "content": [
                                    {"type": "text", "text": '{"question":"请介绍你的系统设计思路",'},
                                    {"type": "text", "text": '"question_type":"technical","intent":"评估架构能力"}'},
                                ]
                            },
                        }
                    ]
                }
            ]
        )
        runtime = AgentRuntime(chat_service=chat_service)
        agent = ResumeAgent().definition

        message = await runtime._next_message(
            agent=agent,
            messages=[{"role": "user", "content": "test"}],
            context={"resume_content": {}},
        )

        self.assertEqual(
            message["content"],
            '{"question":"请介绍你的系统设计思路","question_type":"technical","intent":"评估架构能力"}',
        )

    async def test_next_message_falls_back_to_stream_when_non_stream_provider_returns_empty_packet(self):
        chat_service = FakeChatService(
            responses=[
                {
                    "choices": [
                        {
                            "finish_reason": None,
                            "message": {
                                "content": None,
                            },
                        }
                    ],
                    "usage": {"total_tokens": 0},
                }
            ],
            stream_rounds=[
                [
                    {
                        "content": "我来直接帮你改写这条亮点。",
                    },
                    {
                        "tool_calls": [
                            {
                                "index": 0,
                                "id": "call_1",
                                "function": {
                                    "name": "update_highlight",
                                    "arguments": '{"section":"projects","item_id":"proj_1","highlight_id":"proj_hl_1","text":"突出结果导向表达","reason":"强化结果表达"}',
                                },
                            }
                        ]
                    },
                ]
            ],
        )
        runtime = AgentRuntime(chat_service=chat_service)
        agent = ResumeAgent().definition

        message = await runtime._next_message(
            agent=agent,
            messages=[{"role": "user", "content": "test"}],
            context={"resume_content": {}},
        )

        self.assertEqual(chat_service.chat_calls, 1)
        self.assertEqual(chat_service.stream_calls, 1)
        self.assertEqual(message["content"], "我来直接帮你改写这条亮点。")
        self.assertEqual(message["tool_calls"][0]["function"]["name"], "update_highlight")


if __name__ == "__main__":
    unittest.main()
