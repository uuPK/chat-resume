"""
TTS (Text-to-Speech) API端点
提供文本转语音和语音克隆功能
"""

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
from typing import Optional
from app.infra.database import get_db
from app.services.voice import TTSService
from app.services.voice.tts_service import TTSProvider
from app.entrypoints.http.deps import get_current_user
from pydantic import BaseModel
import tempfile
import os

router = APIRouter()


class TTSRequest(BaseModel):
    """用于承载文本转语音请求参数。"""

    text: str
    voice_id: Optional[str] = "female-tianmei-jingpin"
    emotion: Optional[str] = "neutral"
    model: Optional[str] = "speech-02-turbo"
    format: Optional[str] = "mp3"
    sample_rate: Optional[int] = 32000


class VoiceCloneRequest(BaseModel):
    """用于承载语音克隆请求参数。"""

    voice_name: str = "cloned_voice"


@router.post("/text-to-speech")
async def text_to_speech(
    request: TTSRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """用于把文本转换成可下载的语音文件。"""
    try:
        tts_service = TTSService(TTSProvider.MINIMAX)

        result = await tts_service.synthesize_speech(
            text=request.text,
            voice=request.voice_id or "female-tianmei-jingpin",
            format=request.format or "mp3",
            sample_rate=request.sample_rate or 32000,
        )

        from fastapi.responses import Response

        return Response(
            content=result,
            media_type=f"audio/{request.format or 'mp3'}",
            headers={
                "Content-Disposition": f"attachment; filename=speech.{request.format or 'mp3'}"
            },
        )

    except Exception as e:
        # 如果是余额不足，返回503 Service Unavailable
        if "insufficient balance" in str(e):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"TTS服务不可用: {str(e)}",
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"语音生成失败: {str(e)}",
            )


@router.post("/clone-voice")
async def clone_voice(
    request: VoiceCloneRequest,
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """用于接收用户声音样本并触发语音克隆流程。"""
    try:
        # 验证文件格式
        allowed_formats = ["mp3", "wav", "m4a"]
        if not file.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="文件名不能为空",
            )
        file_extension = file.filename.split(".")[-1].lower()

        if file_extension not in allowed_formats:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"不支持的文件格式。支持的格式: {', '.join(allowed_formats)}",
            )

        # 验证文件大小 (20MB)
        if file.size and file.size > 20 * 1024 * 1024:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="文件大小不能超过20MB"
            )

        # 保存临时文件
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=f".{file_extension}"
        ) as temp_file:
            content = await file.read()
            temp_file.write(content)
            temp_file_path = temp_file.name

        try:
            # TODO: 重新实现语音克隆功能
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail="语音克隆功能暂时不可用",
            )

        finally:
            # 清理临时文件
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"语音克隆失败: {str(e)}",
        )


@router.get("/voices")
async def get_voice_list(
    current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)
):
    """用于返回当前 TTS 服务支持的音色列表。"""
    try:
        tts_service = TTSService(TTSProvider.MINIMAX)

        # TODO: 使用新的get_available_voices方法
        voices = await tts_service.get_available_voices()

        return {"success": True, "data": voices, "message": "获取音色列表成功"}

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取音色列表失败: {str(e)}",
        )



@router.get("/health")
async def health_check():
    """用于返回 TTS 服务的基础健康状态。"""
    try:
        # TODO: 实现健康检查方法
        health_status = {"status": "healthy"}

        # 根据健康状态返回不同的HTTP状态码
        if health_status["status"] == "healthy":
            return {
                "success": True,
                "data": health_status,
                "message": "TTS服务健康检查完成",
            }
        elif health_status["status"] == "error":
            # 如果是余额不足，返回503 Service Unavailable
            if health_status.get("error_type") == "insufficient_balance":
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=f"TTS服务不可用: {health_status['message']}",
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"TTS服务错误: {health_status['message']}",
                )
        else:
            return {
                "success": False,
                "data": health_status,
                "message": "TTS服务状态未知",
            }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"健康检查失败: {str(e)}",
        )
