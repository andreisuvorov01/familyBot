from fastapi import FastAPI, Request, status
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from contextlib import asynccontextmanager
import os
import time

from app.core.config import settings
from app.core.database import engine
from app.core.models.base import Base
from app.api.tasks import router as tasks_router
from app.core.security.rate_limiter import rate_limit_middleware
from app.core.logging_config import logger, log_with_context


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan контекст для управления жизненным циклом приложения"""
    logger.info("Starting Family Task API...")

    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables created/verified successfully")
    except Exception as e:
        logger.error(f"Failed to create database tables: {str(e)}")
        raise

    yield

    logger.info("Shutting down Family Task API...")
    await engine.dispose()


# Получаем список разрешённых origins из env
_raw_origins = os.getenv("ALLOWED_ORIGINS", "")
ALLOWED_ORIGINS = [o.strip() for o in _raw_origins.split(",") if o.strip()] or ["*"]

app = FastAPI(
    title="Family Task API",
    version="2.0.0",
    description="API для семейного органайзера",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    # allow_credentials=True нельзя использовать вместе с allow_origins=["*"]
    allow_credentials=len(ALLOWED_ORIGINS) > 0 and ALLOWED_ORIGINS != ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_rate_limiting(request: Request, call_next):
    return await rate_limit_middleware(request, call_next)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()

    if request.url.path.startswith("/static"):
        return await call_next(request)

    logger.info(
        f"Incoming request: {request.method} {request.url.path} - "
        f"Client: {request.client.host if request.client else 'unknown'}"
    )

    try:
        response = await call_next(request)
        process_time = time.time() - start_time
        response.headers["X-Process-Time"] = str(process_time)
        logger.info(
            f"Request completed: {request.method} {request.url.path} - "
            f"Status: {response.status_code} - Time: {process_time:.3f}s"
        )
        return response
    except Exception as e:
        process_time = time.time() - start_time
        logger.error(
            f"Request failed: {request.method} {request.url.path} - "
            f"Error: {str(e)} - Time: {process_time:.3f}s"
        )
        raise


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = []
    for error in exc.errors():
        errors.append({
            "field": ".".join(str(loc) for loc in error["loc"][1:]),
            "message": error["msg"],
            "type": error["type"]
        })
    log_with_context(
        "WARNING",
        f"Validation error: {errors}",
        path=request.url.path,
        method=request.method
    )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": "Validation error", "errors": errors}
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    log_with_context(
        "ERROR",
        f"Unhandled exception: {str(exc)}",
        path=request.url.path,
        method=request.method,
        error_type=type(exc).__name__
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "Internal server error",
            "message": "Something went wrong. Please try again later."
        }
    )


app.include_router(tasks_router)
app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "family-task-api",
        "version": "2.0.0",
        "timestamp": time.time()
    }


@app.get("/")
async def serve_spa():
    return FileResponse("app/static/index.html")


@app.get("/api/info")
async def api_info():
    return {
        "name": "Family Task API",
        "version": "2.0.0",
        "endpoints": {
            "tasks": "/api/tasks",
            "health": "/health",
            "docs": "/docs"
        }
    }
