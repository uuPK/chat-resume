import sys
import tempfile
import unittest
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.agents.resume.executor import ResumeToolExecutor  # noqa: E402
from app.infra.config import settings  # noqa: E402
from app.services.memory import UserMemoryService  # noqa: E402


class ResumeToolExecutorTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_user_memory_dir = settings.USER_MEMORY_DIR
        settings.USER_MEMORY_DIR = self.temp_dir.name

    def tearDown(self):
        settings.USER_MEMORY_DIR = self.original_user_memory_dir
        self.temp_dir.cleanup()

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

    def test_read_user_memory_returns_default_template_for_new_user(self):
        executor = ResumeToolExecutor()

        result = executor.execute(
            tool_name="read_user_memory",
            tool_input={},
            context={"resume_content": {}, "user_id": 101},
        )

        self.assertTrue(result["result"]["success"])
        self.assertFalse(result["result"]["exists"])
        self.assertIn("# 长期记忆", result["result"]["content"])
        self.assertEqual(result["requires_confirmation"], False)

    def test_write_user_memory_persists_markdown_for_bound_user(self):
        executor = ResumeToolExecutor()
        content = "# 长期记忆\n\n## 写作偏好\n- 不要夸大经历\n"

        result = executor.execute(
            tool_name="write_user_memory",
            tool_input={"content": content},
            context={"resume_content": {}, "user_id": 202},
        )

        self.assertTrue(result["result"]["success"])
        self.assertIn("不要夸大经历", result["result"]["content"])
        stored = UserMemoryService().read_memory(202)
        self.assertTrue(stored["exists"])
        self.assertIn("不要夸大经历", stored["content"])
        self.assertEqual(result["requires_confirmation"], False)
