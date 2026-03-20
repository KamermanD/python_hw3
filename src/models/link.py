from datetime import datetime, timezone
from sqlalchemy.orm import relationship
from src.core.database import Base
from sqlalchemy import (
    Column, Integer, String, DateTime, Boolean, BigInteger, ForeignKey, UUID
)


def current_utc_time():
    return datetime.now(timezone.utc)


class Link(Base):
    __tablename__ = "links"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    original_url = Column(String, nullable=False)
    short_code = Column(String, unique=True, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), default=current_utc_time)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    owner_id = Column(UUID, ForeignKey("users.id"), nullable=False)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    clicks_count = Column(BigInteger, default=0)
    last_clicked_at = Column(DateTime(timezone=True), nullable=True)
    is_public = Column(Boolean, default=False)

    owner = relationship("AppUser", foreign_keys=[owner_id], back_populates="links")
    project = relationship("ProjectEntity", back_populates="links")

    def __repr__(self):
        return (
            f"Link(id={self.id}, short={self.short_code}, "
            f"orig={self.original_url}, prj={self.project_id}, "
            f"exp={self.expires_at})"
        )