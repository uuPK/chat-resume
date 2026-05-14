"""用于定义数据库结构迁移脚本。"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b2c3d4e5f6a1"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """用于执行数据库升级迁移。"""
    op.add_column('resumes', sa.Column('layout_config', sa.JSON(), nullable=True))


def downgrade() -> None:
    """用于执行数据库回滚迁移。"""
    op.drop_column('resumes', 'layout_config')
