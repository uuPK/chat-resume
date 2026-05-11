import asyncio
import sys
import tempfile
import unittest
from pathlib import Path

from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.agents.resume.agent import ResumeAgent  # noqa: E402
from app.infra.config import settings  # noqa: E402
from app.runtime.deepagents_runtime import DeepAgentRuntime  # noqa: E402
from app.services.llm.chat_service import ChatService  # noqa: E402


class FakeDeepAgentChatModel(FakeMessagesListChatModel):
    def bind_tools(self, tools, *, tool_choice=None, **kwargs):
        del tools, tool_choice, kwargs
        return self


def fake_tool_call(
    *,
    name: str,
    args: dict,
    call_id: str,
) -> dict:
    return {"name": name, "args": args, "id": call_id}


class ResumeAgentSmokeTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_user_memory_dir = settings.USER_MEMORY_DIR
        settings.USER_MEMORY_DIR = self.temp_dir.name

    def tearDown(self):
        settings.USER_MEMORY_DIR = self.original_user_memory_dir
        self.temp_dir.cleanup()

    def _build_agent(self, responses):
        agent = ResumeAgent()
        agent.runtime = DeepAgentRuntime(
            model=FakeDeepAgentChatModel(responses=responses)
        )
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
        agent = self._build_agent(
            [AIMessage(content="我建议优先强化项目结果和量化指标。")]
        )
        resume = self._sample_resume()

        result = await agent.optimize("帮我看看这份简历怎么优化", resume)

        self.assertEqual(result["content"], "我建议优先强化项目结果和量化指标。")
        self.assertEqual(result["tool_calls"], [])
        self.assertEqual(resume["summary"]["text"], "3年 Python 后端开发经验")

    async def test_optimize_updates_resume_via_tool_call(self):
        agent = self._build_agent(
            [
                AIMessage(
                    content="",
                    tool_calls=[
                        fake_tool_call(
                            name="update_highlight",
                            call_id="call_1",
                            args={
                                "section": "work_experience",
                                "item_id": "work_1",
                                "highlight_id": "hl_1",
                                "text": "维护多个后台服务，并推动核心接口响应时间下降 30%",
                            },
                        )
                    ],
                ),
                AIMessage(content="我已经把工作经历改成结果导向表达，并补了量化成果。"),
            ]
        )
        resume = self._sample_resume()

        result = await agent.optimize("优化我的工作经历", resume)

        self.assertIn("量化成果", result["content"])
        self.assertEqual(len(result["tool_calls"]), 1)
        self.assertIn(
            "响应时间下降 30%",
            resume["work_experience"][0]["highlights"][0]["text"],
        )

    async def test_optimize_executes_all_deep_agent_tool_calls(self):
        agent = self._build_agent(
            [
                AIMessage(
                    content="",
                    tool_calls=[
                        fake_tool_call(
                            name="update_overview",
                            call_id="call_first",
                            args={
                                "section": "projects",
                                "item_id": "proj_1",
                                "overview": "新的项目简介",
                            },
                        ),
                        fake_tool_call(
                            name="add_highlight",
                            call_id="call_second",
                            args={
                                "section": "projects",
                                "item_id": "proj_1",
                                "text": "这条不应在同一轮被执行",
                            },
                        ),
                    ],
                ),
                AIMessage(content="已先完成第一步修改。"),
            ]
        )
        resume = self._sample_resume()

        result = await agent.optimize("优化项目内容", resume)

        self.assertEqual(result["content"], "已先完成第一步修改。")
        self.assertEqual(len(result["tool_calls"]), 2)
        self.assertEqual(resume["projects"][0]["overview"], "新的项目简介")
        self.assertEqual(len(resume["projects"][0]["highlights"]), 2)
        self.assertEqual(
            resume["projects"][0]["highlights"][-1]["text"],
            "这条不应在同一轮被执行",
        )

    async def test_optimize_retries_recoverable_tool_error(self):
        agent = self._build_agent(
            [
                AIMessage(
                    content="",
                    tool_calls=[
                        fake_tool_call(
                            name="update_overview",
                            call_id="call_bad",
                            args={"section": "projects", "overview": "缺少 item_id"},
                        )
                    ],
                ),
                AIMessage(
                    content="",
                    tool_calls=[
                        fake_tool_call(
                            name="update_overview",
                            call_id="call_fixed",
                            args={
                                "section": "projects",
                                "item_id": "proj_1",
                                "overview": "重试后写入的简介",
                            },
                        )
                    ],
                ),
                AIMessage(content="已根据工具错误修正参数并完成修改。"),
            ]
        )
        resume = self._sample_resume()

        result = await agent.optimize("优化项目简介", resume)

        self.assertEqual(len(result["tool_calls"]), 2)
        self.assertEqual(resume["projects"][0]["overview"], "重试后写入的简介")
        self.assertIn("修正参数", result["content"])

    async def test_optimize_stream_applies_change_after_confirmation(self):
        agent = self._build_agent(
            [
                AIMessage(
                    content="",
                    tool_calls=[
                        fake_tool_call(
                            name="update_highlight",
                            call_id="call_stream_1",
                            args={
                                "section": "work_experience",
                                "item_id": "work_1",
                                "highlight_id": "hl_1",
                                "text": (
                                    "维护多个后台服务，支撑日活 10 万用户，"
                                    "并完成接口性能优化"
                                ),
                            },
                        )
                    ],
                ),
                AIMessage(content="已完成优化，重点突出系统规模和性能成果。"),
            ]
        )
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

    async def test_optimize_stream_serializes_multiple_business_tool_confirmations(
        self,
    ):
        agent = self._build_agent(
            [
                AIMessage(
                    content="",
                    tool_calls=[
                        fake_tool_call(
                            name="update_overview",
                            call_id="call_stream_first",
                            args={
                                "section": "projects",
                                "item_id": "proj_1",
                                "overview": "先优化项目简介",
                            },
                        ),
                        fake_tool_call(
                            name="add_highlight",
                            call_id="call_stream_second",
                            args={
                                "section": "projects",
                                "item_id": "proj_1",
                                "text": "同一轮不应继续新增亮点",
                            },
                        ),
                    ],
                ),
                AIMessage(content="已按顺序完成项目简介和项目亮点优化。"),
            ]
        )
        resume = self._sample_resume()
        confirmation_queue = asyncio.Queue()
        confirmation_queue.put_nowait(True)
        confirmation_queue.put_nowait(True)

        events = []
        async for event in agent.optimize_stream(
            user_message="优化项目内容",
            resume_content=resume,
            conversation_history=[],
            confirmation_queue=confirmation_queue,
        ):
            events.append(event)

        pending_events = [event for event in events if event.get("tool_pending")]
        confirmed_events = [event for event in events if event.get("tool_confirmed")]
        self.assertEqual(len(pending_events), 2)
        self.assertEqual(len(confirmed_events), 2)
        self.assertEqual(resume["projects"][0]["overview"], "先优化项目简介")
        self.assertEqual(len(resume["projects"][0]["highlights"]), 2)
        self.assertEqual(
            resume["projects"][0]["highlights"][-1]["text"],
            "同一轮不应继续新增亮点",
        )
        self.assertEqual(
            "".join(event.get("content", "") for event in events),
            "已按顺序完成项目简介和项目亮点优化。",
        )

    async def test_optimize_stream_reject_keeps_resume_unchanged(self):
        agent = self._build_agent(
            [
                AIMessage(
                    content="",
                    tool_calls=[
                        fake_tool_call(
                            name="update_highlight",
                            call_id="call_stream_2",
                            args={
                                "section": "work_experience",
                                "item_id": "work_1",
                                "highlight_id": "hl_1",
                                "text": "这是一个不应被应用的修改",
                            },
                        )
                    ],
                ),
                AIMessage(content="我保留了原内容，等待你提供更具体的目标岗位。"),
            ]
        )
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
        agent = self._build_agent(
            [
                AIMessage(
                    content="",
                    tool_calls=[
                        fake_tool_call(
                            name="update_overview",
                            call_id="call_stream_bad",
                            args={"section": "projects", "overview": "缺少 item_id"},
                        )
                    ],
                ),
                AIMessage(
                    content="",
                    tool_calls=[
                        fake_tool_call(
                            name="update_overview",
                            call_id="call_stream_fixed",
                            args={
                                "section": "projects",
                                "item_id": "proj_1",
                                "overview": "流式重试后的简介",
                            },
                        )
                    ],
                ),
                AIMessage(content="已完成流式重试。"),
            ]
        )
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

    async def test_optimize_stream_auto_executes_read_user_memory_without_confirmation(
        self,
    ):
        agent = self._build_agent(
            [
                AIMessage(
                    content="",
                    tool_calls=[
                        fake_tool_call(
                            name="read_user_memory",
                            call_id="call_read_memory_1",
                            args={},
                        )
                    ],
                ),
                AIMessage(content="我已读取你的长期记忆，并会按既有偏好继续优化。"),
            ]
        )
        resume = self._sample_resume()
        confirmation_queue = asyncio.Queue()

        events = []
        async for event in agent.optimize_stream(
            user_message="读取我之前记住的偏好",
            resume_content=resume,
            conversation_history=[],
            confirmation_queue=confirmation_queue,
            user_id=55,
        ):
            events.append(event)

        self.assertFalse(any(event.get("tool_pending") for event in events))
        self.assertFalse(any(event.get("tool_confirmed") for event in events))
        self.assertEqual(
            "".join(event.get("content", "") for event in events),
            "我已读取你的长期记忆，并会按既有偏好继续优化。",
        )


class ResumeDeepAgentRuntimeTests(unittest.IsolatedAsyncioTestCase):
    def _sample_resume(self):
        return {
            "work_experience": [
                {
                    "id": "work_1",
                    "company": "某科技公司",
                    "position": "Python 开发工程师",
                    "highlights": [{"id": "hl_1", "text": "维护多个后台服务"}],
                }
            ]
        }

    async def test_resume_agent_uses_deep_agent_runtime_by_default(self):
        agent = ResumeAgent()

        self.assertIsInstance(agent.runtime, DeepAgentRuntime)

    async def test_deep_agent_runtime_disables_parallel_tool_calls_at_model_layer(
        self,
    ):
        runtime = DeepAgentRuntime()

        model = runtime._build_model(ResumeAgent().definition)

        self.assertEqual(model.model_kwargs.get("parallel_tool_calls"), False)

    async def test_deep_agent_runtime_stream_preserves_confirmation_flow(self):
        model = FakeDeepAgentChatModel(
            responses=[
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "update_highlight",
                            "args": {
                                "section": "work_experience",
                                "item_id": "work_1",
                                "highlight_id": "hl_1",
                                "text": "维护多个后台服务，支撑日活 10 万用户",
                                "reason": "补充业务规模",
                            },
                            "id": "call_deep_1",
                        }
                    ],
                ),
                AIMessage(content="已完成优化。"),
            ]
        )
        agent = ResumeAgent()
        agent.runtime = DeepAgentRuntime(model=model)
        resume = self._sample_resume()
        confirmation_queue = asyncio.Queue()
        confirmation_queue.put_nowait(True)

        events = []
        async for event in agent.optimize_stream(
            user_message="优化这段工作经历",
            resume_content=resume,
            conversation_history=[],
            confirmation_queue=confirmation_queue,
            allowed_sections={"work_experience"},
        ):
            events.append(event)

        self.assertTrue(any(event.get("tool_pending") for event in events))
        self.assertTrue(any(event.get("tool_confirmed") for event in events))
        self.assertEqual(
            resume["work_experience"][0]["highlights"][0]["text"],
            "维护多个后台服务，支撑日活 10 万用户",
        )
        self.assertEqual(
            "".join(event.get("content", "") for event in events),
            "已完成优化。",
        )

    async def test_deep_agent_runtime_stream_emits_agent_trace_logs(self):
        model = FakeDeepAgentChatModel(
            responses=[
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "update_highlight",
                            "args": {
                                "section": "work_experience",
                                "item_id": "work_1",
                                "highlight_id": "hl_1",
                                "text": "维护多个后台服务，支撑日活 10 万用户",
                                "reason": "补充业务规模",
                            },
                            "id": "call_deep_trace",
                        }
                    ],
                ),
                AIMessage(content="已完成优化。"),
            ]
        )
        agent = ResumeAgent()
        agent.runtime = DeepAgentRuntime(model=model)
        resume = self._sample_resume()
        confirmation_queue = asyncio.Queue()
        confirmation_queue.put_nowait(True)

        original_trace_log_enabled = settings.AGENT_TRACE_LOG_ENABLED
        settings.AGENT_TRACE_LOG_ENABLED = True
        try:
            with self.assertLogs("app.runtime.deepagents_runtime", level="INFO") as logs:
                events = []
                async for event in agent.optimize_stream(
                    user_message="优化这段工作经历",
                    resume_content=resume,
                    conversation_history=[],
                    confirmation_queue=confirmation_queue,
                    allowed_sections={"work_experience"},
                ):
                    events.append(event)
        finally:
            settings.AGENT_TRACE_LOG_ENABLED = original_trace_log_enabled

        trace_records = [
            record for record in logs.records if getattr(record, "agent_trace", False)
        ]
        trace_messages = [record.getMessage() for record in trace_records]

        self.assertTrue(any(event.get("tool_confirmed") for event in events))
        self.assertEqual(
            "".join(event.get("content", "") for event in events),
            "已完成优化。",
        )
        self.assertEqual(len(trace_records), len(logs.records))
        self.assertIn("agent.trace.run.started", trace_messages)
        self.assertIn("agent.trace.prompt.rendered", trace_messages)
        self.assertIn("agent.trace.llm.request", trace_messages)
        self.assertIn("agent.trace.reasoning.tool_call_detected", trace_messages)
        self.assertEqual(
            trace_messages.count("agent.trace.reasoning.tool_call_detected"),
            1,
        )
        self.assertNotIn("agent.trace.intermediate.skipped", trace_messages)
        self.assertIn("agent.trace.tool.requested", trace_messages)
        self.assertIn("agent.trace.tool.preview", trace_messages)
        self.assertIn("agent.trace.tool.confirmation", trace_messages)
        self.assertIn("agent.trace.tool.executed", trace_messages)
        self.assertIn("agent.trace.intermediate.chunk", trace_messages)
        self.assertIn("agent.trace.llm.response", trace_messages)
        self.assertIn("agent.trace.run.completed", trace_messages)

        run_ids = {getattr(record, "run_id", None) for record in trace_records}
        self.assertEqual(len(run_ids), 1)
        self.assertNotIn(None, run_ids)

        requested = next(
            record
            for record in trace_records
            if record.getMessage() == "agent.trace.tool.requested"
        )
        self.assertEqual(requested.tool_name, "update_highlight")
        self.assertNotIn("resume_content", requested.tool_input)
        self.assertNotIn("content", requested.tool_input)
        self.assertIn("text", requested.tool_input)

        executed = next(
            record
            for record in trace_records
            if record.getMessage() == "agent.trace.tool.executed"
        )
        self.assertEqual(executed.tool_name, "update_highlight")
        self.assertIs(executed.result_success, True)
        self.assertEqual(executed.result_summary["diff_item_count"], 1)

        response = next(
            record
            for record in trace_records
            if record.getMessage() == "agent.trace.llm.response"
        )
        self.assertEqual(response.response_preview, "已完成优化。")
        self.assertEqual(response.chunk_count, 1)


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
                            {
                                "type": "text",
                                "text": '{"question":"请介绍你的系统设计思路",',
                            },
                            {
                                "type": "text",
                                "text": '"question_type":"technical","intent":"评估架构能力"}',
                            },
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


class RuntimePublicApiTests(unittest.TestCase):
    def test_agent_runtime_compatibility_entrypoint_is_removed(self):
        import app.runtime as runtime

        self.assertNotIn("AgentRuntime", runtime.__all__)
        with self.assertRaises(AttributeError):
            getattr(runtime, "AgentRuntime")

    def test_agent_definition_lives_in_runtime_contracts(self):
        from app.runtime.contracts import AgentDefinition

        agent = ResumeAgent()
        self.assertIsInstance(agent.definition, AgentDefinition)


if __name__ == "__main__":
    unittest.main()
