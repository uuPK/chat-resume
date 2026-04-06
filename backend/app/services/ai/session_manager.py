"""
工具确认 Session 管理器

每个流式聊天请求对应一个 session，session 持有一个 asyncio.Queue，
用于在 agent 暂停时接收前端发来的 confirm/reject 信号。
"""

import asyncio
from typing import Dict, Optional


class ConfirmationSessionManager:
    def __init__(self):
        self._queues: Dict[str, asyncio.Queue] = {}

    def create(self, session_id: str) -> asyncio.Queue:
        """创建 session 并返回对应的队列。"""
        q: asyncio.Queue = asyncio.Queue(maxsize=1)
        self._queues[session_id] = q
        return q

    def get(self, session_id: str) -> Optional[asyncio.Queue]:
        return self._queues.get(session_id)

    async def put(self, session_id: str, confirmed: bool) -> bool:
        """向 session 队列投递确认结果，返回 False 表示 session 不存在。"""
        q = self._queues.get(session_id)
        if q is None:
            return False
        await q.put(confirmed)
        return True

    def remove(self, session_id: str) -> None:
        self._queues.pop(session_id, None)


# 模块级单例
confirmation_manager = ConfirmationSessionManager()
