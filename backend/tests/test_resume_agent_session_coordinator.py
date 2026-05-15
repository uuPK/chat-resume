"""用于覆盖简历 Agent 会话协调器的持久化边界。"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.infra.database import Base  # noqa: E402
from app.models import Resume, User  # noqa: E402
from app.services.agent.resume_agent_session_coordinator import (  # noqa: E402
    ResumeAgentSessionCoordinator,
    ResumeAgentStreamInput,
)
from app.state.store import AgentSessionStore  # noqa: E402


class ResumeAgentSessionCoordinatorTests(unittest.TestCase):
    """用于验证简历 Agent 会话模块的公开接口。"""

    def setUp(self):
        """用于准备测试数据库和简历。"""
        engine = create_engine(
            "sqlite:///:memory:", connect_args={"check_same_thread": False}
        )
        Base.metadata.create_all(bind=engine)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        self.db = self.SessionLocal()

        user = User(email="coordinator@example.com", hashed_password="hashed")
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        self.user = user

        resume = Resume(
            title="协调器简历",
            owner_id=user.id,
            content={
                "projects": [
                    {
                        "id": "proj_1",
                        "name": "Chat Resume",
                        "overview": "旧简介",
                    }
                ],
                "skills": ["Python"],
            },
        )
        self.db.add(resume)
        self.db.commit()
        self.db.refresh(resume)
        self.resume = resume

    def tearDown(self):
        """用于关闭测试数据库连接。"""
        self.db.close()

    def test_prepare_stream_session_creates_context_and_session(self):
        """用于验证会话模块创建可运行上下文并记录用户消息。"""
        coordinator = ResumeAgentSessionCoordinator(self.db)
        request = ResumeAgentStreamInput(
            message="复述当前简历",
            resume_id=self.resume.id,
            user_id=self.user.id,
            request_id="req_prepare",
            chat_history=[{"role": "assistant", "content": "旧上下文"}],
            visible_modules=["projects"],
        )

        context = coordinator.prepare_stream_session(
            request=request,
            session_id="coordinator_stream",
        )

        assert context.session_id == "coordinator_stream"
        assert context.resume_content == {
            "projects": [
                {
                    "id": "proj_1",
                    "name": "Chat Resume",
                    "overview": "旧简介",
                }
            ]
        }
        assert context.conversation_history == []
        store = AgentSessionStore(self.db)
        session = store.get_session("coordinator_stream")
        assert session is not None
        assert session.status == "running"
        assert store.get_latest_event("coordinator_stream").event_type == "user_message"

    def test_public_events_are_recorded_and_replayed_after_cursor(self):
        """用于验证公开 SSE 事件由会话模块统一分配 cursor。"""
        coordinator = ResumeAgentSessionCoordinator(self.db)
        store = AgentSessionStore(self.db)
        store.create_session(
            session_id="coordinator_replay",
            user_id=self.user.id,
            resume_id=self.resume.id,
            task_type="resume_optimization",
        )

        first = coordinator.record_public_event(
            store=store,
            session_id="coordinator_replay",
            event={"session_id": "coordinator_replay"},
        )
        second = coordinator.record_public_event(
            store=store,
            session_id="coordinator_replay",
            event={"content": "断线后补发"},
        )

        replayed = coordinator.replay_public_events(
            session_id="coordinator_replay",
            user_id=self.user.id,
            after_sequence=int(first["event_id"].rsplit(":", 1)[1]),
        )

        assert second["event_id"].startswith("coordinator_replay:")
        assert replayed == [second]

    def test_resume_paused_session_applies_tool_and_persists_resume(self):
        """用于验证 paused 工具确认可恢复执行并落库。"""
        coordinator = ResumeAgentSessionCoordinator(self.db)
        store = AgentSessionStore(self.db)
        store.create_session(
            session_id="coordinator_resume",
            user_id=self.user.id,
            resume_id=self.resume.id,
            task_type="resume_optimization",
            metadata={"visible_modules": ["projects"]},
        )
        store.update_status("coordinator_resume", "waiting_confirmation", current_step="call_1")
        store.append_event(
            session_id="coordinator_resume",
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
                            "overview": "恢复后的新简介",
                        },
                    },
                },
            },
        )
        store.append_confirmation_event(
            session_id="coordinator_resume",
            call_id="call_1",
            confirmed=True,
            tool_name="优化简介",
            active_stream=False,
        )
        store.update_status("coordinator_resume", "paused", current_step="call_1")

        result = coordinator.resume_paused_session(
            session_id="coordinator_resume",
            user_id=self.user.id,
        )

        assert result["ok"] is True
        assert result["applied"] is True
        self.db.refresh(self.resume)
        assert self.resume.content["projects"][0]["overview"] == "恢复后的新简介"
        assert store.get_session("coordinator_resume").status == "completed"


if __name__ == "__main__":
    unittest.main()
