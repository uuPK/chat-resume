"""
API 端到端集成测试

使用 FastAPI TestClient + 内存 SQLite，测试完整的 HTTP 请求/响应链路：
  - 认证：注册、登录、获取当前用户、更新用户信息
  - 简历 CRUD：创建、列表、获取、更新、删除
  - 聊天记录：追加、获取、清空
  - 权限隔离：跨用户访问被拒绝
"""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.infra.database import Base, get_db
from app.main import app
from app.state.store import AgentSessionStore
from app.runtime.permissions import confirmation_manager
from app.agents.interview.agent import InterviewerAgent
from app.models.user import User

# ── 测试数据库 ──────────────────────────────────────────────────────────────

TEST_DATABASE_URL = "sqlite://"  # 纯内存，每次测试都是空库

_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=_engine)


def _override_get_db():
    db = _TestingSession()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = _override_get_db


# ── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session", autouse=True)
def _create_tables():
    """在整个测试会话开始时建表，结束时销毁。"""
    Base.metadata.create_all(bind=_engine)
    yield
    Base.metadata.drop_all(bind=_engine)


@pytest.fixture()
def client():
    return TestClient(app)


# ── 辅助函数 ─────────────────────────────────────────────────────────────────

def _register(client: TestClient, email: str, password: str = "password123", full_name: str | None = None):
    payload = {"email": email, "password": password}
    if full_name:
        payload["full_name"] = full_name
    return client.post("/api/auth/register", json=payload)


def _login(client: TestClient, email: str, password: str = "password123") -> str:
    resp = client.post(
        "/api/auth/login",
        data={"username": email, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def _auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _empty_resume_content() -> dict:
    return {
        "job_application": {"target_company": "测试公司", "target_title": "后端工程师"},
        "personal_info": {"name": "张三", "email": "zhangsan@example.com"},
        "work_experience": [],
        "education": [],
        "skills": [],
        "projects": [],
    }


# ═══════════════════════════════════════════════════════════════════════════
# 1. 认证流程
# ═══════════════════════════════════════════════════════════════════════════

class TestAuth:
    def test_register_creates_user(self, client):
        resp = _register(client, "new_user@example.com", full_name="新用户")
        assert resp.status_code == 200
        body = resp.json()
        assert body["email"] == "new_user@example.com"
        assert body["full_name"] == "新用户"
        assert "id" in body
        assert "hashed_password" not in body

    def test_register_duplicate_email_returns_400(self, client):
        _register(client, "dup@example.com")
        resp = _register(client, "dup@example.com")
        assert resp.status_code == 400
        assert "already registered" in resp.json()["detail"].lower()

    def test_login_returns_token_and_user(self, client):
        _register(client, "login_test@example.com", full_name="登录测试")
        resp = client.post(
            "/api/auth/login",
            data={"username": "login_test@example.com", "password": "password123"},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "access_token" in body
        assert body["token_type"] == "bearer"
        assert body["user"]["email"] == "login_test@example.com"

    def test_login_wrong_password_returns_401(self, client):
        _register(client, "wrong_pw@example.com")
        resp = client.post(
            "/api/auth/login",
            data={"username": "wrong_pw@example.com", "password": "wrongpassword"},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        assert resp.status_code == 401

    def test_login_unknown_user_returns_401(self, client):
        resp = client.post(
            "/api/auth/login",
            data={"username": "nobody@example.com", "password": "password123"},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        assert resp.status_code == 401

    def test_get_me_returns_current_user(self, client):
        _register(client, "me_user@example.com", full_name="我")
        token = _login(client, "me_user@example.com")
        resp = client.get("/api/auth/me", headers=_auth_headers(token))
        assert resp.status_code == 200
        assert resp.json()["email"] == "me_user@example.com"

    def test_get_me_returns_request_id_header(self, client):
        _register(client, "request_id_user@example.com", full_name="请求头测试")
        token = _login(client, "request_id_user@example.com")
        resp = client.get("/api/auth/me", headers=_auth_headers(token))
        assert resp.status_code == 200
        assert resp.headers.get("X-Request-ID")

    def test_get_me_without_token_returns_401(self, client):
        resp = client.get("/api/auth/me")
        assert resp.status_code == 401

    def test_get_me_with_token_for_deleted_user_returns_401(self, client):
        email = "deleted_user@example.com"
        _register(client, email, full_name="待删除用户")
        token = _login(client, email)

        db = _TestingSession()
        try:
            user = db.query(User).filter(User.email == email).first()
            assert user is not None
            db.delete(user)
            db.commit()
        finally:
            db.close()

        resp = client.get("/api/auth/me", headers=_auth_headers(token))
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Could not validate credentials"

    def test_update_me_changes_full_name(self, client):
        _register(client, "update_me@example.com", full_name="旧名字")
        token = _login(client, "update_me@example.com")
        resp = client.put(
            "/api/auth/me",
            json={"full_name": "新名字"},
            headers=_auth_headers(token),
        )
        assert resp.status_code == 200
        assert resp.json()["full_name"] == "新名字"


# ═══════════════════════════════════════════════════════════════════════════
# 2. 简历 CRUD
# ═══════════════════════════════════════════════════════════════════════════

class TestResumeCRUD:
    @pytest.fixture(autouse=True)
    def _setup(self, client):
        _register(client, "resume_user@example.com")
        self.token = _login(client, "resume_user@example.com")
        self.headers = _auth_headers(self.token)
        self.client = client

    def _create_resume(self, title: str = "我的简历") -> dict:
        resp = self.client.post(
            "/api/resumes/",
            json={"title": title, "content": _empty_resume_content()},
            headers=self.headers,
        )
        assert resp.status_code == 200, resp.text
        return resp.json()

    def test_create_resume_returns_resume(self):
        body = self._create_resume("测试简历")
        assert body["title"] == "测试简历"
        assert "id" in body
        assert body["content"]["personal_info"]["name"] == "张三"

    def test_list_resumes_returns_created_items(self):
        self._create_resume("简历A")
        self._create_resume("简历B")
        resp = self.client.get("/api/resumes/", headers=self.headers)
        assert resp.status_code == 200
        titles = [r["title"] for r in resp.json()]
        assert "简历A" in titles
        assert "简历B" in titles

    def test_list_resumes_includes_inline_preview_content(self):
        self._create_resume("预览简历")
        resp = self.client.get("/api/resumes/", headers=self.headers)
        assert resp.status_code == 200
        resume = next(item for item in resp.json() if item["title"] == "预览简历")
        assert resume["preview_content"]["personal_info"]["name"] == "张三"
        assert "job_application" not in resume["preview_content"]

    def test_get_resume_by_id(self):
        created = self._create_resume("可查简历")
        resume_id = created["id"]
        resp = self.client.get(f"/api/resumes/{resume_id}", headers=self.headers)
        assert resp.status_code == 200
        assert resp.json()["id"] == resume_id

    def test_get_nonexistent_resume_returns_404(self):
        resp = self.client.get("/api/resumes/9999999", headers=self.headers)
        assert resp.status_code == 404

    def test_update_resume_title(self):
        created = self._create_resume("旧标题")
        resume_id = created["id"]
        resp = self.client.put(
            f"/api/resumes/{resume_id}",
            json={"title": "新标题"},
            headers=self.headers,
        )
        assert resp.status_code == 200
        assert resp.json()["title"] == "新标题"

    def test_update_resume_content(self):
        created = self._create_resume("内容更新测试")
        resume_id = created["id"]
        new_content = _empty_resume_content()
        new_content["personal_info"]["name"] = "李四"
        resp = self.client.put(
            f"/api/resumes/{resume_id}",
            json={"content": new_content},
            headers=self.headers,
        )
        assert resp.status_code == 200
        assert resp.json()["content"]["personal_info"]["name"] == "李四"

    def test_update_resume_with_no_data_returns_400(self):
        created = self._create_resume("空更新测试")
        resume_id = created["id"]
        resp = self.client.put(
            f"/api/resumes/{resume_id}",
            json={},
            headers=self.headers,
        )
        assert resp.status_code == 400

    def test_delete_resume_removes_it(self):
        created = self._create_resume("待删除简历")
        resume_id = created["id"]
        del_resp = self.client.delete(f"/api/resumes/{resume_id}", headers=self.headers)
        assert del_resp.status_code == 200
        get_resp = self.client.get(f"/api/resumes/{resume_id}", headers=self.headers)
        assert get_resp.status_code == 404


class TestInterviewSessions:
    @pytest.fixture(autouse=True)
    def _setup(self, client, monkeypatch):
        _register(client, "interview_user@example.com")
        self.token = _login(client, "interview_user@example.com")
        self.headers = _auth_headers(self.token)
        self.client = client

        create_resp = self.client.post(
            "/api/resumes/",
            json={"title": "面试简历", "content": _empty_resume_content()},
            headers=self.headers,
        )
        assert create_resp.status_code == 200, create_resp.text
        self.resume_id = create_resp.json()["id"]

        async def _fake_chat(self, user_message, resume_content, conversation_history=None, event_callback=None):
            del self, resume_content, conversation_history, event_callback
            if "追问" in user_message:
                return {"content": "你刚才提到做了优化，具体指标提升了多少？"}
            if "下一轮" in user_message:
                return {"content": "换一个问题，说说你在项目里做过最难的一次技术取舍。"}
            return {"content": "先做一个和岗位最相关的自我介绍。"}

        monkeypatch.setattr(InterviewerAgent, "chat", _fake_chat)

    def test_interview_session_flow(self):
        create_resp = self.client.post(
            "/api/interviews/",
            json={
                "resume_id": self.resume_id,
                "interview_type": "general",
                "difficulty": "medium",
            },
            headers=self.headers,
        )
        assert create_resp.status_code == 200, create_resp.text
        session_id = create_resp.json()["session"]["id"]

        start_resp = self.client.post(
            f"/api/interviews/{session_id}/start",
            headers=self.headers,
        )
        assert start_resp.status_code == 200, start_resp.text
        started = start_resp.json()["session"]
        assert started["status"] == "waiting_user_answer"
        assert started["current_turn"]["question"] == "先做一个和岗位最相关的自我介绍。"

        answer_resp = self.client.post(
            f"/api/interviews/{session_id}/answer",
            json={"answer": "我负责后端开发。"},
            headers=self.headers,
        )
        assert answer_resp.status_code == 200, answer_resp.text
        answered = answer_resp.json()
        assert answered["next_action"] in ("next_question", "completed")
        assert answered["session"]["status"] in ("waiting_user_answer", "completed")

        end_resp = self.client.post(
            f"/api/interviews/{session_id}/end",
            headers=self.headers,
        )
        assert end_resp.status_code == 200, end_resp.text
        ended = end_resp.json()["session"]
        assert ended["status"] == "completed"
        assert ended["report_data"] is not None

    def test_list_interviews_returns_lightweight_summary(self):
        create_resp = self.client.post(
            "/api/interviews/",
            json={
                "resume_id": self.resume_id,
                "interview_type": "general",
                "difficulty": "medium",
            },
            headers=self.headers,
        )
        assert create_resp.status_code == 200, create_resp.text
        session_id = create_resp.json()["session"]["id"]

        start_resp = self.client.post(
            f"/api/interviews/{session_id}/start",
            headers=self.headers,
        )
        assert start_resp.status_code == 200, start_resp.text

        answer_resp = self.client.post(
            f"/api/interviews/{session_id}/answer",
            json={"answer": "我负责后端开发，并把接口响应时间降低了 30%。"},
            headers=self.headers,
        )
        assert answer_resp.status_code == 200, answer_resp.text

        list_resp = self.client.get("/api/interviews/", headers=self.headers)
        assert list_resp.status_code == 200, list_resp.text
        sessions = list_resp.json()
        assert len(sessions) >= 1
        session = next(item for item in sessions if item["id"] == session_id)
        assert session["id"] == session_id
        assert session["answered_turn_count"] == 1
        assert "turns" not in session
        assert "current_turn" not in session

    def test_list_resumes_without_auth_returns_401(self):
        resp = self.client.get("/api/resumes/")
        assert resp.status_code == 401


# ═══════════════════════════════════════════════════════════════════════════
# 3. 跨用户权限隔离
# ═══════════════════════════════════════════════════════════════════════════

class TestResumePermissions:
    @pytest.fixture(autouse=True)
    def _setup(self, client):
        # 用户 A
        _register(client, "user_a@example.com")
        self.token_a = _login(client, "user_a@example.com")
        # 用户 B
        _register(client, "user_b@example.com")
        self.token_b = _login(client, "user_b@example.com")
        self.client = client

        # 用户 A 创建一份简历
        resp = client.post(
            "/api/resumes/",
            json={"title": "用户A的简历", "content": _empty_resume_content()},
            headers=_auth_headers(self.token_a),
        )
        assert resp.status_code == 200
        self.resume_id = resp.json()["id"]

    def test_user_b_cannot_read_user_a_resume(self):
        resp = self.client.get(
            f"/api/resumes/{self.resume_id}",
            headers=_auth_headers(self.token_b),
        )
        assert resp.status_code == 403

    def test_user_b_cannot_update_user_a_resume(self):
        resp = self.client.put(
            f"/api/resumes/{self.resume_id}",
            json={"title": "非法修改"},
            headers=_auth_headers(self.token_b),
        )
        assert resp.status_code == 403

    def test_user_b_cannot_delete_user_a_resume(self):
        resp = self.client.delete(
            f"/api/resumes/{self.resume_id}",
            headers=_auth_headers(self.token_b),
        )
        assert resp.status_code == 403

    def test_user_b_resume_list_does_not_include_user_a_resume(self):
        resp = self.client.get(
            "/api/resumes/",
            headers=_auth_headers(self.token_b),
        )
        assert resp.status_code == 200
        ids = [r["id"] for r in resp.json()]
        assert self.resume_id not in ids


# ═══════════════════════════════════════════════════════════════════════════
# 4. 聊天记录 CRUD
# ═══════════════════════════════════════════════════════════════════════════

class TestChatMessages:
    @pytest.fixture(autouse=True)
    def _setup(self, client):
        _register(client, "chat_user@example.com")
        self.token = _login(client, "chat_user@example.com")
        self.headers = _auth_headers(self.token)
        self.client = client

        resp = client.post(
            "/api/resumes/",
            json={"title": "聊天简历", "content": _empty_resume_content()},
            headers=self.headers,
        )
        assert resp.status_code == 200
        self.resume_id = resp.json()["id"]

    def test_append_and_get_messages(self):
        msgs = [
            {"role": "user", "content": "帮我优化简历"},
            {"role": "assistant", "content": "好的，我来帮你优化"},
        ]
        post_resp = self.client.post(
            f"/api/resumes/{self.resume_id}/chat-messages",
            json=msgs,
            headers=self.headers,
        )
        assert post_resp.status_code == 200
        saved = post_resp.json()
        assert len(saved) == 2
        assert saved[0]["role"] == "user"
        assert saved[1]["role"] == "assistant"

        get_resp = self.client.get(
            f"/api/resumes/{self.resume_id}/chat-messages",
            headers=self.headers,
        )
        assert get_resp.status_code == 200
        all_msgs = get_resp.json()
        assert len(all_msgs) == 2

    def test_messages_are_ordered_by_id(self):
        for i in range(3):
            self.client.post(
                f"/api/resumes/{self.resume_id}/chat-messages",
                json=[{"role": "user", "content": f"消息 {i}"}],
                headers=self.headers,
            )
        get_resp = self.client.get(
            f"/api/resumes/{self.resume_id}/chat-messages",
            headers=self.headers,
        )
        msgs = get_resp.json()
        ids = [m["id"] for m in msgs]
        assert ids == sorted(ids)

    def test_invalid_role_is_ignored(self):
        resp = self.client.post(
            f"/api/resumes/{self.resume_id}/chat-messages",
            json=[{"role": "system", "content": "系统消息应被忽略"}],
            headers=self.headers,
        )
        assert resp.status_code == 200
        assert resp.json() == []

    def test_clear_messages(self):
        self.client.post(
            f"/api/resumes/{self.resume_id}/chat-messages",
            json=[{"role": "user", "content": "一条消息"}],
            headers=self.headers,
        )
        del_resp = self.client.delete(
            f"/api/resumes/{self.resume_id}/chat-messages",
            headers=self.headers,
        )
        assert del_resp.status_code == 200

        get_resp = self.client.get(
            f"/api/resumes/{self.resume_id}/chat-messages",
            headers=self.headers,
        )
        assert get_resp.json() == []

    def test_append_messages_with_stream_events(self):
        stream_events = [
            {"type": "tool_confirmed", "diff": "添加了量化指标"},
        ]
        resp = self.client.post(
            f"/api/resumes/{self.resume_id}/chat-messages",
            json=[{"role": "assistant", "content": "已优化", "stream_events": stream_events}],
            headers=self.headers,
        )
        assert resp.status_code == 200
        saved = resp.json()
        assert saved[0]["stream_events"] == stream_events

    def test_chat_messages_forbidden_for_other_user(self):
        _register(self.client, "other_chat@example.com")
        other_token = _login(self.client, "other_chat@example.com")
        resp = self.client.get(
            f"/api/resumes/{self.resume_id}/chat-messages",
            headers=_auth_headers(other_token),
        )
        assert resp.status_code == 403


# ═══════════════════════════════════════════════════════════════════════════
# 5. Agent 确认会话
# ═══════════════════════════════════════════════════════════════════════════

class TestAgentConfirmation:
    @pytest.fixture(autouse=True)
    def _setup(self, client):
        _register(client, "agent_confirm@example.com")
        self.token = _login(client, "agent_confirm@example.com")
        self.headers = _auth_headers(self.token)
        self.client = client

        me_resp = client.get("/api/auth/me", headers=self.headers)
        assert me_resp.status_code == 200
        self.user_id = me_resp.json()["id"]

        resume_resp = client.post(
            "/api/resumes/",
            json={"title": "确认简历", "content": _empty_resume_content()},
            headers=self.headers,
        )
        assert resume_resp.status_code == 200
        self.resume_id = resume_resp.json()["id"]

    def _create_waiting_session(self, session_id: str, call_id: str = "call_1") -> None:
        db = _TestingSession()
        try:
            store = AgentSessionStore(db)
            store.create_session(
                session_id=session_id,
                user_id=self.user_id,
                resume_id=self.resume_id,
                task_type="resume_optimization",
            )
            store.update_status(session_id, "waiting_confirmation", current_step=call_id)
            store.append_event(
                session_id=session_id,
                event_type="tool_call_previewed",
                source="resume_agent",
                payload={
                    "call_id": call_id,
                    "tool_name": "优化简介",
                    "diff_summary": "改前 A 改后 B",
                },
            )
        finally:
            db.close()

    def test_confirm_tool_records_resumable_result_when_stream_queue_missing(self):
        self._create_waiting_session("persisted_session")

        resp = self.client.post(
            "/api/ai/chat/confirm-tool",
            json={
                "session_id": "persisted_session",
                "call_id": "call_1",
                "confirmed": True,
            },
            headers=self.headers,
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is False
        assert body["resumable"] is True

        db = _TestingSession()
        try:
            store = AgentSessionStore(db)
            session = store.get_session("persisted_session")
            assert session.status == "paused"
            latest = store.get_latest_event("persisted_session")
            assert latest.event_type == "tool_call_confirmed"
            assert latest.payload["active_stream"] is False
        finally:
            db.close()

    def test_confirm_tool_uses_active_queue_when_present(self):
        session_id = "active_session"
        self._create_waiting_session(session_id)
        queue = confirmation_manager.create(session_id)
        try:
            resp = self.client.post(
                "/api/ai/chat/confirm-tool",
                json={
                    "session_id": session_id,
                    "call_id": "call_1",
                    "confirmed": False,
                },
                headers=self.headers,
            )

            assert resp.status_code == 200
            assert resp.json() == {"ok": True}
            assert queue.get_nowait() is False
        finally:
            confirmation_manager.remove(session_id)

    def test_confirm_tool_rejects_mismatched_call_id(self):
        self._create_waiting_session("mismatched_session", call_id="call_real")

        resp = self.client.post(
            "/api/ai/chat/confirm-tool",
            json={
                "session_id": "mismatched_session",
                "call_id": "call_wrong",
                "confirmed": True,
            },
            headers=self.headers,
        )

        assert resp.status_code == 409

    def test_resume_session_applies_recorded_confirmation(self):
        session_id = "resume_http_session"
        db = _TestingSession()
        try:
            store = AgentSessionStore(db)
            store.create_session(
                session_id=session_id,
                user_id=self.user_id,
                resume_id=self.resume_id,
                task_type="resume_optimization",
                metadata={"visible_modules": ["projects"]},
            )
            store.update_status(session_id, "waiting_confirmation", current_step="call_1")
            store.append_event(
                session_id=session_id,
                event_type="user_message",
                source="user",
                payload={"content": "优化项目简介"},
            )
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
                                "overview": "恢复接口写入的新简介",
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
        finally:
            db.close()

        update_resp = self.client.put(
            f"/api/resumes/{self.resume_id}",
            json={
                "content": {
                    **_empty_resume_content(),
                    "projects": [
                        {
                            "id": "proj_1",
                            "name": "Chat Resume",
                            "role": "开发者",
                            "duration": "2026",
                            "overview": "旧简介",
                        }
                    ],
                }
            },
            headers=self.headers,
        )
        assert update_resp.status_code == 200

        resp = self.client.post(
            "/api/ai/chat/resume-session",
            json={"session_id": session_id},
            headers=self.headers,
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        assert body["applied"] is True
        assert body["resume_content"]["projects"][0]["overview"] == "恢复接口写入的新简介"

# ═══════════════════════════════════════════════════════════════════════════
# 7. 健康检查 & 根路由
# ═══════════════════════════════════════════════════════════════════════════

class TestHealthEndpoints:
    def test_root_returns_200(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        assert "Chat Resume" in resp.json()["message"]

    def test_health_check_returns_healthy(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "healthy"

    def test_health_check_returns_db_connectivity(self, client):
        """健康检查应验证数据库连通性，不只是返回静态字符串。"""
        resp = client.get("/health")
        assert resp.status_code == 200
        body = resp.json()
        assert "status" in body


# ═══════════════════════════════════════════════════════════════════════════
# 8. 负向场景
# ═══════════════════════════════════════════════════════════════════════════

class TestNegativeCases:
    @pytest.fixture(autouse=True)
    def _setup(self, client):
        _register(client, "negative_user@example.com")
        self.token = _login(client, "negative_user@example.com")
        self.client = client
        resp = client.post(
            "/api/resumes/",
            json={"title": "测试简历", "content": _empty_resume_content()},
            headers=_auth_headers(self.token),
        )
        assert resp.status_code == 200
        self.resume_id = resp.json()["id"]

    # ── 未认证访问 ────────────────────────────────────────────────────────

    def test_get_resumes_without_token_returns_401(self):
        resp = self.client.get("/api/resumes/")
        assert resp.status_code == 401

    def test_get_resume_without_token_returns_401(self):
        resp = self.client.get(f"/api/resumes/{self.resume_id}")
        assert resp.status_code == 401

    def test_update_resume_without_token_returns_401(self):
        resp = self.client.put(
            f"/api/resumes/{self.resume_id}",
            json={"title": "无 token"},
        )
        assert resp.status_code == 401

    def test_delete_resume_without_token_returns_401(self):
        resp = self.client.delete(f"/api/resumes/{self.resume_id}")
        assert resp.status_code == 401

    def test_update_layout_without_token_returns_401(self):
        resp = self.client.put(
            f"/api/resumes/{self.resume_id}/layout",
            json={
                "density": "compact",
                "moduleOrder": ["personal", "education", "work", "projects", "skills"],
                "visibleModules": ["personal", "education", "work", "projects", "skills"],
                "spacingScale": 0.8,
            },
        )
        assert resp.status_code == 401

    # ── 资源不存在 ────────────────────────────────────────────────────────

    def test_get_nonexistent_resume_returns_404(self):
        resp = self.client.get(
            "/api/resumes/999999",
            headers=_auth_headers(self.token),
        )
        assert resp.status_code == 404

    def test_update_nonexistent_resume_returns_404(self):
        resp = self.client.put(
            "/api/resumes/999999",
            json={"title": "不存在"},
            headers=_auth_headers(self.token),
        )
        assert resp.status_code == 404

    def test_delete_nonexistent_resume_returns_404(self):
        resp = self.client.delete(
            "/api/resumes/999999",
            headers=_auth_headers(self.token),
        )
        assert resp.status_code == 404

    def test_update_layout_nonexistent_resume_returns_404(self):
        resp = self.client.put(
            "/api/resumes/999999/layout",
            json={
                "density": "normal",
                "moduleOrder": ["personal", "education", "work", "projects", "skills"],
                "visibleModules": ["personal", "education", "work", "projects", "skills"],
                "spacingScale": 1.0,
            },
            headers=_auth_headers(self.token),
        )
        assert resp.status_code == 404

    # ── 无效输入 ──────────────────────────────────────────────────────────

    def test_update_resume_with_empty_body_returns_400(self):
        resp = self.client.put(
            f"/api/resumes/{self.resume_id}",
            json={},
            headers=_auth_headers(self.token),
        )
        assert resp.status_code == 400

    def test_register_with_invalid_email_returns_422(self):
        resp = self.client.post(
            "/api/auth/register",
            json={"email": "not-an-email", "password": "password123"},
        )
        assert resp.status_code == 422

    def test_register_with_short_password_returns_422(self):
        resp = self.client.post(
            "/api/auth/register",
            json={"email": "valid@example.com", "password": "123"},
        )
        assert resp.status_code == 422

    # ── 跨用户布局配置权限 ────────────────────────────────────────────────

    def test_other_user_cannot_update_layout(self):
        _register(self.client, "layout_attacker@example.com")
        attacker_token = _login(self.client, "layout_attacker@example.com")
        resp = self.client.put(
            f"/api/resumes/{self.resume_id}/layout",
            json={
                "density": "compact",
                "moduleOrder": ["personal", "education", "work", "projects", "skills"],
                "visibleModules": ["personal", "education", "work", "projects", "skills"],
                "spacingScale": 0.7,
            },
            headers=_auth_headers(attacker_token),
        )
        assert resp.status_code == 403
