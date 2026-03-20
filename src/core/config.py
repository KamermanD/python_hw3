from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Any
import json
import os
from pydantic import Field, PostgresDsn, SecretStr, field_validator


class AppConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=os.getenv("ENV_FILE", ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

    DB_USER: str
    DB_PASS: SecretStr
    DB_HOST: str
    DB_PORT: int = 5432
    DB_NAME: str
    DB_INIT: bool = False
    ENABLE_SQL_LOG: bool = False
    DB_ECHO: bool = False
    # JWT_SECRET: str = os.environ.get("JWT_SECRET", "supersecret")

    @property
    def database_async_dsn(self) -> str:
        return str(
            PostgresDsn.build(
                scheme="postgresql+asyncpg",
                username=self.DB_USER,
                password=self.DB_PASS.get_secret_value(),
                host=self.DB_HOST,
                port=self.DB_PORT,
                path=self.DB_NAME,
            )
        )

    @property
    def database_sync_dsn(self) -> str:
        return str(
            PostgresDsn.build(
                scheme="postgresql",
                username=self.DB_USER,
                password=self.DB_PASS.get_secret_value(),
                host=self.DB_HOST,
                port=self.DB_PORT,
                path=self.DB_NAME,
            )
        )

    REDIS_HOST: str
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: SecretStr | None = None
    REDIS_DB: int = 0
    CACHE_USE_SSL: bool = False

    @property
    def cache_dsn(self) -> str:
  
        pwd = (
            f":{self.REDIS_PASSWORD.get_secret_value()}" 
            if self.REDIS_PASSWORD 
            else ""
        )
        credentials = f"{pwd }@" if pwd  else ""
        protocol = "rediss" if self.CACHE_USE_SSL else "redis"

        return f"{protocol }://{credentials }{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    JWT_SECRET: SecretStr

    CORS_ORIGINS: List[str] = []
    CORS_HEADERS: List[str] = ["*"]
    CORS_METHODS: List[str] = ["*"]
    CORS_CREDENTIALS: bool = True

    CLEANUP_INTERVAL_MIN: int = Field(
        default=1, description="Интервал очистки в минутах"
    )

    LOG_LEVEL: str = "INFO"

    @field_validator("CORS_ORIGINS", "CORS_HEADERS", "CORS_METHODS", mode="before")
    @classmethod
    def normalize_list(cls, value: Any) -> Any:
        if isinstance(value, str):
            if value.startswith("[") and value.endswith("]"):
                try:
                    return json.loads(value)
                except json.JSONDecodeError:
                    pass
            return [item.strip() for item in value.split(",") if item.strip()]
        return value


settings = AppConfig()

if __name__ == "__main__":
    print("Загрузка конфигурации")
    
    print(
        settings .model_dump(
            exclude={
                "DB_PASS",
                "SMTP_PASSWORD",
                "REDIS_PASSWORD",
                "SECRET"
            }
        )
    )
    print("\nРассчитанные DSNs")
    print(f"Асинхронная база данных DSN: {settings .database_async_dsn}")
    print(f"Синхронизировать DSN базы данных: {settings .database_sync_dsn}")
    print(f"Redis DSN: {settings .cache_dsn}")

    print("\nСекретные значения (скрытые)")
    print(f"DB Password: {settings .DB_PASS}")
    print(f"Cache Password: {settings .REDIS_PASSWORD}")
    print(f"Secret Key: {settings .JWT_SECRET}")
