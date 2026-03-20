import uuid
from src.models.link import Link
from uuid import uuid4
import string
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload
from src.models.project import ProjectEntity
from datetime import datetime
from src.models.user import AppUser
import random


def build_random_token(size: int = 8) -> str:
    alphabet = string.ascii_lowercase
    return "".join(random.choice(alphabet) for _ in range(size))


async def create_user_fixture(
    session: AsyncSession,
    force_admin: bool = False,
    prepared_email: Optional[str] = None,
    password: str = "test_password",
    active: bool = True,
    superuser: bool = False,
    verified: bool = False,
    auto_flush: bool = True,
) -> AppUser:

    if force_admin:
        superuser = True
    
    unique_suffix = f"_{uuid.uuid4().hex[:8]}"
    
    if prepared_email:
        at_position = prepared_email.find("@")
        if at_position != -1:
            email = f"{prepared_email[:at_position]}{unique_suffix}{prepared_email[at_position:]}"
        else:
            email = f"{prepared_email}{unique_suffix}@example.com"
    else:
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        random_string = build_random_token(5)
        email = f"test_user_{timestamp}_{random_string}@example.com"
    
    user_entity = AppUser(
        email=email,
        hashed_password=password,
        is_active=active,
        is_superuser=superuser,
        is_verified=verified,
    )

    session.add(user_entity)

    if auto_flush:
        try:
            await session.flush()
        except IntegrityError as exc:
            await session.rollback()
            if "duplicate key" in str(exc) and "email" in str(exc):
                return await create_user_fixture(
                    session=session,
                    force_admin=force_admin,
                    password=password,
                    active=active,
                    superuser=superuser,
                    verified=verified,
                    auto_flush=auto_flush,
                )
            else:
                raise

    return user_entity


async def create_project_fixture(
    session: AsyncSession,
    title: Optional[str] = None,
    details: Optional[str] = None,
    owner: Optional[AppUser] = None,
    participants: Optional[List[AppUser]] = None,
    auto_flush: bool = True,
) -> ProjectEntity:

    if owner is None:
        owner = await create_user_fixture(session, auto_flush=False)

    if not title:
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        title = f"Test Project {timestamp} {build_random_token(5)}"

    details = details or f"Auto description for {title}"

    project_entity = ProjectEntity(
        name=title,
        description=details,
        owner_id=owner.id,
        default_link_lifetime_days=30,
    )

    if participants:
            project_entity.members.extend(participants)

    session.add(project_entity)

    if auto_flush:
        await session.flush()

    return project_entity


async def attach_user_to_project(
    session: AsyncSession, 
    project_id: int, 
    user_id: uuid.UUID, 
    admin: bool = False
) -> None:
    insert_stmt = text("""
        INSERT INTO project_members (project_id, user_id, is_admin) 
        VALUES (:project_id, :user_id, :is_admin)
    """)
    await session.execute(
        insert_stmt, 
        {"project_id": project_id, "user_id": user_id, "is_admin": admin}
    )
    # await session.flush()


async def create_link_fixture(
    session: AsyncSession,
    url: Optional[str] = None,
    code: Optional[str] = None,
    owner: Optional[AppUser] = None,
    project: Optional[ProjectEntity] = None,
    auto_flush: bool = True,
) -> Link:

    if owner is None:
        owner = await create_user_fixture(session, auto_flush=False)
    
    if project is None:
        project = await create_project_fixture(session, owner=owner, auto_flush=False)
    
    
    if not url:
        ts = datetime.now().strftime("%Y%m%d%H%M%S")
        url = f"https://example.com/{ts}/{build_random_token(5)}"

    if not code:
        code = f"lnk_{build_random_token(6)}"

    link_entity = Link(
        original_url=url,
        short_code=code,
        owner_id=owner.id,
        project_id=project.id,
    )

    session.add(link_entity)

    if auto_flush:
        await session.flush()

    return link_entity


async def create_test_project_with_members(
    db: AsyncSession,
    owner: Optional[AppUser] = None,
    members: Optional[List[AppUser]] = None,
    project_name: Optional[str] = None,
) -> ProjectEntity:

    if owner is None:
        owner = await create_user_fixture(db, auto_flush=False)

    project = await create_project_fixture(db, title=project_name, owner=owner, auto_flush=False)

    await attach_user_to_project(db, project.id, owner.id, admin=True)

    if members:
        for member in members:
            await attach_user_to_project(db, project.id, member.id)

    await db.flush()
    return project


async def create_bulk_links(
    session: AsyncSession,
    amount: int = 5,
    owner: Optional[AppUser] = None,
    project: Optional[ProjectEntity] = None,
) -> List[Link]:

    if owner is None:
        owner = await create_user_fixture(session, auto_flush=False)
    
    if project is None:
        project = await create_project_fixture(session, owner=owner, auto_flush=False)

    result_links: List[Link] = []
    for idx in range(amount):
        link = Link(
            original_url=f"https://example.com/item_{idx}",
            short_code=f"bulk_{idx}_{build_random_token(4)}",
            owner_id=owner.id,
            project_id=project.id,
        )
        session.add(link)
        result_links.append(link)
    await session.flush()

    return result_links


async def fetch_user_with_links(
        session: AsyncSession,
        user_id: int
) -> Optional[AppUser]:

    stmt = (
        select(AppUser)
        .where(AppUser.id == user_id)
        .options(selectinload(AppUser.links))
    )

    result = await session.execute(stmt)
    return result.scalars().first()


async def fetch_project_with_users(
    session: AsyncSession, 
    project_id: int
) -> Optional[ProjectEntity]:

    stmt = (
        select(ProjectEntity)
        .where(ProjectEntity.id == project_id)
        .options(selectinload(ProjectEntity.members))
    )
    result = await session.execute(stmt)
    return result.scalars().first()
