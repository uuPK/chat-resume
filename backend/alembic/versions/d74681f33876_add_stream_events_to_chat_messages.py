"""add stream_events to chat messages

Revision ID: d74681f33876
Revises: d4e2f1a3b567
Create Date: 2026-04-06 20:51:07.536173

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'd74681f33876'
down_revision = 'd4e2f1a3b567'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'resume_chat_messages',
        sa.Column('stream_events', sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('resume_chat_messages', 'stream_events')
