import logging
import json
import sys
from datetime import datetime
from typing import Any, Dict
from logging.handlers import RotatingFileHandler


class JSONFormatter(logging.Formatter):
    """Форматтер для структурированных JSON логов"""
    
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # Добавляем дополнительные поля
        if hasattr(record, "extra"):
            log_data.update(record.extra)
        
        # Добавляем exception info если есть
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        return json.dumps(log_data, ensure_ascii=False, default=str)


def setup_logging():
    """Настройка структурированного логирования"""
    
    # Создаем логгер
    logger = logging.getLogger("familybot")
    logger.setLevel(logging.INFO)
    
    # Удаляем существующие обработчики
    logger.handlers.clear()
    
    # Консольный handler (для разработки)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    console_handler.setFormatter(console_formatter)
    
    # File handler с ротацией (для продакшена)
    file_handler = RotatingFileHandler(
        "logs/familybot.log",
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding="utf-8"
    )
    file_handler.setLevel(logging.INFO)
    json_formatter = JSONFormatter()
    file_handler.setFormatter(json_formatter)
    
    # Error file handler
    error_handler = RotatingFileHandler(
        "logs/errors.log",
        maxBytes=5 * 1024 * 1024,  # 5MB
        backupCount=3,
        encoding="utf-8"
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(json_formatter)
    
    # Добавляем обработчики
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    logger.addHandler(error_handler)
    
    # Настраиваем логирование для зависимостей
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("aiogram").setLevel(logging.INFO)
    logging.getLogger("apscheduler").setLevel(logging.WARNING)
    
    return logger


# Создаем директорию для логов
import os
os.makedirs("logs", exist_ok=True)

# Инициализируем логгер
logger = setup_logging()


def log_with_context(
    level: str,
    message: str,
    user_id: int = None,
    family_id: str = None,
    task_id: int = None,
    **extra
):
    """Логирование с контекстом пользователя"""
    log_method = getattr(logger, level.lower(), logger.info)
    
    extra_data = extra.copy()
    if user_id:
        extra_data["user_id"] = user_id
    if family_id:
        extra_data["family_id"] = family_id
    if task_id:
        extra_data["task_id"] = task_id
    
    # Создаем LogRecord с дополнительными полями
    log_record = logger.makeRecord(
        logger.name,
        getattr(logging, level.upper(), logging.INFO),
        "",  # fn
        0,   # lno
        message,
        None,
        None,
        extra=None
    )
    log_record.extra = extra_data

    logger.handle(log_record)


# Декоратор для логирования вызовов функций
def log_function_call(func):
    """Декоратор для логирования вызовов функций"""
    async def async_wrapper(*args, **kwargs):
        log_with_context(
            "INFO",
            f"Calling {func.__name__}",
            **kwargs
        )
        try:
            result = await func(*args, **kwargs)
            log_with_context(
                "INFO",
                f"Successfully executed {func.__name__}",
                **kwargs
            )
            return result
        except Exception as e:
            log_with_context(
                "ERROR",
                f"Error in {func.__name__}: {str(e)}",
                **kwargs
            )
            raise
    
    def sync_wrapper(*args, **kwargs):
        log_with_context(
            "INFO",
            f"Calling {func.__name__}",
            **kwargs
        )
        try:
            result = func(*args, **kwargs)
            log_with_context(
                "INFO",
                f"Successfully executed {func.__name__}",
                **kwargs
            )
            return result
        except Exception as e:
            log_with_context(
                "ERROR",
                f"Error in {func.__name__}: {str(e)}",
                **kwargs
            )
            raise
    
    return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper


import asyncio