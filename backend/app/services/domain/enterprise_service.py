from typing import List, Optional
from sqlalchemy.orm import Session
from app.models.enterprise import EnterpriseJob, JobDelivery
from app.schemas.enterprise import EnterpriseJobCreate, EnterpriseJobUpdate, JobDeliveryCreate
from fastapi import HTTPException

class EnterpriseService:
    def __init__(self, db: Session):
        self.db = db

    def create_job(self, enterprise_id: int, job_in: EnterpriseJobCreate) -> EnterpriseJob:
        job = EnterpriseJob(
            enterprise_id=enterprise_id,
            title=job_in.title,
            description=job_in.description,
            skills_required=job_in.skills_required,
            location=job_in.location,
            salary_range=job_in.salary_range,
            is_active=True
        )
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)
        return job

    def get_jobs_by_enterprise(self, enterprise_id: int) -> List[EnterpriseJob]:
        return self.db.query(EnterpriseJob).filter(
            EnterpriseJob.enterprise_id == enterprise_id
        ).order_by(EnterpriseJob.created_at.desc()).all()

    def update_job(self, job_id: int, enterprise_id: int, job_in: EnterpriseJobUpdate) -> EnterpriseJob:
        job = self.db.query(EnterpriseJob).filter(
            EnterpriseJob.id == job_id,
            EnterpriseJob.enterprise_id == enterprise_id
        ).first()
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        
        update_data = job_in.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(job, key, value)
            
        self.db.commit()
        self.db.refresh(job)
        return job

    def get_job(self, job_id: int) -> Optional[EnterpriseJob]:
        return self.db.query(EnterpriseJob).filter(EnterpriseJob.id == job_id).first()

    def create_delivery(self, candidate_id: int, resume_id: int, delivery_in: JobDeliveryCreate) -> JobDelivery:
        # Check if already delivered
        existing = self.db.query(JobDelivery).filter(
            JobDelivery.job_id == delivery_in.job_id,
            JobDelivery.candidate_id == candidate_id
        ).first()
        if existing:
            raise HTTPException(status_code=400, detail="You have already applied for this job.")

        delivery = JobDelivery(
            job_id=delivery_in.job_id,
            candidate_id=candidate_id,
            resume_id=resume_id,
            status="pending"
        )
        self.db.add(delivery)
        self.db.commit()
        self.db.refresh(delivery)
        return delivery

    def get_deliveries_for_enterprise(self, enterprise_id: int) -> List[JobDelivery]:
        return self.db.query(JobDelivery).join(EnterpriseJob).filter(
            EnterpriseJob.enterprise_id == enterprise_id
        ).order_by(JobDelivery.created_at.desc()).all()

    def get_deliveries_for_candidate(self, candidate_id: int) -> List[JobDelivery]:
        return self.db.query(JobDelivery).filter(
            JobDelivery.candidate_id == candidate_id
        ).order_by(JobDelivery.created_at.desc()).all()

    def get_delivery(self, delivery_id: int, enterprise_id: int) -> JobDelivery:
        delivery = self.db.query(JobDelivery).join(EnterpriseJob).filter(
            JobDelivery.id == delivery_id,
            EnterpriseJob.enterprise_id == enterprise_id
        ).first()
        if not delivery:
            raise HTTPException(status_code=404, detail="Delivery not found")
        return delivery
        
    def update_delivery_match(self, delivery: JobDelivery, match_score: int, analysis_result: dict):
        delivery.match_score = match_score
        delivery.analysis_result = analysis_result
        self.db.commit()
        self.db.refresh(delivery)
        return delivery
