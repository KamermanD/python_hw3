import pytest_asyncio
from uuid import uuid4
from typing import List
from src.models.project import ProjectEntity
from sqlalchemy.ext.asyncio import AsyncSession
from src.models.link import Link
from src.models.user import AppUser
from tests.helpers import create_user_fixture, create_project_fixture, create_link_fixture, create_bulk_links


@pytest_asyncio.fixture
async def sample_user(db_session: AsyncSession) -> AppUser:
    user_instance = await create_user_fixture(
        session=db_session,
        superuser=False,
        prepared_email="user_basic@example.com",
        password="user_password",
        active=True,
        verified=False,
    )
    return user_instance


@pytest_asyncio.fixture
async def super_user(db_session: AsyncSession) -> AppUser:
    admin_instance = await create_user_fixture(
        session=db_session,
        superuser=True,
        prepared_email="super_admin@example.com",
        password="super_password",
        active=True,
        verified=True,
    )
    return admin_instance


@pytest_asyncio.fixture
async def sample_project(
    db_session: AsyncSession, sample_user: AppUser
) -> ProjectEntity:
    project_obj = await create_project_fixture(
        session=db_session,
        title="Sample Project",
        details="Project used in tests",
        owner=sample_user,
    )
    return project_obj


@pytest_asyncio.fixture
async def project_with_users(
    db_session: AsyncSession, 
    sample_user: AppUser, 
    super_user: AppUser
) -> ProjectEntity:
    project_obj = await create_project_fixture(
        session=db_session,
        title="Collaborative Project",
        details="Project with multiple participants",
        owner=sample_user,
        participants=[sample_user, super_user],
    )
    return project_obj


@pytest_asyncio.fixture
async def single_link(
    db_session: AsyncSession, 
    sample_user: AppUser, 
    sample_project: ProjectEntity
) -> Link:
    link_obj = await create_link_fixture(
        session=db_session,
        url="https://example.com/sample",
        code=f"lnk_{uuid4().hex[:8]}",
        owner=sample_user,
        project=sample_project,
    )
    return link_obj



@pytest_asyncio.fixture
async def multiple_links(
    db_session: AsyncSession, 
    sample_user: AppUser, 
    sample_project: ProjectEntity
) -> List[Link]:
    links_collection = await create_bulk_links(
        session=db_session,
        amount=5,
        owner=sample_user,
        project=sample_project,
    )
    return links_collection
