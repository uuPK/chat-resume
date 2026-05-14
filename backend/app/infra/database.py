"""
数据库连接管理模块

负责建立和管理数据库连接，包括引擎创建、会话管理和基础模型类。
使用SQLAlchemy ORM进行数据库操作。
"""

from __future__ import annotations

from time import perf_counter
from typing import Any, Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.infra.config import settings
from app.infra.db_observability import record_checkout, record_query

connect_args: dict[str, Any] = {}
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine_kwargs: dict[str, Any] = {"connect_args": connect_args}
if not settings.DATABASE_URL.startswith("sqlite"):
    engine_kwargs.update(
        {
            "pool_pre_ping": True,
            "pool_recycle": 1800,
            "pool_size": 5,
            "max_overflow": 10,
        }
    )

engine = create_engine(settings.DATABASE_URL, **engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@event.listens_for(engine, "before_cursor_execute")
def before_cursor_execute(
    _conn, _cursor, _statement, _parameters, context, _executemany
):
    """用于处理before游标执行。"""
    context._query_started_at = perf_counter()


@event.listens_for(engine, "after_cursor_execute")
def after_cursor_execute(_conn, _cursor, statement, _parameters, context, _executemany):
    """用于处理after游标执行。"""
    query_started_at = getattr(context, "_query_started_at", None)
    if query_started_at is None:
        return
    record_query(statement, (perf_counter() - query_started_at) * 1000)


class Base(DeclarativeBase):
    """用于为所有 ORM 模型提供统一的声明式基类。"""


def get_db() -> Generator[Session, None, None]:
    """用于按请求生命周期提供数据库会话。"""
    db = SessionLocal()
    checkout_started_at = perf_counter()
    db.connection()
    record_checkout((perf_counter() - checkout_started_at) * 1000)
    try:
        yield db
    finally:
        db.close()
