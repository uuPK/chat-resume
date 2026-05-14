"""用于定义数据库结构迁移脚本。"""

from alembic import op
import sqlalchemy as sa


revision = "c4d5e6f7a8b9"
down_revision = "b2c3d4e5f6a1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """用于执行数据库升级迁移。"""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()

    if "resume_proposals" in tables:
        op.drop_index("idx_resume_proposals_resume_id", table_name="resume_proposals")
        op.drop_index("ix_resume_proposals_id", table_name="resume_proposals")
        op.drop_table("resume_proposals")


def downgrade() -> None:
    """用于执行数据库回滚迁移。"""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()

    if "resume_proposals" not in tables:
        op.create_table(
            "resume_proposals",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("resume_id", sa.Integer(), nullable=False),
            sa.Column("user_message", sa.Text(), nullable=False),
            sa.Column("section", sa.String(), nullable=True),
            sa.Column("status", sa.String(), nullable=False, server_default="pending"),
            sa.Column("summary", sa.Text(), nullable=True),
            sa.Column("proposed_content", sa.JSON(), nullable=False),
            sa.Column("proposed_patch", sa.JSON(), nullable=True),
            sa.Column("tool_calls", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["resume_id"], ["resumes.id"]),
        )
        op.create_index("ix_resume_proposals_id", "resume_proposals", ["id"], unique=False)
        op.create_index(
            "idx_resume_proposals_resume_id",
            "resume_proposals",
            ["resume_id"],
            unique=False,
        )
