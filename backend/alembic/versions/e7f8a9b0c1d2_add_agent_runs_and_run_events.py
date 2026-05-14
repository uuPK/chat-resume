"""用于定义数据库结构迁移脚本。"""

from alembic import op
import sqlalchemy as sa


revision = "e7f8a9b0c1d2"
down_revision = "c4d5e6f7a8b9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """用于执行数据库升级迁移。"""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()

    if "agent_runs" not in tables:
        op.create_table(
            "agent_runs",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("agent_type", sa.String(), nullable=False),
            sa.Column("run_kind", sa.String(), nullable=False),
            sa.Column("status", sa.String(), nullable=False),
            sa.Column("session_id", sa.String(), nullable=True),
            sa.Column("interview_session_id", sa.Integer(), nullable=True),
            sa.Column("resume_id", sa.Integer(), nullable=True),
            sa.Column("input_text", sa.Text(), nullable=True),
            sa.Column("final_output", sa.Text(), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("metadata_json", sa.JSON(), nullable=True),
            sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.ForeignKeyConstraint(["interview_session_id"], ["interview_sessions.id"]),
            sa.ForeignKeyConstraint(["resume_id"], ["resumes.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_agent_runs_id", "agent_runs", ["id"], unique=False)
        op.create_index("ix_agent_runs_user_id", "agent_runs", ["user_id"], unique=False)
        op.create_index("ix_agent_runs_agent_type", "agent_runs", ["agent_type"], unique=False)
        op.create_index("ix_agent_runs_run_kind", "agent_runs", ["run_kind"], unique=False)
        op.create_index("ix_agent_runs_status", "agent_runs", ["status"], unique=False)
        op.create_index("ix_agent_runs_session_id", "agent_runs", ["session_id"], unique=False)
        op.create_index("ix_agent_runs_interview_session_id", "agent_runs", ["interview_session_id"], unique=False)
        op.create_index("ix_agent_runs_resume_id", "agent_runs", ["resume_id"], unique=False)

    if "agent_run_events" not in tables:
        op.create_table(
            "agent_run_events",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("run_id", sa.String(), nullable=False),
            sa.Column("sequence", sa.Integer(), nullable=False),
            sa.Column("step_id", sa.String(), nullable=True),
            sa.Column("step_index", sa.Integer(), nullable=True),
            sa.Column("event_type", sa.String(), nullable=False),
            sa.Column("payload", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["run_id"], ["agent_runs.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_agent_run_events_id", "agent_run_events", ["id"], unique=False)
        op.create_index("ix_agent_run_events_run_id", "agent_run_events", ["run_id"], unique=False)
        op.create_index("ix_agent_run_events_step_id", "agent_run_events", ["step_id"], unique=False)
        op.create_index("ix_agent_run_events_step_index", "agent_run_events", ["step_index"], unique=False)
        op.create_index("ix_agent_run_events_event_type", "agent_run_events", ["event_type"], unique=False)
        op.create_index(
            "idx_agent_run_events_run_sequence",
            "agent_run_events",
            ["run_id", "sequence"],
            unique=True,
        )


def downgrade() -> None:
    """用于执行数据库回滚迁移。"""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()

    if "agent_run_events" in tables:
        op.drop_index("idx_agent_run_events_run_sequence", table_name="agent_run_events")
        op.drop_index("ix_agent_run_events_event_type", table_name="agent_run_events")
        op.drop_index("ix_agent_run_events_step_index", table_name="agent_run_events")
        op.drop_index("ix_agent_run_events_step_id", table_name="agent_run_events")
        op.drop_index("ix_agent_run_events_run_id", table_name="agent_run_events")
        op.drop_index("ix_agent_run_events_id", table_name="agent_run_events")
        op.drop_table("agent_run_events")

    if "agent_runs" in tables:
        op.drop_index("ix_agent_runs_resume_id", table_name="agent_runs")
        op.drop_index("ix_agent_runs_interview_session_id", table_name="agent_runs")
        op.drop_index("ix_agent_runs_session_id", table_name="agent_runs")
        op.drop_index("ix_agent_runs_status", table_name="agent_runs")
        op.drop_index("ix_agent_runs_run_kind", table_name="agent_runs")
        op.drop_index("ix_agent_runs_agent_type", table_name="agent_runs")
        op.drop_index("ix_agent_runs_user_id", table_name="agent_runs")
        op.drop_index("ix_agent_runs_id", table_name="agent_runs")
        op.drop_table("agent_runs")
