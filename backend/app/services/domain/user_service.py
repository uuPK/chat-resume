"""
用户业务逻辑服务模块

提供用户相关的核心业务逻辑，包括用户注册、认证、信息管理等功能。
处理用户数据验证和安全性检查。
"""

from typing import Optional

from sqlalchemy.orm import Session

from app.infra.security import get_password_hash, verify_password
from app.models.user import User
from app.schemas.auth import UserCreate, UserUpdate


class UserService:
    """用于封装用户的注册、查询和认证逻辑。"""

    def __init__(self, db: Session):
        """用于保存当前请求复用的数据库会话。"""
        self.db = db

    def get_by_id(self, user_id: int) -> Optional[User]:
        """用于按主键查询单个用户。"""
        return self.db.query(User).filter(User.id == user_id).first()

    def get_by_email(self, email: str) -> Optional[User]:
        """用于按邮箱查询单个用户。"""
        return self.db.query(User).filter(User.email == email).first()

    def create(self, user_create: UserCreate) -> User:
        """用于创建一个带密码哈希的新用户。"""
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
        """用于校验邮箱密码并拦截已禁用账号。"""
        user = self.get_by_email(email)
        if not user:
            return None
        if not user.is_active:
            return None
        if not user.hashed_password:
            return None
        if not verify_password(password, user.hashed_password):
            return None
        return user

    def update(self, user_id: int, user_update: UserUpdate) -> Optional[User]:
        """用于更新用户的可编辑基础资料。"""
        user = self.get_by_id(user_id)
        if not user:
            return None

        # 更新用户信息
        if user_update.full_name is not None:
            setattr(user, "full_name", user_update.full_name)

        self.db.commit()
        self.db.refresh(user)
        return user
