"""用于定义数据库结构迁移脚本。"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'd74681f33876'
down_revision = 'd4e2f1a3b567'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """用于执行数据库升级迁移。"""
    op.add_column(
        'resume_chat_messages',
        sa.Column('stream_events', sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    """用于执行数据库回滚迁移。"""
    op.drop_column('resume_chat_messages', 'stream_events')
