"""用于覆盖 test_resume_agent_smoke.py 对应的回归测试。"""

import asyncio
import sys
import unittest
from typing import Any
from pathlib import Path
from pi_agent_core import (
    AssistantMessage,
    StreamDoneEvent,
    StreamStartEvent,
    StreamTextDeltaEvent,
    StreamTextEndEvent,
    StreamTextStartEvent,
    StreamToolCallEndEvent,
    StreamToolCallStartEvent,
    TextContent,
    ToolCall,
)
from pi_agent_core.types import AgentContext, Model, SimpleStreamOptions, StreamResult

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.agents.resume.agent import ResumeAgent  # noqa: E402
from app.infra.config import settings  # noqa: E402
from app.runtime.pi_agent_runtime import PiAgentRuntime  # noqa: E402
from app.services.llm.chat_service import ChatService  # noqa: E402


class FakeModelResponse:
    """用于描述测试模型返回的文本或工具调用。"""

    def __init__(
        self,
        content: str,
        tool_calls: list[dict[str, Any]] | None = None,
    ):
        """用于处理init。"""
        self.content = content
        self.tool_calls = tool_calls or []


class FakePiAgentStream:
    """用于给 pi-agent-core runtime 提供确定性的模型事件。"""

    def __init__(self, messages: list[AssistantMessage]):
        """用于处理init。"""
        self.messages = list(messages)
        self.calls = 0

    async def __call__(
        self,
        model: Model,
        context: AgentContext,
        options: SimpleStreamOptions,
    ) -> StreamResult:
        """返回 pi-agent-core 期望的 stream result。"""
        del model, context, options
        message = self.messages[self.calls]
        self.calls += 1
        events = self._events_for(message)

        async def events_iter():
            """按顺序返回预设模型事件。"""
            for event in events:
                yield event

        async def result():
            """返回当前预设 assistant message。"""
            return message

        return {"events": events_iter(), "result": result}

    @staticmethod
    def _events_for(message: AssistantMessage) -> list[Any]:
        """把一个完整 assistant message 转成流式事件。"""
        events: list[Any] = [StreamStartEvent(partial=message)]
        for index, block in enumerate(message.content):
            if isinstance(block, TextContent):
                events.extend(
                    [
                        StreamTextStartEvent(content_index=index, partial=message),
                        StreamTextDeltaEvent(
                            content_index=index,
                            delta=block.text,
                            partial=message,
                        ),
                        StreamTextEndEvent(
                            content_index=index,
                            content=block.text,
                            partial=message,
                        ),
                    ]
                )
            if isinstance(block, ToolCall):
                events.extend(
                    [
                        StreamToolCallStartEvent(
                            content_index=index,
                            partial=message,
                        ),
                        StreamToolCallEndEvent(
                            content_index=index,
                            tool_call=block,
                            partial=message,
                        ),
                    ]
                )
        events.append(StreamDoneEvent(reason=message.stop_reason, message=message))
        return events


def fake_pi_text(text: str) -> AssistantMessage:
    """构造 pi-agent-core 文本 assistant message。"""
    return AssistantMessage(content=[TextContent(text=text)], stop_reason="stop")


def fake_pi_tool_call(
    *,
    name: str,
    args: dict,
    call_id: str,
) -> AssistantMessage:
    """构造 pi-agent-core 工具调用 assistant message。"""
    return AssistantMessage(
        content=[ToolCall(id=call_id, name=name, arguments=args)],
        stop_reason="toolUse",
    )


def fake_pi_message(response: FakeModelResponse) -> AssistantMessage:
    """把测试响应转换为 pi-agent-core assistant message。"""
    if response.tool_calls:
        content: list[Any] = []
        for index, call in enumerate(response.tool_calls):
            raw_args = call.get("args")
            args = raw_args if isinstance(raw_args, dict) else {}
            content.append(
                ToolCall(
                    id=str(call.get("id") or f"call_{index}"),
                    name=str(call.get("name") or ""),
                    arguments=args,
                )
            )
        return AssistantMessage(
            content=content,
            stop_reason="toolUse",
        )
    return fake_pi_text(response.content)


def fake_tool_call(
    *,
    name: str,
    args: dict,
    call_id: str,
) -> dict:
    """用于构造toolcall。"""
    return {"name": name, "args": args, "id": call_id}


class ResumeAgentSmokeTests(unittest.IsolatedAsyncioTestCase):
    def _build_agent(self, responses):
        """用于构建Agent。"""
        agent = ResumeAgent()
        agent.runtime = PiAgentRuntime(
            stream_fn=FakePiAgentStream(
                [fake_pi_message(response) for response in responses]
            )
        )
        return agent

    def _sample_resume(self):
        """用于处理示例简历。"""
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
        """用于验证stripredundantfieldsremovesemptysummary。"""
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
        """用于验证stripredundantfieldsdropssummaryevenwhennonempty。"""
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
        """用于验证runtoolrejectshiddensection。"""
        agent = ResumeAgent()
        result = agent._run_tool(
            {
                "function": {
                    "name": "add_bullet",
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
        """用于验证updateoverviewtoolupdatesprojectoverview。"""
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
        """用于验证updateoverviewdefaultsmissingsectiontoprojects。"""
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
        """用于验证updateoverviewmissingitemidreturnsrecoverable错误。"""
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
        """用于验证invalidtoolargumentsjsonreturnsrecoverable错误。"""
        agent = ResumeAgent()
        resume = self._sample_resume()

        result = agent._run_tool(
            {
                "function": {
                    "name": "update_bullet",
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

    def test_update_bullet_tool_updates_single_highlight(self):
        """用于验证updatebullettoolupdatessinglehighlight。"""
        agent = ResumeAgent()
        resume = self._sample_resume()

        result = agent._run_tool(
            {
                "function": {
                    "name": "update_bullet",
                    "arguments": {
                        "section": "work_experience",
                        "item_id": "work_1",
                        "bullet_id": "hl_1",
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

    def test_add_bullet_tool_appends_highlight(self):
        """用于验证addbullettoolappendshighlight。"""
        agent = ResumeAgent()
        resume = self._sample_resume()

        result = agent._run_tool(
            {
                "function": {
                    "name": "add_bullet",
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

    def test_remove_bullet_tool_deletes_highlight(self):
        """用于验证removebullettooldeleteshighlight。"""
        agent = ResumeAgent()
        resume = self._sample_resume()

        result = agent._run_tool(
            {
                "function": {
                    "name": "remove_bullet",
                    "arguments": {
                        "section": "projects",
                        "item_id": "proj_1",
                        "bullet_id": "proj_hl_1",
                    },
                }
            },
            {"resume_content": resume},
        )

        self.assertTrue(result["result"]["success"])
        self.assertEqual(resume["projects"][0]["highlights"], [])

    async def test_optimize_returns_plain_text_without_mutation(self):
        """用于验证optimizereturnsplaintextwithoutmutation。"""
        agent = self._build_agent(
            [FakeModelResponse(content="我建议优先强化项目结果和量化指标。")]
        )
        resume = self._sample_resume()

        result = await agent.optimize("帮我看看这份简历怎么优化", resume)

        self.assertEqual(result["content"], "我建议优先强化项目结果和量化指标。")
        self.assertEqual(result["tool_calls"], [])
        self.assertEqual(resume["summary"]["text"], "3年 Python 后端开发经验")

    async def test_optimize_updates_resume_via_tool_call(self):
        """用于验证optimizeupdates简历viatoolcall。"""
        agent = self._build_agent(
            [
                FakeModelResponse(
                    content="",
                    tool_calls=[
                        fake_tool_call(
                            name="update_bullet",
                            call_id="call_1",
                            args={
                                "section": "work_experience",
                                "item_id": "work_1",
                                "bullet_id": "hl_1",
                                "text": "维护多个后台服务，并推动核心接口响应时间下降 30%",
                            },
                        )
                    ],
                ),
                FakeModelResponse(content="我已经把工作经历改成结果导向表达，并补了量化成果。"),
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

    async def test_optimize_executes_all_pi_agent_tool_calls(self):
        """用于验证optimizeexecutesallpiAgenttoolcalls。"""
        agent = self._build_agent(
            [
                FakeModelResponse(
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
                            name="add_bullet",
                            call_id="call_second",
                            args={
                                "section": "projects",
                                "item_id": "proj_1",
                                "text": "这条不应在同一轮被执行",
                            },
                        ),
                    ],
                ),
                FakeModelResponse(content="已先完成第一步修改。"),
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
        """用于验证optimizeretriesrecoverabletool错误。"""
        agent = self._build_agent(
            [
                FakeModelResponse(
                    content="",
                    tool_calls=[
                        fake_tool_call(
                            name="update_overview",
                            call_id="call_bad",
                            args={"section": "projects", "overview": "缺少 item_id"},
                        )
                    ],
                ),
                FakeModelResponse(
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
                FakeModelResponse(content="已根据工具错误修正参数并完成修改。"),
            ]
        )
        resume = self._sample_resume()

        result = await agent.optimize("优化项目简介", resume)

        self.assertEqual(len(result["tool_calls"]), 2)
        self.assertEqual(resume["projects"][0]["overview"], "重试后写入的简介")
        self.assertIn("修正参数", result["content"])

    async def test_optimize_stream_applies_change_after_confirmation(self):
        """用于验证optimizestreamapplieschangeafterconfirmation。"""
        agent = self._build_agent(
            [
                FakeModelResponse(
                    content="",
                    tool_calls=[
                        fake_tool_call(
                            name="update_bullet",
                            call_id="call_stream_1",
                            args={
                                "section": "work_experience",
                                "item_id": "work_1",
                                "bullet_id": "hl_1",
                                "text": (
                                    "维护多个后台服务，支撑日活 10 万用户，"
                                    "并完成接口性能优化"
                                ),
                            },
                        )
                    ],
                ),
                FakeModelResponse(content="已完成优化，重点突出系统规模和性能成果。"),
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
        visible_tool_events = [
            event for event in events if event.get("event_type") == "tool_call"
        ]
        self.assertEqual(len(visible_tool_events), 1)
        self.assertEqual(visible_tool_events[0]["tool_id"], "update_bullet")
        self.assertEqual(visible_tool_events[0]["call_id"], "call_stream_1")
        pending_events = [event for event in events if event.get("tool_pending")]
        confirmed_events = [event for event in events if event.get("tool_confirmed")]
        self.assertEqual(pending_events[0]["call_id"], "call_stream_1")
        self.assertEqual(confirmed_events[0]["call_id"], "call_stream_1")
        self.assertLess(
            events.index(visible_tool_events[0]),
            next(index for index, event in enumerate(events) if event.get("tool_pending")),
        )
        self.assertEqual(
            resume["work_experience"][0]["highlights"][0]["text"],
            "维护多个后台服务，支撑日活 10 万用户，并完成接口性能优化",
        )
        self.assertEqual(agent.runtime.stream_fn.calls, 1)

    async def test_optimize_stream_limits_first_round_to_one_business_confirmation(
        self,
    ):
        """用于验证optimizestream首轮只展示一个业务工具确认。"""
        agent = self._build_agent(
            [
                FakeModelResponse(
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
                            name="add_bullet",
                            call_id="call_stream_second",
                            args={
                                "section": "projects",
                                "item_id": "proj_1",
                                "text": "同一轮不应继续新增亮点",
                            },
                        ),
                    ],
                ),
                FakeModelResponse(content="已按顺序完成项目简介和项目亮点优化。"),
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
        self.assertEqual(len(pending_events), 1)
        self.assertEqual(len(confirmed_events), 1)
        self.assertEqual(resume["projects"][0]["overview"], "先优化项目简介")
        self.assertEqual(len(resume["projects"][0]["highlights"]), 1)
        self.assertEqual(
            resume["projects"][0]["highlights"][0]["text"],
            "支持流式简历优化",
        )
        self.assertEqual(agent.runtime.stream_fn.calls, 1)

    async def test_optimize_stream_allows_summary_tool_after_confirmed_change(self):
        """用于验证确认改动后同一工具批次仍可生成岗位匹配摘要。"""
        agent = self._build_agent(
            [
                FakeModelResponse(
                    content="",
                    tool_calls=[
                        fake_tool_call(
                            name="update_bullet",
                            call_id="call_stream_change",
                            args={
                                "section": "work_experience",
                                "item_id": "work_1",
                                "bullet_id": "hl_1",
                                "text": "维护 Agent 后端服务，支撑高并发 API",
                                "reason": "补充岗位关键词",
                            },
                        ),
                        fake_tool_call(
                            name="generate_job_match_summary",
                            call_id="call_stream_summary",
                            args={},
                        ),
                    ],
                ),
                FakeModelResponse(content="不应触发第二次模型回复。"),
            ]
        )
        resume = self._sample_resume()
        resume["job_application"] = {
            "jd_text": "要求 Agent、后端、API、高并发、Redis 经验。"
        }
        confirmation_queue = asyncio.Queue()
        confirmation_queue.put_nowait(True)

        events = []
        async for event in agent.optimize_stream(
            user_message="优化并说明岗位匹配情况",
            resume_content=resume,
            conversation_history=[],
            confirmation_queue=confirmation_queue,
        ):
            events.append(event)

        summary_events = [
            event
            for event in events
            if event.get("event_type") == "tool_result"
            and isinstance(event.get("result"), dict)
            and event["result"].get("job_match_summary")
        ]

        self.assertEqual(agent.runtime.stream_fn.calls, 1)
        self.assertEqual(len(summary_events), 1)
        summary = summary_events[0]["result"]["job_match_summary"]
        self.assertIn("Agent", summary["matched_keywords"])
        self.assertIn("Redis", summary["missing_keywords"])
        self.assertEqual(
            summary["resume_changes"],
            ["补充岗位关键词：维护 Agent 后端服务，支撑高并发 API"],
        )

    async def test_optimize_stream_reject_keeps_resume_unchanged(self):
        """用于验证optimizestreamrejectkeeps简历unchanged。"""
        agent = self._build_agent(
            [
                FakeModelResponse(
                    content="",
                    tool_calls=[
                        fake_tool_call(
                            name="update_bullet",
                            call_id="call_stream_2",
                            args={
                                "section": "work_experience",
                                "item_id": "work_1",
                                "bullet_id": "hl_1",
                                "text": "这是一个不应被应用的修改",
                            },
                        )
                    ],
                ),
                FakeModelResponse(content="我保留了原内容，等待你提供更具体的目标岗位。"),
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
        """用于验证optimizestreamemitstoolcallfailedthenrecovers。"""
        agent = self._build_agent(
            [
                FakeModelResponse(
                    content="",
                    tool_calls=[
                        fake_tool_call(
                            name="update_overview",
                            call_id="call_stream_bad",
                            args={"section": "projects", "overview": "缺少 item_id"},
                        )
                    ],
                ),
                FakeModelResponse(
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
                FakeModelResponse(content="已完成流式重试。"),
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

class ResumePiAgentRuntimeTests(unittest.IsolatedAsyncioTestCase):
    def _sample_resume(self):
        """用于处理示例简历。"""
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

    async def test_resume_agent_uses_pi_agent_runtime_by_default(self):
        """用于验证简历AgentusespiAgentruntimebydefault。"""
        agent = ResumeAgent()

        self.assertIsInstance(agent.runtime, PiAgentRuntime)

    async def test_pi_agent_runtime_stream_preserves_confirmation_flow(self):
        """用于验证piAgentruntimestreampreservesconfirmationflow。"""
        agent = ResumeAgent()
        agent.runtime = PiAgentRuntime(
            stream_fn=FakePiAgentStream(
                [
                    fake_pi_tool_call(
                        name="update_bullet",
                        args={
                            "section": "work_experience",
                            "item_id": "work_1",
                            "bullet_id": "hl_1",
                            "text": "维护多个后台服务，支撑日活 10 万用户",
                            "reason": "补充业务规模",
                        },
                        call_id="call_pi_1",
                    ),
                    fake_pi_text("已完成优化。"),
                ]
            )
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
            allowed_sections={"work_experience"},
        ):
            events.append(event)

        self.assertTrue(any(event.get("tool_pending") for event in events))
        self.assertTrue(any(event.get("tool_confirmed") for event in events))
        self.assertEqual(
            resume["work_experience"][0]["highlights"][0]["text"],
            "维护多个后台服务，支撑日活 10 万用户",
        )
        self.assertEqual(agent.runtime.stream_fn.calls, 1)

    async def test_pi_agent_runtime_stream_emits_agent_trace_logs(self):
        """用于验证piAgentruntimestreamemitsAgenttracelogs。"""
        agent = ResumeAgent()
        agent.runtime = PiAgentRuntime(
            stream_fn=FakePiAgentStream(
                [
                    fake_pi_tool_call(
                        name="update_bullet",
                        args={
                            "section": "work_experience",
                            "item_id": "work_1",
                            "bullet_id": "hl_1",
                            "text": "维护多个后台服务，支撑日活 10 万用户",
                            "reason": "补充业务规模",
                        },
                        call_id="call_pi_trace",
                    ),
                    fake_pi_text("已完成优化。"),
                ]
            )
        )
        resume = self._sample_resume()
        confirmation_queue = asyncio.Queue()
        confirmation_queue.put_nowait(True)

        original_trace_log_enabled = settings.AGENT_TRACE_LOG_ENABLED
        settings.AGENT_TRACE_LOG_ENABLED = True
        try:
            with self.assertLogs("app.runtime.pi_agent_runtime", level="INFO") as logs:
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
        self.assertEqual(agent.runtime.stream_fn.calls, 1)
        self.assertIn("agent.trace.run.started", trace_messages)
        self.assertIn("agent.trace.prompt.rendered", trace_messages)
        self.assertIn("agent.trace.llm.request", trace_messages)
        self.assertIn("agent.trace.reasoning.tool_call_detected", trace_messages)
        self.assertIn("agent.trace.tool.requested", trace_messages)
        self.assertIn("agent.trace.tool.preview", trace_messages)
        self.assertIn("agent.trace.tool.confirmation", trace_messages)
        self.assertIn("agent.trace.tool.executed", trace_messages)
        self.assertIn("agent.trace.llm.response", trace_messages)
        self.assertIn("agent.trace.run.stopped_after_confirmation", trace_messages)
        self.assertIn("agent.trace.run.completed", trace_messages)


class ChatServiceChunkParsingTests(unittest.TestCase):
    def test_extract_sse_data_accepts_data_prefix_without_space(self):
        """用于验证extractssedataacceptsdataprefixwithoutspace。"""
        self.assertEqual(
            ChatService._extract_sse_data('data:{"choices":[{"text":"ok"}]}'),
            '{"choices":[{"text":"ok"}]}',
        )

    def test_extract_stream_delta_accepts_message_content(self):
        """用于验证extractstreamdeltaacceptsmessagecontent。"""
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
        """用于验证extractstreamdeltaflattenscontentparts。"""
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
        """用于验证Agentruntimecompatibilityentrypointisremoved。"""
        import app.runtime as runtime

        self.assertNotIn("AgentRuntime", runtime.__all__)
        with self.assertRaises(AttributeError):
            getattr(runtime, "AgentRuntime")

    def test_agent_definition_lives_in_runtime_contracts(self):
        """用于验证Agentdefinitionlivesinruntimecontracts。"""
        from app.runtime.contracts import AgentDefinition

        agent = ResumeAgent()
        self.assertIsInstance(agent.definition, AgentDefinition)


if __name__ == "__main__":
    unittest.main()
