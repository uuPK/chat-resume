"""
数据库连接管理模块

负责建立和管理数据库连接，包括引擎创建、会话管理和基础模型类。
使用SQLAlchemy ORM进行数据库操作。
"""

from time import perf_counter

from sqlalchemy import create_engine, event
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.core.config import settings
from app.core.db_observability import record_checkout, record_query

connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine_kwargs = {"connect_args": connect_args}
if not settings.DATABASE_URL.startswith("sqlite"):
    engine_kwargs.update(
        pool_pre_ping=True,
        pool_recycle=1800,
        pool_size=5,
        max_overflow=10,
    )

engine = create_engine(settings.DATABASE_URL, **engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@event.listens_for(engine, "before_cursor_execute")
def before_cursor_execute(
    conn, cursor, statement, parameters, context, executemany
):
    context._query_started_at = perf_counter()


@event.listens_for(engine, "after_cursor_execute")
def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    query_started_at = getattr(context, "_query_started_at", None)
    if query_started_at is None:
        return
    record_query(statement, (perf_counter() - query_started_at) * 1000)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    checkout_started_at = perf_counter()
    db.connection()
    record_checkout((perf_counter() - checkout_started_at) * 1000)
    try:
        yield db
    finally:
        db.close()
