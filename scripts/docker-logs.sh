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
        if command -v docker-compose &> /dev/null; then
            docker-compose logs api --tail=100
        else
            docker compose logs api --tail=100
        fi
        ;;
    2)
        echo "🤖 Логи бота:"
        if command -v docker-compose &> /dev/null; then
            docker-compose logs bot --tail=100
        else
            docker compose logs bot --tail=100
        fi
        ;;
    3)
        echo "🌐 Логи Nginx:"
        if command -v docker-compose &> /dev/null; then
            docker-compose logs nginx --tail=100
        else
            docker compose logs nginx --tail=100
        fi
        ;;
    4)
        echo "🐘 Логи PostgreSQL:"
        if command -v docker-compose &> /dev/null; then
            docker-compose logs postgres --tail=100
        else
            docker compose logs postgres --tail=100
        fi
        ;;
    5)
        echo "🔴 Логи Redis:"
        if command -v docker-compose &> /dev/null; then
            docker-compose logs redis --tail=100
        else
            docker compose logs redis --tail=100
        fi
        ;;
    6)
        echo "📋 Все логи:"
        if command -v docker-compose &> /dev/null; then
            docker-compose logs --tail=50
        else
            docker compose logs --tail=50
        fi
        ;;
    7)
        echo "🔄 Логи в реальном времени:"
        if command -v docker-compose &> /dev/null; then
            docker-compose logs -f
        else
            docker compose logs -f
        fi
        ;;
    *)
        echo "❌ Неверный выбор"
        exit 1
        ;;
esac