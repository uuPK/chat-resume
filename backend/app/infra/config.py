"""
应用配置管理模块

负责加载和管理所有应用配置，包括数据库连接、JWT密钥、API密钥等。
使用Pydantic BaseSettings进行配置验证和环境变量读取。
"""

from typing import List, Union
from pydantic import field_validator
from pydantic_settings import BaseSettings
import os


class Settings(BaseSettings):
    PROJECT_NAME: str = "Chat Resume API"
    VERSION: str = "1.0.0"
    API_STR: str = "/api"
    APP_ENV: str = os.getenv(
        "APP_ENV",
        os.getenv("NODE_ENV", os.getenv("RAILWAY_ENVIRONMENT_NAME", "development")),
    )

    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FORMAT: str = os.getenv("LOG_FORMAT", "text")

    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./chat_resume.db")

    # Redis
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379")

    # Security
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-secret-key-here")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8  # 8 days

    # CORS
    BACKEND_CORS_ORIGINS: Union[str, List[str]] = (
        "http://localhost:3000,https://localhost:3000"
    )

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, list):
            return v
        return []

    # OpenRouter API
    OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")
    OPENROUTER_API_BASE: str = os.getenv(
        "OPENROUTER_API_BASE", "https://openrouter.ai/api/v1"
    )
    OPENROUTER_MODEL: str = os.getenv("OPENROUTER_MODEL", "google/gemini-2.5-flash")
    OPENROUTER_VISION_MODEL: str = os.getenv(
        "OPENROUTER_VISION_MODEL",
        os.getenv("OPENROUTER_MODEL", "google/gemini-2.5-flash"),
    )
    OPENROUTER_CONNECT_TIMEOUT_SECONDS: float = float(
        os.getenv("OPENROUTER_CONNECT_TIMEOUT_SECONDS", "15")
    )
    OPENROUTER_READ_TIMEOUT_SECONDS: float = float(
        os.getenv("OPENROUTER_READ_TIMEOUT_SECONDS", "90")
    )
    OPENROUTER_WRITE_TIMEOUT_SECONDS: float = float(
        os.getenv("OPENROUTER_WRITE_TIMEOUT_SECONDS", "30")
    )
    OPENROUTER_MAX_RETRIES: int = int(os.getenv("OPENROUTER_MAX_RETRIES", "2"))
    OPENROUTER_RETRY_BACKOFF_SECONDS: float = float(
        os.getenv("OPENROUTER_RETRY_BACKOFF_SECONDS", "1.5")
    )

    # MiniMax TTS API
    MINIMAX_API_KEY: str = os.getenv("MINIMAX_API_KEY", "")
    MINIMAX_API_BASE: str = os.getenv("MINIMAX_API_BASE", "https://api.minimaxi.com")
    MINIMAX_GROUP_ID: str = os.getenv("MINIMAX_GROUP_ID", "")

    # 火山引擎大模型流式语音识别API
    VOLCENGINE_APP_KEY: str = os.getenv("VOLCENGINE_APP_KEY", "")
    VOLCENGINE_ACCESS_TOKEN: str = os.getenv("VOLCENGINE_ACCESS_TOKEN", "")
    VOLCENGINE_ASR_RESOURCE_ID: str = os.getenv(
        "VOLCENGINE_ASR_RESOURCE_ID", "volc.bigasr.sauc.duration"
    )

    # 火山引擎ASR API
    VOLCENGINE_ASR_API_KEY: str = os.getenv("VOLCENGINE_ASR_API_KEY", "")
    VOLCENGINE_ASR_APP_ID: str = os.getenv("VOLCENGINE_ASR_APP_ID", "")

    # 火山引擎大模型ASR API
    VOLCENGINE_BIGMODEL_API_KEY: str = os.getenv("VOLCENGINE_BIGMODEL_API_KEY", "")
    VOLCENGINE_BIGMODEL_APP_ID: str = os.getenv("VOLCENGINE_BIGMODEL_APP_ID", "")

    # 火山引擎TTS API
    VOLCENGINE_TTS_API_KEY: str = os.getenv("VOLCENGINE_TTS_API_KEY", "")
    VOLCENGINE_TTS_APP_ID: str = os.getenv("VOLCENGINE_TTS_APP_ID", "")

    # File upload
    UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", "uploads")
    MAX_FILE_SIZE: int = 50 * 1024 * 1024  # 50MB
    JD_OCR_MAX_FILE_SIZE: int = int(os.getenv("JD_OCR_MAX_FILE_SIZE", str(10 * 1024 * 1024)))
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:3000")

    # Observability
    SENTRY_DSN: str = os.getenv("SENTRY_DSN", "")
    SENTRY_ENVIRONMENT: str = os.getenv(
        "SENTRY_ENVIRONMENT",
        os.getenv("RAILWAY_ENVIRONMENT_NAME", "development"),
    )
    SENTRY_RELEASE: str = os.getenv(
        "SENTRY_RELEASE",
        os.getenv("RAILWAY_GIT_COMMIT_SHA", ""),
    )
    SENTRY_TRACES_SAMPLE_RATE: float = float(
        os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.1")
    )
    SENTRY_SEND_DEFAULT_PII: bool = (
        os.getenv("SENTRY_SEND_DEFAULT_PII", "false").strip().lower() == "true"
    )
    LANGFUSE_PUBLIC_KEY: str = os.getenv("LANGFUSE_PUBLIC_KEY", "")
    LANGFUSE_SECRET_KEY: str = os.getenv("LANGFUSE_SECRET_KEY", "")
    LANGFUSE_HOST: str = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")
    LANGFUSE_SAMPLE_RATE: float = float(os.getenv("LANGFUSE_SAMPLE_RATE", "1.0"))
    LANGFUSE_DEBUG: bool = (
        os.getenv("LANGFUSE_DEBUG", "false").strip().lower() == "true"
    )

    model_config = {"case_sensitive": True, "env_file": ".env", "extra": "ignore"}


settings = Settings.model_validate({})
