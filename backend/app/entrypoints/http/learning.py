from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.infra.database import get_db
from app.models.user import User
from app.entrypoints.http.deps import get_current_user
from app.services.domain.learning_service import LearningService
from app.services.domain.school_service import SchoolService

router = APIRouter()

@router.get("/courses")
def get_published_courses(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    school_service = SchoolService(db)
    courses = school_service.get_published_courses()
    return courses

@router.post("/courses/{course_id}/enroll")
def enroll_course(course_id: int, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    school_service = SchoolService(db)
    course = school_service.get_course(course_id)
    if not course or not course.published:
        raise HTTPException(status_code=404, detail="Course not found or not published")
        
    learning_service = LearningService(db)
    enrollment = learning_service.enroll_course(current_user["id"], course_id)
    return {"status": "success", "enrollment_id": enrollment.id}

@router.get("/plan")
def get_learning_plan(db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    learning_service = LearningService(db)
    courses = learning_service.get_user_plan(current_user["id"])
    return courses
