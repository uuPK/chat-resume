from sqlalchemy.orm import Session
from app.models.learning import CandidateCourseEnrollment
from app.models.school import AICourse

class LearningService:
    def __init__(self, db: Session):
        self.db = db

    def enroll_course(self, user_id: int, course_id: int) -> CandidateCourseEnrollment:
        # Check if already enrolled
        enrollment = self.db.query(CandidateCourseEnrollment).filter_by(
            user_id=user_id, course_id=course_id
        ).first()
        
        if not enrollment:
            enrollment = CandidateCourseEnrollment(user_id=user_id, course_id=course_id)
            self.db.add(enrollment)
            self.db.commit()
            self.db.refresh(enrollment)
            
        return enrollment

    def get_user_plan(self, user_id: int) -> list[AICourse]:
        # Returns courses the user is enrolled in
        enrollments = self.db.query(CandidateCourseEnrollment).filter_by(user_id=user_id).all()
        course_ids = [e.course_id for e in enrollments]
        
        if not course_ids:
            return []
            
        return self.db.query(AICourse).filter(AICourse.id.in_(course_ids)).all()
