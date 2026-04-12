"""
Durable store for agent sessions and event logs.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4
from typing import Any, Iterable

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.agent_session import AgentEvent, AgentSession


class AgentSessionStore:
    def __init__(self, db: Session):
        self.db = db

    def create_session(
        self,
        *,
        user_id: int,
        task_type: str,
        resume_id: int | None = None,
        metadata: dict[str, Any] | None = None,
        session_id: str | None = None,
    ) -> AgentSession:
        session = AgentSession(
            id=session_id or uuid4().hex,
            user_id=user_id,
            resume_id=resume_id,
            task_type=task_type,
            status="created",
            metadata_json=metadata or {},
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session

    def get_session(self, session_id: str) -> AgentSession | None:
        return (
            self.db.query(AgentSession)
            .filter(AgentSession.id == session_id)
            .first()
        )

    def update_status(
        self,
        session_id: str,
        status: str,
        *,
        current_step: str | None = None,
        failed_reason: str | None = None,
        clear_current_step: bool = False,
    ) -> AgentSession | None:
        session = self.get_session(session_id)
        if not session:
            return None
        session.status = status
        if clear_current_step:
            session.current_step = None
        elif current_step is not None:
            session.current_step = current_step
        if failed_reason is not None:
            session.failed_reason = failed_reason
        if status in {"completed", "failed", "cancelled"}:
            session.completed_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(session)
        return session

    def append_event(
        self,
        *,
        session_id: str,
        event_type: str,
        source: str,
        payload: dict[str, Any] | None = None,
    ) -> AgentEvent:
        sequence = self._next_sequence(session_id)
        event = AgentEvent(
            session_id=session_id,
            sequence=sequence,
            event_type=event_type,
            source=source,
            payload=payload or {},
        )
        self.db.add(event)
        self.db.commit()
        self.db.refresh(event)
        return event

    def list_events(
        self,
        session_id: str,
        *,
        after_sequence: int | None = None,
        limit: int | None = None,
    ) -> list[AgentEvent]:
        query = (
            self.db.query(AgentEvent)
            .filter(AgentEvent.session_id == session_id)
            .order_by(AgentEvent.sequence.asc())
        )
        if after_sequence is not None:
            query = query.filter(AgentEvent.sequence > after_sequence)
        if limit is not None:
            query = query.limit(limit)
        return list(query.all())

    def get_latest_event(
        self,
        session_id: str,
        *,
        event_type: str | None = None,
    ) -> AgentEvent | None:
        query = self.db.query(AgentEvent).filter(AgentEvent.session_id == session_id)
        if event_type is not None:
            query = query.filter(AgentEvent.event_type == event_type)
        return query.order_by(AgentEvent.sequence.desc()).first()

    def append_confirmation_event(
        self,
        *,
        session_id: str,
        call_id: str,
        confirmed: bool,
        source: str = "user",
        tool_name: str | None = None,
        active_stream: bool = True,
    ) -> AgentEvent:
        return self.append_event(
            session_id=session_id,
            event_type="tool_call_confirmed" if confirmed else "tool_call_rejected",
            source=source,
            payload={
                "call_id": call_id,
                "tool_name": tool_name,
                "active_stream": active_stream,
            },
        )

    def append_events(
        self,
        session_id: str,
        events: Iterable[tuple[str, str, dict[str, Any]]],
    ) -> list[AgentEvent]:
        return [
            self.append_event(
                session_id=session_id,
                event_type=event_type,
                source=source,
                payload=payload,
            )
            for event_type, source, payload in events
        ]

    def _next_sequence(self, session_id: str) -> int:
        current = (
            self.db.query(func.max(AgentEvent.sequence))
            .filter(AgentEvent.session_id == session_id)
            .scalar()
        )
        return int(current or 0) + 1
