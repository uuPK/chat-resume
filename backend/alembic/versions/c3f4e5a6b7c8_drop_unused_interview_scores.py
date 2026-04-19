"""删除不再使用的面试评分列

Revision ID: c3f4e5a6b7c8
Revises: a1b2c3d4e5f6
Create Date: 2026-04-19 23:40:00.000000
"""

from alembic import op
import sqlalchemy as sa


# 用于标识 Alembic 迁移链路。
revision = "c3f4e5a6b7c8"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """用于删除已停用的面试评分列。"""
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    session_columns = {column["name"] for column in inspector.get_columns("interview_sessions")}
    if "overall_score" in session_columns:
        op.drop_column("interview_sessions", "overall_score")

    turn_columns = {column["name"] for column in inspector.get_columns("interview_turns")}
    if "score" in turn_columns:
        op.drop_column("interview_turns", "score")


def downgrade() -> None:
    """用于在回滚时恢复旧的面试评分列。"""
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    session_columns = {column["name"] for column in inspector.get_columns("interview_sessions")}
    if "overall_score" not in session_columns:
        op.add_column("interview_sessions", sa.Column("overall_score", sa.Integer(), nullable=True))

    turn_columns = {column["name"] for column in inspector.get_columns("interview_turns")}
    if "score" not in turn_columns:
        op.add_column("interview_turns", sa.Column("score", sa.Integer(), nullable=True))
