"""用于定义数据库结构迁移脚本。"""

from alembic import op
import sqlalchemy as sa


revision = "a1b2c3d4e5f6"
down_revision = "f2b1c4d5e6f7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """用于执行数据库升级迁移。"""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    migrate_sessions = "interview_sessions" in tables
    migrate_turns = "interview_turns" in tables

    if migrate_sessions:
        op.execute(
            """
            CREATE TABLE interview_sessions_new (
                id INTEGER NOT NULL PRIMARY KEY,
                user_id INTEGER,
                resume_id INTEGER NOT NULL,
                target_title VARCHAR,
                target_company VARCHAR,
                jd_text TEXT,
                interview_type VARCHAR NOT NULL DEFAULT 'general',
                difficulty VARCHAR NOT NULL DEFAULT 'medium',
                language VARCHAR NOT NULL DEFAULT 'zh-CN',
                mode VARCHAR NOT NULL DEFAULT 'text',
                status VARCHAR NOT NULL DEFAULT 'created',
                current_round_index INTEGER NOT NULL DEFAULT 0,
                current_turn_index INTEGER NOT NULL DEFAULT 0,
                plan_json JSON,
                overall_score INTEGER,
                report_data JSON,
                started_at TIMESTAMP,
                ended_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP,
                FOREIGN KEY(resume_id) REFERENCES resumes (id),
                FOREIGN KEY(user_id) REFERENCES users (id)
            )
            """
        )
        op.execute(
            """
            INSERT INTO interview_sessions_new (
                id, user_id, resume_id, target_title, target_company, jd_text,
                interview_type, difficulty, language, mode, status,
                current_round_index, current_turn_index, plan_json,
                overall_score, report_data, started_at, ended_at,
                created_at, updated_at
            )
            SELECT
                id,
                user_id,
                resume_id,
                target_title,
                target_company,
                COALESCE(jd_text, jd_content),
                COALESCE(interview_type, 'general'),
                COALESCE(difficulty, 'medium'),
                COALESCE(language, 'zh-CN'),
                COALESCE(mode, 'text'),
                COALESCE(status, 'created'),
                COALESCE(current_round_index, 0),
                COALESCE(current_turn_index, 0),
                plan_json,
                overall_score,
                report_data,
                started_at,
                ended_at,
                created_at,
                updated_at
            FROM interview_sessions
            """
        )

    if migrate_turns:
        turn_indexes = {idx["name"] for idx in inspector.get_indexes("interview_turns")}
        if "idx_interview_turns_status" in turn_indexes:
            op.drop_index("idx_interview_turns_status", table_name="interview_turns")
        if "idx_interview_turns_session_turn_index" in turn_indexes:
            op.drop_index("idx_interview_turns_session_turn_index", table_name="interview_turns")
        if "idx_interview_turns_session_id" in turn_indexes:
            op.drop_index("idx_interview_turns_session_id", table_name="interview_turns")

        op.execute(
            f"""
            CREATE TABLE interview_turns_new (
                id INTEGER NOT NULL PRIMARY KEY,
                session_id INTEGER NOT NULL,
                turn_index INTEGER NOT NULL,
                round_index INTEGER NOT NULL DEFAULT 0,
                question TEXT NOT NULL,
                question_type VARCHAR NOT NULL DEFAULT 'general',
                intent TEXT,
                expected_points JSON,
                answer TEXT,
                evaluation JSON,
                score INTEGER,
                follow_up_count INTEGER NOT NULL DEFAULT 0,
                status VARCHAR NOT NULL DEFAULT 'planned',
                asked_at TIMESTAMP,
                answered_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP,
                FOREIGN KEY(session_id) REFERENCES {"interview_sessions_new" if migrate_sessions else "interview_sessions"} (id) ON DELETE CASCADE
            )
            """
        )
        op.execute(
            """
            INSERT INTO interview_turns_new (
                id, session_id, turn_index, round_index, question, question_type,
                intent, expected_points, answer, evaluation, score, follow_up_count,
                status, asked_at, answered_at, created_at, updated_at
            )
            SELECT
                id, session_id, turn_index, COALESCE(round_index, 0), question,
                COALESCE(question_type, 'general'), intent, expected_points, answer,
                evaluation, score, COALESCE(follow_up_count, 0),
                COALESCE(status, 'planned'), asked_at, answered_at, created_at, updated_at
            FROM interview_turns
            """
        )

        op.drop_table("interview_turns")

    if migrate_sessions:
        op.drop_table("interview_sessions")
        op.rename_table("interview_sessions_new", "interview_sessions")
        op.create_index("ix_interview_sessions_id", "interview_sessions", ["id"], unique=False)
        op.create_index("idx_interview_sessions_resume_id", "interview_sessions", ["resume_id"], unique=False)
        op.create_index("idx_interview_sessions_status", "interview_sessions", ["status"], unique=False)
        op.create_index("idx_interview_sessions_resume_status", "interview_sessions", ["resume_id", "status"], unique=False)

    if migrate_turns:
        op.rename_table("interview_turns_new", "interview_turns")
        op.create_index("idx_interview_turns_session_id", "interview_turns", ["session_id"], unique=False)
        op.create_index("idx_interview_turns_session_turn_index", "interview_turns", ["session_id", "turn_index"], unique=True)
        op.create_index("idx_interview_turns_status", "interview_turns", ["status"], unique=False)


def downgrade() -> None:
    """用于执行数据库回滚迁移。"""
    pass
