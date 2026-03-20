from fastapi_cache.backends.redis import RedisBackend
from fastapi_cache import FastAPICache
from redis.asyncio import Redis
from src.core.logger import logger
from src.core.config import settings 
from pydantic import HttpUrl
import json
from typing import Optional, Any
from datetime import datetime, timezone


class CustomPydanticJSONEncoder(json.JSONEncoder):

    def default(self, value):
        if hasattr(value, "model_dump"):
            return value.model_dump()

        if isinstance(value, HttpUrl):
            return str(value)

        if isinstance(value, datetime):
            dt_value = value
            if dt_value.tzinfo is None:
                dt_value = dt_value.replace(tzinfo=timezone.utc)
            return dt_value.isoformat()

        return super().default(value)


class AsyncCacheHandler:

    def __init__(self):
        self._redis_client: Optional[Redis] = None
        self._backend: Optional[RedisBackend] = None

    async def initialize(self):
        try:
            password = (settings .REDIS_PASSWORD.get_secret_value() if settings .REDIS_PASSWORD else None)

            self._redis_client = Redis(
                host=settings .REDIS_HOST,
                port=settings .REDIS_PORT,
                password=password,
                db=settings .REDIS_DB,
                decode_responses=True,
                ssl=settings .CACHE_USE_SSL,
            )
            self._backend = RedisBackend(self._redis_client)
            FastAPICache.init(self._backend, prefix="fastapi-cache")
            logger.info("Диспетчер кэша успешно инициализирован")
        except Exception as exc:
            logger.error(f"Не удалось инициализировать диспетчер кэша: {exc}")
            raise

    async def get_value(self, key: str) -> Optional[Any]:

        try:
            raw_data = await self._backend.get(key)
            if raw_data:
                return json.loads(raw_data)
            return None
        except Exception as exc:
            logger.error(f"Ошибка при получении значения кэша для ключа {key}: {exc}")
            return None

    async def set_value(self, key: str, value: Any, ttl_seconds: int = 3600) -> bool:

        try:
            serialized = json.dumps(value, cls=CustomPydanticJSONEncoder)
            await self._backend.set(key, serialized, ttl_seconds)
            return True
        except Exception as exc:
            logger.error(f"Ошибка при установке значения кэша для ключа {key}: {exc}")
            return False

    async def delete_key(self, key: str) -> bool:
        try:
            if "*" in key:
                cursor = 0
                pattern = key
                while True:
                    cursor, keys = await self._redis_client.scan(cursor, match=pattern, count=100)
                    if keys:
                        await self._redis_client.delete(*keys)
                    if cursor == 0:
                        break
            else:
                await self._redis_client.delete(key)
            return True
        except Exception as exc:
            logger.error(f"Ошибка при удалении значения кэша для ключа {key}: {exc}")
            return False

    async def clear_all(self) -> bool:
        try:
            await self._backend.clear()
            return True
        except Exception as exc:
            logger.error(f"Ошибка при очистке кэша: {exc}")
            return False

    async def close_connection(self):
        if self._redis_client:
            await self._redis_client.close()
            logger.info("Подключение к кэшу закрыто")

app_cache = AsyncCacheHandler()
