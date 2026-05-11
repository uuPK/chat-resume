"""add resume upload jobs

Revision ID: 2b4c6d8e0f12
Revises: 1a2b3c4d5e6f
Create Date: 2026-05-11 11:20:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "2b4c6d8e0f12"
down_revision: Union[str, None] = "1a2b3c4d5e6f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "resume_upload_jobs",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("original_filename", sa.String(), nullable=False),
        sa.Column("file_path", sa.String(), nullable=True),
        sa.Column("resume_id", sa.Integer(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=True,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["resume_id"], ["resumes.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_resume_upload_jobs_resume_id"),
        "resume_upload_jobs",
        ["resume_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_resume_upload_jobs_status"),
        "resume_upload_jobs",
        ["status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_resume_upload_jobs_user_id"),
        "resume_upload_jobs",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_resume_upload_jobs_user_id"), table_name="resume_upload_jobs"
    )
    op.drop_index(op.f("ix_resume_upload_jobs_status"), table_name="resume_upload_jobs")
    op.drop_index(
        op.f("ix_resume_upload_jobs_resume_id"), table_name="resume_upload_jobs"
    )
    op.drop_table("resume_upload_jobs")
