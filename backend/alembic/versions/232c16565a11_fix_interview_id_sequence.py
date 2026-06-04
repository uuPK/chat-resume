"""fix_interview_id_sequence

Revision ID: 232c16565a11
Revises: 718b6f1fd7e9
Create Date: 2026-06-03 16:41:29.959637

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '232c16565a11'
down_revision = '718b6f1fd7e9'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SEQUENCE IF NOT EXISTS interview_sessions_id_seq OWNED BY interview_sessions.id;")
    op.execute("SELECT setval('interview_sessions_id_seq', coalesce(max(id), 0) + 1, false) FROM interview_sessions;")
    op.execute("ALTER TABLE interview_sessions ALTER COLUMN id SET DEFAULT nextval('interview_sessions_id_seq');")
    op.execute("CREATE SEQUENCE IF NOT EXISTS interview_turns_id_seq OWNED BY interview_turns.id;")
    op.execute("SELECT setval('interview_turns_id_seq', coalesce(max(id), 0) + 1, false) FROM interview_turns;")
    op.execute("ALTER TABLE interview_turns ALTER COLUMN id SET DEFAULT nextval('interview_turns_id_seq');")

def downgrade() -> None:
    op.execute("ALTER TABLE interview_sessions ALTER COLUMN id DROP DEFAULT;")
    op.execute("DROP SEQUENCE IF EXISTS interview_sessions_id_seq;")
    op.execute("ALTER TABLE interview_turns ALTER COLUMN id DROP DEFAULT;")
    op.execute("DROP SEQUENCE IF EXISTS interview_turns_id_seq;")