#!/bin/bash

# Скрипт остановки Family Bot в Docker

echo "🛑 Остановка Family Bot в Docker..."

# Останавливаем контейнеры
if command -v docker-compose &> /dev/null; then
    docker-compose down
else
    docker compose down
fi

echo "✅ Контейнеры остановлены!"
echo ""
echo "📊 Текущий статус:"
if command -v docker-compose &> /dev/null; then
    docker-compose ps
else
    docker compose ps
fi