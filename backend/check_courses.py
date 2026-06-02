from sqlalchemy.orm import Session
from app.infra.database import engine
from app.models.school import AICourse

with Session(engine) as session:
    courses = session.query(AICourse).all()
    for c in courses:
        print(f"Course {c.id}: {c.title}, published={c.published}")
