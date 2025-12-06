"""添加性能优化索引

Revision ID: add_perf_indexes_001
Revises: a8d672decd64
Create Date: 2025-11-26 10:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# 修订版本标识符
revision = "add_perf_indexes_001"
down_revision = "a8d672decd64"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # Helper to check if index exists
    def index_exists(table_name, index_name):
        indexes = inspector.get_indexes(table_name)
        return any(idx["name"] == index_name for idx in indexes)

    # 为简历查询添加索引（用户获取其简历时频繁使用）
    if not index_exists("resumes", "idx_resumes_owner_id"):
        op.create_index("idx_resumes_owner_id", "resumes", ["owner_id"], unique=False)

    # 为优化记录查询添加索引
    if not index_exists("optimization_records", "idx_optimization_records_resume_id"):
        op.create_index(
            "idx_optimization_records_resume_id",
            "optimization_records",
            ["resume_id"],
            unique=False,
        )

    # 为面试会话的复合查询添加索引（常见：查询特定简历的所有面试）
    if not index_exists("interview_sessions", "idx_interview_sessions_resume_id"):
        op.create_index(
            "idx_interview_sessions_resume_id",
            "interview_sessions",
            ["resume_id"],
            unique=False,
        )

    # 为面试状态查询添加索引（查询活跃/已完成的面试）
    if not index_exists("interview_sessions", "idx_interview_sessions_status"):
        op.create_index(
            "idx_interview_sessions_status",
            "interview_sessions",
            ["status"],
            unique=False,
        )

    # 复合索引：查询特定简历的活跃面试（最常见的查询模式）
    if not index_exists("interview_sessions", "idx_interview_sessions_resume_status"):
        op.create_index(
            "idx_interview_sessions_resume_status",
            "interview_sessions",
            ["resume_id", "status"],
            unique=False,
        )


def downgrade() -> None:
    """移除性能优化索引"""
    op.drop_index("idx_interview_sessions_resume_status")
    op.drop_index("idx_interview_sessions_status")
    op.drop_index("idx_interview_sessions_resume_id")
    op.drop_index("idx_optimization_records_resume_id")
    op.drop_index("idx_resumes_owner_id")
