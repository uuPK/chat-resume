from app.infra.database import engine
from sqlalchemy import text

with engine.connect() as conn:
    print(conn.execute(text("SELECT column_default FROM information_schema.columns WHERE table_name='interview_sessions' AND column_name='id'")).fetchone())
