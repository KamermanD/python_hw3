import pytest
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload
from uuid import uuid4
from src.models.project import ProjectEntity
from src.models.user import init_user_db, SQLAlchemyUserDatabase
from src.models.user import AppUser
from tests.helpers import create_user_fixture, create_project_fixture, create_link_fixture, fetch_user_with_links, fetch_project_with_users


@pytest.mark.asyncio
class TestUserModel:

    async def test_user_init_fields(self, db_session: AsyncSession):

        user_data = {
            "email": "demo@example.com",
            "hashed_password": "securehash",
            "is_active": True,
            "is_superuser": False,
            "is_verified": False,
        }

        user = AppUser(**user_data)

        assert user.email == user_data["email"]
        assert user.hashed_password == user_data["hashed_password"]
        assert user.is_active == user_data["is_active"]
        assert user.is_superuser == user_data["is_superuser"]
        assert user.is_verified == user_data["is_verified"]

        db_session.add(user)

    async def test_unique_email_constraint(self, db_session: AsyncSession):

        unique_email = f"user_{uuid4().hex}@example.com"

        first_user = await create_user_fixture(
            session=db_session, prepared_email=unique_email, password="pass1"
        )

        stmt = select(AppUser).where(AppUser.id == first_user.id)
        result = await db_session.execute(stmt)
        persisted_user = result.scalar_one()

        duplicate_user = AppUser(
            email=persisted_user.email,
            hashed_password="anotherpass",
            is_active=True,
            is_superuser=False,
            is_verified=False,
        )

        db_session.add(duplicate_user)
        with pytest.raises(IntegrityError):
            await db_session.flush()

    async def test_user_database_provider(self, db_session):

        generator = init_user_db(db_session)
        db_instance = await generator.__anext__()
        assert isinstance(db_instance, SQLAlchemyUserDatabase)
        assert db_instance.session == db_session
        assert db_instance.user_table == AppUser

        with pytest.raises(StopAsyncIteration):
            await generator.__anext__()

    async def test_user_project_links(self, db_session: AsyncSession):

        account = await create_user_fixture(session=db_session)

        proj_a = await create_project_fixture(
            session=db_session,
            title="Alpha",
            details="Alpha desc",
            owner=account,
        )

        proj_b = await create_project_fixture(
            session=db_session,
            title="Beta",
            details="Beta desc",
            owner=account,
            participants=[account],
        )

        await db_session.commit()

        proj_with_members = await fetch_project_with_users(db_session, proj_b.id)

        stmt = (
            select(AppUser)
            .where(AppUser.id == account.id)
            .options(selectinload(AppUser.projects))
        )
        result = await db_session.execute(stmt)
        loaded_account = result.scalar_one()
        assert len(loaded_account.projects) >= 1 
        assert any(p.id == proj_b.id for p in loaded_account.projects)
        assert any(m.id == account.id for m in proj_with_members.members)

    async def test_user_owns_links(
        self, db_session: AsyncSession,
        sample_user: AppUser, 
        sample_project: ProjectEntity
    ):

        link_one = await create_link_fixture(
            session=db_session,
            url="https://site.com/one",
            code=f"link_one_{uuid4().hex[:6]}",
            owner=sample_user,
            project=sample_project,
        )

        link_two = await create_link_fixture(
            session=db_session,
            url="https://site.com/two",
            code=f"link_two_{uuid4().hex[:6]}",
            owner=sample_user,
            project=sample_project,
        )

        await db_session.commit()
        user_loaded = await fetch_user_with_links(db_session, sample_user.id)

        assert user_loaded is not None
        assert len(user_loaded.links) >= 2
        assert any(l.original_url.endswith("/one") for l in user_loaded.links)
        assert any(l.original_url.endswith("/two") for l in user_loaded.links)

    async def test_user_links_with_fixtures(
        self, 
        db_session: AsyncSession, 
        sample_user: AppUser, 
        multiple_links: list
    ):

        user_loaded = await fetch_user_with_links(db_session, sample_user.id)

        assert user_loaded is not None
        assert len(user_loaded.links) >= len(multiple_links)
        existing_ids = {link.id for link in user_loaded.links}
        for link in multiple_links:
            assert link.id in existing_ids
