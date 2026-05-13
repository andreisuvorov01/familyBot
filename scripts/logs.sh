#!/bin/bash

# Скрипт просмотра логов Family Bot

echo "📋 Логи Family Bot"
echo ""

# Показываем меню
echo "Выберите приложение для просмотра логов:"
echo "1) API (familybot-api)"
echo "2) Бот (familybot-bot)"
echo "3) Все логи"
echo "4) Ошибки API"
echo "5) Ошибки бота"
echo ""

read -p "Введите номер: " choice

case $choice in
    1)
        echo "📊 Логи API:"
        pm2 logs familybot-api --lines 100
        ;;
    2)
        echo "🤖 Логи бота:"
        pm2 logs familybot-bot --lines 100
        ;;
    3)
        echo "📋 Все логи:"
        pm2 logs --lines 50
        ;;
    4)
        echo "❌ Ошибки API:"
        if [ -f "logs/pm2-api-error.log" ]; then
            tail -100 logs/pm2-api-error.log
        else
            echo "Файл логов не найден: logs/pm2-api-error.log"
        fi
        ;;
    5)
        echo "❌ Ошибки бота:"
        if [ -f "logs/pm2-bot-error.log" ]; then
            tail -100 logs/pm2-bot-error.log
        else
            echo "Файл логов не найден: logs/pm2-bot-error.log"
        fi
        ;;
    *)
        echo "❌ Неверный выбор"
        exit 1
        ;;
esac