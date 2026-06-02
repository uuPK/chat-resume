import sys
from sqlalchemy import text
from app.infra.database import engine

def create_table():
    with engine.connect() as conn:
        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS ai_courses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title VARCHAR(200) NOT NULL,
            description TEXT,
            target_skills TEXT,
            outline TEXT,
            published BOOLEAN DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """))
        conn.commit()
        print("ai_courses table created.")

if __name__ == "__main__":
    create_table()
