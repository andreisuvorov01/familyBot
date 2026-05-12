# Multi-stage build для Family Bot

# Stage 1: Builder
FROM python:3.11-slim as builder

WORKDIR /app

# Установка системных зависимостей
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Копирование requirements
COPY requirements.txt .

# Установка Python зависимостей
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Stage 2: Runtime
FROM python:3.11-slim

WORKDIR /app

# Установка runtime зависимостей
RUN apt-get update && apt-get install -y \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Создание пользователя для безопасности
RUN groupadd -r familybot && useradd -r -g familybot familybot

# Копирование зависимостей из builder
COPY --from=builder /usr/local/lib/python3.11/site-packages/ /usr/local/lib/python3.11/site-packages/
COPY --from=builder /usr/local/bin/ /usr/local/bin/

# Копирование исходного кода
COPY . .

# Создание директорий для логов и данных
RUN mkdir -p logs && \
    mkdir -p data && \
    chown -R familybot:familybot /app

# Настройка прав
RUN chmod +x scripts/*.sh && \
    chmod +x migrate.py

# Переключение на непривилегированного пользователя
USER familybot

# Настройка переменных окружения
ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    DATABASE_URL=sqlite+aiosqlite:///./data/family_base.db \
    WEBAPP_URL=https://my-family-tasks.duckdns.org \
    PORT=8000

# Открытие порта
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Команда запуска
CMD ["sh", "-c", "python migrate.py && uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]