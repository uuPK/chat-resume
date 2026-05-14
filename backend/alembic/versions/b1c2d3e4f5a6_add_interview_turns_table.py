"""用于定义数据库结构迁移脚本。"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "b1c2d3e4f5a6"
down_revision = "d74681f33876"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """用于执行数据库升级迁移。"""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()

    if "interview_turns" not in existing_tables:
        op.create_table(
            "interview_turns",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column(
                "session_id",
                sa.Integer(),
                sa.ForeignKey("interview_sessions.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("turn_index", sa.Integer(), nullable=False),
            sa.Column("question", sa.Text(), nullable=False),
            sa.Column("question_type", sa.String(), nullable=False, server_default="general"),
            sa.Column("intent", sa.Text(), nullable=True),
            sa.Column("answer", sa.Text(), nullable=True),
            sa.Column("evaluation", sa.JSON(), nullable=True),
            sa.Column("score", sa.Integer(), nullable=True),
            sa.Column("status", sa.String(), nullable=False, server_default="asked"),
            sa.Column("asked_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("answered_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=True,
            ),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        )

    indexes = {idx["name"] for idx in inspector.get_indexes("interview_turns")} if "interview_turns" in inspector.get_table_names() else set()

    if "idx_interview_turns_session_id" not in indexes:
        op.create_index(
            "idx_interview_turns_session_id",
            "interview_turns",
            ["session_id"],
            unique=False,
        )

    if "idx_interview_turns_session_turn_index" not in indexes:
        op.create_index(
            "idx_interview_turns_session_turn_index",
            "interview_turns",
            ["session_id", "turn_index"],
            unique=True,
        )

    if "idx_interview_turns_status" not in indexes:
        op.create_index(
            "idx_interview_turns_status",
            "interview_turns",
            ["status"],
            unique=False,
        )


def downgrade() -> None:
    """用于执行数据库回滚迁移。"""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()

    if "interview_turns" in existing_tables:
        indexes = {idx["name"] for idx in inspector.get_indexes("interview_turns")}
        if "idx_interview_turns_status" in indexes:
            op.drop_index("idx_interview_turns_status", table_name="interview_turns")
        if "idx_interview_turns_session_turn_index" in indexes:
            op.drop_index(
                "idx_interview_turns_session_turn_index",
                table_name="interview_turns",
            )
        if "idx_interview_turns_session_id" in indexes:
            op.drop_index("idx_interview_turns_session_id", table_name="interview_turns")
        op.drop_table("interview_turns")
