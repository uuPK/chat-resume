"""
主应用入口模块

FastAPI应用的初始化和配置入口点。
负责路由注册、中间件配置、错误处理和启动逻辑。
"""

import logging
from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.entrypoints.http.deps import authenticate_token_with_db
from app.entrypoints.http.router import api_router
from app.infra.config import settings
from app.infra.database import SessionLocal
from app.infra.db_observability import (
    get_request_metrics,
    reset_request_metrics,
    start_request_metrics,
)
from app.infra.langfuse_setup import configure_langfuse, shutdown_langfuse
from app.infra.langsmith_setup import configure_langsmith, shutdown_langsmith
from app.infra.logging_setup import configure_logging
from app.infra.request_context import bind_log_context, reset_log_context
from app.infra.sentry_setup import configure_sentry

configure_logging()
logger = logging.getLogger(__name__)
configure_sentry()
configure_langfuse()
configure_langsmith()


def _truncate_log_value(value: str | None, limit: int = 240) -> str:
    if not value:
        return "-"
    normalized = " ".join(value.split())
    if len(normalized) <= limit:
        return normalized
    return f"{normalized[:limit]}..."


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_STR}/openapi.json",
)

_PROTECTED_API_PREFIXES = (
    f"{settings.API_STR}/resumes",
    f"{settings.API_STR}/interviews",
    f"{settings.API_STR}/upload",
    f"{settings.API_STR}/ai",
    f"{settings.API_STR}/users",
    f"{settings.API_STR}/tts",
    f"{settings.API_STR}/asr",
    f"{settings.API_STR}/digital-human",
)
_AUTH_EXEMPT_PATHS = {
    f"{settings.API_STR}/resumes/download",
}
_SLOW_REQUEST_LOG_MS = 1000.0


def _is_protected_api_path(path: str) -> bool:
    """用于判断请求路径是否属于必须先鉴权的敏感 API。"""
    if path in _AUTH_EXEMPT_PATHS:
        return False
    if any(path.startswith(f"{exempt}/") for exempt in _AUTH_EXEMPT_PATHS):
        return False
    return any(
        path == prefix or path.startswith(f"{prefix}/")
        for prefix in _PROTECTED_API_PREFIXES
    )


def _extract_request_token(request: Request) -> str:
    """用于从请求头或 Cookie 中提取访问令牌。"""
    authorization = request.headers.get("Authorization", "").strip()
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() == "bearer" and token:
        return token
    cookie_token = request.cookies.get(settings.ACCESS_TOKEN_COOKIE_NAME)
    if cookie_token:
        return cookie_token
    raise HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


@app.middleware("http")
async def authenticate_protected_api_requests(request: Request, call_next):
    """用于在进入敏感 API 前统一完成服务端身份鉴权。"""
    path = request.url.path
    if request.method == "OPTIONS" or not _is_protected_api_path(path):
        return await call_next(request)

    db = SessionLocal()
    try:
        token = _extract_request_token(request)
        claims, current_user = authenticate_token_with_db(token, db)
        request.state.current_user_claims = claims
        request.state.current_user = current_user
    except HTTPException as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
            headers=exc.headers,
        )
    finally:
        db.close()

    return await call_next(request)


# 添加中间件来记录请求
@app.middleware("http")
async def log_requests(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or uuid4().hex
    request.state.request_id = request_id
    context_tokens = bind_log_context(request_id=request_id)
    request_started_at = perf_counter()
    metrics_token = start_request_metrics()
    response = None
    try:
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
    finally:
        request_elapsed_ms = (perf_counter() - request_started_at) * 1000
        metrics = get_request_metrics()
        status_code = response.status_code if response is not None else 500
        should_log_request = (
            status_code >= 400 or request_elapsed_ms >= _SLOW_REQUEST_LOG_MS
        )
        if should_log_request and metrics is None:
            logger.info(
                "request.finished",
                extra={
                    "http_method": request.method,
                    "http_path": request.url.path,
                    "http_status": status_code,
                    "request_ms": round(request_elapsed_ms, 2),
                },
            )
        elif should_log_request:
            logger.info(
                "request.finished",
                extra={
                    "http_method": request.method,
                    "http_path": request.url.path,
                    "http_status": status_code,
                    "request_ms": round(request_elapsed_ms, 2),
                    "db_checkout_count": metrics.checkout_count,
                    "db_checkout_ms": round(metrics.checkout_ms_total, 2),
                    "db_query_count": metrics.query_count,
                    "db_query_ms": round(metrics.query_ms_total, 2),
                    "db_longest_query_ms": round(metrics.longest_query_ms, 2),
                    "db_longest_query_sql": _truncate_log_value(
                        metrics.longest_query_statement
                    ),
                },
            )
        reset_request_metrics(metrics_token)
        reset_log_context(context_tokens)


# 数据库迁移由 Railway 的 startCommand 处理
logger.debug("app.starting")

# 从环境变量获取CORS配置
cors_origins = settings.BACKEND_CORS_ORIGINS
logger.debug("cors.config.loaded", extra={"cors_origin_count": len(cors_origins)})

# Cookie 鉴权要求显式 origin，避免浏览器在跨域时丢掉凭证。
configured_origins = [
    origin
    for origin in cors_origins
    if origin and origin != "http://localhost:3000,https://localhost:3000"
]
dev_origins = [
    "http://localhost:3000",
    "https://localhost:3000",
    "http://127.0.0.1:3000",
    "https://127.0.0.1:3000",
]
origin_candidates = configured_origins or [settings.FRONTEND_URL, *dev_origins]
if settings.APP_ENV.strip().lower() == "development":
    origin_candidates = [*origin_candidates, settings.FRONTEND_URL, *dev_origins]
effective_origins = list(
    dict.fromkeys(origin for origin in origin_candidates if origin)
)
logger.debug(
    "cors.config.effective",
    extra={"cors_origin_count": len(effective_origins)},
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=effective_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=86400,
)

app.include_router(api_router, prefix=settings.API_STR)


@app.get("/")
async def root():
    return {"message": "Chat Resume API"}


@app.get("/health")
async def health_check(response: Response):
    from app.infra.database import SessionLocal

    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
        return {"status": "healthy"}
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        response.status_code = 503
        return {"status": "unhealthy", "detail": "database unavailable"}
    finally:
        db.close()


@app.get("/api/test")
async def test_endpoint():
    return {"message": "API is working", "cors": "enabled"}


@app.on_event("startup")
async def log_application_ready():
    logger.info("app.ready")


@app.on_event("shutdown")
async def shutdown_observability_clients():
    shutdown_langfuse()
    shutdown_langsmith()


# 移除手动OPTIONS处理，让CORS中间件自动处理
