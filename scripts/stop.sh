#!/bin/bash

# Скрипт остановки Family Bot

echo "🛑 Остановка Family Bot..."

# Останавливаем приложения через PM2
pm2 stop ecosystem.config.js

echo "✅ Приложения остановлены!"
echo ""
echo "📊 Текущий статус:"
pm2 status