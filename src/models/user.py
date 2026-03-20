from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi_users.db import SQLAlchemyBaseUserTableUUID, SQLAlchemyUserDatabase
from src.core.database import get_async_session, Base
from sqlalchemy.orm import relationship


class AppUser(SQLAlchemyBaseUserTableUUID, Base):
    __tablename__ = "users"
    __table_args__ = {"extend_existing": True}

    projects = relationship(
        "ProjectEntity", secondary="project_members", back_populates="members"
    )
    links = relationship("Link", back_populates="owner")


async def init_user_db(session: AsyncSession = Depends(get_async_session)):
    yield SQLAlchemyUserDatabase(session, AppUser)
