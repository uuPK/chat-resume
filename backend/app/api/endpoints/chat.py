"""
智能聊天API端点模块

提供与AI助手聊天交互的API端点，包括简历优化建议、面试指导等。
处理自然语言处理和AI服务集成。
"""

from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Dict, Any, cast
from app.services.ai import ChatService
from app.services.core import ResumeService
from app.prompt import ResumePrompts, InterviewPrompts
from app.core.database import get_db
from app.api.deps import get_current_user
import json
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


class ChatRequest(BaseModel):
    """聊天请求模型"""

    message: str
    resume_id: int
    chat_history: list = []  # 聊天历史，可选
    is_interview: bool = False  # 是否为面试模式
    interview_mode: str = (
        "comprehensive"  # 面试模式：comprehensive, technical, behavioral
    )


class ChatResponse(BaseModel):
    """聊天响应模型"""

    response: str
    service: str = "openrouter"
    is_configured: bool = True


@router.post("/chat", response_model=ChatResponse)
async def chat_with_resume(
    chat_request: ChatRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """与AI助手聊天，基于用户真实简历内容"""

    try:
        # 获取用户真实简历数据
        resume_service = ResumeService(db)
        resume = resume_service.get_by_id(chat_request.resume_id)

        # 验证简历存在性和用户权限
        if not resume:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="简历不存在"
            )

        # 调试信息
        logger.debug(f"Resume ID: {chat_request.resume_id}")
        logger.debug(f"Resume owner_id: {resume.owner_id}")
        logger.debug(f"Current user ID: {current_user['id']}")
        logger.debug(f"Current user: {current_user}")

        if resume.owner_id != current_user["id"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"没有权限访问此简历 (简历所有者: {resume.owner_id}, 当前用户: {current_user['id']})",
            )

        # 使用真实简历数据
        resume_content = resume.content

        # 使用新的提示词管理系统，包含聊天历史
        chat_service = ChatService()
        # 显式类型转换：resume.content 是 Column[JSON] 但运行时是 dict
        resume_dict: Dict[str, Any] = cast(
            Dict[str, Any], resume_content if isinstance(resume_content, dict) else {}
        )
        messages = ResumePrompts.build_chat_messages(
            chat_request.message, resume_dict, chat_request.chat_history
        )

        # 调用AI服务
        response = await chat_service._chat_completion_non_stream(messages)

        # 从新服务响应中提取内容
        if chat_service.provider == "gemini":
            ai_response = (
                response.get("candidates", [{}])[0]
                .get("content", {})
                .get("parts", [{}])[0]
                .get("text", "")
            )
        else:
            ai_response = (
                response.get("choices", [{}])[0].get("message", {}).get("content", "")
            )

        return ChatResponse.model_construct(
            response=ai_response, service="openrouter", is_configured=True
        )

    except HTTPException:
        # 重新抛出HTTP异常
        raise
    except Exception as e:
        # 处理其他异常
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"AI服务暂时不可用: {str(e)}",
        )


@router.post("/chat/stream")
async def chat_with_resume_stream(
    chat_request: ChatRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """与AI助手进行流式聊天，基于用户真实简历内容"""

    logger.info("=== 流式聊天API被调用 ===")
    logger.info(f"收到请求 - is_interview: {chat_request.is_interview}")
    logger.info(f"用户消息: {chat_request.message}")

    async def generate_stream():
        try:
            # 获取用户真实简历数据
            resume_service = ResumeService(db)
            resume = resume_service.get_by_id(chat_request.resume_id)

            # 验证简历存在性和用户权限
            if not resume:
                error_data = {"error": "简历不存在", "done": True}
                yield f"data: {json.dumps(error_data, ensure_ascii=False)}\n\n"
                return

            # 调试信息
            logger.debug(f"Stream Resume ID: {chat_request.resume_id}")
            logger.debug(f"Stream Resume owner_id: {resume.owner_id}")
            logger.debug(f"Stream Current user ID: {current_user['id']}")
            logger.debug(f"Stream Current user: {current_user}")

            if resume.owner_id != current_user["id"]:
                error_data = {
                    "error": f"没有权限访问此简历 (简历所有者: {resume.owner_id}, 当前用户: {current_user['id']})",
                    "done": True,
                }
                yield f"data: {json.dumps(error_data, ensure_ascii=False)}\n\n"
                return

            # 使用真实简历数据
            # 显式类型转换：resume.content 是 Column[JSON] 但运行时是 dict
            resume_dict: Dict[str, Any] = cast(
                Dict[str, Any],
                resume.content if isinstance(resume.content, dict) else {},
            )

            chat_service = ChatService()

            # 根据模式构建不同的消息
            logger.debug(f"is_interview: {chat_request.is_interview}")
            logger.debug(f"chat_request: {chat_request}")

            if chat_request.is_interview:
                # 面试模式：使用面试官提示词
                logger.debug(f"使用面试官提示词，模式: {chat_request.interview_mode}")
                messages = InterviewPrompts.build_interview_messages(
                    chat_request.message,
                    resume_dict,
                    chat_request.chat_history,
                    chat_request.interview_mode,
                )
            else:
                # 普通模式：使用简历优化师提示词
                logger.debug("使用简历优化师提示词")
                messages = ResumePrompts.build_chat_messages(
                    chat_request.message, resume_dict, chat_request.chat_history
                )

            # 流式响应
            async for content_chunk in chat_service._chat_completion_stream(messages):
                # 解析流式响应数据
                try:
                    chunk_data = json.loads(content_chunk)
                    # 提取内容
                    if "choices" in chunk_data and chunk_data["choices"]:
                        delta = chunk_data["choices"][0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            data = {"content": content, "done": False}
                            yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
                except json.JSONDecodeError:
                    # 如果无法解析，直接使用原始数据
                    if content_chunk.strip() and content_chunk != "[DONE]":
                        data = {"content": content_chunk, "done": False}
                        yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

            # 发送结束标记
            end_data = {"content": "", "done": True}
            yield f"data: {json.dumps(end_data, ensure_ascii=False)}\n\n"

        except Exception as e:
            # 发送错误信息
            error_data = {"error": f"AI服务暂时不可用: {str(e)}", "done": True}
            yield f"data: {json.dumps(error_data, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "*",
        },
    )


@router.get("/status")
async def get_ai_status():
    """获取AI服务状态"""
    try:
        chat_service = ChatService()
        # 简单的状态检查
        if chat_service.api_key and chat_service.api_key.strip():
            return {
                "service": "openrouter",
                "status": "connected",
                "is_configured": True,
            }
        else:
            return {
                "service": "mock",
                "status": "not_configured",
                "is_configured": False,
            }
    except Exception:
        return {"service": "mock", "status": "error", "is_configured": False}
