"""用于扫描并清理超时 paused session。"""

import logging
from typing import Callable

from sqlalchemy.orm import Session

from app.state.store import AgentSessionStore

logger = logging.getLogger(__name__)


async def sweep_timed_out_sessions(
    db_session_factory: Callable[[], Session],
    timeout_seconds: int = 600,
) -> int:
    """扫描并将超时 paused session 标记为 failed，返回处理数量。"""
    db = db_session_factory()
    try:
        store = AgentSessionStore(db)
        session_ids = store.get_timed_out_paused_sessions(timeout_seconds)
        for session_id in session_ids:
            store.update_status(session_id, "failed", failed_reason="confirmation_timeout")
            store.append_event(
                session_id=session_id,
                event_type="session_timed_out",
                source="sweeper",
                payload={"timeout_seconds": timeout_seconds},
            )
            logger.info(
                "session_sweeper.timed_out",
                extra={"session_id": session_id, "timeout_seconds": timeout_seconds},
            )
        return len(session_ids)
    finally:
        db.close()


__all__ = ["sweep_timed_out_sessions"]
