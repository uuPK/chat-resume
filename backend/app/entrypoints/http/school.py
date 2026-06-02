from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.infra.database import get_db
from app.entrypoints.http.deps import get_current_user
from app.schemas.school import (
    MarketGapsResponse,
    GenerateCourseRequest,
    PublishCourseRequest,
    AICourseResponse
)
from app.services.domain.school_service import SchoolService

router = APIRouter(prefix="/school", tags=["school"])

def require_school_role(current_user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    if current_user.get("role") != "school":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Requires school role"
        )
    return current_user

@router.get("/market-gaps", response_model=MarketGapsResponse)
async def get_market_gaps(
    db: Session = Depends(get_db),
    current_user: dict[str, Any] = Depends(require_school_role)
):
    service = SchoolService(db)
    return await service.calculate_market_gaps()

@router.post("/generate-course", response_model=AICourseResponse)
def generate_course(
    request: GenerateCourseRequest,
    db: Session = Depends(get_db),
    current_user: dict[str, Any] = Depends(require_school_role)
):
    service = SchoolService(db)
    return service.generate_course(request.target_skills)

@router.get("/courses", response_model=List[AICourseResponse])
def get_courses(
    db: Session = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user)
):
    service = SchoolService(db)
    if current_user.get("role") == "school":
        from app.models.school import AICourse
        return db.query(AICourse).order_by(AICourse.id.desc()).all()
    
    return service.get_published_courses()

@router.post("/publish-course", response_model=AICourseResponse)
def publish_course(
    request: PublishCourseRequest,
    db: Session = Depends(get_db),
    current_user: dict[str, Any] = Depends(require_school_role)
):
    service = SchoolService(db)
    course = service.publish_course(request.course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    return course
