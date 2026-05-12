#!/bin/bash

# Скрипт просмотра логов Docker

echo "📋 Логи Family Bot в Docker"
echo ""

# Показываем меню
echo "Выберите сервис для просмотра логов:"
echo "1) API (FastAPI)"
echo "2) Бот (Telegram)"
echo "3) Nginx"
echo "4) PostgreSQL"
echo "5) Redis"
echo "6) Все логи"
echo "7) Логи с follow (-f)"
echo ""

read -p "Введите номер: " choice

case $choice in
    1)
        echo "📊 Логи API:"
        docker-compose logs api --tail=100
        ;;
    2)
        echo "🤖 Логи бота:"
        docker-compose logs bot --tail=100
        ;;
    3)
        echo "🌐 Логи Nginx:"
        docker-compose logs nginx --tail=100
        ;;
    4)
        echo "🐘 Логи PostgreSQL:"
        docker-compose logs postgres --tail=100
        ;;
    5)
        echo "🔴 Логи Redis:"
        docker-compose logs redis --tail=100
        ;;
    6)
        echo "📋 Все логи:"
        docker-compose logs --tail=50
        ;;
    7)
        echo "🔄 Логи в реальном времени:"
        docker-compose logs -f
        ;;
    *)
        echo "❌ Неверный выбор"
        exit 1
        ;;
esac