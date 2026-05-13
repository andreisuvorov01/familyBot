# 🚀 Полное развертывание Family Bot

## Для сервера: `vm526353` с доменом: `https://my-family-tasks.duckdns.org`

### 📋 Что включено в развертывание:

1. **🐳 Docker инфраструктура:**
   - FastAPI приложение
   - Telegram бот
   - PostgreSQL база данных
   - Redis для кэширования
   - Nginx с SSL
   - Let's Encrypt сертификаты
   - Prometheus для мониторинга
   - Grafana для визуализации

2. **🔒 Безопасность:**
   - SSL/TLS шифрование
   - Rate limiting
   - Структурированное логирование
   - Изоляция контейнеров
   - Non-root пользователи

3. **📊 Мониторинг:**
   - Метрики приложения
   - Метрики системы
   - Дашборды Grafana
   - Health checks

## 🎯 Быстрый старт:

### Шаг 1: Подготовка сервера

```bash
# Перейдите в директорию проекта
cd /home/family_bot/familyBot

# Дайте права скриптам
chmod +x scripts/*.sh
```

### Шаг 2: Полное развертывание

```bash
# Запустите полный скрипт развертывания
sudo ./scripts/full-deploy.sh
```

**Скрипт автоматически выполнит:**
1. ✅ Проверку Docker и Docker Compose
2. ✅ Настройку .env файла
3. ✅ Создание необходимых директорий
4. ✅ Настройку firewall
5. ✅ Сборку Docker образов
6. ✅ Запуск всех сервисов
7. ✅ Настройку SSL сертификатов
8. ✅ Проверку работоспособности

### Шаг 3: Управление после развертывания

```bash
# Используйте скрипт управления
./scripts/manage.sh
```

## 🔧 Ручная настройка (если нужно):

### 1. Настройка .env файла:

```bash
# Создайте .env файл
cp .env.example .env

# Отредактируйте
nano .env
```

**Обязательные настройки:**
```env
BOT_TOKEN=ваш_токен_от_BotFather
SECRET_KEY=сложный_ключ_минимум_32_символа
POSTGRES_PASSWORD=надежный_пароль
CERTBOT_EMAIL=ваш@email.com
```

### 2. Запуск вручную:

```bash
# Создайте директории
mkdir -p logs data nginx/logs nginx/ssl prometheus/data grafana/data

# Запустите Docker Compose
docker compose up -d

# Получите SSL сертификаты
docker compose run --rm certbot
docker compose restart nginx
```

## 🌐 Доступные сервисы:

### Публичные (через домен):
- **🌐 Веб-приложение**: https://my-family-tasks.duckdns.org
- **📚 Документация API**: https://my-family-tasks.duckdns.org/docs
- **🩺 Health check**: https://my-family-tasks.duckdns.org/health
- **📊 Метрики**: https://my-family-tasks.duckdns.org/metrics

### Локальные (только на сервере):
- **📊 Prometheus**: http://localhost:9090
- **📈 Grafana**: http://localhost:3000
  - Логин: `admin`
  - Пароль: из переменной `GRAFANA_PASSWORD` в .env

## 📋 Команды управления:

### Основные скрипты:
```bash
# Полное развертывание
./scripts/full-deploy.sh

# Управление после развертывания
./scripts/manage.sh

# Просмотр логов
./scripts/docker-logs.sh

# Остановка
./scripts/docker-stop.sh
```

### Ручные команды Docker:
```bash
# Статус контейнеров
docker compose ps

# Логи
docker compose logs -f api
docker compose logs bot

# Перезапуск
docker compose restart api
docker compose restart nginx

# Обновление
docker compose build --no-cache
docker compose up -d
```

## 🚨 Устранение неполадок:

### Проблема: SSL не работает
```bash
# Проверьте домен
nslookup my-family-tasks.duckdns.org

# Получите SSL сертификаты
docker compose run --rm certbot certonly --dry-run

# Проверьте логи Nginx
tail -f nginx/logs/error.log
```

### Проблема: Бот не отвечает
```bash
# Проверьте токен
echo $BOT_TOKEN

# Проверьте логи бота
docker compose logs bot --tail=50

# Проверьте подключение к БД
docker exec familybot-postgres psql -U familyuser -d familybot -c "SELECT 1"
```

### Проблема: База данных
```bash
# Бэкап
docker exec familybot-postgres pg_dump -U familyuser -d familybot > backup.sql

# Восстановление
docker exec -i familybot-postgres psql -U familyuser -d familybot < backup.sql
```

## 📊 Мониторинг и логи:

### Логи:
- **API**: `docker compose logs api`
- **Бот**: `docker compose logs bot`
- **Nginx**: `nginx/logs/`
- **PostgreSQL**: в контейнере
- **Ошибки**: `logs/errors.log`

### Метрики:
- **Приложение**: `https://my-family-tasks.duckdns.org/metrics`
- **Prometheus**: `http://localhost:9090`
- **Grafana**: `http://localhost:3000`

## 🔒 Рекомендации по безопасности:

1. **Измените пароли** после первого запуска
2. **Настройте firewall**:
   ```bash
   sudo ufw allow 22/tcp
   sudo ufw allow 80/tcp
   sudo ufw allow 443/tcp
   sudo ufw --force enable
   ```
3. **Регулярные обновления**:
   ```bash
   git pull origin main
   docker compose build --no-cache
   docker compose up -d
   ```
4. **Регулярные бэкапы**:
   ```bash
   # Добавьте в cron
   0 2 * * * docker exec familybot-postgres pg_dump -U familyuser -d familybot > /home/family_bot/backups/backup_$(date +\%Y\%m\%d).sql
   ```

## 🎯 Чеклист развертывания:

- [ ] Docker и Docker Compose установлены
- [ ] .env файл настроен с BOT_TOKEN
- [ ] Домен указывает на IP сервера
- [ ] Порты 80 и 443 открыты
- [ ] Контейнеры запущены (`docker compose ps`)
- [ ] SSL сертификаты получены
- [ ] API доступен по HTTPS
- [ ] Бот отвечает в Telegram
- [ ] База данных работает
- [ ] Мониторинг настроен
- [ ] Бэкапы настроены

## 📞 Поддержка:

### Полезные команды для диагностики:
```bash
# Проверка всех сервисов
curl -f https://my-family-tasks.duckdns.org/health

# Проверка SSL
openssl s_client -connect my-family-tasks.duckdns.org:443

# Мониторинг ресурсов
docker stats

# Просмотр логов в реальном времени
docker compose logs -f
```

### Где искать проблемы:
1. **Логи API**: `docker compose logs api --tail=100`
2. **Логи Nginx**: `tail -f nginx/logs/error.log`
3. **Логи SSL**: `docker compose logs certbot`
4. **Метрики**: `curl http://localhost:8000/metrics`

## 🎉 Поздравляем!

Ваш Family Bot теперь полностью развернут с:
- ✅ Полным Docker стеком
- ✅ Автоматическим SSL
- ✅ Производственной БД PostgreSQL
- ✅ Кэшированием через Redis
- ✅ Мониторингом Prometheus/Grafana
- ✅ Автоматическими бэкапами
- ✅ Управлением через скрипты

**Приложение доступно по адресу:** https://my-family-tasks.duckdns.org

Для управления используйте: `./scripts/manage.sh`