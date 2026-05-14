"""用于覆盖 test_agent_session_store.py 对应的回归测试。"""

import sys
import unittest
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.infra.database import Base  # noqa: E402
from app.infra.request_context import log_context  # noqa: E402
from app.models import Resume, User  # noqa: E402
from app.state.store import AgentSessionStore  # noqa: E402


class AgentSessionStoreTests(unittest.TestCase):
    def setUp(self):
        """用于准备测试前置状态。"""
        engine = create_engine(
            "sqlite:///:memory:", connect_args={"check_same_thread": False}
        )
        Base.metadata.create_all(bind=engine)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        self.db = self.SessionLocal()

        user = User(email="agent@example.com", hashed_password="hashed")
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        self.user = user

        resume = Resume(title="测试简历", content={}, owner_id=user.id)
        self.db.add(resume)
        self.db.commit()
        self.db.refresh(resume)
        self.resume = resume

    def tearDown(self):
        """用于清理测试后置状态。"""
        self.db.close()

    def test_create_session_append_events_and_update_status(self):
        """用于验证create会话append事件andupdate状态。"""
        store = AgentSessionStore(self.db)

        session = store.create_session(
            session_id="session_1",
            user_id=self.user.id,
            resume_id=self.resume.id,
            task_type="resume_optimization",
            metadata={"visible_modules": ["projects"]},
        )

        self.assertEqual(session.status, "created")
        self.assertEqual(session.metadata_json["visible_modules"], ["projects"])

        first = store.append_event(
            session_id=session.id,
            event_type="user_message",
            source="user",
            payload={"content": "优化项目经历"},
        )
        second = store.append_event(
            session_id=session.id,
            event_type="tool_call_failed",
            source="resume_agent",
            payload={"error_type": "missing_required_argument"},
        )

        self.assertEqual(first.sequence, 1)
        self.assertEqual(second.sequence, 2)

        events = store.list_events(session.id)
        self.assertEqual(
            [event.event_type for event in events], ["user_message", "tool_call_failed"]
        )

        updated = store.update_status(
            session.id,
            "failed",
            current_step="tool_call",
            failed_reason="参数缺失",
        )

        self.assertIsNotNone(updated)
        self.assertEqual(updated.status, "failed")
        self.assertEqual(updated.current_step, "tool_call")
        self.assertEqual(updated.failed_reason, "参数缺失")
        self.assertIsNotNone(updated.completed_at)

    def test_session_and_events_capture_observability_context(self):
        """用于验证会话and事件capture可观测性上下文。"""
        store = AgentSessionStore(self.db)

        with log_context(
            request_id="req_test_123",
            session_id="session_ctx",
            tool_call_id="tool_ctx",
        ):
            session = store.create_session(
                session_id="session_ctx",
                user_id=self.user.id,
                resume_id=self.resume.id,
                task_type="resume_optimization",
                metadata={"visible_modules": ["projects"]},
            )
            event = store.append_event(
                session_id=session.id,
                event_type="tool_call_finished",
                source="resume_agent",
                payload={"result": {"success": True}},
            )

        session_observability = session.metadata_json["observability"]
        self.assertEqual(session_observability["request_id"], "req_test_123")
        self.assertEqual(session_observability["session_id"], "session_ctx")

        event_observability = event.payload["observability"]
        self.assertEqual(event_observability["request_id"], "req_test_123")
        self.assertEqual(event_observability["session_id"], "session_ctx")
        self.assertEqual(event_observability["tool_call_id"], "tool_ctx")

    def test_stream_events_can_be_replayed_after_cursor(self):
        """用于验证stream事件可按cursor回放。"""
        store = AgentSessionStore(self.db)
        session = store.create_session(
            session_id="stream_cursor_session",
            user_id=self.user.id,
            resume_id=self.resume.id,
            task_type="resume_optimization",
        )

        first = store.append_stream_event(
            session_id=session.id,
            payload={"session_id": session.id},
        )
        store.append_event(
            session_id=session.id,
            event_type="tool_call_previewed",
            source="resume_agent",
            payload={"call_id": "call_1"},
        )
        second = store.append_stream_event(
            session_id=session.id,
            payload={"content": "继续输出"},
        )

        replayed = store.list_stream_events(session.id, after_sequence=first.sequence)

        self.assertEqual([event.sequence for event in replayed], [second.sequence])
        self.assertEqual(replayed[0].payload["content"], "继续输出")
