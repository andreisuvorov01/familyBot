# Multi-stage build для Family Bot API

# Stage 1: Builder
FROM python:3.11-slim@sha256:ad5dadd957f6a3b5e9253c89cbca6df0a70a0e83cb60ede5b4bb03abd9bfdb5e as builder

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Stage 2: Runtime
FROM python:3.11-slim@sha256:ad5dadd957f6a3b5e9253c89cbca6df0a70a0e83cb60ede5b4bb03abd9bfdb5e

WORKDIR /app

RUN apt-get update && apt-get install -y \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd -r familybot && useradd -r -g familybot familybot

COPY --from=builder /usr/local/lib/python3.11/site-packages/ /usr/local/lib/python3.11/site-packages/
COPY --from=builder /usr/local/bin/ /usr/local/bin/

COPY . .

RUN mkdir -p logs data && \
    chown -R familybot:familybot /app

RUN chmod +x scripts/*.sh

USER familybot

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PORT=8000

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
