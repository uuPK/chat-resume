"""add provider identities

Revision ID: 0f4e3d2c1b0a
Revises: f1a2b3c4d5e6
Create Date: 2026-05-10 16:50:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0f4e3d2c1b0a"
down_revision: Union[str, None] = "f1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """用于支持第三方登录身份绑定和无密码本地用户。"""
    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column(
            "hashed_password",
            existing_type=sa.String(),
            nullable=True,
        )

    op.create_table(
        "provider_identities",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("provider_user_id", sa.String(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("provider_email", sa.String(), nullable=False),
        sa.Column("provider_email_verified", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=True,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "provider",
            "provider_user_id",
            name="uq_provider_identities_provider_user_id",
        ),
    )
    op.create_index(
        op.f("ix_provider_identities_id"),
        "provider_identities",
        ["id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_provider_identities_provider"),
        "provider_identities",
        ["provider"],
        unique=False,
    )
    op.create_index(
        op.f("ix_provider_identities_provider_email"),
        "provider_identities",
        ["provider_email"],
        unique=False,
    )
    op.create_index(
        op.f("ix_provider_identities_user_id"),
        "provider_identities",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    """用于回滚第三方登录身份绑定表。"""
    op.drop_index(
        op.f("ix_provider_identities_user_id"),
        table_name="provider_identities",
    )
    op.drop_index(
        op.f("ix_provider_identities_provider_email"),
        table_name="provider_identities",
    )
    op.drop_index(
        op.f("ix_provider_identities_provider"),
        table_name="provider_identities",
    )
    op.drop_index(
        op.f("ix_provider_identities_id"),
        table_name="provider_identities",
    )
    op.drop_table("provider_identities")

    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column(
            "hashed_password",
            existing_type=sa.String(),
            nullable=False,
        )
