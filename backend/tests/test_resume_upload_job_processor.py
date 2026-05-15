"""用于覆盖简历上传解析 Job 模块。"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.infra.database import Base  # noqa: E402
from app.models import ResumeUploadJob, User  # noqa: E402
from app.services.processing.resume_upload_job import (  # noqa: E402
    RESUME_UPLOAD_STATUS_COMPLETED,
    RESUME_UPLOAD_STATUS_FAILED,
    RESUME_UPLOAD_STATUS_PROCESSING,
    ResumeUploadJobProcessor,
)


class FakeFileService:
    """用于模拟文件提取和清理。"""

    def __init__(self, *, extracted_text: str = "简历文本"):
        """保存测试文本和清理记录。"""
        self.extracted_text = extracted_text
        self.extracted: list[tuple[str, str]] = []
        self.deleted: list[str] = []

    def extract_text_from_file(self, file_path: str, filename: str) -> str:
        """记录提取请求并返回固定文本。"""
        self.extracted.append((file_path, filename))
        return self.extracted_text

    def delete_file(self, file_path: str) -> bool:
        """记录清理请求。"""
        self.deleted.append(file_path)
        return True


class FakeParser:
    """用于模拟简历解析器。"""

    model = "fake-parser"

    def __init__(self, *, result: dict[str, Any] | None = None, error: Exception | None = None):
        """保存解析结果或错误。"""
        self.result = result or {
            "personal_info": {"name": "测试用户"},
            "education": [],
            "work_experience": [],
            "projects": [],
            "skills": [],
            "parsing_method": "fake",
            "parsing_quality": 0.9,
        }
        self.error = error
        self.inputs: list[str] = []

    async def parse_resume_text_async(self, text: str) -> dict[str, Any]:
        """记录解析输入并返回固定结果。"""
        self.inputs.append(text)
        if self.error is not None:
            raise self.error
        return self.result


class ResumeUploadJobProcessorTests(unittest.IsolatedAsyncioTestCase):
    """用于验证上传解析 Job 的状态机。"""

    def setUp(self):
        """用于准备内存数据库。"""
        engine = create_engine(
            "sqlite:///:memory:", connect_args={"check_same_thread": False}
        )
        Base.metadata.create_all(bind=engine)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        self.db = self.SessionLocal()

        user = User(email="upload-job@example.com", hashed_password="hashed")
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        self.user = user

    def tearDown(self):
        """用于关闭数据库。"""
        self.db.close()

    def _create_job(self, *, job_id: str, file_path: str | None = "/tmp/resume.txt") -> None:
        """用于创建 queued 上传任务。"""
        self.db.add(
            ResumeUploadJob(
                id=job_id,
                user_id=self.user.id,
                status="queued",
                original_filename="resume.txt",
                file_path=file_path,
            )
        )
        self.db.commit()

    async def test_processor_completes_queued_job(self):
        """用于验证 queued -> processing -> completed 并创建简历。"""
        self._create_job(job_id="job_success")
        file_service = FakeFileService(extracted_text="张三 Python 工程师")
        parser = FakeParser()
        processor = ResumeUploadJobProcessor(
            session_factory=self.SessionLocal,
            file_service_factory=lambda: file_service,
            parser_factory=lambda: parser,
        )

        await processor.process("job_success")

        db = self.SessionLocal()
        try:
            job = db.query(ResumeUploadJob).filter(ResumeUploadJob.id == "job_success").one()
            assert job.status == RESUME_UPLOAD_STATUS_COMPLETED
            assert job.resume_id is not None
            assert job.error is None
            assert file_service.extracted == [("/tmp/resume.txt", "resume.txt")]
            assert file_service.deleted == ["/tmp/resume.txt"]
            assert parser.inputs == ["张三 Python 工程师"]
        finally:
            db.close()

    async def test_processor_marks_failed_job_and_cleans_file(self):
        """用于验证解析失败时写入 failed/error 并清理临时文件。"""
        self._create_job(job_id="job_failed")
        file_service = FakeFileService()
        processor = ResumeUploadJobProcessor(
            session_factory=self.SessionLocal,
            file_service_factory=lambda: file_service,
            parser_factory=lambda: FakeParser(error=RuntimeError("parser exploded")),
        )

        await processor.process("job_failed")

        db = self.SessionLocal()
        try:
            job = db.query(ResumeUploadJob).filter(ResumeUploadJob.id == "job_failed").one()
            assert job.status == RESUME_UPLOAD_STATUS_FAILED
            assert job.resume_id is None
            assert "parser exploded" in str(job.error)
            assert file_service.deleted == ["/tmp/resume.txt"]
        finally:
            db.close()

    async def test_processor_missing_file_path_fails_job(self):
        """用于验证缺少文件路径时任务进入 failed。"""
        self._create_job(job_id="job_missing_path", file_path=None)
        file_service = FakeFileService()
        processor = ResumeUploadJobProcessor(
            session_factory=self.SessionLocal,
            file_service_factory=lambda: file_service,
            parser_factory=lambda: FakeParser(),
        )

        await processor.process("job_missing_path")

        db = self.SessionLocal()
        try:
            job = (
                db.query(ResumeUploadJob)
                .filter(ResumeUploadJob.id == "job_missing_path")
                .one()
            )
            assert job.status == RESUME_UPLOAD_STATUS_FAILED
            assert "Uploaded file path is missing" in str(job.error)
            assert file_service.deleted == []
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()
