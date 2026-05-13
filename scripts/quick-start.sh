#!/bin/bash

# Быстрый старт Family Bot в Docker

set -e

echo "🚀 Быстрый старт Family Bot..."
echo ""

# Проверяем Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker не установлен. Устанавливаем..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    sudo usermod -aG docker $USER
    echo "✅ Docker установлен. Перезапустите терминал и запустите скрипт снова."
    exit 0
fi

# Проверяем Docker Compose
if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo "❌ Docker Compose не установлен. Устанавливаем..."
    sudo apt update
    sudo apt install -y docker-compose-plugin
    echo "✅ Docker Compose установлен"
fi

# Создаем простой .env файл если его нет
if [ ! -f .env ]; then
    echo "📝 Создаем .env файл из шаблона..."
    cp .env.simple .env
    echo ""
    echo "⚠️  ВАЖНО: Отредактируйте файл .env перед запуском!"
    echo "   nano .env"
    echo ""
    echo "Необходимо установить:"
    echo "1. BOT_TOKEN - получите у @BotFather"
    echo "2. SECRET_KEY - любой сложный ключ"
    echo "3. POSTGRES_PASSWORD - пароль для базы данных"
    echo "4. CERTBOT_EMAIL - ваш email для SSL"
    echo ""
    read -p "Открыть файл для редактирования? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        if command -v nano &> /dev/null; then
            nano .env
        else
            vi .env
        fi
    fi
fi

# Загружаем переменные
if [ -f .env ]; then
    echo "📋 Загружаем настройки из .env..."
    # Безопасная загрузка переменных
    while IFS='=' read -r key value; do
        # Пропускаем комментарии и пустые строки
        if [[ ! $key =~ ^# && -n $key ]]; then
            # Убираем кавычки если есть
            value="${value%\"}"
            value="${value#\"}"
            export "$key=$value"
        fi
    done < .env
fi

# Проверяем обязательные переменные
echo "🔍 Проверяем настройки..."
ERRORS=0

if [ -z "${BOT_TOKEN:-}" ]; then
    echo "❌ Ошибка: BOT_TOKEN не установлен"
    ERRORS=1
else
    echo "✅ BOT_TOKEN: установлен"
fi

if [ -z "${SECRET_KEY:-}" ]; then
    echo "❌ Ошибка: SECRET_KEY не установлен"
    ERRORS=1
else
    echo "✅ SECRET_KEY: установлен"
fi

if [ -z "${POSTGRES_PASSWORD:-}" ]; then
    echo "⚠️  POSTGRES_PASSWORD не установлен, используем changeme123"
    export POSTGRES_PASSWORD=changeme123
else
    echo "✅ POSTGRES_PASSWORD: установлен"
fi

if [ -z "${CERTBOT_EMAIL:-}" ]; then
    echo "⚠️  CERTBOT_EMAIL не установлен, SSL может не работать"
else
    echo "✅ CERTBOT_EMAIL: установлен"
fi

if [ $ERRORS -eq 1 ]; then
    echo ""
    echo "❌ Исправьте ошибки в .env файле и запустите снова"
    exit 1
fi

# Создаем директории
echo ""
echo "📁 Создаем директории..."
mkdir -p logs data nginx/logs nginx/ssl

# Запускаем Docker Compose
echo ""
echo "🐳 Запускаем Docker Compose..."
if command -v docker-compose &> /dev/null; then
    docker-compose up -d
else
    docker compose up -d
fi

echo ""
echo "⏳ Ожидаем запуск сервисов..."
sleep 10

# Проверяем статус
echo ""
echo "📊 Статус контейнеров:"
if command -v docker-compose &> /dev/null; then
    docker-compose ps
else
    docker compose ps
fi

echo ""
echo "🎉 Family Bot запущен!"
echo ""
echo "🌐 Веб-приложение: https://my-family-tasks.duckdns.org"
echo "📚 Документация: https://my-family-tasks.duckdns.org/docs"
echo "🩺 Health check: https://my-family-tasks.duckdns.org/health"
echo ""
echo "📋 Команды управления:"
echo "  ./scripts/docker-logs.sh    # Просмотр логов"
echo "  ./scripts/docker-stop.sh    # Остановка"
echo "  docker compose restart api  # Перезапуск API"
echo ""
echo "🔒 Для настройки SSL выполните:"
echo "  docker compose run --rm certbot"
echo "  docker compose restart nginx"