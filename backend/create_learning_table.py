import sys
from sqlalchemy import text
from app.infra.database import engine

def create_table():
    with engine.connect() as conn:
        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS candidate_course_enrollments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            course_id INTEGER NOT NULL,
            status VARCHAR(50) DEFAULT 'in_progress',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id),
            FOREIGN KEY(course_id) REFERENCES ai_courses(id)
        )
        """))
        conn.commit()
        print("candidate_course_enrollments table created.")

if __name__ == "__main__":
    create_table()
