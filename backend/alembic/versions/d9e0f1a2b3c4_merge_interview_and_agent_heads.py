"""合并面试链路与 agent 链路的 Alembic 头结点

Revision ID: d9e0f1a2b3c4
Revises: c3f4e5a6b7c8, f8a9b0c1d2e3
Create Date: 2026-04-19 23:59:00.000000
"""

from typing import Sequence, Union


# 用于标识 Alembic 合并迁移的版本信息。
revision: str = "d9e0f1a2b3c4"
down_revision: Union[str, Sequence[str], None] = ("c3f4e5a6b7c8", "f8a9b0c1d2e3")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """用于把两条迁移分支合并成单一 head。"""
    pass


def downgrade() -> None:
    """用于回滚这条合并迁移本身。"""
    pass
