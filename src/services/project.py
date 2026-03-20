from datetime import datetime, timezone
from src.models.user import AppUser
from uuid import UUID
from typing import List, Dict, Any
from src.schemas.project import NewProject, UpdateProject, AddProjectMember
from sqlalchemy import select, update, delete
from fastapi import HTTPException, status
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi_users.password import PasswordHelper
from src.models.project import ProjectEntity, project_members


class ProjectHandler:
    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session

    async def add_new_project(
            self, project_info: NewProject, owner_uuid: UUID
    ) -> ProjectEntity:
        project_record = ProjectEntity(
            name=project_info.project_name,
            description=project_info.project_description,
            default_link_lifetime_days=project_info.default_link_days,
            owner_id=owner_uuid,
        )

        self.db_session.add(project_record)
        await self.db_session.commit()
        await self.db_session.refresh(project_record)

        insert_stmt = project_members.insert().values(
            project_id=project_record.id,
            user_id=owner_uuid,
            is_admin=True,
            joined_at=datetime.now(timezone.utc),
        )

        await self.db_session.execute(insert_stmt)
        await self.db_session.commit()

        return project_record

    async def fetch_project(
        self, project_id: int, user_uuid: UUID, superuser: bool = False
    ) -> ProjectEntity:

        query = (
            select(ProjectEntity)
            .where(ProjectEntity.id == project_id)
            .options(selectinload(ProjectEntity.members))
        )
        result = await self.db_session.execute(query)
        project_record = result.scalars().first()

        if not project_record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Проект с ID {project_id} не найден",
            )

        if superuser:
            self.db_session.expunge(project_record)
            return project_record

        has_access = project_record.owner_id == user_uuid or any(
            member.id  == user_uuid for member in project_record.members
        )
        if not has_access:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Нет доступа к этому проекту",
            )

        self.db_session.expunge(project_record)
        return project_record

    async def fetch_user_projects(
        self, user_uuid: UUID, superuser: bool = False
    ) -> List[ProjectEntity]:

        if superuser:
            stmt = select(ProjectEntity).order_by(ProjectEntity.created_at.desc())
        else:
            stmt = (
                select(ProjectEntity)
                .outerjoin(
                    project_members, 
                    ProjectEntity.id == project_members.c.project_id
                )
                .where(
                    (ProjectEntity.owner_id == user_uuid)
                    | (project_members.c.user_id == user_uuid)
                )
                .order_by(ProjectEntity.created_at.desc())
            )

        result = await self.db_session.execute(stmt)
        user_projects = result.scalars().all()

        for proj in user_projects:
            self.db_session.expunge(proj)

        return user_projects

    async def modify_project(
        self, proj_id: int, update_info: UpdateProject, user_uuid: UUID
    ) -> ProjectEntity:

        await self.verify_project_admin(proj_id, user_uuid)
        changes = update_info.model_dump(exclude_unset=True, exclude_none=True)
        if not changes:
            return await self.fetch_project(proj_id, user_uuid, False)

        stmt = (
            update(ProjectEntity)
            .where(ProjectEntity.id == proj_id)
            .values(**changes)
        )
        await self.db_session.execute(stmt)
        await self.db_session.commit()

        return await self.fetch_project(proj_id, user_uuid, False)

    async def remove_project(
            self, proj_id: int, user_uuid: UUID
    ) -> Dict[str, Any]:

        project = await self.verify_project_admin(proj_id, user_uuid)
        if project.owner_id != user_uuid:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Только владелец проекта может удалить его",
            )

        if project.name == "Public" and project.owner_id is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Публичный проект нельзя удалить",
            )

        stmt = delete(ProjectEntity).where(ProjectEntity.id == proj_id)
        await self.db_session.execute(stmt)
        await self.db_session.commit()

        return {"message": f"Проект с ID {proj_id} успешно удален"}

    async def add_member_to_project(
        self, proj_id: int, member_data: AddProjectMember, user_uuid: UUID
    ) -> Dict[str, Any]:

        await self.verify_project_admin(proj_id, user_uuid)

        query = select(AppUser).where(AppUser.email == member_data.email)
        result = await self.db_session.execute(query)
        target_user = result.scalars().first()

        if not target_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Пользователь с email {member_data.email} не найден",
            )

        query = select(project_members).where(
            project_members.c.project_id == proj_id,
            project_members.c.user_id == target_user.id,
        )
        result = await self.db_session.execute(query)
        existing = result.first()

        if existing:
            stmt = (
                update(project_members)
                .where(
                    project_members.c.project_id == proj_id,
                    project_members.c.user_id == target_user.id,
                )
                .values(is_admin=member_data.is_admin)
            )
            await self.db_session.execute(stmt)
            await self.db_session.commit()

            return {"message": f"Роль пользователя с email {member_data.email} обновлена"}

        stmt = project_members.insert().values(
            project_id=proj_id,
            user_id=target_user.id,
            is_admin=member_data.is_admin,
            joined_at=datetime.now(timezone.utc),
        )
        await self.db_session.execute(stmt)
        await self.db_session.commit()

        return {"message": f"Пользователь с email {member_data.email} успешно добавлен в проект"}

    async def revoke_user_from_project(
        self, project_ref: int, target_user_uuid: UUID, requester_uuid: UUID
    ) -> Dict[str, Any]:

        project_entity = await self.verify_project_admin(project_ref, requester_uuid)

        if target_user_uuid == project_entity.owner_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Удаление владельца проекта запрещено",
            )

        delete_stmt = delete(project_members).where(
            project_members.c.project_id == project_ref,
            project_members.c.user_id == target_user_uuid,
        )
        delete_result = await self.db_session.execute(delete_stmt)

        if delete_result.rowcount == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Пользователь не найден в списке участников проекта",
            )

        await self.db_session.commit()

        return {"message": f"Пользователь с ID '{target_user_uuid}' успешно удалён из проекта"}

    async def ensure_public_project(self) -> ProjectEntity:

        query = select(ProjectEntity).where(ProjectEntity.name == "Public")
        result = await self.db_session.execute(query)
        final_public_proj = result.scalars().first()

        if final_public_proj:
            self.db_session.expunge(final_public_proj)
            return final_public_proj


        query = select(AppUser).where(AppUser.is_superuser == True).limit(1)
        result = await self.db_session.execute(query)
        admin_user = result.scalars().first()

        if not admin_user:
            password_helper = PasswordHelper()
            system_user_id = UUID()
            admin_user = AppUser(
                id=system_user_id,
                email="system@example.com",
                hashed_password=password_helper.hash(str(UUID())),
                is_active=True,
                is_verified=True,
                is_superuser=True,
            )
            self.db_session.add(admin_user)
            await self.db_session.commit()
            admin_id = system_user_id
        else:
            admin_id = admin_user.id

        final_public_proj = ProjectEntity(
            name="Public",
            description="Проект для публичных ссылок и незарегистрированных пользователей",
            default_link_lifetime_days=5,
            owner_id=admin_id,
        )

        self.db_session.add(final_public_proj)
        await self.db_session.commit()

        query = select(ProjectEntity).where(ProjectEntity.id == final_public_proj.id)
        result = await self.db_session.execute(query)
        final_public_proj = result.scalars().first()
        self.db_session.expunge(final_public_proj)

        return final_public_proj

    async def verify_project_admin(self, proj_id: int, user_uuid: UUID) -> ProjectEntity:

        admin_check_query = (
            select(ProjectEntity)
            .where(ProjectEntity.id == proj_id)
            .options(selectinload(ProjectEntity.members))
        )
        result = await self.db_session.execute(admin_check_query)
        project_obj = result.scalars().first()

        if not project_obj:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Проект с ID {proj_id} не найден",
            )

        if project_obj.name == "Public":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Публичный проект нельзя редактировать",
            )

        if project_obj.owner_id == user_uuid:
            return project_obj

        admin_check_query = select(project_members).where(
            project_members.c.project_id == proj_id,
            project_members.c.user_id == user_uuid,
            project_members.c.is_admin == True,
        )
        result = await self.db_session.execute(admin_check_query)
        is_proj_admin = result.first() is not None

        if not is_proj_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Для выполнения этой операции требуются права администратора проекта",
            )

        return project_obj
