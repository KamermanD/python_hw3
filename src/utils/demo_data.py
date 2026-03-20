import asyncio
import uuid
from src.services.link import LinkManager
from typing import AsyncIterator
from src.services.project import ProjectHandler
from src.schemas.link import LinkNewModel
from src.core.logger import logger
from src.core.database import get_async_session
from src.schemas.project import NewProject
from src.models.user import AppUser
from fastapi_users.password import PasswordHelper



async def fetch_next(iterator: AsyncIterator):
    return await iterator.__anext__()


async def generate_demo_environment() -> bool:

    session_gen = get_async_session()
    session = await fetch_next(session_gen)
    try:
        project_service = ProjectHandler(session)
        link_service = LinkManager(session)
        
        public_proj = await project_service.ensure_public_project()

        password_util = PasswordHelper()
        demo_password_hash = password_util.hash("password123")

        sys_admin = AppUser(
            id=uuid.uuid4(),
            email="admin@example.com",
            hashed_password=demo_password_hash,
            is_active=True,
            is_verified=True,
            is_superuser=True,
        )
        session.add(sys_admin)
        await session.commit()
        await session.refresh(sys_admin)

        user_a = AppUser(
            id=uuid.uuid4(),
            email="user1@example.com",
            hashed_password=demo_password_hash,
            is_active=True,
            is_verified=True,
            is_superuser=False,
        )
        user_b = AppUser(
            id=uuid.uuid4(),
            email="user2@example.com",
            hashed_password=demo_password_hash,
            is_active=True,
            is_verified=True,
            is_superuser=False,
        )
        session.add_all([user_a, user_b])
        await session.commit()
        await session.refresh(user_a)
        await session.refresh(user_b)

        personal_project = await project_service.add_new_project(
            project_info=NewProject(
                name="User1 Personal Project",
                description="Личный проект для ссылок",
                default_link_lifetime_days=30,
            ),
            owner_uuid=user_a.id,
        )

        work_project_user1 = await project_service.add_new_project(
            project_info=NewProject(
                name="User1 Work Project",
                description="Рабочий проект",
                default_link_lifetime_days=90,
            ),
            owner_uuid=user_a.id,
        )

        work_project_user2 = await project_service.add_new_project(
            project_info=NewProject(
                name="User2 Work Project",
                description="Рабочий проект",
                default_link_lifetime_days=90,
            ),
            owner_uuid=user_b.id,
        )


        link_public_1 = await link_service.create_link(
            link_data=LinkNewModel(original_url="https://example.com/link1", is_public=True)
        )

        link_project1_public = await link_service.create_link(
            link_data=LinkNewModel(
                original_url="https://example.com/link2",
                short_code="link2",
                project_id=personal_project.id,
                is_public=True,
            ),
            owner_uuid=user_a.id,
            proj_id=personal_project.id,
        )

        link_project1_private = await link_service.create_link(
            link_data=LinkNewModel(
                original_url="https://example.com/link3",
                project_id=personal_project.id,
                is_public=False,
            ),
            owner_uuid=user_a.id,
            proj_id=personal_project.id,
        )

        link_project2_private = await link_service.create_link(
            link_data=LinkNewModel(
                original_url="https://example.com/link4",
                short_code="link4",
                project_id=work_project_user1.id,
                is_public=False,
            ),
            owner_uuid=user_a.id,
            proj_id=work_project_user1.id,
        )

        link_user2_public = await link_service.create_link(
            link_data=LinkNewModel(
                original_url="https://example.com/link5",
                short_code="link5",
                project_id=work_project_user2.id,
                is_public=True,
            ),
            owner_uuid=user_b.id,
            proj_id=work_project_user2.id,
        )

        link_user2_private = await link_service.create_link(
            link_data=LinkNewModel(
                original_url="https://example.com/link6",
                short_code="link6",
                project_id=work_project_user2.id,
                is_public=False,
            ),
            owner_uuid=user_b.id,
            proj_id=work_project_user2.id,
        )
        link_team22 = await link_service.create_link(
            link_data=LinkNewModel(
                original_url="http://team22.ykdns.net/",
                short_code="team22",
                is_public=True,
            ),
            owner_uuid=user_a.id,
            proj_id=personal_project.id,
        )

        logger.debug(f"""\n
=============== ДЕМОНСТРАЦИОННЫЕ ДАННЫЕ СОЗДАНЫ ===============
Пользователи:
- admin@example.com / password123 / {sys_admin.id}
- user1@example.com / password123 / {user_a.id}
- user2@example.com / password123 / {user_b.id}
Проекты:
- {public_proj}
- {personal_project}
- {work_project_user1}
- {work_project_user2}
Ссылки:
- {link_public_1}
- {link_project1_public}
- {link_project1_private}
- {link_project2_private}
- {link_user2_public}
- {link_user2_private}
- {link_team22}
        """)

        return True
    except Exception as exc:
        logger.error(f"Ошибка при создании демонстрационных данных: {exc}")
        raise exc
    finally:
        await session.commit()


if __name__ == "__main__":
    asyncio.run(generate_demo_environment())
