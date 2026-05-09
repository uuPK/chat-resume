import sys
import unittest
from pathlib import Path

from jinja2 import Template

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.agents.resume.agent import ResumeAgent  # noqa: E402
from app.agents.resume.stream_events import (  # noqa: E402
    normalize_resume_stream_payload,
    tool_pending_event,
)
from app.tools.resume.registry import RESUME_TOOLS_SCHEMA  # noqa: E402
from app.tools.resume.update_highlight_tool import update_highlight  # noqa: E402


class ResumeAgentPromptContextTests(unittest.TestCase):
    def test_prompt_context_includes_job_application_fields(self):
        agent = ResumeAgent()
        context = agent._build_prompt_context(
            {
                "resume_content": {
                    "job_application": {
                        "target_title": "前端工程师",
                        "target_company": "字节跳动",
                        "jd_text": "负责复杂前端交互、性能优化和工程化建设",
                    },
                    "projects": [],
                }
            }
        )

        self.assertEqual(context["target_title"], "前端工程师")
        self.assertEqual(context["target_company"], "字节跳动")
        self.assertIn("性能优化", context["jd_text"])
        self.assertIn('"job_application"', context["resume_json"])

    def test_resume_tools_schema_exposes_optional_reason_field(self):
        schema = RESUME_TOOLS_SCHEMA
        update_highlight = next(
            tool for tool in schema if tool["function"]["name"] == "update_highlight"
        )

        properties = update_highlight["function"]["parameters"]["properties"]
        self.assertIn("reason", properties)
        self.assertEqual(properties["reason"]["type"], "string")

    def test_resume_tools_schema_exposes_user_memory_tools(self):
        tool_names = {tool["function"]["name"] for tool in RESUME_TOOLS_SCHEMA}

        self.assertIn("read_user_memory", tool_names)
        self.assertIn("write_user_memory", tool_names)

    def test_resume_tool_result_includes_structured_diff_reason(self):
        resume_content = {
            "projects": [
                {
                    "id": "proj_1",
                    "name": "Chat Resume",
                    "highlights": [
                        {"id": "hl_1", "text": "负责前端开发"},
                    ],
                }
            ]
        }

        result = update_highlight(
            resume_content,
            section="projects",
            item_id="proj_1",
            highlight_id="hl_1",
            text="主导前端重构，首屏加载提速 35%",
            reason="补充量化结果",
        )

        self.assertTrue(result["success"])
        self.assertIn("改动理由：补充量化结果", result["diff_summary"])
        self.assertEqual(result["diff_items"][0]["reason"], "补充量化结果")
        self.assertIn("35%", result["diff_items"][0]["after"])

    def test_resume_stream_event_contract_keeps_structured_diff(self):
        event = tool_pending_event(
            call_id="call_1",
            tool_id="update_highlight",
            tool_call={
                "id": "call_1",
                "type": "function",
                "function": {"name": "update_highlight", "arguments": {}},
            },
            tool_display_name="优化成果",
            tool_input={"section": "projects"},
            diff_summary="旧文本 diff",
            diff_items=[
                {
                    "before": "负责前端开发",
                    "after": "主导前端重构，首屏加载提速 35%",
                    "reason": "补充量化结果",
                }
            ],
            tool_calls=[],
        )

        self.assertEqual(event["event_type"], "tool_pending")
        self.assertTrue(event["tool_pending"])
        self.assertEqual(event["tool_id"], "update_highlight")
        self.assertEqual(event["tool_display_name"], "优化成果")
        self.assertEqual(event["tool_name"], "优化成果")
        self.assertEqual(event["diff_items"][0]["reason"], "补充量化结果")

    def test_resume_stream_event_normalizes_legacy_payload(self):
        event = normalize_resume_stream_payload(
            {
                "tool_pending": True,
                "call_id": "call_1",
                "tool_call": {
                    "function": {
                        "name": "update_highlight",
                    }
                },
                "tool_name": "优化成果",
                "diff_items": [{"before": "A", "after": "B", "reason": 123}],
            }
        )

        self.assertEqual(event["event_type"], "tool_pending")
        self.assertEqual(event["tool_id"], "update_highlight")
        self.assertEqual(event["tool_display_name"], "优化成果")
        self.assertEqual(event["diff_items"][0]["reason"], "123")

    def test_system_prompt_includes_quantified_rewrite_guidance(self):
        prompt_path = BACKEND_DIR / "app" / "prompts" / "resume_agent" / "system.md"
        template = Template(prompt_path.read_text(encoding="utf-8"))
        rendered = template.render(
            target_title="前端工程师",
            target_company="字节跳动",
            jd_text="负责复杂前端交互与性能优化",
            resume_json="{}",
        )

        self.assertIn("量化改写优先级", rendered)
        self.assertIn("做成了什么、影响了什么、提升了多少", rendered)
        self.assertIn("不允许编造不存在的数字", rendered)

    def test_system_prompt_includes_memory_tool_guidance(self):
        prompt_path = BACKEND_DIR / "app" / "prompts" / "resume_agent" / "system.md"
        template = Template(prompt_path.read_text(encoding="utf-8"))
        rendered = template.render(
            target_title="AI Agent 开发工程师",
            target_company="腾讯",
            jd_text="负责 Agent 产品能力建设",
            resume_json="{}",
        )

        self.assertIn("read_user_memory", rendered)
        self.assertIn("write_user_memory", rendered)
        self.assertIn("长期记忆只记录稳定信息", rendered)

    def test_system_prompt_enforces_optimize_first_default(self):
        prompt_path = BACKEND_DIR / "app" / "prompts" / "resume_agent" / "system.md"
        template = Template(prompt_path.read_text(encoding="utf-8"))
        rendered = template.render(
            target_title="产品经理",
            target_company="美团",
            jd_text="负责策略优化与跨团队协同",
            resume_json='{"work_experience": [{"id": "work_1", "highlights": []}]}',
        )

        self.assertIn("默认执行 `optimize-first`", rendered)
        self.assertIn("必须直接调用工具产出改动", rendered)
        self.assertIn("首轮目标是“先产出改动”", rendered)

    def test_system_prompt_limits_follow_up_to_defined_exception_cases(self):
        prompt_path = BACKEND_DIR / "app" / "prompts" / "resume_agent" / "system.md"
        template = Template(prompt_path.read_text(encoding="utf-8"))
        rendered = template.render(
            target_title="运营",
            target_company="小红书",
            jd_text="负责活动运营与增长分析",
            resume_json='{"projects": [{"id": "proj_1", "highlights": []}]}',
        )

        self.assertIn("缺输入", rendered)
        self.assertIn("高风险", rendered)
        self.assertIn("指令冲突", rendered)
        self.assertIn("追问必须短、具体、单轮可答", rendered)
        self.assertIn("禁止泛泛地问“要不要我帮你优化”", rendered)

    def test_system_prompt_explicitly_blocks_high_risk_fabrication_requests(self):
        prompt_path = BACKEND_DIR / "app" / "prompts" / "resume_agent" / "system.md"
        template = Template(prompt_path.read_text(encoding="utf-8"))
        rendered = template.render(
            target_title="高级后端工程师",
            target_company="字节跳动",
            jd_text="负责高并发系统设计与稳定性建设",
            resume_json='{"work_experience": [{"id": "work_1", "highlights": []}]}',
        )

        self.assertIn("补一些我没做过的项目", rendered)
        self.assertIn("假装更多年限", rendered)
        self.assertIn("我不能编造你没做过的项目或虚构年限", rendered)
        self.assertIn("不能直接调用工具", rendered)


if __name__ == "__main__":
    unittest.main()
