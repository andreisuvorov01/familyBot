#!/bin/bash
# Первоначальное получение SSL сертификата через Let's Encrypt
# Запускать ОДИН РАЗ перед первым docker compose up с nginx

set -e

if [ -z "${WEBAPP_URL}" ]; then
    source .env 2>/dev/null || true
fi

DOMAIN="${WEBAPP_URL#https://}"
DOMAIN="${DOMAIN#http://}"
EMAIL="${CERTBOT_EMAIL}"

if [ -z "$DOMAIN" ] || [ -z "$EMAIL" ]; then
    echo "Установите WEBAPP_URL и CERTBOT_EMAIL в .env"
    exit 1
fi

echo "Получаем SSL сертификат для домена: $DOMAIN"

# Шаг 1: Запускаем nginx без SSL (временная конфигурация)
cat > /tmp/nginx-nossl.conf << NGINX
server {
    listen 80;
    server_name $DOMAIN;
    location /.well-known/acme-challenge/ {
        root /usr/share/nginx/html;
    }
    location / { return 200 'ok'; }
}
NGINX

docker run --rm -d --name nginx-temp \
  -p 80:80 \
  -v /tmp/nginx-nossl.conf:/etc/nginx/conf.d/default.conf:ro \
  -v nginx_webroot:/usr/share/nginx/html \
  nginx:alpine

# Шаг 2: Получаем сертификат
docker run --rm \
  -v ./nginx/ssl:/etc/letsencrypt \
  -v nginx_webroot:/usr/share/nginx/html \
  certbot/certbot certonly \
    --webroot \
    --webroot-path=/usr/share/nginx/html \
    -d "$DOMAIN" \
    --email "$EMAIL" \
    --agree-tos \
    --no-eff-email

docker stop nginx-temp

# Шаг 3: Копируем сертификаты в ожидаемые nginx пути
mkdir -p ./nginx/ssl/live
cp ./nginx/ssl/live/"$DOMAIN"/fullchain.pem ./nginx/ssl/live/fullchain.pem
cp ./nginx/ssl/live/"$DOMAIN"/privkey.pem ./nginx/ssl/live/privkey.pem

echo "Сертификаты получены. Теперь запускайте: docker compose up -d"
