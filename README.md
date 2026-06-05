# Family Bot - Семейный органайзер

Современный Telegram бот для управления семейными задачами с веб-интерфейсом.

## 🚀 Особенности

- **Семейная регистрация** - создание семьи с уникальным кодом
- **Управление задачами** - личные и общие задачи с дедлайнами
- **Повторяющиеся задачи** - ежедневные, еженедельные, ежемесячные
- **Уведомления** - утренние сводки и напоминания о дедлайнах
- **Веб-интерфейс** - современный SPA с календарем
- **Безопасность** - rate limiting, валидация, логирование

## 🏗️ Архитектура

### Технологический стек
- **Backend**: FastAPI (Python 3.11+)
- **Database**: PostgreSQL
- **Telegram Bot**: aiogram 3.x
- **Frontend**: HTML/CSS/JS + Telegram Web App API
- **Scheduler**: APScheduler
- **Testing**: pytest, pytest-asyncio

### Структура проекта
```
familybot/
├── app/
│   ├── api/              # FastAPI endpoints
│   ├── bot/              # Telegram bot handlers
│   ├── core/             # Ядро приложения
│   │   ├── models/       # SQLAlchemy модели
│   │   ├── repositories/ # Репозитории для работы с БД
│   │   ├── security/     # Безопасность и rate limiting
│   │   └── logging_config.py
│   ├── services/         # Сервисы (scheduler)
│   └── static/           # Фронтенд
├── tests/                # Тесты
├── main.py              # FastAPI приложение
├── bot_polling.py       # Telegram бот
└── requirements.txt     # Зависимости
```

## ⚙️ Установка и запуск

### 1. Клонирование репозитория
```bash
git clone https://github.com/yourusername/familybot.git
cd familybot
```

### 2. Настройка окружения
```bash
cp .env.example .env
# Отредактируйте .env файл
```

### 3. Установка зависимостей
```bash
pip install -r requirements.txt
```

### 4. Настройка базы данных
```bash
python migrate.py
# DATABASE_URL должен указывать на PostgreSQL, например:
# postgresql+asyncpg://familybot:password@localhost:5432/familybot
```

### 5. Запуск приложения

#### Запуск FastAPI сервера:
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

#### Запуск Telegram бота:
```bash
python bot_polling.py
```

### 6. Настройка веб-приложения
- Получите публичный URL для вашего сервера (ngrok, облачный хостинг)
- Обновите `WEBAPP_URL` в `.env` файле
- Настройте веб-приложение в @BotFather

## 📚 API Документация

После запуска сервера:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

### Основные endpoints:
- `GET /api/tasks` - получить задачи
- `POST /api/tasks` - создать задачу
- `PATCH /api/tasks/{id}` - обновить задачу
- `DELETE /api/tasks/{id}` - удалить задачу
- `GET /health` - health check
- `GET /api/info` - информация о API

## 🔧 Команды бота

- `/start` - регистрация и главное меню
- `/tasks` - открыть веб-приложение с задачами
- `/stats` - статистика по задачам
- `/reset` - сброс профиля

## 🧪 Тестирование

```bash
# Установка тестовых зависимостей
pip install -r requirements.txt

# Запуск тестов
pytest tests/ -v

# Запуск тестов с покрытием
pytest tests/ -v --cov=app --cov-report=html

# Линтинг кода
black --check app/ tests/
isort --check-only app/ tests/
mypy app/
```

## 🔒 Безопасность

### Реализованные меры безопасности:
1. **Rate limiting** - защита от DDoS и brute force атак
2. **Валидация данных** - строгая валидация через Pydantic
3. **Telegram Web App аутентификация** - проверка подписи
4. **Логирование** - структурированные JSON логи
5. **Обработка ошибок** - глобальные обработчики исключений

### Рекомендации для продакшена:
1. Используйте отдельного PostgreSQL-пользователя с минимальными правами
2. Настройте HTTPS и валидные SSL сертификаты
3. Используйте переменные окружения для секретов
4. Настройте мониторинг (Sentry, Prometheus)
5. Регулярно обновляйте зависимости

## 📊 Мониторинг

### Health checks:
```bash
curl http://localhost:8000/health
```

### Метрики (если включены):
```bash
curl http://localhost:8000/metrics
```

## 🚀 Развертывание

Проект настроен на ручное развертывание с PostgreSQL: Docker не требуется, основной сценарий запуска — через Python/systemd.

### Ручное развертывание:
1. Настройте сервер (Ubuntu 20.04+)
2. Установите Python 3.11+
3. Настройте systemd сервисы для бота и API
4. Настройте Nginx как reverse proxy
5. Настройте SSL через Let's Encrypt

## 🤝 Вклад в проект

1. Форкните репозиторий
2. Создайте ветку для вашей фичи (`git checkout -b feature/amazing-feature`)
3. Зафиксируйте изменения (`git commit -m 'Add amazing feature'`)
4. Запушьте в ветку (`git push origin feature/amazing-feature`)
5. Откройте Pull Request

## 📄 Лицензия

Этот проект лицензирован под MIT License - смотрите файл LICENSE для деталей.

## 📞 Поддержка

- Issues: https://github.com/yourusername/familybot/issues
- Telegram: @yourusername
- Email: support@example.com