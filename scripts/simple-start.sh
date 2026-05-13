#!/bin/bash

# Упрощенный запуск Family Bot в Docker (только API + Бот + PostgreSQL)

set -e

echo "🚀 Упрощенный запуск Family Bot..."
echo ""

# Проверяем Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker не установлен"
    exit 1
fi

# Проверяем наличие .env файла
if [ ! -f .env ]; then
    echo "📝 Создаем .env файл..."
    if [ -f .env.simple ]; then
        cp .env.simple .env
    else
        echo "BOT_TOKEN=ваш_токен_бота" > .env
        echo "SECRET_KEY=очень_сложный_ключ" >> .env
        echo "POSTGRES_PASSWORD=changeme123" >> .env
        echo "WEBAPP_URL=https://my-family-tasks.duckdns.org" >> .env
    fi
    
    echo ""
    echo "⚠️  Отредактируйте файл .env:"
    echo "   nano .env"
    echo ""
    echo "Обязательно установите BOT_TOKEN (получите у @BotFather)"
    read -p "Продолжить? (y/n): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 0
    fi
fi

# Загружаем переменные
echo "📋 Загружаем настройки..."
if [ -f .env ]; then
    set -a
    source .env
    set +a
fi

# Проверяем обязательные переменные
echo "🔍 Проверяем настройки..."

if [ -z "${BOT_TOKEN:-}" ] || [ "${BOT_TOKEN}" = "ваш_токен_бота" ]; then
    echo "❌ Ошибка: BOT_TOKEN не установлен"
    echo "   Получите токен у @BotFather и установите в .env файле"
    exit 1
fi

if [ -z "${SECRET_KEY:-}" ] || [ "${SECRET_KEY}" = "очень_сложный_ключ" ]; then
    echo "⚠️  SECRET_KEY не установлен, генерируем временный..."
    export SECRET_KEY=$(openssl rand -hex 32)
    echo "SECRET_KEY=${SECRET_KEY}" >> .env
fi

if [ -z "${POSTGRES_PASSWORD:-}" ]; then
    echo "⚠️  POSTGRES_PASSWORD не установлен, используем changeme123"
    export POSTGRES_PASSWORD=changeme123
fi

# Создаем директории
echo ""
echo "📁 Создаем директории..."
mkdir -p logs data

# Строим образы
echo ""
echo "🐳 Строим Docker образы..."
docker build -t familybot-api -f Dockerfile .
docker build -t familybot-bot -f Dockerfile.bot .

# Запускаем упрощенный compose
echo ""
echo "🚀 Запускаем упрощенный стек..."
docker compose -f docker-compose-simple.yml up -d

echo ""
echo "⏳ Ожидаем запуск сервисов..."
sleep 15

# Проверяем статус
echo ""
echo "📊 Статус контейнеров:"
docker compose -f docker-compose-simple.yml ps

echo ""
echo "🎉 Family Bot запущен в упрощенном режиме!"
echo ""
echo "🔗 API доступен по адресу: http://localhost:8000"
echo "📚 Документация: http://localhost:8000/docs"
echo "🩺 Health check: http://localhost:8000/health"
echo ""
echo "🤖 Бот запущен и готов к работе!"
echo ""
echo "📋 Команды управления:"
echo "  docker compose -f docker-compose-simple.yml logs api"
echo "  docker compose -f docker-compose-simple.yml logs bot"
echo "  docker compose -f docker-compose-simple.yml restart api"
echo "  docker compose -f docker-compose-simple.yml down"
echo ""
echo "⚠️  Для работы через домен https://my-family-tasks.duckdns.org"
echo "   нужно настроить Nginx reverse proxy на хосте"