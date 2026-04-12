import sys
import unittest
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.infra.database import Base  # noqa: E402
from app.models import AgentEvent, AgentSession, Resume, User  # noqa: E402
from app.agents.state.agent_session_store import AgentSessionStore  # noqa: E402


class AgentSessionStoreTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
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
        self.db.close()

    def test_create_session_append_events_and_update_status(self):
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
        self.assertEqual([event.event_type for event in events], ["user_message", "tool_call_failed"])

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
