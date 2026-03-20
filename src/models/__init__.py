# flake8: noqa
# Import Base first to avoid circular dependencies if models depend on each other
from src.core.database import Base

# Import all models here so that Alembic can discover them
from src.models.user import AppUser
from src.models.project import ProjectEntity, project_members
from src.models.link import Link
