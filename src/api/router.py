from fastapi import APIRouter
from src.api.misc import router as misc_router
from src.api.project import router as project_router
from src.api.link import router as link_router

router = APIRouter(prefix="/api/v1")


router.include_router(link_router)
router.include_router(project_router)
router.include_router(misc_router)


