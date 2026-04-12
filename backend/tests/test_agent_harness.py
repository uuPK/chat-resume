import asyncio
import sys
import unittest
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.database import Base  # noqa: E402
from app.models import Resume, User  # noqa: E402
from app.agents.runtime.agent_harness import AgentHarness  # noqa: E402
from app.agents.state.agent_session_store import AgentSessionStore  # noqa: E402


class FakeResumeAgent:
    async def optimize_stream(
        self,
        user_message: str,
        resume_content: dict[str, Any],
        conversation_history: list[dict[str, str]],
        confirmation_queue: asyncio.Queue | None,
        allowed_sections: set[str],
    ):
        del user_message, conversation_history, confirmation_queue, allowed_sections
        yield {
            "content": "",
            "tool_pending": True,
            "call_id": "call_1",
            "tool_name": "优化简介",
            "diff_summary": "改前 A 改后 B",
        }
        yield {
            "content": "",
            "tool_confirmed": True,
            "call_id": "call_1",
            "tool_name": "优化简介",
            "resume_content": resume_content,
        }
        yield {"content": "已完成优化。", "resume_content": resume_content}


class AgentHarnessTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        self.db = self.SessionLocal()

        user = User(email="harness@example.com", hashed_password="hashed")
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

    async def test_resume_stream_records_session_events(self):
        harness = AgentHarness(self.db)
        store = AgentSessionStore(self.db)
        session_id = "harness_session_1"

        harness.create_resume_session(
            session_id=session_id,
            user_id=self.user.id,
            resume_id=self.resume.id,
            user_message="优化项目简介",
            visible_modules=["projects"],
        )

        events = []
        async for event in harness.run_resume_stream(
            session_id=session_id,
            agent=FakeResumeAgent(),  # type: ignore[arg-type]
            user_message="优化项目简介",
            resume_content={"projects": []},
            conversation_history=[],
            confirmation_queue=None,
            allowed_sections={"projects"},
        ):
            events.append(event)

        self.assertEqual(len(events), 3)
        session = store.get_session(session_id)
        self.assertIsNotNone(session)
        self.assertEqual(session.status, "completed")

        event_types = [event.event_type for event in store.list_events(session_id)]
        self.assertEqual(
            event_types,
            [
                "user_message",
                "tool_call_previewed",
                "tool_call_confirmed",
                "agent_response",
                "checkpoint_saved",
                "session_completed",
            ],
        )

    def test_resume_session_applies_confirmed_paused_tool_call(self):
        harness = AgentHarness(self.db)
        store = AgentSessionStore(self.db)
        session_id = "resume_paused_session"
        resume = {
            "projects": [
                {
                    "id": "proj_1",
                    "name": "Chat Resume",
                    "overview": "旧简介",
                }
            ]
        }

        harness.create_resume_session(
            session_id=session_id,
            user_id=self.user.id,
            resume_id=self.resume.id,
            user_message="优化项目简介",
            visible_modules=["projects"],
        )
        store.update_status(session_id, "waiting_confirmation", current_step="call_1")
        store.append_event(
            session_id=session_id,
            event_type="tool_call_previewed",
            source="resume_agent",
            payload={
                "call_id": "call_1",
                "tool_name": "优化简介",
                "tool_call": {
                    "id": "call_1",
                    "type": "function",
                    "function": {
                        "name": "update_overview",
                        "arguments": {
                            "section": "projects",
                            "item_id": "proj_1",
                            "overview": "恢复后的简介",
                        },
                    },
                },
            },
        )
        store.append_confirmation_event(
            session_id=session_id,
            call_id="call_1",
            confirmed=True,
            tool_name="优化简介",
            active_stream=False,
        )
        store.update_status(session_id, "paused", current_step="call_1")

        result = harness.resume_session(
            session_id=session_id,
            resume_content=resume,
            allowed_sections={"projects"},
        )

        self.assertTrue(result["success"])
        self.assertTrue(result["applied"])
        self.assertEqual(resume["projects"][0]["overview"], "恢复后的简介")
        self.assertEqual(store.get_session(session_id).status, "completed")
        self.assertEqual(
            store.get_latest_event(session_id).event_type,
            "session_completed",
        )
