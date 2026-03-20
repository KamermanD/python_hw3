from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends, status
from src.models.user import AppUser
from src.auth.users import current_user_active , current_user_optional 
from src.schemas.link import LinkDetailsModel, LinkNewModel, LinkModifyModel, LinkAnalyticsModel, LinkResponse
from src.core.database import get_async_session
from src.services.link import LinkManager


router = APIRouter(prefix="/links", tags=["Links"])


async def link_service_provider(session: AsyncSession = Depends(get_async_session)):
    return LinkManager(session)


@router.get("/search", response_model=List[LinkDetailsModel])
async def find_links_by_url(
    query_url: str,
    active_user: AppUser = Depends(current_user_active ),
    service: LinkManager = Depends(link_service_provider),
    max_results: int = 10,
):
    user_id = active_user.id
    results = await service.find_links(query_url, user_id, max_results)
    return results


@router.post("/shorten", response_model=LinkDetailsModel, status_code=status.HTTP_201_CREATED)
async def shorten_link_endpoint(
    payload: LinkNewModel,
    current_user: Optional[AppUser] = Depends(current_user_optional ),
    service: LinkManager = Depends(link_service_provider),
):
    owner_id = current_user.id if current_user else None
    project_id = payload.project_ref
    new_link = await service.create_link(payload, owner_id, project_id)

    return new_link


@router.put("/{short_code}", response_model=LinkDetailsModel)
async def modify_short_link(
    code: str,
    new_data: LinkModifyModel,
    current_user: AppUser = Depends(current_user_active ),
    service: LinkManager = Depends(link_service_provider),
):
    return await service.modify_link(code, new_data, current_user.id)


@router.get("/popular", response_model=List[LinkResponse])
async def fetch_top_links(
    max_items: int = 10,
    service: LinkManager = Depends(link_service_provider),
):
    top_links  = await service.fetch_popular_links(max_items)
    response_list = []
    for link in top_links:
        response_list.append(
            LinkResponse(
                original_url=link.original_url,
                short_code=link.short_code,
                expires_at=link.expires_at,
                clicks_count=link.clicks_count,
            )
        )
    return response_list


@router.get("/{short_code}/stats", response_model=LinkAnalyticsModel)
async def fetch_short_link_stats(
    code: str,
    current_user: Optional[AppUser] = Depends(current_user_optional ),
    service: LinkManager = Depends(link_service_provider),
):
    user_id = current_user.id if current_user else None
    return await service.retrieve_link_stats(code, user_id)


@router.delete("/{short_code}", response_model=Dict[str, Any])
async def remove_short_link(
    code: str,
    current_user: AppUser = Depends(current_user_active ),
    service: LinkManager = Depends(link_service_provider),
):
    return await service.remove_link(code, current_user.id)



