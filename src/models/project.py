from datetime import datetime, timezone
from sqlalchemy.orm import relationship
from src.core.database import Base
from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Table, UUID


def current_utc():
    return datetime.now(timezone.utc)


project_members = Table(
    "project_members",
    Base.metadata,
    Column(
        "project_id",
        Integer,
        ForeignKey("projects.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("user_id", UUID, ForeignKey("users.id"), primary_key=True),
    Column("is_admin", Boolean, default=False),
    Column("joined_at", DateTime(timezone=True), default=current_utc),
    extend_existing=True,
)


class ProjectEntity(Base):
    __tablename__ = "projects"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String, nullable=False)
    description = Column(String)
    default_link_lifetime_days = Column(Integer, nullable=False, default=30)
    created_at = Column(DateTime(timezone=True), default=current_utc)
    owner_id = Column(UUID, ForeignKey("users.id"), nullable=True)

    members = relationship("AppUser", secondary=project_members, back_populates="projects")
    links = relationship("Link", back_populates="project")
    owner = relationship("AppUser", foreign_keys=[owner_id])

    def __repr__(self):
         return (
            f"Project(id={self.id}, name={self.name}, owner_id={self.owner_id})"
        )