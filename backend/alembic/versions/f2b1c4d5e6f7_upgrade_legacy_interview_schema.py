"""用于定义数据库结构迁移脚本。"""

from alembic import op
import sqlalchemy as sa


revision = "f2b1c4d5e6f7"
down_revision = "e1f2a3b4c5d6"
branch_labels = None
depends_on = None


def _column_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    """用于处理字段names。"""
    return {col["name"] for col in inspector.get_columns(table_name)}


def upgrade() -> None:
    """用于执行数据库升级迁移。"""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "interview_sessions" in tables:
        session_columns = _column_names(inspector, "interview_sessions")

        if "user_id" not in session_columns:
            op.add_column("interview_sessions", sa.Column("user_id", sa.Integer(), nullable=True))
        if "target_title" not in session_columns:
            op.add_column("interview_sessions", sa.Column("target_title", sa.String(), nullable=True))
        if "target_company" not in session_columns:
            op.add_column("interview_sessions", sa.Column("target_company", sa.String(), nullable=True))
        if "jd_text" not in session_columns:
            op.add_column("interview_sessions", sa.Column("jd_text", sa.Text(), nullable=True))
        if "interview_type" not in session_columns:
            op.add_column(
                "interview_sessions",
                sa.Column("interview_type", sa.String(), nullable=False, server_default="general"),
            )
        if "difficulty" not in session_columns:
            op.add_column(
                "interview_sessions",
                sa.Column("difficulty", sa.String(), nullable=False, server_default="medium"),
            )
        if "language" not in session_columns:
            op.add_column(
                "interview_sessions",
                sa.Column("language", sa.String(), nullable=False, server_default="zh-CN"),
            )
        if "mode" not in session_columns:
            op.add_column(
                "interview_sessions",
                sa.Column("mode", sa.String(), nullable=False, server_default="text"),
            )
        if "current_round_index" not in session_columns:
            op.add_column(
                "interview_sessions",
                sa.Column("current_round_index", sa.Integer(), nullable=False, server_default="0"),
            )
        if "current_turn_index" not in session_columns:
            op.add_column(
                "interview_sessions",
                sa.Column("current_turn_index", sa.Integer(), nullable=False, server_default="0"),
            )
        if "plan_json" not in session_columns:
            op.add_column("interview_sessions", sa.Column("plan_json", sa.JSON(), nullable=True))
        if "started_at" not in session_columns:
            op.add_column("interview_sessions", sa.Column("started_at", sa.DateTime(timezone=True), nullable=True))
        if "ended_at" not in session_columns:
            op.add_column("interview_sessions", sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True))

        refreshed_columns = _column_names(sa.inspect(bind), "interview_sessions")
        if "jd_content" in refreshed_columns and "jd_text" in refreshed_columns:
            op.execute("UPDATE interview_sessions SET jd_text = COALESCE(jd_text, jd_content)")

    if "interview_turns" in tables:
        turn_columns = _column_names(inspector, "interview_turns")

        if "round_index" not in turn_columns:
            op.add_column(
                "interview_turns",
                sa.Column("round_index", sa.Integer(), nullable=False, server_default="0"),
            )
        if "expected_points" not in turn_columns:
            op.add_column("interview_turns", sa.Column("expected_points", sa.JSON(), nullable=True))
        if "follow_up_count" not in turn_columns:
            op.add_column(
                "interview_turns",
                sa.Column("follow_up_count", sa.Integer(), nullable=False, server_default="0"),
            )


def downgrade() -> None:
    """用于执行数据库回滚迁移。"""
    pass
