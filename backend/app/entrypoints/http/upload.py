"""
文件上传API端点模块

提供文件上传相关的API端点，包括简历文件上传、验证和存储。
处理文件格式检查、大小限制和上传错误处理。
"""

import logging
from time import perf_counter
from typing import NoReturn

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.entrypoints.http.deps import get_current_user
from app.infra.config import settings
from app.infra.database import get_db
from app.schemas.resume import ResumeCreate, ResumeResponse
from app.services.domain import FileService, ResumeService, UploadedFileContent
from app.services.errors import (
    ServiceError,
    ServicePayloadTooLargeError,
    ServiceValidationError,
)
from app.services.processing import JDOcrService, ResumeParser

logger = logging.getLogger(__name__)

router = APIRouter()

_ALLOWED_JD_IMAGE_TYPES = {"image/png", "image/jpeg", "image/jpg", "image/webp"}


class JDOcrResponse(BaseModel):
    """用于承载 JD 图片 OCR 的识别结果。"""

    text: str


def _raise_service_http_error(exc: ServiceError) -> NoReturn:
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


@router.post("/resume", response_model=ResumeResponse)
async def upload_resume(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """用于接收用户上传的简历并完成解析入库。"""

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

    file_service = None
    file_path = None
    request_started_at = perf_counter()
    stage = "validate"

    try:
        # 保存文件
        stage = "save_file"
        file_service = FileService()
        file_content = await file.read()
        file_path = await file_service.save_uploaded_file(
            UploadedFileContent(
                filename=filename,
                content=file_content,
                content_type=file.content_type,
            )
        )

        # 提取文本
        stage = "extract_text"
        extract_started_at = perf_counter()
        text = file_service.extract_text_from_file(file_path, filename)
        extract_elapsed_ms = (perf_counter() - extract_started_at) * 1000

        # 解析简历
        stage = "parse_resume"
        parser = ResumeParser()
        logger.info(
            "resume_upload.parse.started",
            extra={
                "upload_filename": filename,
                "file_bytes": len(file_content),
                "text_chars": len(text),
                "model": parser.model,
            },
        )
        parse_started_at = perf_counter()
        resume_data = await parser.parse_resume_text_async(text)
        parse_elapsed_ms = (perf_counter() - parse_started_at) * 1000

        # 保存到数据库
        stage = "save_resume"
        save_started_at = perf_counter()
        resume_service = ResumeService(db)
        resume_create_data = {
            "title": filename.split(".")[0],
            "content": resume_data,
            "original_filename": filename,
        }
        resume_create = ResumeCreate.model_validate(resume_create_data)
        resume = resume_service.create(resume_create, current_user["id"])
        save_elapsed_ms = (perf_counter() - save_started_at) * 1000
        total_elapsed_ms = (perf_counter() - request_started_at) * 1000
        logger.info(
            "resume_upload.completed",
            extra={
                "resume_id": resume.id,
                "upload_filename": filename,
                "model": parser.model,
                "parsing_method": resume_data.get("parsing_method", "unknown"),
                "parsing_quality": resume_data.get("parsing_quality", 0),
                "extract_ms": round(extract_elapsed_ms, 2),
                "parse_ms": round(parse_elapsed_ms, 2),
                "save_ms": round(save_elapsed_ms, 2),
                "total_ms": round(total_elapsed_ms, 2),
            },
        )

        # 清理临时文件
        stage = "cleanup_file"
        file_service.delete_file(file_path)

        return ResumeResponse.model_validate(resume, from_attributes=True)

    except ServiceError as e:
        # 清理临时文件
        if file_service and file_path:
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
        # 清理临时文件
        if file_service and file_path:
            file_service.delete_file(file_path)

        # 记录详细错误信息
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


@router.post("/jd-ocr", response_model=JDOcrResponse)
async def upload_jd_image_for_ocr(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
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
        logger.exception("JD OCR failed")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"JD 图片识别失败: {exc}",
        )

    return JDOcrResponse(text=text)
