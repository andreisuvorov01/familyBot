-- Инициализация БД при первом запуске PostgreSQL контейнера
-- Этот скрипт выполняется автоматически docker-entrypoint

-- Убедимся что БД и пользователь существуют (на случай ручного запуска)
-- Основные таблицы создаются SQLAlchemy через Base.metadata.create_all в lifespan

-- Расширения
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Индексы производительности (добавляются после создания таблиц через миграции)
-- Здесь можно добавить дополнительные настройки PostgreSQL

-- Установка временной зоны для сессий
ALTER DATABASE familybot SET timezone TO 'Europe/Moscow';
