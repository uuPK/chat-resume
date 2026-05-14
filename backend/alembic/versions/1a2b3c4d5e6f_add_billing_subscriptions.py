"""用于定义数据库结构迁移脚本。"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "1a2b3c4d5e6f"
down_revision: Union[str, None] = "0f4e3d2c1b0a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """用于执行数据库升级迁移。"""
    op.create_table(
        "billing_subscriptions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("provider_subscription_id", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("last_provider_event_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("raw_payload", sa.JSON(), nullable=True),
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
            "provider_subscription_id",
            name="uq_billing_subscriptions_provider_subscription",
        ),
    )
    op.create_index(
        op.f("ix_billing_subscriptions_id"),
        "billing_subscriptions",
        ["id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_billing_subscriptions_provider"),
        "billing_subscriptions",
        ["provider"],
        unique=False,
    )
    op.create_index(
        op.f("ix_billing_subscriptions_status"),
        "billing_subscriptions",
        ["status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_billing_subscriptions_user_id"),
        "billing_subscriptions",
        ["user_id"],
        unique=False,
    )
    op.create_table(
        "billing_webhook_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("event_id", sa.String(), nullable=False),
        sa.Column("event_type", sa.String(), nullable=True),
        sa.Column("raw_payload", sa.JSON(), nullable=True),
        sa.Column(
            "received_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "provider",
            "event_id",
            name="uq_billing_webhook_events_provider_event",
        ),
    )
    op.create_index(
        op.f("ix_billing_webhook_events_id"),
        "billing_webhook_events",
        ["id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_billing_webhook_events_provider"),
        "billing_webhook_events",
        ["provider"],
        unique=False,
    )
    op.create_index(
        op.f("ix_billing_webhook_events_event_type"),
        "billing_webhook_events",
        ["event_type"],
        unique=False,
    )


def downgrade() -> None:
    """用于执行数据库回滚迁移。"""
    op.drop_index(
        op.f("ix_billing_webhook_events_event_type"),
        table_name="billing_webhook_events",
    )
    op.drop_index(
        op.f("ix_billing_webhook_events_provider"),
        table_name="billing_webhook_events",
    )
    op.drop_index(
        op.f("ix_billing_webhook_events_id"),
        table_name="billing_webhook_events",
    )
    op.drop_table("billing_webhook_events")
    op.drop_index(
        op.f("ix_billing_subscriptions_user_id"),
        table_name="billing_subscriptions",
    )
    op.drop_index(
        op.f("ix_billing_subscriptions_status"),
        table_name="billing_subscriptions",
    )
    op.drop_index(
        op.f("ix_billing_subscriptions_provider"),
        table_name="billing_subscriptions",
    )
    op.drop_index(
        op.f("ix_billing_subscriptions_id"),
        table_name="billing_subscriptions",
    )
    op.drop_table("billing_subscriptions")
