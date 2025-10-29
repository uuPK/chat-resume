from fastapi import APIRouter, Depends
from app.schemas.auth import UserResponse
from app.api.deps import get_current_user

router = APIRouter()


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: dict = Depends(get_current_user)):
    return UserResponse.model_validate(
        {
            "id": current_user["id"],
            "email": current_user["email"],
            "full_name": current_user["full_name"],
            "is_active": current_user["is_active"],
            "created_at": current_user["created_at"],
        }
    )
