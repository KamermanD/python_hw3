from sqlalchemy.ext.asyncio import AsyncSession
from src.models.project import ProjectEntity
from src.models.user import AppUser
from datetime import datetime, timezone
from uuid import uuid4
import pytest
from src.models.link import Link, current_utc_time
from tests.helpers import create_link_fixture


@pytest.mark.asyncio
class TestShortLinkModel:
    async def test_link_string_representation(
        self, db_session: AsyncSession, sample_user: AppUser, sample_project: ProjectEntity
    ):
        sample_link = await create_link_fixture(
            session=db_session,
            url="https://mysite.com",
            owner=sample_user,
            project=sample_project,
        )

        result_str = repr(sample_link)
        assert isinstance(result_str, str)

        expected_str = (
            f"Link(id={sample_link.id}, short={sample_link.short_code}, "
            f"orig={sample_link.original_url}, prj={sample_link.project_id}, "
            f"exp={sample_link.expires_at})"
            )
        assert result_str == expected_str

    async def test_link_creation(
        self, db_session: AsyncSession, sample_user: AppUser, sample_project: ProjectEntity
    ):
        code = f"linktest_{uuid4().hex[:8]}"
        new_link = await create_link_fixture(
            session=db_session,
            url="https://mysite.com",
            code=code,
            owner=sample_user,
            project=sample_project,
        )

        await db_session.refresh(new_link)

        assert isinstance(new_link.id, int)
        assert new_link.original_url == "https://mysite.com"
        assert new_link.short_code.startswith("linktest_")
        assert new_link.project_id == sample_project.id
        assert new_link.owner_id == sample_user.id
        assert new_link.clicks_count == 0
        assert new_link.last_clicked_at is None
        assert isinstance(new_link.created_at, datetime)
        assert new_link.created_at.tzinfo == timezone.utc

    async def test_link_retrieval_by_id(
        self, db_session: AsyncSession, sample_user: AppUser, sample_project: ProjectEntity
    ):

        code = f"linkread_{uuid4().hex[:8]}"
        created_link = await create_link_fixture(
            session=db_session,
            url="https://mysite.com",
            code=code,
            owner=sample_user,
            project=sample_project,
        )

        fetched_link = await db_session.get(Link, created_link.id)

        assert fetched_link is not None
        assert fetched_link.id == created_link.id
        assert fetched_link.original_url == "https://mysite.com"
        # assert fetched_link.short_code == code
        # assert fetched_link.project_id == sample_project.id
        # assert fetched_link.owner_id == sample_user.id

    async def test_link_update(
            self, db_session: AsyncSession, single_link: Link
    ):

        single_link.original_url = "https://updated.com"
        single_link.is_public = True

        await db_session.commit()
        # await db_session.flush()     
        await db_session.refresh(single_link)

        assert single_link.original_url == "https://updated.com"
        assert single_link.is_public is True

    async def test_link_deletion(
        self, db_session: AsyncSession, sample_user: AppUser, sample_project: ProjectEntity
    ):

        code = f"linkdel_{uuid4().hex[:8]}"
        link_to_delete = await create_link_fixture(
            session=db_session,
            url="https://mysite.com",
            code=code,
            owner=sample_user,
            project=sample_project,
        )

        link_id = link_to_delete.id

        await db_session.delete(link_to_delete)
        await db_session.commit()
        # await db_session.flush()  
        assert await db_session.get(Link, link_id) is None

    def test_current_utc_time_function(self):
        now = current_utc_time()

        assert isinstance(now, datetime)
        assert now.tzinfo == timezone.utc

    async def test_links_fixture_integrity(self, db_session: AsyncSession, multiple_links: list):
        assert len(multiple_links) == 5

        for item in multiple_links:
            assert item.original_url.startswith("https://example.com/item_")
            assert item.short_code.startswith("bulk_")
            assert item.clicks_count == 0
