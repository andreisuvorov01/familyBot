#!/bin/bash

# Полноценный скрипт развертывания Family Bot со всем стеком

set -e

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Функции для вывода
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Проверка прав
check_root() {
    if [ "$EUID" -ne 0 ]; then 
        print_warning "Рекомендуется запускать скрипт с правами root (sudo)"
        read -p "Продолжить? (y/n): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
}

# Проверка Docker
check_docker() {
    if ! command -v docker &> /dev/null; then
        print_error "Docker не установлен"
        print_info "Устанавливаем Docker..."
        
        # Установка Docker
        curl -fsSL https://get.docker.com -o get-docker.sh
        sudo sh get-docker.sh
        sudo usermod -aG docker $USER
        
        print_success "Docker установлен"
        print_warning "Перезапустите терминал или выполните: newgrp docker"
        exit 0
    fi
    
    if ! docker info &> /dev/null; then
        print_error "Docker не запущен или нет прав"
        print_info "Запускаем Docker..."
        sudo systemctl start docker
        sudo systemctl enable docker
    fi
    
    print_success "Docker проверен: $(docker --version)"
}

# Проверка Docker Compose
check_docker_compose() {
    if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
        print_error "Docker Compose не установлен"
        print_info "Устанавливаем Docker Compose..."
        
        # Установка Docker Compose Plugin
        sudo apt update
        sudo apt install -y docker-compose-plugin
        
        print_success "Docker Compose установлен"
    fi
    
    print_success "Docker Compose проверен"
}

# Настройка .env файла
setup_env() {
    print_info "Настройка окружения..."
    
    if [ ! -f .env ]; then
        print_warning "Файл .env не найден"
        
        if [ -f .env.example ]; then
            cp .env.example .env
            print_info "Создан .env файл из примера"
        else
            # Создаем базовый .env файл
            cat > .env << EOF
# ============================================
# Family Bot Configuration
# ============================================

# 🔐 ОБЯЗАТЕЛЬНЫЕ НАСТРОЙКИ
BOT_TOKEN=your_telegram_bot_token_here
SECRET_KEY=$(openssl rand -hex 32)
POSTGRES_PASSWORD=$(openssl rand -hex 16)
CERTBOT_EMAIL=your-email@example.com

# ============================================
# ОПЦИОНАЛЬНЫЕ НАСТРОЙКИ
# ============================================

# Application
WEBAPP_URL=https://my-family-tasks.duckdns.org
DATABASE_URL=postgresql+asyncpg://familyuser:\${POSTGRES_PASSWORD}@postgres:5432/familybot
REDIS_URL=redis://redis:6379/0
ENABLE_REDIS=true

# Security
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=30
RATE_LIMIT_REQUESTS=100
RATE_LIMIT_WINDOW=60

# Scheduler
TIMEZONE=Europe/Moscow
MORNING_NOTIFICATION_HOUR=9
MORNING_NOTIFICATION_MINUTE=0
DEADLINE_CHECK_INTERVAL=1

# Logging
LOG_LEVEL=INFO
LOG_FILE=/app/logs/familybot.log
LOG_MAX_SIZE=10485760
LOG_BACKUP_COUNT=5

# Monitoring
ENABLE_METRICS=true
PROMETHEUS_MULTIPROC_DIR=/tmp
GRAFANA_PASSWORD=admin123

# Application Settings
DEBUG=false
ENVIRONMENT=production
ALLOWED_ORIGINS=https://my-family-tasks.duckdns.org

# Docker
COMPOSE_PROJECT_NAME=familybot
COMPOSE_HTTP_TIMEOUT=300
EOF
            print_info "Создан базовый .env файл"
        fi
    fi
    
    # Загружаем переменные
    set -a
    source .env
    set +a
    
    # Проверяем обязательные переменные
    local errors=0
    
    if [ -z "${BOT_TOKEN}" ] || [ "${BOT_TOKEN}" = "your_telegram_bot_token_here" ]; then
        print_error "BOT_TOKEN не установлен"
        print_info "Получите токен у @BotFather в Telegram"
        errors=1
    fi
    
    if [ -z "${CERTBOT_EMAIL}" ] || [ "${CERTBOT_EMAIL}" = "your-email@example.com" ]; then
        print_error "CERTBOT_EMAIL не установлен"
        print_info "Установите ваш email для SSL сертификатов"
        errors=1
    fi
    
    if [ $errors -eq 1 ]; then
        print_warning "Открываю файл .env для редактирования..."
        sleep 2
        
        if command -v nano &> /dev/null; then
            nano .env
        elif command -v vi &> /dev/null; then
            vi .env
        else
            print_error "Не найден редактор. Отредактируйте файл вручную: $(pwd)/.env"
            exit 1
        fi
        
        # Перезагружаем переменные
        set -a
        source .env
        set +a
    fi
    
    print_success "Окружение настроено"
}

# Создание директорий
create_directories() {
    print_info "Создание директорий..."
    
    # Основные директории
    mkdir -p logs data
    
    # Nginx директории
    mkdir -p nginx/logs nginx/ssl nginx/conf.d
    
    # SSL директории для Let's Encrypt
    mkdir -p nginx/ssl/live/my-family-tasks.duckdns.org
    mkdir -p nginx/ssl/archive/my-family-tasks.duckdns.org
    
    # Мониторинг
    mkdir -p prometheus/data grafana/data grafana/provisioning/datasources grafana/provisioning/dashboards
    
    # Создаем конфигурацию Grafana если нет
    if [ ! -f grafana/provisioning/datasources/prometheus.yml ]; then
        cat > grafana/provisioning/datasources/prometheus.yml << EOF
apiVersion: 1

datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
    editable: true
    jsonData:
      timeInterval: 15s
      queryTimeout: 60s
      httpMethod: POST
EOF
    fi
    
    # Устанавливаем права
    chmod 755 logs data nginx prometheus grafana
    
    print_success "Директории созданы"
}

# Настройка firewall
setup_firewall() {
    print_info "Настройка firewall..."
    
    if command -v ufw &> /dev/null; then
        sudo ufw allow 22/tcp    # SSH
        sudo ufw allow 80/tcp    # HTTP
        sudo ufw allow 443/tcp   # HTTPS
        sudo ufw --force enable
        print_success "Firewall настроен"
    else
        print_warning "UFW не установлен, пропускаем настройку firewall"
    fi
}

# Сборка Docker образов
build_docker_images() {
    print_info "Сборка Docker образов..."
    
    # Используем совместимые зависимости
    if [ -f requirements-compatible.txt ]; then
        cp requirements-compatible.txt requirements.txt
        print_info "Используем совместимые зависимости"
    fi
    
    # Собираем образы
    if command -v docker-compose &> /dev/null; then
        docker-compose build --no-cache
    else
        docker compose build --no-cache
    fi
    
    print_success "Docker образы собраны"
}

# Запуск Docker Compose
start_docker_compose() {
    print_info "Запуск Docker Compose..."
    
    # Сначала запускаем только базу данных и Redis
    print_info "Запускаем базу данных и Redis..."
    if command -v docker-compose &> /dev/null; then
        docker-compose up -d postgres redis
    else
        docker compose up -d postgres redis
    fi
    
    # Ждем запуска БД
    print_info "Ожидаем запуск PostgreSQL..."
    sleep 10
    
    # Запускаем остальные сервисы
    print_info "Запускаем остальные сервисы..."
    if command -v docker-compose &> /dev/null; then
        docker-compose up -d
    else
        docker compose up -d
    fi
    
    print_success "Docker Compose запущен"
}

# Настройка SSL сертификатов
setup_ssl() {
    print_info "Настройка SSL сертификатов..."
    
    # Ждем запуска Nginx
    print_info "Ожидаем запуск Nginx..."
    sleep 10
    
    # Проверяем доступность домена
    print_info "Проверка домена my-family-tasks.duckdns.org..."
    if ! nslookup my-family-tasks.duckdns.org &> /dev/null; then
        print_warning "Домен не разрешается. Убедитесь что домен указывает на IP сервера"
    fi
    
    # Получаем SSL сертификаты
    print_info "Получение SSL сертификатов Let's Encrypt..."
    
    if command -v docker-compose &> /dev/null; then
        docker-compose run --rm certbot certonly --webroot --webroot-path=/usr/share/nginx/html -d my-family-tasks.duckdns.org --email ${CERTBOT_EMAIL} --agree-tos --no-eff-email --force-renewal || {
            print_warning "Не удалось получить SSL сертификаты. Проверьте:"
            print_warning "1. Домен my-family-tasks.duckdns.org указывает на IP сервера"
            print_warning "2. Порты 80 и 443 открыты"
            print_warning "3. Email в CERTBOT_EMAIL корректен"
        }
    else
        docker compose run --rm certbot certonly --webroot --webroot-path=/usr/share/nginx/html -d my-family-tasks.duckdns.org --email ${CERTBOT_EMAIL} --agree-tos --no-eff-email --force-renewal || {
            print_warning "Не удалось получить SSL сертификаты. Проверьте:"
            print_warning "1. Домен my-family-tasks.duckdns.org указывает на IP сервера"
            print_warning "2. Порты 80 и 443 открыты"
            print_warning "3. Email в CERTBOT_EMAIL корректен"
        }
    fi
    
    # Перезапускаем Nginx с SSL
    print_info "Перезапуск Nginx с SSL..."
    if command -v docker-compose &> /dev/null; then
        docker-compose restart nginx
    else
        docker compose restart nginx
    fi
    
    print_success "SSL настроен"
}

# Проверка работоспособности
check_health() {
    print_info "Проверка работоспособности..."
    
    # Даем время на запуск
    print_info "Ожидаем полный запуск сервисов..."
    sleep 20
    
    local errors=0
    
    # Проверяем API
    print_info "Проверка API..."
    if curl -f http://localhost:8000/health &> /dev/null; then
        print_success "API работает"
    else
        print_error "API не отвечает"
        errors=1
    fi
    
    # Проверяем Nginx
    print_info "Проверка Nginx..."
    if curl -f http://localhost:80 &> /dev/null; then
        print_success "Nginx работает"
    else
        print_error "Nginx не отвечает"
        errors=1
    fi
    
    # Проверяем PostgreSQL
    print_info "Проверка PostgreSQL..."
    if docker exec familybot-postgres pg_isready -U familyuser -d familybot &> /dev/null; then
        print_success "PostgreSQL работает"
    else
        print_error "PostgreSQL не отвечает"
        errors=1
    fi
    
    # Проверяем Redis
    print_info "Проверка Redis..."
    if docker exec familybot-redis redis-cli ping &> /dev/null; then
        print_success "Redis работает"
    else
        print_error "Redis не отвечает"
        errors=1
    fi
    
    if [ $errors -eq 0 ]; then
        print_success "Все сервисы работают корректно"
    else
        print_warning "Некоторые сервисы имеют проблемы. Проверьте логи"
    fi
}

# Показать информацию о развертывании
show_deployment_info() {
    echo ""
    echo -e "${GREEN}============================================${NC}"
    echo -e "${GREEN}        Family Bot успешно развернут!       ${NC}"
    echo -e "${GREEN}============================================${NC}"
    echo ""
    
    echo -e "${BLUE}🌐 Публичные сервисы:${NC}"
    echo "   Веб-приложение:  https://my-family-tasks.duckdns.org"
    echo "   Документация API: https://my-family-tasks.duckdns.org/docs"
    echo "   Health check:    https://my-family-tasks.duckdns.org/health"
    echo "   Метрики:         https://my-family-tasks.duckdns.org/metrics"
    echo ""
    
    echo -e "${BLUE}🔧 Локальные сервисы (только на сервере):${NC}"
    echo "   Prometheus:      http://localhost:9090"
    echo "   Grafana:         http://localhost:3000"
    echo "   Логин Grafana:   admin / ${GRAFANA_PASSWORD:-admin123}"
    echo ""
    
    echo -e "${BLUE}🐳 Docker контейнеры:${NC}"
    if command -v docker-compose &> /dev/null; then
        docker-compose ps
    else
        docker compose ps
    fi
    echo ""
    
    echo -e "${BLUE}📋 Команды управления:${NC}"
    echo "   Просмотр логов:      ./scripts/docker-logs.sh"
    echo "   Остановка:           ./scripts/docker-stop.sh"
    echo "   Перезапуск:          docker compose restart api"
    echo "   Обновление:          git pull && docker compose up -d --build"
    echo "   SSL обновление:      docker compose run --rm certbot renew"
    echo ""
    
    echo -e "${BLUE}📊 Мониторинг:${NC}"
    echo "   Логи API:          docker compose logs api"
    echo "   Логи бота:         docker compose logs bot"
    echo "   Логи Nginx:        tail -f nginx/logs/error.log"
    echo "   Метрики:           curl http://localhost:8000/metrics"
    echo ""
    
    echo -e "${YELLOW}⚠️  Важные шаги после развертывания:${NC}"
    echo "   1. Проверьте работу бота в Telegram: /start"
    echo "   2. Настройте регулярные бэкапы БД"
    echo "   3. Настройте мониторинг в Grafana"
    echo "   4. Обновите пароли в .env файле"
    echo ""
    
    echo -e "${GREEN}🎉 Поздравляем! Family Bot готов к работе!${NC}"
}

# Основная функция
main() {
    echo -e "${GREEN}============================================${NC}"
    echo -e "${GREEN}    Полное развертывание Family Bot         ${NC}"
    echo -e "${GREEN}============================================${NC}"
    echo ""
    
    # Проверка прав
    check_root
    
    # Проверка Docker
    check_docker
    
    # Проверка Docker Compose
    check_docker_compose
    
    # Настройка окружения
    setup_env
    
    # Создание директорий
    create_directories
    
    # Настройка firewall
    setup_firewall
    
    # Сборка Docker образов
    build_docker_images
    
    # Запуск Docker Compose
    start_docker_compose
    
    # Настройка SSL
    setup_ssl
    
    # Проверка работоспособности
    check_health
    
    # Показать информацию
    show_deployment_info
}

# Обработка ошибок
trap 'print_error "Скрипт завершен с ошибкой"; exit 1' ERR

# Запуск основной функции
main "$@"