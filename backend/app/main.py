"""
主应用入口模块

FastAPI应用的初始化和配置入口点。
负责路由注册、中间件配置、错误处理和启动逻辑。
"""

from time import perf_counter

from fastapi import FastAPI, Request, Response
from sqlalchemy import text
from fastapi.middleware.cors import CORSMiddleware
from app.infra.config import settings
from app.infra.db_observability import (
    get_request_metrics,
    reset_request_metrics,
    start_request_metrics,
)
from app.api.api import api_router
from app.infra.database import engine, Base
import logging

# 配置日志格式
log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
logging.basicConfig(
    level=log_level,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
# 第三方 HTTP 库的低级调试日志只在 WARNING 以上才输出
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_STR}/openapi.json",
)


# 添加中间件来记录请求
@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info(f"Request: {request.method} {request.url}")
    request_started_at = perf_counter()
    metrics_token = start_request_metrics()
    response = None
    try:
        response = await call_next(request)
        return response
    finally:
        request_elapsed_ms = (perf_counter() - request_started_at) * 1000
        metrics = get_request_metrics()
        status_code = response.status_code if response is not None else 500
        if metrics is None:
            logger.info(
                "Response: %s request_ms=%.2f",
                status_code,
                request_elapsed_ms,
            )
        else:
            logger.info(
                "Response: %s request_ms=%.2f db_checkout_count=%s db_checkout_ms=%.2f db_query_count=%s db_query_ms=%.2f db_longest_query_ms=%.2f db_longest_query_sql=%s",
                status_code,
                request_elapsed_ms,
                metrics.checkout_count,
                metrics.checkout_ms_total,
                metrics.query_count,
                metrics.query_ms_total,
                metrics.longest_query_ms,
                metrics.longest_query_statement or "-",
            )
        reset_request_metrics(metrics_token)


# 数据库迁移由 Railway 的 startCommand 处理
logger.info("应用启动中...")

# 从环境变量获取CORS配置
cors_origins = settings.BACKEND_CORS_ORIGINS
logger.info(f"CORS Origins from settings: {cors_origins}")
logger.info(f"CORS Origins type: {type(cors_origins)}")

# 如果是生产环境且配置了特定域名，使用特定域名；否则允许所有来源
if (
    cors_origins
    and len(cors_origins) > 0
    and cors_origins != ["http://localhost:3000,https://localhost:3000"]
):
    logger.info("Using specific CORS origins")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["*"],
        max_age=86400,
    )
else:
    logger.info("Using wildcard CORS origins")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
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


# 移除手动OPTIONS处理，让CORS中间件自动处理
