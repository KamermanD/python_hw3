from typing import List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends, status
from uuid import UUID
from src.core.database import get_async_session
from src.models.user import AppUser
from src.auth.users import current_user_active 
from src.schemas.project import (
    ProjectDetails,
    NewProject,
    UpdateProject,
    AddProjectMember,
    PublicProjectInfo,
    ProjectResponseModel,
)
from src.services.project import ProjectHandler

router = APIRouter(prefix="/projects", tags=["Projects"])


async def init_project_service(session: AsyncSession = Depends(get_async_session)):
    return ProjectHandler(session)


@router.get("", response_model=List[ProjectResponseModel])
async def list_user_projects(
    current_user: AppUser = Depends(current_user_active ),
    service: ProjectHandler = Depends(init_project_service),
):
    user_projects = await service.fetch_user_projects(
        current_user.id, current_user.is_superuser
    )
    return user_projects


@router.post(
    "", response_model=ProjectResponseModel, status_code=status.HTTP_201_CREATED
)
async def add_new_project(
    project_data: NewProject,
    current_user: AppUser = Depends(current_user_active ),
    service: ProjectHandler = Depends(init_project_service),
):
    return await service.add_new_project(project_data, current_user.id)


@router.get("/{project_id}", response_model=ProjectResponseModel)
async def fetch_project_by_id(
    proj_id: int,
    current_user: AppUser = Depends(current_user_active ),
    service: ProjectHandler = Depends(init_project_service),
):
    project_data = await service.fetch_project(proj_id, current_user.id, current_user.is_superuser)
    return await project_data


@router.get("/public", response_model=PublicProjectInfo)
async def fetch_public_project(
    service: ProjectHandler = Depends(init_project_service),
):
    public_proj = await service.ensure_public_project()
    return await public_proj


@router.delete("/{project_id}", response_model=Dict[str, Any])
async def remove_project(
    proj_id: int,
    current_user: AppUser = Depends(current_user_active ),
    service: ProjectHandler = Depends(init_project_service),
):
    result = await service.remove_project(proj_id, current_user.id)
    return result


@router.put("/{project_id}", response_model=ProjectResponseModel)
async def modify_project(
    proj_id: int,
    update_data: UpdateProject,
    current_user: AppUser = Depends(current_user_active ),
    service: ProjectHandler = Depends(init_project_service),
):
    updated_project = await service.modify_project(proj_id, update_data, current_user.id)
    return updated_project


@router.delete("/{project_id}/members/{member_id}", response_model=Dict[str, Any])
async def exclude_member(
    proj_id: int,
    member_uuid: UUID,
    current_user: AppUser = Depends(current_user_active ),
    service: ProjectHandler = Depends(init_project_service),
):
    result = await service.revoke_user_from_project(proj_id, member_uuid, current_user.id)
    return result


@router.post("/{project_id}/members", response_model=Dict[str, Any])
async def include_member(
    proj_id: int,
    member_data: AddProjectMember,
    current_user: AppUser = Depends(current_user_active ),
    service: ProjectHandler = Depends(init_project_service),
):
    result = await service.add_member_to_project(proj_id, member_data, current_user.id)
    return result



