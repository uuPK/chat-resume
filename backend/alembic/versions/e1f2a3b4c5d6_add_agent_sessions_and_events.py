"""用于定义数据库结构迁移脚本。"""

from alembic import op
import sqlalchemy as sa


revision = "e1f2a3b4c5d6"
down_revision = "b1c2d3e4f5a6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """用于执行数据库升级迁移。"""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()

    if "agent_sessions" not in tables:
        op.create_table(
            "agent_sessions",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("resume_id", sa.Integer(), nullable=True),
            sa.Column("task_type", sa.String(), nullable=False),
            sa.Column("status", sa.String(), nullable=False),
            sa.Column("current_step", sa.String(), nullable=True),
            sa.Column("failed_reason", sa.Text(), nullable=True),
            sa.Column("metadata_json", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["resume_id"], ["resumes.id"]),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_agent_sessions_id", "agent_sessions", ["id"], unique=False)
        op.create_index("ix_agent_sessions_user_id", "agent_sessions", ["user_id"], unique=False)
        op.create_index("ix_agent_sessions_resume_id", "agent_sessions", ["resume_id"], unique=False)
        op.create_index("ix_agent_sessions_status", "agent_sessions", ["status"], unique=False)

    if "agent_events" not in tables:
        op.create_table(
            "agent_events",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("session_id", sa.String(), nullable=False),
            sa.Column("sequence", sa.Integer(), nullable=False),
            sa.Column("event_type", sa.String(), nullable=False),
            sa.Column("source", sa.String(), nullable=False),
            sa.Column("payload", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["session_id"], ["agent_sessions.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_agent_events_id", "agent_events", ["id"], unique=False)
        op.create_index("ix_agent_events_session_id", "agent_events", ["session_id"], unique=False)
        op.create_index("ix_agent_events_event_type", "agent_events", ["event_type"], unique=False)
        op.create_index(
            "idx_agent_events_session_sequence",
            "agent_events",
            ["session_id", "sequence"],
            unique=True,
        )


def downgrade() -> None:
    """用于执行数据库回滚迁移。"""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()

    if "agent_events" in tables:
        op.drop_index("idx_agent_events_session_sequence", table_name="agent_events")
        op.drop_index("ix_agent_events_event_type", table_name="agent_events")
        op.drop_index("ix_agent_events_session_id", table_name="agent_events")
        op.drop_index("ix_agent_events_id", table_name="agent_events")
        op.drop_table("agent_events")

    if "agent_sessions" in tables:
        op.drop_index("ix_agent_sessions_status", table_name="agent_sessions")
        op.drop_index("ix_agent_sessions_resume_id", table_name="agent_sessions")
        op.drop_index("ix_agent_sessions_user_id", table_name="agent_sessions")
        op.drop_index("ix_agent_sessions_id", table_name="agent_sessions")
        op.drop_table("agent_sessions")
