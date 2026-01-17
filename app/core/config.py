from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import SecretStr

class Settings(BaseSettings):
    # Pydantic автоматически ищет переменные с такими же именами (регистр не важен)
    BOT_TOKEN: str
    DATABASE_URL: str
    SECRET_KEY: str
    WEBAPP_URL: str

    # Настройка для чтения .env файла
    model_config = SettingsConfigDict(
        env_file=".env",            # Имя файла
        env_file_encoding="utf-8",
        extra="ignore"              # Игнорировать лишние переменные в .env
    )

# Создаем экземпляр настроек, который будем импортировать в другие файлы
settings = Settings()
