from sqlalchemy.ext.asyncio import AsyncSession
import pytest
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from src.models.link import Link
from src.models.project import ProjectEntity
from src.models.user import AppUser
from tests.helpers import create_user_fixture, create_project_fixture, create_link_fixture, attach_user_to_project


@pytest.mark.asyncio
class TestProjectEntityModel:

    async def test_project_creation_flow(self, db_session: AsyncSession):

        new_project = ProjectEntity(
            name="Demo Project",
            description="Demo description",
            default_link_lifetime_days=30,
            created_at=datetime.now(timezone.utc),
            owner_id=None,
        )

        db_session.add(new_project)
        await db_session.commit()
        await db_session.refresh(new_project)

        assert isinstance(new_project.id, int)
        assert new_project.name == "Demo Project"
        assert new_project.description == "Demo description"
        assert new_project.default_link_lifetime_days == 30
        assert isinstance(new_project.created_at, datetime)
        assert new_project.created_at.tzinfo == timezone.utc
        assert new_project.owner_id is None
        
        expected = f"Project(id={new_project.id}, name={new_project.name}, owner_id={new_project.owner_id})"
        assert repr(new_project) == expected

    async def test_project_fetch_by_id(self, db_session: AsyncSession):

        created_project = await create_project_fixture(
            session=db_session,
            title="Readable Project",
            details="Readable description",
        )

        fetched_project = await db_session.get(ProjectEntity, created_project.id)

        assert fetched_project is not None
        assert fetched_project.id == created_project.id
        assert fetched_project.name == "Readable Project"
        assert fetched_project.description == "Readable description"

    async def test_project_modification(self, db_session: AsyncSession):

        editable_project = await create_project_fixture(
            session=db_session,
            title="Old Name", 
            details="Old Description"
        )

        editable_project.name = "New Name"
        editable_project.description = "New Description"

        await db_session.commit()
        await db_session.refresh(editable_project)

        assert editable_project.name == "New Name"
        assert editable_project.description == "New Description"

    async def test_project_removal(self, db_session: AsyncSession):

        removable_project = await create_project_fixture(
            session=db_session,
            title="Delete Me",
            details="To be removed",
        )

        proj_id = removable_project.id

        await db_session.delete(removable_project)
        await db_session.commit()
        assert await db_session.get(ProjectEntity, proj_id) is None

    async def test_project_link_binding(self, db_session: AsyncSession, sample_user: AppUser):

        container_project = await create_project_fixture(
            session=db_session,
            title="Link Container",
            details="Holds links",
            owner=sample_user,
        )

        link_one = await create_link_fixture(
            session=db_session,
            url="https://site.com/a",
            owner=sample_user,
            project=container_project,
        )

        link_two = await create_link_fixture(
            session=db_session,
            url="https://site.com/b",
            owner=sample_user,
            project=container_project,
        )

        stmt = (
            select(ProjectEntity)
            .where(ProjectEntity.id == container_project.id)
            .options(selectinload(ProjectEntity.links))
        )
        result = await db_session.execute(stmt)
        container_project = result.scalar_one()

        assert len(container_project.links) == 2
        assert any(l.original_url.endswith("/a")  for l in container_project.links)
        assert any(l.original_url.endswith("/b")  for l in container_project.links)

        stmt = (
            select(Link)
            .where(Link.id.in_([link_one.id, link_two.id]))
            .options(selectinload(Link.project))
        )
        result = await db_session.execute(stmt)
        related_links = result.scalars().all()

        for link in related_links:
            assert link.project_id == container_project.id
            assert link.project.name == "Link Container"

    async def test_project_user_membership(self, db_session: AsyncSession):

        base_project = await create_project_fixture(
            db_session,
            title="Members Project",
            details="Members inside",
        )

        member_one = await create_user_fixture(db_session)
        member_two = await create_user_fixture(db_session)

        await attach_user_to_project(db_session, base_project.id, member_one.id, admin=False)
        await attach_user_to_project(db_session, base_project.id, member_two.id, admin=False)
        await db_session.commit()

        stmt = (
            select(ProjectEntity)
            .where(ProjectEntity.id == base_project.id)
            .options(selectinload(ProjectEntity.members))
        )
        result = await db_session.execute(stmt)
        base_project = result.scalar_one()

        assert len(base_project.members) == 2
        assert any(m.id == member_one.id for m in base_project.members)
        assert any(m.id == member_two.id for m in base_project.members)

        stmt = (
            select(AppUser)
            .where(AppUser.id.in_([member_one.id, member_two.id]))
            .options(selectinload(AppUser.projects))
        )
        result = await db_session.execute(stmt)
        users_loaded = result.scalars().all()

        for u in users_loaded:
            assert len(u.projects) == 1
            assert u.projects[0].id == base_project.id

    async def test_project_fixture_integrity(
        self, db_session: AsyncSession, project_with_users: ProjectEntity
    ):

        stmt = (
            select(ProjectEntity)
            .where(ProjectEntity.id == project_with_users.id)
            .options(selectinload(ProjectEntity.members))
        )
        result = await db_session.execute(stmt)
        project_loaded = result.scalar_one()

        assert  len(project_loaded.members) >= 2
        assert project_loaded.name == "Collaborative Project"

    async def test_project_links_fixture(
        self, db_session: AsyncSession, sample_project: ProjectEntity, multiple_links: list
    ):

        stmt = (
            select(ProjectEntity)
            .where(ProjectEntity.id == sample_project.id)
            .options(selectinload(ProjectEntity.links))
        )
        result = await db_session.execute(stmt)
        project_loaded = result.scalar_one()

        assert len(project_loaded.links) >= 2
