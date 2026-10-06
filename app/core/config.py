from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Pydantic автоматически ищет переменные с такими же именами (регистр не важен)
    BOT_TOKEN: str
    DATABASE_URL: str
    SECRET_KEY: str
    WEBAPP_URL: str

    # Часовой пояс по умолчанию для новых пользователей
    DEFAULT_TIMEZONE: str = "Europe/Moscow"

    # Google Calendar (интеграция включается, когда заданы client id/secret)
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    # По умолчанию: {WEBAPP_URL}/api/google/callback
    GOOGLE_REDIRECT_URI: str = ""
    # Ключ Fernet для шифрования refresh token. Если не задан — выводится из SECRET_KEY
    TOKEN_ENCRYPTION_KEY: str = ""

    # Настройка для чтения .env файла
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"  # Имя файла  # Игнорировать лишние переменные в .env
    )

    @property
    def google_enabled(self) -> bool:
        return bool(self.GOOGLE_CLIENT_ID and self.GOOGLE_CLIENT_SECRET)

    @property
    def google_redirect_uri(self) -> str:
        return self.GOOGLE_REDIRECT_URI or f"{self.WEBAPP_URL.rstrip('/')}/api/google/callback"


# Создаем экземпляр настроек, который будем импортировать в другие файлы
settings = Settings()
