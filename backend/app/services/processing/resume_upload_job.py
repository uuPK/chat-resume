"""用于处理简历上传后的后台解析 Job。"""

from __future__ import annotations

import logging
from collections.abc import Callable
from time import perf_counter
from typing import Any, Protocol

from sqlalchemy.orm import Session

from app.infra.database import SessionLocal
from app.models.resume import ResumeUploadJob
from app.schemas.resume import ResumeCreate
from app.services.domain import FileService, ResumeService
from app.services.errors import ServiceValidationError
from app.services.processing.resume_parser import ResumeParser

RESUME_UPLOAD_STATUS_QUEUED = "queued"
RESUME_UPLOAD_STATUS_PROCESSING = "processing"
RESUME_UPLOAD_STATUS_COMPLETED = "completed"
RESUME_UPLOAD_STATUS_FAILED = "failed"

logger = logging.getLogger(__name__)


class ResumeUploadFileAdapter(Protocol):
    """用于描述上传 Job 需要的文件操作。"""

    def extract_text_from_file(self, file_path: str, filename: str) -> str:
        """从已保存文件提取文本。"""
        ...

    def delete_file(self, file_path: str) -> bool:
        """删除已保存文件。"""
        ...


class ResumeTextParser(Protocol):
    """用于描述上传 Job 需要的简历解析器。"""

    model: str

    async def parse_resume_text_async(self, text: str) -> dict[str, Any]:
        """解析简历文本为结构化内容。"""
        ...


class ResumeUploadJobProcessor:
    """用于拥有简历上传解析任务的状态转移、解析和清理规则。"""

    def __init__(
        self,
        *,
        session_factory: Callable[[], Session] = SessionLocal,
        file_service_factory: Callable[[], ResumeUploadFileAdapter] = FileService,
        parser_factory: Callable[[], ResumeTextParser] = ResumeParser,
        log: logging.Logger | None = None,
    ):
        """用于初始化后台 Job 依赖。"""
        self.session_factory = session_factory
        self.file_service_factory = file_service_factory
        self.parser_factory = parser_factory
        self.logger = log or logger

    async def process(self, job_id: str) -> None:
        """后台解析已保存的简历文件，并把完成状态写回任务表。"""
        db = self.session_factory()
        file_service = self.file_service_factory()
        request_started_at = perf_counter()
        stage = "load_job"
        job = self._load_job(db, job_id)
        if job is None:
            db.close()
            return

        try:
            self._mark_processing(db, job)
            filename = job.original_filename
            file_path = job.file_path
            if not file_path:
                raise ServiceValidationError("Uploaded file path is missing")

            stage = "extract_text"
            extract_started_at = perf_counter()
            text = file_service.extract_text_from_file(file_path, filename)
            extract_elapsed_ms = (perf_counter() - extract_started_at) * 1000

            stage = "parse_resume"
            parser = self.parser_factory()
            self.logger.info(
                "resume_upload.parse.started model=%s job_id=%s",
                parser.model,
                job_id,
            )
            parse_started_at = perf_counter()
            resume_data = await parser.parse_resume_text_async(text)
            parse_elapsed_ms = (perf_counter() - parse_started_at) * 1000

            stage = "save_resume"
            save_started_at = perf_counter()
            resume = self._create_resume(
                db=db,
                user_id=job.user_id,
                filename=filename,
                resume_data=resume_data,
            )
            save_elapsed_ms = (perf_counter() - save_started_at) * 1000

            self._mark_completed(db, job, resume_id=int(resume.id))
            self._log_completed(
                parser=parser,
                job_id=job_id,
                resume_id=int(resume.id),
                resume_data=resume_data,
                extract_elapsed_ms=extract_elapsed_ms,
                parse_elapsed_ms=parse_elapsed_ms,
                save_elapsed_ms=save_elapsed_ms,
                request_started_at=request_started_at,
            )
        except Exception as exc:
            self.logger.exception(
                "resume_upload.job.failed",
                extra={
                    "job_id": job_id,
                    "stage": stage,
                    "error_type": type(exc).__name__,
                    "total_ms": round((perf_counter() - request_started_at) * 1000, 2),
                },
            )
            db.rollback()
            self._mark_failed(db, job, error=str(exc))
        finally:
            try:
                if job.file_path:
                    file_service.delete_file(job.file_path)
            finally:
                db.close()

    def _load_job(self, db: Session, job_id: str) -> ResumeUploadJob | None:
        """用于读取待处理上传任务。"""
        job = db.query(ResumeUploadJob).filter(ResumeUploadJob.id == job_id).first()
        if job is None:
            self.logger.warning("resume_upload.job.missing job_id=%s", job_id)
        return job

    @staticmethod
    def _mark_processing(db: Session, job: ResumeUploadJob) -> None:
        """用于把任务标记为 processing。"""
        job.status = RESUME_UPLOAD_STATUS_PROCESSING
        job.error = None
        db.add(job)
        db.commit()

    @staticmethod
    def _mark_completed(
        db: Session,
        job: ResumeUploadJob,
        *,
        resume_id: int,
    ) -> None:
        """用于把任务标记为 completed。"""
        job.status = RESUME_UPLOAD_STATUS_COMPLETED
        job.resume_id = resume_id
        job.error = None
        db.add(job)
        db.commit()

    @staticmethod
    def _mark_failed(db: Session, job: ResumeUploadJob, *, error: str) -> None:
        """用于把任务标记为 failed。"""
        job.status = RESUME_UPLOAD_STATUS_FAILED
        job.error = error
        db.add(job)
        db.commit()

    @staticmethod
    def _create_resume(
        *,
        db: Session,
        user_id: int,
        filename: str,
        resume_data: dict[str, Any],
    ) -> Any:
        """用于把解析结果创建为简历记录。"""
        resume_service = ResumeService(db)
        resume_create = ResumeCreate.model_validate(
            {
                "title": filename.rsplit(".", 1)[0],
                "content": resume_data,
                "original_filename": filename,
            }
        )
        return resume_service.create(resume_create, user_id)

    def _log_completed(
        self,
        *,
        parser: ResumeTextParser,
        job_id: str,
        resume_id: int,
        resume_data: dict[str, Any],
        extract_elapsed_ms: float,
        parse_elapsed_ms: float,
        save_elapsed_ms: float,
        request_started_at: float,
    ) -> None:
        """用于记录 Job 成功完成的阶段耗时。"""
        total_elapsed_ms = (perf_counter() - request_started_at) * 1000
        self.logger.info(
            (
                "resume_upload.completed model=%s job_id=%s resume_id=%s method=%s "
                "quality=%s extract_ms=%.2f parse_ms=%.2f save_ms=%.2f total_ms=%.2f"
            ),
            parser.model,
            job_id,
            resume_id,
            resume_data.get("parsing_method", "unknown"),
            resume_data.get("parsing_quality", 0),
            extract_elapsed_ms,
            parse_elapsed_ms,
            save_elapsed_ms,
            total_elapsed_ms,
        )


__all__ = [
    "RESUME_UPLOAD_STATUS_COMPLETED",
    "RESUME_UPLOAD_STATUS_FAILED",
    "RESUME_UPLOAD_STATUS_PROCESSING",
    "RESUME_UPLOAD_STATUS_QUEUED",
    "ResumeUploadJobProcessor",
]
