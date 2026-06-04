from app.infra.database import engine
from sqlalchemy import text

with engine.connect() as conn:
    try:
        conn.execute(text("CREATE SEQUENCE IF NOT EXISTS interview_sessions_id_seq OWNED BY interview_sessions.id;"))
        conn.execute(text("SELECT setval('interview_sessions_id_seq', coalesce(max(id), 0) + 1, false) FROM interview_sessions;"))
        conn.execute(text("ALTER TABLE interview_sessions ALTER COLUMN id SET DEFAULT nextval('interview_sessions_id_seq');"))
        
        conn.execute(text("CREATE SEQUENCE IF NOT EXISTS interview_turns_id_seq OWNED BY interview_turns.id;"))
        conn.execute(text("SELECT setval('interview_turns_id_seq', coalesce(max(id), 0) + 1, false) FROM interview_turns;"))
        conn.execute(text("ALTER TABLE interview_turns ALTER COLUMN id SET DEFAULT nextval('interview_turns_id_seq');"))
        conn.commit()
        print("Fixed sequences!")
    except Exception as e:
        print(f"Error: {e}")
