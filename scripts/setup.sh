#!/bin/bash

# Скрипт настройки сервера для Family Bot

set -e

echo "🛠️  Настройка сервера для Family Bot..."
echo ""

# Проверяем, запущен ли скрипт от root
if [ "$EUID" -ne 0 ]; then 
    echo "⚠️  Рекомендуется запускать скрипт с правами root (sudo)"
    read -p "Продолжить? (y/n): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# 1. Обновление системы
echo "1. 🔄 Обновление системы..."
apt-get update
apt-get upgrade -y

# 2. Установка Python
echo "2. 🐍 Установка Python 3.11..."
apt-get install -y python3.11 python3.11-venv python3.11-dev python3-pip

# 3. Установка Node.js и PM2
echo "3. 📦 Установка Node.js и PM2..."
curl -fsSL https://deb.nodesource.com/setup_18.x | bash -
apt-get install -y nodejs
npm install -g pm2

# 4. Установка PostgreSQL (опционально)
echo "4. 🐘 Установка PostgreSQL (опционально)..."
read -p "Установить PostgreSQL? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    apt-get install -y postgresql postgresql-contrib
    systemctl start postgresql
    systemctl enable postgresql
    
    echo "Создание базы данных и пользователя..."
    sudo -u postgres psql -c "CREATE DATABASE familybot;"
    sudo -u postgres psql -c "CREATE USER familyuser WITH PASSWORD 'your_password_here';"
    sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE familybot TO familyuser;"
    sudo -u postgres psql -c "ALTER USER familyuser WITH SUPERUSER;"
    
    echo "✅ PostgreSQL установлен и настроен"
    echo "📝 Не забудьте обновить DATABASE_URL в .env файле:"
    echo "   DATABASE_URL=postgresql+asyncpg://familyuser:your_password_here@localhost:5432/familybot"
fi

# 5. Установка Nginx (опционально)
echo "5. 🌐 Установка Nginx (опционально)..."
read -p "Установить Nginx? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    apt-get install -y nginx
    systemctl start nginx
    systemctl enable nginx
    
    # Создаем конфиг Nginx
    cat > /etc/nginx/sites-available/familybot << EOF
server {
    listen 80;
    server_name your-domain.com;
    
    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
    
    location /static/ {
        alias /var/www/familybot/app/static/;
        expires 30d;
    }
    
    # WebSocket support
    location /ws/ {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
EOF
    
    ln -sf /etc/nginx/sites-available/familybot /etc/nginx/sites-enabled/
    nginx -t
    systemctl reload nginx
    
    echo "✅ Nginx установлен и настроен"
    echo "📝 Не забудьте:"
    echo "   - Обновить server_name в конфиге Nginx"
    echo "   - Настроить SSL через Let's Encrypt"
fi

# 6. Настройка firewall
echo "6. 🔥 Настройка firewall..."
apt-get install -y ufw
ufw allow 22/tcp  # SSH
ufw allow 80/tcp  # HTTP
ufw allow 443/tcp # HTTPS
ufw --force enable

# 7. Создание пользователя для приложения
echo "7. 👤 Создание пользователя для приложения..."
read -p "Создать пользователя 'familybot'? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    useradd -m -s /bin/bash familybot
    echo "✅ Пользователь familybot создан"
    echo "📝 Для переключения: sudo su - familybot"
fi

# 8. Настройка автозапуска PM2
echo "8. ⚡ Настройка автозапуска PM2..."
pm2 startup
pm2 save

echo ""
echo "🎉 Настройка сервера завершена!"
echo ""
echo "📋 Следующие шаги:"
echo "1. Склонируйте репозиторий:"
echo "   git clone https://github.com/yourusername/familybot.git"
echo "2. Настройте .env файл:"
echo "   cp .env.example .env"
echo "   nano .env"
echo "3. Запустите приложение:"
echo "   ./scripts/start.sh"
echo ""
echo "🔗 Документация:"
echo "   - API: http://localhost:8000/docs"
echo "   - PM2: pm2 status, pm2 logs, pm2 monit"