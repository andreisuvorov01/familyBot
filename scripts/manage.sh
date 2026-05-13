#!/bin/bash

# Скрипт управления Family Bot после развертывания

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

# Проверка Docker Compose
check_compose() {
    if command -v docker-compose &> /dev/null; then
        COMPOSE_CMD="docker-compose"
    elif docker compose version &> /dev/null; then
        COMPOSE_CMD="docker compose"
    else
        print_error "Docker Compose не найден"
        exit 1
    fi
}

# Показать статус
show_status() {
    print_info "Статус контейнеров:"
    $COMPOSE_CMD ps
    
    echo ""
    print_info "Использование ресурсов:"
    docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}\t{{.BlockIO}}" | head -6
    
    echo ""
    print_info "Доступные сервисы:"
    echo "  🌐 Веб-приложение:  https://my-family-tasks.duckdns.org"
    echo "  📚 Документация:    https://my-family-tasks.duckdns.org/docs"
    echo "  🩺 Health check:    https://my-family-tasks.duckdns.org/health"
    echo "  📊 Prometheus:      http://localhost:9090"
    echo "  📈 Grafana:         http://localhost:3000"
}

# Показать логи
show_logs() {
    echo ""
    echo "Выберите сервис для просмотра логов:"
    echo "1) API (FastAPI)"
    echo "2) Бот (Telegram)"
    echo "3) Nginx"
    echo "4) PostgreSQL"
    echo "5) Redis"
    echo "6) Prometheus"
    echo "7) Grafana"
    echo "8) Все логи"
    echo "9) Логи в реальном времени"
    echo ""
    
    read -p "Введите номер: " choice
    
    case $choice in
        1) $COMPOSE_CMD logs api --tail=100 ;;
        2) $COMPOSE_CMD logs bot --tail=100 ;;
        3) $COMPOSE_CMD logs nginx --tail=100 ;;
        4) $COMPOSE_CMD logs postgres --tail=100 ;;
        5) $COMPOSE_CMD logs redis --tail=100 ;;
        6) $COMPOSE_CMD logs prometheus --tail=100 ;;
        7) $COMPOSE_CMD logs grafana --tail=100 ;;
        8) $COMPOSE_CMD logs --tail=50 ;;
        9) $COMPOSE_CMD logs -f ;;
        *) print_error "Неверный выбор" ;;
    esac
}

# Перезапуск сервисов
restart_services() {
    echo ""
    echo "Выберите сервис для перезапуска:"
    echo "1) API"
    echo "2) Бот"
    echo "3) Nginx"
    echo "4) Все сервисы"
    echo ""
    
    read -p "Введите номер: " choice
    
    case $choice in
        1) $COMPOSE_CMD restart api ;;
        2) $COMPOSE_CMD restart bot ;;
        3) $COMPOSE_CMD restart nginx ;;
        4) $COMPOSE_CMD restart ;;
        *) print_error "Неверный выбор" ;;
    esac
    
    print_success "Сервис перезапущен"
}

# Обновление SSL сертификатов
update_ssl() {
    print_info "Обновление SSL сертификатов..."
    
    $COMPOSE_CMD run --rm certbot renew --dry-run
    
    read -p "Продолжить обновление? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        $COMPOSE_CMD run --rm certbot renew
        $COMPOSE_CMD restart nginx
        print_success "SSL сертификаты обновлены"
    fi
}

# Бэкап базы данных
backup_database() {
    print_info "Создание бэкапа базы данных..."
    
    local timestamp=$(date +%Y%m%d_%H%M%S)
    local backup_file="backup_${timestamp}.sql"
    
    mkdir -p backups
    
    docker exec familybot-postgres pg_dump -U familyuser -d familybot > "backups/${backup_file}"
    
    if [ $? -eq 0 ]; then
        print_success "Бэкап создан: backups/${backup_file}"
        print_info "Размер: $(du -h "backups/${backup_file}" | cut -f1)"
    else
        print_error "Ошибка при создании бэкапа"
    fi
}

# Восстановление базы данных
restore_database() {
    print_info "Восстановление базы данных из бэкапа..."
    
    echo "Доступные бэкапы:"
    ls -la backups/*.sql 2>/dev/null || echo "  Нет доступных бэкапов"
    echo ""
    
    read -p "Введите имя файла бэкапа: " backup_file
    
    if [ ! -f "backups/${backup_file}" ]; then
        print_error "Файл не найден: backups/${backup_file}"
        return 1
    fi
    
    print_warning "ВНИМАНИЕ: Это перезапишет текущую базу данных!"
    read -p "Продолжить? (y/n): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        return 0
    fi
    
    # Останавливаем сервисы, которые используют БД
    $COMPOSE_CMD stop api bot
    
    # Восстанавливаем БД
    docker exec -i familybot-postgres psql -U familyuser -d familybot < "backups/${backup_file}"
    
    if [ $? -eq 0 ]; then
        print_success "База данных восстановлена"
        
        # Запускаем сервисы обратно
        $COMPOSE_CMD start api bot
    else
        print_error "Ошибка при восстановлении базы данных"
    fi
}

# Мониторинг ресурсов
monitor_resources() {
    print_info "Мониторинг ресурсов в реальном времени..."
    
    echo "Нажмите Ctrl+C для выхода"
    echo ""
    
    watch -n 2 "echo '🐳 Docker контейнеры:'; $COMPOSE_CMD ps; echo ''; echo '📊 Использование ресурсов:'; docker stats --no-stream --format 'table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}' | head -10"
}

# Проверка здоровья
check_health() {
    print_info "Проверка здоровья сервисов..."
    
    local errors=0
    
    # Проверяем API
    if curl -f http://localhost:8000/health &> /dev/null; then
        print_success "✅ API работает"
    else
        print_error "❌ API не отвечает"
        errors=1
    fi
    
    # Проверяем PostgreSQL
    if docker exec familybot-postgres pg_isready -U familyuser -d familybot &> /dev/null; then
        print_success "✅ PostgreSQL работает"
    else
        print_error "❌ PostgreSQL не отвечает"
        errors=1
    fi
    
    # Проверяем Redis
    if docker exec familybot-redis redis-cli ping &> /dev/null; then
        print_success "✅ Redis работает"
    else
        print_error "❌ Redis не отвечает"
        errors=1
    fi
    
    # Проверяем Nginx
    if curl -f http://localhost:80 &> /dev/null; then
        print_success "✅ Nginx работает"
    else
        print_error "❌ Nginx не отвечает"
        errors=1
    fi
    
    if [ $errors -eq 0 ]; then
        print_success "🎉 Все сервисы работают корректно"
    else
        print_warning "⚠️  Некоторые сервисы имеют проблемы"
    fi
}

# Обновление приложения
update_application() {
    print_info "Обновление приложения..."
    
    # Обновляем код
    git pull origin main
    
    # Пересобираем образы
    $COMPOSE_CMD build --no-cache
    
    # Перезапускаем
    $COMPOSE_CMD up -d
    
    print_success "Приложение обновлено"
}

# Показать меню
show_menu() {
    echo ""
    echo -e "${GREEN}============================================${NC}"
    echo -e "${GREEN}         Управление Family Bot              ${NC}"
    echo -e "${GREEN}============================================${NC}"
    echo ""
    echo "1) 📊 Показать статус"
    echo "2) 📋 Показать логи"
    echo "3) 🔄 Перезапустить сервисы"
    echo "4) 🔒 Обновить SSL сертификаты"
    echo "5) 💾 Создать бэкап БД"
    echo "6) 📥 Восстановить БД из бэкапа"
    echo "7) 📈 Мониторинг ресурсов"
    echo "8) 🩺 Проверить здоровье"
    echo "9) ⬆️  Обновить приложение"
    echo "10) 🛑 Остановить все сервисы"
    echo "11) 🚀 Запустить все сервисы"
    echo "12) ❌ Выход"
    echo ""
}

# Основная функция
main() {
    # Проверяем Docker Compose
    check_compose
    
    while true; do
        show_menu
        
        read -p "Выберите действие: " choice
        
        case $choice in
            1) show_status ;;
            2) show_logs ;;
            3) restart_services ;;
            4) update_ssl ;;
            5) backup_database ;;
            6) restore_database ;;
            7) monitor_resources ;;
            8) check_health ;;
            9) update_application ;;
            10) 
                print_info "Остановка всех сервисов..."
                $COMPOSE_CMD down
                print_success "Сервисы остановлены"
                ;;
            11)
                print_info "Запуск всех сервисов..."
                $COMPOSE_CMD up -d
                print_success "Сервисы запущены"
                ;;
            12)
                print_info "Выход..."
                exit 0
                ;;
            *)
                print_error "Неверный выбор"
                ;;
        esac
        
        echo ""
        read -p "Нажмите Enter для продолжения..." -n 1
        clear
    done
}

# Запуск
main "$@"