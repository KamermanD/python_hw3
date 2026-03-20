import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from src.models.user import AppUser
from src.models.project import ProjectEntity
from tests.helpers import create_user_fixture, create_project_fixture, create_link_fixture, attach_user_to_project


@pytest.mark.asyncio
class TestEntityRelationships:

    async def test_project_member_association(self, db_session: AsyncSession):

        owner_user = await create_user_fixture(session=db_session)
        member_a = await create_user_fixture(session=db_session)
        member_b = await create_user_fixture(session=db_session)

        project_fetched = await create_project_fixture(session=db_session, title="Project Alpha", owner=owner_user)

        await attach_user_to_project(db_session, project_fetched.id, owner_user.id, admin=True)
        await attach_user_to_project(db_session, project_fetched.id, member_a.id)
        await attach_user_to_project(db_session, project_fetched.id, member_b.id)

        await db_session.commit()

        stmt = select(ProjectEntity).where(ProjectEntity.id == project_fetched.id).options(selectinload(ProjectEntity.members))
        result = await db_session.execute(stmt)
        project_fetched = result.scalar_one()

        assert len(project_fetched.members) == 3

        stmt = select(AppUser).where(AppUser.id == member_a.id).options(selectinload(AppUser.projects))
        result = await db_session.execute(stmt)
        user_fetched = result.scalar_one()

        assert len(user_fetched.projects) == 1
        assert user_fetched.projects[0].id == project_fetched.id

    async def test_project_contains_links(self, db_session: AsyncSession):
        author = await create_user_fixture(session=db_session)
        project_fetched = await create_project_fixture(session=db_session, title="Project Beta", owner=author)

        link_one = await create_link_fixture(session=db_session, url="https://site.com/1", owner=author, project=project_fetched)
        link_two = await create_link_fixture(session=db_session, url="https://example.com/2", owner=author, project=project_fetched)

        await db_session.commit()

        stmt = select(ProjectEntity).where(ProjectEntity.id == project_fetched.id).options(selectinload(ProjectEntity.links))
        result = await db_session.execute(stmt)
        project_fetched = result.scalar_one()

        assert len(project_fetched.links) == 2
        assert all(link.project_id == project_fetched.id for link in project_fetched.links)

    async def test_user_links_association(self, db_session: AsyncSession):

        user_fetched = await create_user_fixture(session=db_session)
        project_gamma = await create_project_fixture(session=db_session, title="Project Gamma", owner=user_fetched)

        link_one = await create_link_fixture(session=db_session, url="https://site.com/3", owner=user_fetched, project=project_gamma)
        link_two = await create_link_fixture(session=db_session, url="https://site.com/4", owner=user_fetched, project=project_gamma)

        await db_session.commit()

        stmt = select(AppUser).where(AppUser.id == user_fetched.id).options(selectinload(AppUser.links))
        result = await db_session.execute(stmt)
        user_fetched = result.scalar_one()

        assert len(user_fetched.links) == 2
        assert all(link.owner_id == user_fetched.id for link in user_fetched.links)

    async def test_admin_user_access_to_projects(self, db_session: AsyncSession):
        admin_fetched = await create_user_fixture(session=db_session, superuser=True, prepared_email="admin_test@example.com")
        project_owner = await create_user_fixture(session=db_session)

        project_delta = await create_project_fixture(session=db_session, title="Project Delta", owner=project_owner)
        await attach_user_to_project(db_session, project_id=project_delta.id, user_id=admin_fetched.id, admin=True)

        await db_session.commit()

        stmt = select(AppUser).where(AppUser.id == admin_fetched.id).options(selectinload(AppUser.projects))
        result = await db_session.execute(stmt)
        admin_fetched = result.scalar_one()

        assert len(admin_fetched.projects) == 1
        assert admin_fetched.projects[0].id == project_delta.id

    async def test_user_multiple_project_ownership(self, db_session: AsyncSession):

        user_fetched = await create_user_fixture(session=db_session)

        project_one = await create_project_fixture(session=db_session, title="User Project 1", owner=user_fetched)
        project_two = await create_project_fixture(session=db_session, title="User Project 2", owner=user_fetched)

        await attach_user_to_project(db_session, project_one.id, user_fetched.id, admin=True)
        await attach_user_to_project(db_session, project_two.id, user_fetched.id, admin=True)

        await db_session.commit()

        stmt = select(AppUser).where(AppUser.id == user_fetched.id).options(selectinload(AppUser.projects))
        result = await db_session.execute(stmt)
        user_fetched = result.scalar_one()

        assert len(user_fetched.projects) == 2

        owned_projects = [p for p in user_fetched.projects if p.owner_id == user_fetched.id]
        assert len(owned_projects) == 2
