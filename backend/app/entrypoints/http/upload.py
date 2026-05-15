"""
文件上传API端点模块

提供文件上传相关的API端点，包括简历文件上传、验证和存储。
处理文件格式检查、大小限制和上传错误处理。
"""

import logging
from time import perf_counter
from typing import NoReturn
from uuid import uuid4

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    UploadFile,
    status,
)
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.entrypoints.http.deps import get_current_user, require_active_subscription
from app.infra.config import settings
from app.infra.database import SessionLocal, get_db
from app.models.resume import ResumeUploadJob
from app.services.domain import FileService, UploadedFileContent
from app.services.errors import (
    ServiceError,
    ServicePayloadTooLargeError,
    ServiceValidationError,
)
from app.services.processing import JDOcrService, ResumeParser
from app.services.processing.resume_upload_job import (
    RESUME_UPLOAD_STATUS_QUEUED,
    ResumeUploadJobProcessor,
)

logger = logging.getLogger(__name__)

router = APIRouter()

_ALLOWED_JD_IMAGE_TYPES = {"image/png", "image/jpeg", "image/jpg", "image/webp"}
_JD_OCR_PROVIDER_REJECTION_DETAIL = (
    "JD 图片识别失败：当前视觉模型请求被供应商拒绝。"
    "请检查 OPENROUTER_VISION_MODEL 是否配置为支持图片输入的模型。"
)


class JDOcrResponse(BaseModel):
    """用于承载 JD 图片 OCR 的识别结果。"""

    text: str


class ResumeUploadJobCreated(BaseModel):
    """用于返回已入队的简历解析任务。"""

    job_id: str
    status: str


class ResumeUploadJobStatus(BaseModel):
    """用于返回简历上传解析任务的当前状态。"""

    job_id: str
    status: str
    resume_id: int | None = None
    error: str | None = None
    original_filename: str


def _raise_service_http_error(exc: ServiceError) -> NoReturn:
    """用于抛出服务HTTP错误。"""
    if isinstance(exc, ServicePayloadTooLargeError):
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=str(exc),
        ) from exc
    if isinstance(exc, ServiceValidationError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=str(exc),
    ) from exc


def _format_jd_ocr_error(exc: Exception) -> str:
    """用于避免把 OpenRouter/provider 原始错误直接暴露到前端。"""
    message = str(exc)
    if (
        "provider Terms Of Service" in message
        or "violation of provider Terms Of Service" in message
        or "AI服务请求失败: 403" in message
    ):
        return _JD_OCR_PROVIDER_REJECTION_DETAIL
    return f"JD 图片识别失败: {message}"


def _is_jd_ocr_provider_rejection(exc: Exception) -> bool:
    """用于判断jdocr提供方拒绝响应。"""
    message = str(exc)
    return (
        "provider Terms Of Service" in message
        or "violation of provider Terms Of Service" in message
        or "AI服务请求失败: 403" in message
    )


def _validate_jd_image(file: UploadFile) -> None:
    """用于校验 JD OCR 上传的图片格式是否受支持。"""
    content_type = (file.content_type or "").lower()
    if content_type not in _ALLOWED_JD_IMAGE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Unsupported image format. "
                "Please upload PNG, JPG, JPEG, or WEBP images."
            ),
        )


def _build_upload_job_status(job: ResumeUploadJob) -> ResumeUploadJobStatus:
    """用于构建上传任务状态。"""
    return ResumeUploadJobStatus(
        job_id=job.id,
        status=job.status,
        resume_id=job.resume_id,
        error=job.error,
        original_filename=job.original_filename,
    )


async def process_resume_upload_job(job_id: str) -> None:
    """用于把后台解析任务委托给上传 Job 模块。"""
    processor = ResumeUploadJobProcessor(
        session_factory=SessionLocal,
        file_service_factory=FileService,
        parser_factory=ResumeParser,
        log=logger,
    )
    await processor.process(job_id)


@router.post(
    "/resume",
    response_model=ResumeUploadJobCreated,
    status_code=status.HTTP_202_ACCEPTED,
)
async def upload_resume(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """用于接收用户上传的简历并创建后台解析任务。"""

    # 验证文件类型
    allowed_extensions = {".pdf", ".docx", ".doc", ".txt"}
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No filename provided.",
        )
    filename = file.filename
    file_extension = filename.split(".")[-1].lower()
    if f".{file_extension}" not in allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Unsupported file format. Please upload PDF, DOCX, DOC, or TXT files."
            ),
        )

    file_service = FileService()
    file_path = None
    request_started_at = perf_counter()
    stage = "validate"

    try:
        stage = "save_file"
        file_content = await file.read()
        file_path = await file_service.save_uploaded_file(
            UploadedFileContent(
                filename=filename,
                content=file_content,
                content_type=file.content_type,
            )
        )

        stage = "create_job"
        job = ResumeUploadJob(
            id=uuid4().hex,
            user_id=current_user["id"],
            status=RESUME_UPLOAD_STATUS_QUEUED,
            original_filename=filename,
            file_path=file_path,
        )
        db.add(job)
        db.commit()
        logger.info(
            "resume_upload.job.created job_id=%s user_id=%s filename=%s total_ms=%.2f",
            job.id,
            current_user["id"],
            filename,
            (perf_counter() - request_started_at) * 1000,
        )
        background_tasks.add_task(process_resume_upload_job, job.id)

        return ResumeUploadJobCreated(
            job_id=job.id,
            status=job.status,
        )

    except ServiceError as e:
        if file_path:
            file_service.delete_file(file_path)
        logger.warning(
            "resume_upload.failed",
            extra={
                "upload_filename": filename,
                "stage": stage,
                "error_type": type(e).__name__,
                "total_ms": round((perf_counter() - request_started_at) * 1000, 2),
            },
        )
        _raise_service_http_error(e)
    except Exception as e:
        if file_path:
            file_service.delete_file(file_path)
        logger.exception(
            "resume_upload.failed",
            extra={
                "upload_filename": filename,
                "stage": stage,
                "error_type": type(e).__name__,
                "total_ms": round((perf_counter() - request_started_at) * 1000, 2),
            },
        )

        # 根据错误类型返回不同的错误信息
        if "数据库" in str(e) or "database" in str(e).lower():
            detail = "数据库保存失败，请稍后重试"
        elif "解析" in str(e) or "parsing" in str(e).lower():
            detail = "简历解析失败，请检查文件格式"
        else:
            detail = f"简历处理失败: {str(e)}"

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=detail
        )


@router.get("/resume-jobs/{job_id}", response_model=ResumeUploadJobStatus)
async def get_resume_upload_job(
    job_id: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """用于查询当前用户的一次简历上传解析任务状态。"""
    job = (
        db.query(ResumeUploadJob)
        .filter(
            ResumeUploadJob.id == job_id,
            ResumeUploadJob.user_id == current_user["id"],
        )
        .first()
    )
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Upload job not found",
        )
    return _build_upload_job_status(job)


@router.post("/jd-ocr", response_model=JDOcrResponse)
async def upload_jd_image_for_ocr(
    file: UploadFile = File(...),
    current_user: dict = Depends(require_active_subscription),
):
    """用于接收 JD 图片并调用视觉模型识别文字。"""
    del current_user
    _validate_jd_image(file)

    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded image is empty.",
        )
    if len(image_bytes) > settings.JD_OCR_MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail="JD image is too large.",
        )

    try:
        ocr_service = JDOcrService()
        text = await ocr_service.extract_text_from_image(
            image_bytes=image_bytes,
            mime_type=(file.content_type or "image/png").lower(),
        )
    except Exception as exc:
        if _is_jd_ocr_provider_rejection(exc):
            logger.warning("JD OCR provider rejected all configured vision models")
        else:
            logger.exception("JD OCR failed")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=_format_jd_ocr_error(exc),
        )

    return JDOcrResponse(text=text)
