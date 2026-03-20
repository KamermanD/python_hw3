from typing import AsyncGenerator
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from src.core.logger import logger
from src.core.config import settings 


class Base(DeclarativeBase):
    pass


db_engine = create_async_engine(
    settings .database_async_dsn, 
    echo=settings .ENABLE_SQL_LOG
)
async_session_factory = async_sessionmaker(
    db_engine, 
    class_=AsyncSession, 
    expire_on_commit=False
)


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        yield session


async def clear_database_tables():
    async with db_engine.begin() as connection:
        try:
            await connection.run_sync(Base.metadata.drop_all)
        except Exception as err:
            logger.error(f"Ошибка при удалении таблиц: {err}")


async def initialize_database(recreate=False):

    async with db_engine.begin() as connection:
        try:
            if recreate:
                logger.debug("Удаление таблиц...")
                await connection.run_sync(Base.metadata.drop_all)

            logger.debug("Создание таблиц...")
            await connection.run_sync(Base.metadata.create_all)
        except Exception as exc:
            logger.error(f"Ошибка при создании таблиц: {exc}")
            raise
