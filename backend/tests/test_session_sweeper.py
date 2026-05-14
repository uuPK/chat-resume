"""用于覆盖 session_sweeper 的回归测试。"""

import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.infra.database import Base  # noqa: E402
from app.models import Resume, User  # noqa: E402
from app.runtime.session_sweeper import sweep_timed_out_sessions  # noqa: E402
from app.state.store import AgentSessionStore  # noqa: E402


class SessionSweeperTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        """用于准备测试前置状态。"""
        engine = create_engine(
            "sqlite:///:memory:", connect_args={"check_same_thread": False}
        )
        Base.metadata.create_all(bind=engine)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        db = self.SessionLocal()

        user = User(email="sweeper@example.com", hashed_password="hashed")
        db.add(user)
        db.commit()
        db.refresh(user)
        self.user_id = user.id

        resume = Resume(title="测试简历", content={}, owner_id=user.id)
        db.add(resume)
        db.commit()
        db.refresh(resume)
        self.resume_id = resume.id
        db.close()

    def _make_store(self):
        """用于为每次测试创建独立的 store 实例。"""
        db = self.SessionLocal()
        return AgentSessionStore(db), db

    def _create_paused_session(self, session_id: str, updated_at: datetime) -> None:
        """用于创建一个已 paused 且 updated_at 指定时间的 session。"""
        store, db = self._make_store()
        store.create_session(
            session_id=session_id,
            user_id=self.user_id,
            resume_id=self.resume_id,
            task_type="resume_optimization",
        )
        store.update_status(session_id, "paused")
        # 直接修改 updated_at 绕过 onupdate 约束
        from app.state.models import AgentSession
        db.query(AgentSession).filter(AgentSession.id == session_id).update(
            {"updated_at": updated_at}
        )
        db.commit()
        db.close()

    async def test_timed_out_paused_session_becomes_failed(self):
        """paused session 超时后 sweep 应将其状态改为 failed。"""
        old_time = datetime.now(timezone.utc) - timedelta(seconds=700)
        self._create_paused_session("s_timeout", old_time)

        count = await sweep_timed_out_sessions(self.SessionLocal, timeout_seconds=600)

        self.assertEqual(count, 1)
        store, db = self._make_store()
        session = store.get_session("s_timeout")
        self.assertEqual(session.status, "failed")
        self.assertEqual(session.failed_reason, "confirmation_timeout")
        latest_event = store.get_latest_event("s_timeout")
        self.assertEqual(latest_event.event_type, "session_timed_out")
        db.close()

    async def test_paused_session_not_timed_out_is_left_alone(self):
        """paused session 未超时时 sweep 不应处理。"""
        recent_time = datetime.now(timezone.utc) - timedelta(seconds=100)
        self._create_paused_session("s_recent", recent_time)

        count = await sweep_timed_out_sessions(self.SessionLocal, timeout_seconds=600)

        self.assertEqual(count, 0)
        store, db = self._make_store()
        session = store.get_session("s_recent")
        self.assertEqual(session.status, "paused")
        db.close()

    async def test_non_paused_sessions_are_ignored(self):
        """running/completed 状态的 session 不应被 sweep 处理。"""
        store, db = self._make_store()
        store.create_session(
            session_id="s_running",
            user_id=self.user_id,
            resume_id=self.resume_id,
            task_type="resume_optimization",
        )
        store.update_status("s_running", "running")
        store.create_session(
            session_id="s_completed",
            user_id=self.user_id,
            resume_id=self.resume_id,
            task_type="resume_optimization",
        )
        store.update_status("s_completed", "completed")
        db.close()

        count = await sweep_timed_out_sessions(self.SessionLocal, timeout_seconds=600)

        self.assertEqual(count, 0)

    async def test_sweep_returns_correct_count(self):
        """sweep 返回的数量应等于实际处理的超时 session 数。"""
        old_time = datetime.now(timezone.utc) - timedelta(seconds=700)
        self._create_paused_session("s_batch_1", old_time)
        self._create_paused_session("s_batch_2", old_time)

        recent_time = datetime.now(timezone.utc) - timedelta(seconds=100)
        self._create_paused_session("s_batch_recent", recent_time)

        count = await sweep_timed_out_sessions(self.SessionLocal, timeout_seconds=600)

        self.assertEqual(count, 2)


if __name__ == "__main__":
    unittest.main()
