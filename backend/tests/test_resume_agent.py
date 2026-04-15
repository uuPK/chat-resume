import sys
import unittest
from pathlib import Path
from jinja2 import Template


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.agents.definitions.resume_agent import ResumeAgent  # noqa: E402
from app.agents.tools.resume_tools import ResumeTools  # noqa: E402


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
        schema = ResumeTools.get_tools_schema()
        update_highlight = next(
            tool for tool in schema if tool["function"]["name"] == "update_highlight"
        )

        properties = update_highlight["function"]["parameters"]["properties"]
        self.assertIn("reason", properties)
        self.assertEqual(properties["reason"]["type"], "string")

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

        result = ResumeTools.update_highlight(
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

    def test_system_prompt_includes_quantified_rewrite_guidance(self):
        prompt_path = (
            BACKEND_DIR / "app" / "prompts" / "resume_agent" / "system.md"
        )
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


if __name__ == "__main__":
    unittest.main()
