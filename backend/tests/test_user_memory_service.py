import sys
import tempfile
import unittest
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.memory import UserMemoryService  # noqa: E402


class UserMemoryServiceTests(unittest.TestCase):
    def test_read_and_write_are_isolated_per_user(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            service = UserMemoryService(base_dir=temp_dir)

            initial = service.read_memory(1)
            self.assertFalse(initial["exists"])
            self.assertIn("# 长期记忆", initial["content"])

            service.write_memory(1, "## 写作偏好\n- 结果导向")
            user_one = service.read_memory(1)
            user_two = service.read_memory(2)

            self.assertTrue(user_one["exists"])
            self.assertIn("结果导向", user_one["content"])
            self.assertFalse(user_two["exists"])
            self.assertNotIn("结果导向", user_two["content"])
