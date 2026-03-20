import uvicorn
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from fastapi import FastAPI
from src.core.config import settings 
from src.core.logger import logger
from src.core.database import initialize_database
from src.core.middleware import RequestLoggerMiddleware, init_cors
from src.core.scheduler import Scheduler
from src.utils.cache import app_cache
from src.auth.router import router as auth_router
from src.api.router import router as api_router
from src.api.redirect import router as redirect_router
from src.utils.demo_data import generate_demo_environment


app_scheduler = Scheduler()


async def clear_redis_cache():
    try:
        await app_cache._redis_client.flushdb()
        logger.info("Кэш Redis успешно очищен")
    except Exception as e:
        logger.error(f"Ошибка при очистке кэша Redis: {e}")


async def initialize_database():
    try:
        logger.info("Инициализация базы данных...")
        await initialize_database(recreate=True)
        logger.info("Создание демонстрационных данных...")
        await generate_demo_environment()
        logger.info("База данных успешно инициализирована")
    except Exception as e:
        logger.error(f"Ошибка при инициализации базы данных: {e}")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    await app_cache.initialize()

    app_scheduler.start()

    if settings .DB_INIT:
        logger.debug("Очистка кэша Redis перед запуском базы данных...")
        await clear_redis_cache()
        await initialize_database()

    yield

    logger.info("Очистка кэша Redis перед завершением работы...")
    await clear_redis_cache()
    app_scheduler.stop()
    await app_cache.close_connection()


app = FastAPI(lifespan=lifespan)

init_cors(app)

app.add_middleware(RequestLoggerMiddleware)

app.include_router(api_router)
app.include_router(auth_router)
app.include_router(redirect_router)

if __name__ == "__main__":
    uvicorn.run(
        "src.main:app",
        reload=True,
        host="0.0.0.0",
        log_level="info",
        timeout_keep_alive=20,
        timeout_graceful_shutdown=15,
    )
