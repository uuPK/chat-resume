import sys
import unittest
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.agents.resume.executor import ResumeToolExecutor  # noqa: E402


class ResumeToolExecutorTests(unittest.TestCase):
    def test_execute_wraps_success_result(self):
        resume = {
            "projects": [{"id": "proj_1", "name": "Chat Resume", "overview": "旧简介"}]
        }
        executor = ResumeToolExecutor()

        result = executor.execute(
            tool_name="update_overview",
            tool_input={
                "section": "projects",
                "item_id": "proj_1",
                "overview": "新简介",
            },
            context={"resume_content": resume, "allowed_sections": {"projects"}},
        )

        self.assertTrue(result["result"]["success"])
        self.assertEqual(result["tool_name"], "优化简介")
        self.assertEqual(resume["projects"][0]["overview"], "新简介")

    def test_execute_returns_structured_hidden_section_error(self):
        executor = ResumeToolExecutor()

        result = executor.execute(
            tool_name="add_highlight",
            tool_input={
                "section": "projects",
                "item_id": "proj_1",
                "text": "新增成果",
            },
            context={
                "resume_content": {"projects": []},
                "allowed_sections": {"skills"},
            },
        )

        self.assertFalse(result["result"]["success"])
        self.assertEqual(result["result"]["error"]["type"], "hidden_section")
        self.assertFalse(result["result"]["error"]["recoverable"])
