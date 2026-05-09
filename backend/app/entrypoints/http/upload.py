"""
文件上传API端点模块

提供文件上传相关的API端点，包括简历文件上传、验证和存储。
处理文件格式检查、大小限制和上传错误处理。
"""

import logging

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.entrypoints.http.deps import get_current_user
from app.infra.config import settings
from app.infra.database import get_db
from app.schemas.resume import ResumeCreate, ResumeResponse
from app.services.domain import FileService, ResumeService
from app.services.processing import JDOcrService, ResumeParser

logger = logging.getLogger(__name__)

router = APIRouter()

_ALLOWED_JD_IMAGE_TYPES = {"image/png", "image/jpeg", "image/jpg", "image/webp"}


class JDOcrResponse(BaseModel):
    """用于承载 JD 图片 OCR 的识别结果。"""

    text: str


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
    file_extension = file.filename.split(".")[-1].lower()
    if f".{file_extension}" not in allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Unsupported file format. Please upload PDF, DOCX, DOC, or TXT files."
            ),
        )

    file_service = None
    file_path = None

    try:
        # 保存文件
        file_service = FileService()
        file_path = await file_service.save_uploaded_file(file)

        # 提取文本
        text = file_service.extract_text_from_file(file_path, file.filename or "")
        logger.info(
            "resume_upload.text_extracted",
            extra={"text_chars": len(text), "upload_filename": file.filename or ""},
        )

        # 解析简历
        parser = ResumeParser()
        logger.info("resume_upload.parse.started")
        resume_data = await parser.parse_resume_text_async(text)
        logger.info(
            "resume_upload.parse.completed",
            extra={
                "parsing_quality": resume_data.get("parsing_quality", 0),
                "parsing_method": resume_data.get("parsing_method", "unknown"),
            },
        )

        # 保存到数据库
        resume_service = ResumeService(db)
        resume_create_data = {
            "title": (file.filename or "").split(".")[0],
            "content": resume_data,
            "original_filename": file.filename,
        }
        resume_create = ResumeCreate.model_validate(resume_create_data)
        logger.info("resume_upload.save.started")
        resume = resume_service.create(resume_create, current_user["id"])
        logger.info("resume_upload.save.completed", extra={"resume_id": resume.id})

        # 清理临时文件
        file_service.delete_file(file_path)

        return ResumeResponse.model_validate(resume, from_attributes=True)

    except Exception as e:
        # 清理临时文件
        if file_service and file_path:
            file_service.delete_file(file_path)

        # 记录详细错误信息
        logger.error(f"简历上传处理失败: {str(e)}")
        logger.error(f"错误类型: {type(e).__name__}")

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
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
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
