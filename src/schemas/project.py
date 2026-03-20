from uuid import UUID
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class BaseProjectModel(BaseModel):
    project_name: str = Field(..., min_length=1, max_length=100)
    project_description: Optional[str] = Field(None, max_length=500)
    default_link_days: int = Field(default=30, ge=1, le=365)


class NewProject(BaseProjectModel):
    pass


class UpdateProject(BaseProjectModel):
    project_name: Optional[str] = Field(None, min_length=1, max_length=100)
    default_link_days: Optional[int] = Field(None, ge=1, le=365)


class BaseProjectMember(BaseModel):
    is_admin: bool = False


class AddProjectMember(BaseProjectMember):
    email: str


class ProjectMemberInfo(BaseProjectMember):
    member_id: UUID
    joined_at: datetime

    class Config:
        from_attributes = True


class ProjectResponseModel(BaseProjectModel):
    project_id: int
    created_at: datetime
    owner_id: Optional[UUID] = None

    class Config:
        from_attributes = True


class ProjectDetails(BaseProjectModel):
    project_id: int
    created_at: datetime
    owner_id: Optional[UUID] = None
    members: List[ProjectMemberInfo] = []

    class Config:
        from_attributes = True

    def __repr__(self):
        return f"Project(id={self.project_id}, name={self.project_name}, owner_id={self.owner_id})"


class PublicProjectInfo(BaseProjectModel):
    project_id: int
    created_at: datetime
    owner_id: Optional[UUID] = None

    class Config:
        from_attributes = True
