import sys
import unittest
from datetime import datetime
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.api.endpoints.interview import (  # noqa: E402
    _build_session_response,
    _normalize_turns,
    _safe_json_loads,
)
from app.models.resume import InterviewSession  # noqa: E402


class InterviewTurnNormalizationTests(unittest.TestCase):
    def _session(self, questions, answers):
        session = InterviewSession(
            id=1,
            resume_id=99,
            job_position="后端工程师",
            jd_content="负责 Python 后端服务开发",
            questions=questions,
            answers=answers,
            feedback={"mode": "structured_interview", "plan": {"max_turns": 5}},
            status="active",
            overall_score=None,
        )
        session.created_at = datetime(2026, 4, 9)
        session.updated_at = datetime(2026, 4, 9)
        return session

    def test_normalize_legacy_question_answer_records(self):
        session = self._session(
            questions=[{"question": "请介绍一个你负责的项目", "type": "experience"}],
            answers=[
                {
                    "answer": "我负责了一个推荐系统后台服务。",
                    "evaluation": {"score": 8, "feedback": "不错", "improvements": []},
                }
            ],
        )

        turns = _normalize_turns(session)

        self.assertEqual(len(turns), 1)
        self.assertEqual(turns[0]["question"], "请介绍一个你负责的项目")
        self.assertEqual(turns[0]["answer"], "我负责了一个推荐系统后台服务。")
        self.assertEqual(turns[0]["score"], 8)
        self.assertEqual(turns[0]["status"], "answered")

    def test_build_session_response_exposes_current_turn(self):
        session = self._session(
            questions=[
                {
                    "turn_index": 0,
                    "question": "请做一个自我介绍",
                    "question_type": "opening",
                    "status": "answered",
                    "answer": "我有 4 年后端经验",
                    "evaluation": {"score": 8, "feedback": "不错", "improvements": []},
                    "score": 8,
                },
                {
                    "turn_index": 1,
                    "question": "请介绍一个最有挑战的项目",
                    "question_type": "experience",
                    "status": "asked",
                },
            ],
            answers=[
                {
                    "answer": "我有 4 年后端经验",
                    "question_index": 0,
                    "evaluation": {"score": 8, "feedback": "不错", "improvements": []},
                    "score": 8,
                }
            ],
        )

        response = _build_session_response(session, "测试简历")

        self.assertEqual(response.total_questions, 2)
        self.assertEqual(response.answered_questions, 1)
        self.assertIsNotNone(response.current_turn)
        self.assertEqual(response.current_turn.turn_index, 1)
        self.assertEqual(response.current_turn.question, "请介绍一个最有挑战的项目")

    def test_safe_json_loads_accepts_fenced_json(self):
        payload = """```json
{
  "score": 7,
  "feedback": "回答基本合格",
  "improvements": ["补充细节", "加强量化"]
}
```"""

        parsed = _safe_json_loads(payload)

        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["score"], 7)
        self.assertEqual(parsed["feedback"], "回答基本合格")


if __name__ == "__main__":
    unittest.main()
