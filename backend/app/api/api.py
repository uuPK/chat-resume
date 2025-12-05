"""
API路由聚合模块

负责聚合和注册所有API端点路由。
提供统一的API入口点管理。
"""

from fastapi import APIRouter
from app.api.endpoints import (
    auth,
    users,
    resumes,
    upload,
    interview,
    interviews,
    export,
    resume_agent as chat,
    tts,
    asr,
)

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(resumes.router, prefix="/resumes", tags=["resumes"])
api_router.include_router(upload.router, prefix="/upload", tags=["upload"])
api_router.include_router(interview.router, prefix="/resumes", tags=["interview"])
api_router.include_router(interviews.router, prefix="/interviews", tags=["interviews"])
api_router.include_router(export.router, prefix="/resumes", tags=["export"])
api_router.include_router(chat.router, prefix="/ai", tags=["chat"])
api_router.include_router(tts.router, prefix="/tts", tags=["tts"])
api_router.include_router(asr.router, prefix="/asr", tags=["asr"])
