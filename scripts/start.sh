#!/bin/bash

# Скрипт запуска Family Bot с PM2

set -e

echo "🚀 Запуск Family Bot..."

# Создаем директории для логов
mkdir -p logs

# Проверяем наличие .env файла
if [ ! -f .env ]; then
    echo "⚠️  Файл .env не найден. Создаем из примера..."
    cp .env.example .env
    echo "⚠️  Пожалуйста, отредактируйте файл .env перед запуском в продакшене!"
fi

# Проверяем зависимости
echo "📦 Проверяем зависимости Python..."
python -m pip install --upgrade pip
pip install -r requirements.txt

# Запускаем миграции БД
echo "🗄️  Запускаем миграции базы данных..."
python migrate.py

# Запускаем приложения через PM2
echo "⚡ Запускаем приложения через PM2..."

# Проверяем установлен ли PM2
if ! command -v pm2 &> /dev/null; then
    echo "❌ PM2 не установлен. Устанавливаем..."
    npm install -g pm2
fi

# Запускаем приложения
pm2 start ecosystem.config.js

echo "✅ Приложения запущены!"
echo ""
echo "📊 Статус приложений:"
pm2 status
echo ""
echo "📋 Команды для управления:"
echo "  pm2 status              - статус приложений"
echo "  pm2 logs familybot-api  - логи API"
echo "  pm2 logs familybot-bot  - логи бота"
echo "  pm2 restart all         - перезапуск всех приложений"
echo "  pm2 stop all            - остановка всех приложений"
echo "  pm2 delete all          - удаление всех приложений из PM2"
echo ""
echo "🔗 API доступен по адресу: http://localhost:8000"
echo "📚 Документация API: http://localhost:8000/docs"