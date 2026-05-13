#!/bin/bash

# Скрипт запуска Family Bot в Docker

set -e

echo "🐳 Запуск Family Bot в Docker..."
echo ""

# Проверяем наличие .env файла
if [ ! -f .env ]; then
    echo "⚠️  Файл .env не найден. Создаем из примера..."
    cp .env.example .env
    echo ""
    echo "⚠️  ВАЖНО: Отредактируйте файл .env перед запуском!"
    echo "   Необходимо установить:"
    echo "   - BOT_TOKEN (токен Telegram бота)"
    echo "   - SECRET_KEY (секретный ключ для безопасности)"
    echo "   - POSTGRES_PASSWORD (пароль для PostgreSQL)"
    echo "   - CERTBOT_EMAIL (email для SSL сертификатов)"
    echo ""
    read -p "Продолжить без редактирования? (y/n): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        nano .env
    fi
fi

# Загружаем переменные окружения (правильная обработка комментариев и кавычек)
if [ -f .env ]; then
    # Используем более надежный метод загрузки переменных
    set -a
    source .env
    set +a
fi

# Проверяем обязательные переменные
if [ -z "${BOT_TOKEN:-}" ]; then
    echo "❌ Ошибка: BOT_TOKEN не установлен в .env файле"
    echo "   Установите BOT_TOKEN=ваш_токен_бота в файле .env"
    exit 1
fi

if [ -z "${SECRET_KEY:-}" ]; then
    echo "❌ Ошибка: SECRET_KEY не установлен в .env файле"
    echo "   Установите SECRET_KEY=очень_сложный_ключ в файле .env"
    exit 1
fi

if [ -z "${POSTGRES_PASSWORD:-}" ]; then
    echo "⚠️  Предупреждение: POSTGRES_PASSWORD не установлен"
    echo "   Используется значение по умолчанию: changeme123"
    export POSTGRES_PASSWORD=changeme123
fi

if [ -z "${CERTBOT_EMAIL:-}" ]; then
    echo "⚠️  Предупреждение: CERTBOT_EMAIL не установлен"
    echo "   SSL сертификаты не будут работать без email"
    echo "   Установите CERTBOT_EMAIL=ваш@email.com в файле .env"
fi

# Создаем директории
echo "📁 Создаем необходимые директории..."
mkdir -p logs data nginx/logs nginx/ssl prometheus/data grafana/data

# Создаем SSL директории для Let's Encrypt
mkdir -p nginx/ssl/live/my-family-tasks.duckdns.org
mkdir -p nginx/ssl/archive/my-family-tasks.duckdns.org

# Запускаем Docker Compose
echo "🚀 Запускаем Docker Compose..."
if command -v docker-compose &> /dev/null; then
    docker-compose up -d
else
    docker compose up -d
fi

echo ""
echo "✅ Family Bot запущен в Docker!"
echo ""
echo "📊 Статус контейнеров:"
if command -v docker-compose &> /dev/null; then
    docker-compose ps
else
    docker compose ps
fi
echo ""
echo "🔗 Доступные сервисы:"
echo "   🌐 Веб-приложение: https://my-family-tasks.duckdns.org"
echo "   📚 Документация API: https://my-family-tasks.duckdns.org/docs"
echo "   🩺 Health check: https://my-family-tasks.duckdns.org/health"
echo "   📊 Prometheus: http://localhost:9090 (только локально)"
echo "   📈 Grafana: http://localhost:3000 (только локально)"
echo ""
echo "📋 Команды управления:"
echo "   ./scripts/docker-logs.sh        # Просмотр логов"
echo "   ./scripts/docker-stop.sh        # Остановка"
echo "   docker compose restart api      # Перезапуск API"
echo "   docker compose down             # Остановка всех сервисов"
echo "   docker compose ps               # Статус контейнеров"
echo ""
echo "🔒 Настройка SSL (первый запуск):"
echo "   docker compose run --rm certbot # Получение SSL сертификатов"
echo "   docker compose restart nginx    # Перезапуск Nginx с SSL"
echo ""
echo "📝 Логи:"
echo "   API логи: logs/pm2-api-*.log"
echo "   Бот логи: logs/pm2-bot-*.log"
echo "   Nginx логи: nginx/logs/"
echo ""
echo "⚠️  Если SSL не работает, убедитесь что:"
echo "   1. Домен my-family-tasks.duckdns.org указывает на ваш сервер"
echo "   2. Порты 80 и 443 открыты в firewall"
echo "   3. Выполнена команда получения SSL сертификатов"