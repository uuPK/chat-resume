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
from app.services.ai import ChatService, ResumeAgent
from app.services.core import ResumeService
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
    tool_calls: list = []  # 工具调用列表


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
        # 显式类型转换
        resume_dict: Dict[str, Any] = cast(
            Dict[str, Any], resume_content if isinstance(resume_content, dict) else {}
        )

        # 使用简历优化 Agent（支持工具调用）
        agent = ResumeAgent()
        ai_result = await agent.optimize(
            user_message=chat_request.message,
            resume_content=resume_dict,
            conversation_history=chat_request.chat_history,
        )

        # 检查是否有简历更新
        if isinstance(ai_result, dict) and "resume_content" in ai_result:
            logger.info(f"检测到简历更新，正在保存... 简历ID: {chat_request.resume_id}")
            try:
                updated_content = ai_result["resume_content"]
                resume_service.update(
                    chat_request.resume_id, {"content": updated_content}
                )
                logger.info("简历更新保存成功")
            except Exception as e:
                logger.error(f"保存简历更新失败: {e}")

        content = (
            ai_result.get("content") if isinstance(ai_result, dict) else str(ai_result)
        )
        tool_calls = (
            ai_result.get("tool_calls", []) if isinstance(ai_result, dict) else []
        )

        return ChatResponse.model_construct(
            response=content,
            service="openrouter",
            is_configured=True,
            tool_calls=tool_calls,
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

    agent = ResumeAgent()

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

            # 调用简历优化 Agent 获取阶段流式回复
            logger.debug("流式接口使用简历优化 Agent")
            latest_resume_content = None
            async for event in agent.optimize_stream(
                user_message=chat_request.message,
                resume_content=resume_dict,
                conversation_history=chat_request.chat_history,
            ):
                if event.get("resume_content") is not None:
                    latest_resume_content = event["resume_content"]
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

            if latest_resume_content is not None:
                logger.info(
                    f"检测到简历更新，正在保存... 简历ID: {chat_request.resume_id}"
                )
                try:
                    resume_service.update(
                        chat_request.resume_id, {"content": latest_resume_content}
                    )
                    logger.info("简历更新保存成功")
                except Exception as e:
                    logger.error(f"保存简历更新失败: {e}")

            # 发送结束标记
            end_data = {"content": "", "qr_images": [], "tool_calls": [], "done": True}
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


@router.get("/boss/status")
async def get_boss_status(
    current_user: dict = Depends(get_current_user),
):
    """获取Boss直聘登录状态"""
    try:
        from app.services.ai.resume_tools.boss_client import get_login_status

        return get_login_status()
    except Exception as e:
        logger.error(f"获取Boss状态失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取状态失败: {str(e)}",
        )
