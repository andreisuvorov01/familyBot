# Makefile для управления Family Bot

.PHONY: help install dev test lint clean deploy start stop restart logs

# Цвета для вывода
GREEN := \033[0;32m
YELLOW := \033[1;33m
RED := \033[0;31m
NC := \033[0m # No Color

help: ## Показать справку
	@echo "$(GREEN)Family Bot - Makefile$(NC)"
	@echo ""
	@echo "$(YELLOW)Использование:$(NC)"
	@echo "  make <target>"
	@echo ""
	@echo "$(YELLOW)Targets:$(NC)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(GREEN)%-20s$(NC) %s\n", $$1, $$2}'

install: ## Установка зависимостей
	@echo "$(YELLOW)Установка зависимостей...$(NC)"
	pip install --upgrade pip
	pip install -r requirements.txt
	@echo "$(GREEN)✅ Зависимости установлены$(NC)"

dev: ## Запуск в режиме разработки
	@echo "$(YELLOW)Запуск в режиме разработки...$(NC)"
	uvicorn main:app --reload --host 0.0.0.0 --port 8000

test: ## Запуск тестов
	@echo "$(YELLOW)Запуск тестов...$(NC)"
	pytest tests/ -v --cov=app --cov-report=html

lint: ## Проверка кода
	@echo "$(YELLOW)Проверка кода...$(NC)"
	black --check app/ tests/
	isort --check-only app/ tests/
	mypy app/

format: ## Форматирование кода
	@echo "$(YELLOW)Форматирование кода...$(NC)"
	black app/ tests/
	isort app/ tests/

clean: ## Очистка кэша и временных файлов
	@echo "$(YELLOW)Очистка...$(NC)"
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name ".coverage" -delete
	rm -rf htmlcov/ .pytest_cache/ .mypy_cache/
	@echo "$(GREEN)✅ Очистка завершена$(NC)"

# PM2 команды
pm2-install: ## Установка PM2
	@echo "$(YELLOW)Установка PM2...$(NC)"
	npm install -g pm2
	@echo "$(GREEN)✅ PM2 установлен$(NC)"

start: ## Запуск приложений через PM2
	@echo "$(YELLOW)Запуск Family Bot через PM2...$(NC)"
	@mkdir -p logs
	pm2 start ecosystem.config.js
	@echo "$(GREEN)✅ Приложения запущены$(NC)"
	@echo "$(YELLOW)Используйте:$(NC)"
	@echo "  make status    - статус приложений"
	@echo "  make logs      - просмотр логов"
	@echo "  make monit     - мониторинг"

stop: ## Остановка приложений
	@echo "$(YELLOW)Остановка приложений...$(NC)"
	pm2 stop ecosystem.config.js
	@echo "$(GREEN)✅ Приложения остановлены$(NC)"

restart: ## Перезапуск приложений
	@echo "$(YELLOW)Перезапуск приложений...$(NC)"
	pm2 restart ecosystem.config.js
	@echo "$(GREEN)✅ Приложения перезапущены$(NC)"

status: ## Статус приложений
	@echo "$(YELLOW)Статус приложений:$(NC)"
	pm2 status

logs: ## Просмотр логов
	@echo "$(YELLOW)Логи приложений:$(NC)"
	pm2 logs --lines 50

logs-api: ## Логи API
	@echo "$(YELLOW)Логи API:$(NC)"
	pm2 logs familybot-api --lines 100

logs-bot: ## Логи бота
	@echo "$(YELLOW)Логи бота:$(NC)"
	pm2 logs familybot-bot --lines 100

monit: ## Мониторинг PM2
	@echo "$(YELLOW)Запуск мониторинга PM2...$(NC)"
	pm2 monit

setup: ## Настройка автозапуска PM2
	@echo "$(YELLOW)Настройка автозапуска PM2...$(NC)"
	pm2 startup
	pm2 save
	@echo "$(GREEN)✅ Автозапуск настроен$(NC)"

# Миграции БД
migrate: ## Запуск миграций БД
	@echo "$(YELLOW)Запуск миграций БД...$(NC)"
	python migrate.py
	@echo "$(GREEN)✅ Миграции выполнены$(NC)"

migrate-pg: ## Миграция на PostgreSQL
	@echo "$(YELLOW)Миграция на PostgreSQL...$(NC)"
	python migrate_to_postgres.py
	@echo "$(GREEN)✅ Миграция на PostgreSQL завершена$(NC)"

# Деплой
deploy: ## Деплой приложения
	@echo "$(YELLOW)Деплой приложения...$(NC)"
	git pull origin main
	make install
	make migrate
	make restart
	@echo "$(GREEN)✅ Деплой завершен$(NC)"

# Системные команды
health: ## Health check API
	@echo "$(YELLOW)Health check API...$(NC)"
	curl -f http://localhost:8000/health || echo "$(RED)❌ API недоступен$(NC)"

info: ## Информация о API
	@echo "$(YELLOW)Информация о API...$(NC)"
	curl http://localhost:8000/api/info 2>/dev/null | python -m json.tool

docs: ## Открыть документацию API
	@echo "$(YELLOW)Открытие документации API...$(NC)"
	@echo "Документация доступна по адресу:"
	@echo "  http://localhost:8000/docs"
	@echo "  http://localhost:8000/redoc"

# Бэкапы
backup: ## Создание бэкапа БД
	@echo "$(YELLOW)Создание бэкапа БД...$(NC)"
	@mkdir -p backups
	cp family_base.db backups/family_base_$(shell date +%Y%m%d_%H%M%S).db
	@echo "$(GREEN)✅ Бэкап создан в backups/$(NC)"

# Обновление
update: ## Обновление зависимостей
	@echo "$(YELLOW)Обновление зависимостей...$(NC)"
	pip install --upgrade -r requirements.txt
	@echo "$(GREEN)✅ Зависимости обновлены$(NC)"

# Все команды
all: install migrate start ## Установка, миграции и запуск
	@echo "$(GREEN)✅ Family Bot готов к работе!$(NC)"