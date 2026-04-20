"""用于提供用户资料读取接口。"""

from fastapi import APIRouter, Depends

from app.entrypoints.http.deps import get_current_user
from app.schemas.auth import UserResponse

router = APIRouter()


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: dict = Depends(get_current_user)):
    """用于返回当前用户资料，给轻量用户页复用。"""
    return UserResponse.model_validate(
        {
            "id": current_user["id"],
            "email": current_user["email"],
            "full_name": current_user["full_name"],
            "is_active": current_user["is_active"],
            "created_at": current_user["created_at"],
        }
    )
