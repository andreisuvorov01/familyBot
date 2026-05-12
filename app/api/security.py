import hmac
import hashlib
import json
import time
from urllib.parse import parse_qsl
from fastapi import HTTPException, Header
from app.core.config import settings


def verify_telegram_data(init_data: str) -> dict:
    """
    Проверяет подпись Telegram и возвращает данные пользователя.
    """
    if not init_data:
        raise HTTPException(status_code=401, detail="Init data is missing")

    # 1. Парсим строку
    vals = dict(parse_qsl(init_data))
    hash_to_check = vals.pop("hash", None)

    if not hash_to_check:
        raise HTTPException(status_code=401, detail="Hash is missing")

    # 2. Проверка на "протухание" данных (не старше 24 часов)
    auth_date = int(vals.get("auth_date", 0))
    if time.time() - auth_date > 86400:
        raise HTTPException(status_code=401, detail="Init data expired")

    # 3. Валидация подписи
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(vals.items()))
    secret_key = hmac.new(b"WebAppData", settings.BOT_TOKEN.encode(), hashlib.sha256).digest()
    calculated_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    if calculated_hash != hash_to_check:
        raise HTTPException(status_code=403, detail="Invalid signature (data tampered)")

    # 4. Извлекаем объект пользователя
    try:
        user_data = json.loads(vals.get("user", "{}"))
        return user_data
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid user data format")
