from src.services.link import LinkManager
from src.auth.users import current_user_optional 
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends, HTTPException, status
from src.core.logger import logger
from fastapi.responses import RedirectResponse, JSONResponse
from typing import Any, Optional
from src.core.database import get_async_session
from src.models.user import AppUser


router = APIRouter()


async def init_link_service(session: AsyncSession = Depends(get_async_session)):
    return LinkManager(session)


@router.get("/{short_code}", response_class=RedirectResponse, tags=["Links"])
async def go_to_original_link(
    code: str,
    service: LinkManager = Depends(init_link_service),
    current_user: Optional[AppUser] = Depends(current_user_optional ),
):
    try:
        logger.info(f"Перенаправление на: {code}")
        link = await service.get_link_by_short_code(code, current_user)
        logger.info(f"Найденная ссылка: {link.original_url}")
        await service.increment_link_clicks(link.id)

        return RedirectResponse(url=link.original_url)
    except HTTPException as e:
        logger.warning(f"Перенаправление ошибок {code}: {e.detail} (status: {e.status_code})")
        return JSONResponse(status_code=e.status_code, content={"detail": e.detail})
    except Exception as e:
        logger.error(f"Перенаправление непредвиденной ошибки{code}: {str(e)}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Произошла внутренняя ошибка сервера"},
        )
