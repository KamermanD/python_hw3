
import sys
import os

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
    print(f"[TEST INIT] Added project root: {BASE_DIR}")


import pytest
import asyncio
import pytest_asyncio
from httpx import AsyncClient
from src.main import app as application
from src.core.database import get_async_session
from typing import AsyncGenerator
from dotenv import load_dotenv
from alembic.config import Config
load_dotenv(dotenv_path=".env.test", override=True)
from src.core.config import settings
from fastapi import FastAPI
from src.models.user import AppUser
from alembic import command
from src.models.link import Link
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool
from src.models.project import ProjectEntity
# Импортируем наши фикстуры для тестовых данных
from tests.fixtures import (
    sample_user,
    super_user,
    sample_project,
    project_with_users,
    single_link,
    multiple_links,
)

# BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# if BASE_DIR not in sys.path:
#     sys.path.insert(0, BASE_DIR)
#     print(f"[TEST INIT] Added project root: {BASE_DIR}")


@pytest.fixture(scope="session")
def model_registry():
    return {"user": AppUser,
            "link": Link,
            "project": ProjectEntity}


@pytest.fixture(scope="session")
def async_event_loop():

    loop_policy = asyncio.get_event_loop_policy()
    loop_instance = loop_policy.new_event_loop()
    asyncio.set_event_loop(loop_instance)
    
    yield loop_instance

    pending_tasks = asyncio.all_tasks(loop_instance)
    for task in pending_tasks:
        task.cancel()

    if pending_tasks and not loop_instance.is_closed():
        loop_instance.run_until_complete(
            asyncio.gather(*pending_tasks, return_exceptions=True)
        )

    if not loop_instance.is_closed():
        loop_instance.close()


@pytest.fixture(scope="session", autouse=True)
def load_test_env():

    print("[TEST INIT] Loading .env.test...")
    loaded = load_dotenv(dotenv_path=".env.test", override=True)
    
    if not loaded:
        pytest.fail(".env.test not found, cannot run tests.")

    if not settings.database_async_dsn:
        pytest.fail("DATABASE_URL not found in settings")
    
    db_url = str(settings.database_async_dsn)
    print(f"[TEST INIT] DB: {db_url[: db_url.find('@')]}...")



@pytest_asyncio.fixture(scope="session")
async def async_test_engine(async_event_loop) -> AsyncGenerator[AsyncEngine, None]:

    db_url = settings.database_async_dsn
    engine = create_async_engine(
        db_url, 
        poolclass=NullPool, 
        echo=settings.DB_ECHO
    )

    print("[TEST INIT] Engine created")
    yield engine
    print("[TEST CLEANUP] Disposing engine...")
    await engine.dispose()


@pytest.fixture(scope="session", autouse=True)
def run_test_migrations(async_test_engine: AsyncEngine):
    print("[TEST INIT] Applying migrations...")
    
    alembic_cfg = Config("alembic.ini")
    command.upgrade(alembic_cfg, "head")

    print("[TEST INIT] Migrations applied")
    yield


@pytest_asyncio.fixture(scope="session")
async def session_factory(
    async_test_engine: AsyncEngine,
) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(
        bind=async_test_engine, 
        class_=AsyncSession, 
        expire_on_commit=False
    )


@pytest_asyncio.fixture
async def db_session(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[AsyncSession, None]:


    async with session_factory() as session:
        await session.begin()
        
        try:
            yield session
        finally:
            await session.rollback()
            await session.close()


@pytest.fixture
def test_application(
    session_factory: async_sessionmaker[AsyncSession]
) -> FastAPI:

    async def override_db() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
            yield session

    application.dependency_overrides[get_async_session] = override_db
    print("[TEST INIT] Dependency overridden")

    yield application 

    del application.dependency_overrides[get_async_session]
    print("[TEST CLEANUP] Dependency restored")


@pytest_asyncio.fixture
async def http_client(test_application: FastAPI
) -> AsyncGenerator[AsyncClient, None]:

    async with AsyncClient(app=test_application, base_url="http://test") as client:
        print("[TEST INIT] HTTP client ready")
        yield client
