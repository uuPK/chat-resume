"""
用户业务逻辑服务模块

提供用户相关的核心业务逻辑，包括用户注册、认证、信息管理等功能。
处理用户数据验证和安全性检查。
"""

from sqlalchemy.orm import Session
from typing import Optional
from app.models.user import User
from app.schemas.auth import UserCreate, UserUpdate
from app.core.security import get_password_hash, verify_password


class UserService:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, user_id: int) -> Optional[User]:
        return self.db.query(User).filter(User.id == user_id).first()

    def get_by_email(self, email: str) -> Optional[User]:
        return self.db.query(User).filter(User.email == email).first()

    def create(self, user_create: UserCreate) -> User:
        hashed_password = get_password_hash(user_create.password)
        user = User(
            email=user_create.email,
            hashed_password=hashed_password,
            full_name=user_create.full_name,
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def authenticate(self, email: str, password: str) -> Optional[User]:
        user = self.get_by_email(email)
        if not user:
            return None
        if not verify_password(password, str(user.hashed_password)):
            return None
        return user

    def update(self, user_id: int, user_update: UserUpdate) -> Optional[User]:
        """更新用户信息"""
        user = self.get_by_id(user_id)
        if not user:
            return None

        # 更新用户信息
        if user_update.full_name is not None:
            user.full_name = user_update.full_name

        self.db.commit()
        self.db.refresh(user)
        return user
