#!/bin/bash

# Скрипт перезапуска Family Bot

echo "🔄 Перезапуск Family Bot..."

# Перезапускаем приложения через PM2
pm2 restart ecosystem.config.js

echo "✅ Приложения перезапущены!"
echo ""
echo "📊 Статус приложений:"
pm2 status