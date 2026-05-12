#!/bin/bash

# Скрипт остановки Family Bot в Docker

echo "🛑 Остановка Family Bot в Docker..."

# Останавливаем контейнеры
docker-compose down

echo "✅ Контейнеры остановлены!"
echo ""
echo "📊 Текущий статус:"
docker-compose ps