from fastapi import FastAPI, Request, status
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from contextlib import asynccontextmanager
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
    # Startup
    logger.info("Starting Family Task API...")
    
    try:
        # Создание таблиц БД
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables created successfully")
        
    except Exception as e:
        logger.error(f"Failed to create database tables: {str(e)}")
        raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down Family Task API...")
    await engine.dispose()


# Инициализация приложения
app = FastAPI(
    title="Family Task API",
    version="2.0.0",
    description="API для семейного органайзера с улучшенной безопасностью и производительностью",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # В продакшене заменить на конкретные домены
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate limiting middleware
@app.middleware("http")
async def add_rate_limiting(request: Request, call_next):
    return await rate_limit_middleware(request, call_next)


# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Middleware для логирования запросов"""
    start_time = time.time()
    
    # Пропускаем статические файлы
    if request.url.path.startswith("/static"):
        return await call_next(request)
    
    # Логируем входящий запрос
    logger.info(
        f"Incoming request: {request.method} {request.url.path} - "
        f"Client: {request.client.host if request.client else 'unknown'}"
    )
    
    try:
        response = await call_next(request)
        process_time = time.time() - start_time
        
        # Добавляем заголовок с временем обработки
        response.headers["X-Process-Time"] = str(process_time)
        
        # Логируем успешный ответ
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


# Обработка ошибок валидации
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Обработчик ошибок валидации"""
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
        content={
            "detail": "Validation error",
            "errors": errors
        }
    )


# Глобальный обработчик исключений
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Глобальный обработчик исключений"""
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


# Подключаем роутер задач
app.include_router(tasks_router)

# Подключаем статику (Фронтенд)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint для мониторинга"""
    return {
        "status": "healthy",
        "service": "family-task-api",
        "version": "2.0.0",
        "timestamp": time.time()
    }


# Главная страница
@app.get("/")
async def serve_spa():
    return FileResponse("app/static/index.html")


# API информация
@app.get("/api/info")
async def api_info():
    """Информация о API"""
    return {
        "name": "Family Task API",
        "version": "2.0.0",
        "description": "API для управления семейными задачами",
        "endpoints": {
            "tasks": "/api/tasks",
            "health": "/health",
            "docs": "/docs"
        }
    }


