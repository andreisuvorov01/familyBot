#!/bin/bash

# Простейший тестовый запуск

echo "🧪 Тестовый запуск Family Bot..."
echo ""

# Проверяем Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 не установлен"
    exit 1
fi

# Создаем виртуальное окружение
echo "🐍 Создаем виртуальное окружение..."
python3 -m venv venv
source venv/bin/activate

# Устанавливаем зависимости
echo "📦 Устанавливаем зависимости..."
pip install --upgrade pip
pip install -r requirements-compatible.txt

# Создаем .env файл если нет
if [ ! -f .env ]; then
    echo "📝 Создаем тестовый .env файл..."
    echo "BOT_TOKEN=test_token" > .env
    echo "SECRET_KEY=test_secret_key_$(openssl rand -hex 16)" >> .env
    echo "WEBAPP_URL=http://localhost:8000" >> .env
    echo "DATABASE_URL=sqlite+aiosqlite:///./test.db" >> .env
    echo "DEBUG=true" >> .env
fi

# Запускаем миграции
echo "🗄️  Запускаем миграции..."
python migrate.py

# Запускаем приложение
echo "🚀 Запускаем Family Bot..."
echo ""
echo "🌐 API будет доступен по адресу: http://localhost:8000"
echo "📚 Документация: http://localhost:8000/docs"
echo "🩺 Health check: http://localhost:8000/health"
echo ""
echo "Для запуска бота в отдельном терминале выполните:"
echo "  source venv/bin/activate && python bot_polling.py"
echo ""
echo "Нажмите Ctrl+C для остановки"
echo ""

# Запускаем API
uvicorn main:app --reload --host 0.0.0.0 --port 8000