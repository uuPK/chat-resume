"""add resume chat messages table

Revision ID: d4e2f1a3b567
Revises: c3a1f8d4b901
Create Date: 2026-04-06 22:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "d4e2f1a3b567"
down_revision = "c3a1f8d4b901"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()

    if "resume_chat_messages" not in tables:
        op.create_table(
            "resume_chat_messages",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("resume_id", sa.Integer(), nullable=False),
            sa.Column("role", sa.String(), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["resume_id"], ["resumes.id"], ondelete="CASCADE"),
        )
        op.create_index("ix_resume_chat_messages_id", "resume_chat_messages", ["id"])
        op.create_index("idx_resume_chat_messages_resume_id", "resume_chat_messages", ["resume_id"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()
    if "resume_chat_messages" in tables:
        op.drop_index("idx_resume_chat_messages_resume_id", table_name="resume_chat_messages")
        op.drop_index("ix_resume_chat_messages_id", table_name="resume_chat_messages")
        op.drop_table("resume_chat_messages")
