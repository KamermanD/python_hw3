from datetime import datetime, timedelta, timezone
import random
from fastapi import HTTPException, status
from uuid import UUID
import string
from src.models.link import Link
from typing import List, Optional, Dict, Any, Tuple
from src.utils.utils import localize_datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import and_, or_, select, update, delete
from src.core.logger import logger
from src.services.project import ProjectHandler
from src.models.project import ProjectEntity, project_members
from src.models.user import AppUser
from src.schemas.link import LinkNewModel, LinkModifyModel, LinkAnalyticsModel, CachedLinkInfo, CacheLinkSnapshot, CachedLinkClicks
from src.utils.cache import app_cache


class LinkManager:
    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session
        self.cache_prefix = "link:"
        self.cache_ttl_seconds = 3600

    async def _assign_owner_and_project(self, link_data, owner_uuid, proj_id, public_proj):
        if owner_uuid is None:
            if not public_proj.owner_uuid:
                logger.error(f"Публичный проект не имеет владельца: {public_proj}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Не удалось определить владельца публичного проекта",
                )
            owner_uuid = public_proj.owner_uuid
            link_data.proj_ref = public_proj.project_id
            link_data.public_access = True
        elif proj_id:
            link_data.proj_ref = proj_id
        elif link_data.proj_ref is None:
            link_data.proj_ref = public_proj.project_id
        return owner_uuid, link_data.proj_ref
    
    async def _ensure_short_code(self, short_code: Optional[str]) -> str:
        if short_code:
            exists = await self._get_link_by_code(short_code)
            if exists:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Код '{short_code}' уже используется",
                )
            return short_code
        logger.debug("Короткий код не указан, генерируется новый")
        return await self._create_unique_code()
    
    async def _get_project(self, proj_id: int):
        project_service = ProjectHandler(self.db_session)
        return await project_service.fetch_project(proj_id)

    async def _check_project_access(self, proj, owner_uuid, public_proj):
        if owner_uuid != public_proj.owner_uuid and proj.project_id != public_proj.project_id:
            await self._verify_user_in_project(proj.project_id, owner_uuid)

    def _compute_expiration(self, link_data, proj):
        now = datetime.now(timezone.utc)
        min_expire = now + timedelta(minutes=5)
        if not link_data.expires_on:
            link_data.expires_on = now + timedelta(days=proj.default_link_lifetime)
        else:
            link_data.expires_on = localize_datetime(link_data.expires_on)
            if link_data.expires_on < min_expire:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Срок действия ссылки должен быть ≥ 5 минут",
                )
        return link_data.expires_on
    
    async def _get_link_by_code(self, code: str) -> Optional[Link]:
        return await self.db_session.get(Link, code)

    async def _create_unique_code(self) -> str:
        return "".join(random.choices(string.ascii_letters + string.digits, k=6))

    # async def _verify_user_in_project(self, proj_id: int, user_id: UUID):
    #     pass

    async def create_link(
        self, link_data: LinkNewModel, owner_uuid: Optional[UUID] = None, proj_id: Optional[int] = None,
    ) -> Link:

        project_service = ProjectHandler(self.db_session)
        public_proj = await project_service.ensure_public_project()

        owner_uuid, link_data.proj_ref = await self._assign_owner_and_project(
            link_data, owner_uuid, proj_id, public_proj
        )

        link_data.short_key = await self._ensure_short_code(link_data.short_key)

        proj = await self._get_project(link_data.proj_ref)

        link_data.expires_on = self._compute_expiration(link_data, proj)

        new_link = Link(
            original_url=str(link_data.url_original),
            short_code=link_data.code_short,
            expires_at=link_data.expires_on,
            owner_id=owner_uuid,
            project_id=link_data.project_ref,
            is_public=link_data.public_access,
        )

        self.db_session.add(new_link)
        await self.db_session.commit()
        await self.db_session.refresh(new_link)
        logger.debug(f"Created link:\n{new_link}")

        return new_link


    async def get_link_by_short_code(
        self, short_code: str, user: Optional[AppUser] = None
    ) -> Link:

        can_read, _ = await self._evaluate_link_access(
            short_code, user.id if user else None
        )
        if not can_read:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Ссылка не найдена или у вас нет доступа к ней",
            )

        current_time = datetime.now(timezone.utc)
        static_key = f"{self.cache_prefix}{short_code}:static"
        stats_key = f"{self.cache_prefix}{short_code}:stats"

        cached_static = await app_cache.get_value(static_key)
        if cached_static:
            link_static = CacheLinkSnapshot(**cached_static)
            if link_static.expire_time and datetime.fromisoformat(link_static.expire_time).replace(tzinfo=timezone.utc) < current_time:
                await app_cache.delete_key(static_key)
                await app_cache.delete_key(stats_key)
                raise HTTPException(status_code=410, detail="Срок действия ссылки истек")
        
            stats = await self.fetch_link_stats(short_code)
            return link_static.to_link_details(
                clicks_count=stats.total_clicks, last_clicked_at=stats.to_datetime()
            )

        link = await self._get_link_by_code(short_code)
        if not link:
            raise HTTPException(
                status_code=404, detail=f"Ссылка '{short_code}' не найдена"
            )
        if link.expires_at and link.expires_at < current_time:
            raise HTTPException(status_code=410, detail="Срок действия ссылки истек")

        link_static = CacheLinkSnapshot.from_link_details(link)
        link_stats = CachedLinkClicks.from_link_details(link)
        await app_cache.set_value(static_key, link_static.model_dump(), ttl_seconds=self.cache_ttl_seconds)
        await app_cache.set_value(stats_key, link_stats.model_dump(), ttl_seconds=self.cache_ttl_seconds)

        return link


    async def increment_link_clicks(self, link_id: int) -> None:

        stmt = (
            update(Link)
            .where(Link.id == link_id)
            .values(
                clicks_count=Link.clicks_count + 1,
                last_clicked_at=datetime.now(timezone.utc),
            )
            .returning(Link.short_code, Link.clicks_count, Link.last_clicked_at)
        )
        result = await self.db_session.execute(stmt)
        row = result.fetchone()
        await self.db_session.commit()

        if row:
            short_code, total_clicks, last_click_time = row

            logger.debug(f" >>> Обновление кеша статистики для ссылки: {short_code}")
            stats_cache_key = f"{self.cache_prefix}{short_code}:stats"

            cache_data = CachedLinkClicks(
                clicks_count=total_clicks,
                last_clicked_at=localize_datetime(last_click_time).isoformat(),
            )

            await app_cache.set_value(
                stats_cache_key,
                cache_data.model_dump(),
                ttl_seconds=self.cache_ttl_seconds
            )

    async def fetch_link_stats(
        self, code: str, stats_cache_key: str = ""
    ) -> CachedLinkClicks:

        if not stats_cache_key:
            stats_cache_key = f"{self.cache_prefix}{code}:stats"

        cached_data = await app_cache.get_value(stats_cache_key)
        if cached_data:
            return CachedLinkClicks(**cached_data)

        link_record = await self._get_link_by_code(code)
        if link_record:
            stats_data = CachedLinkClicks.from_link_details(link_record)

            await app_cache.set_value(
                stats_cache_key,
                stats_data.model_dump(),
                ttl_seconds=self.cache_ttl_seconds
            )
            return stats_data

        return CachedLinkClicks()

    async def modify_link(
        self, code: str, update_model: LinkModifyModel, user_uuid: UUID
    ) -> Link:

        link_record = await self._get_link_by_code(code)

        if not link_record:
            logger.warning(f" >>> Ссылка не найдена: {code}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Ссылка с кодом '{code}' не найдена",
            )

        if link_record.owner_id != user_uuid:
            can_edit = await self._verify_link_project_access(link_record.id, user_uuid)
            if not can_edit:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Нет прав на редактирование ссылки",
                )

        updated_fields = update_model.model_dump(exclude_unset=True, exclude_none=True)
        if not updated_fields:
            return link_record

        if "original_url" in updated_fields:
            updated_fields["original_url"] = str(updated_fields["original_url"])

        if "expires_at" in updated_fields:
            expires = updated_fields["expires_at"]
            if isinstance(expires, str):
                updated_fields["expires_at"] = localize_datetime(
                    datetime.fromisoformat(expires)
                )
            elif isinstance(expires, datetime):
                updated_fields["expires_at"] = localize_datetime(expires)

        stmt = update(Link).where(Link.id == link_record.id).values(**updated_fields)
        await self.db_session.execute(stmt)
        await self.db_session.commit()

        return await self._get_link_by_code(code)

    async def remove_link(
            self, code: str, user_uuid: UUID
    ) -> Dict[str, Any]:
        
        link_record = await self._get_link_by_code(code)

        if not link_record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Ссылка с кодом '{code}' не найдена",
            )

        if link_record.owner_id != user_uuid:
            can_delete = await self._verify_link_project_admin(link_record.id, user_uuid)
            if not can_delete:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Нет прав на удаление ссылки",
                )

        stmt = delete(Link).where(Link.id == link_record.id)
        await self.db_session.execute(stmt)
        await self.db_session.commit()

        return {"message": f"Ссылка'{code}' удалена"}

    async def retrieve_link_stats(
            self, code: str, user_uuid: UUID
    ) -> LinkAnalyticsModel:
        link_record = await self._get_link_by_code(code)

        if not link_record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Ссылка '{code}' не найдена",
            )

        if not link_record.is_public and link_record.owner_id != user_uuid:
            can_view = await self._verify_link_project_access(link_record.id, user_uuid)
            if not can_view:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Нет доступа к статистике ссылки",
                )

        stats_data = await self.fetch_link_stats(code)

        return LinkAnalyticsModel(
            id = link_record.id,
            short_code = link_record.short_code,
            original_url = link_record.original_url,
            expires_at = link_record.expires_at,
            is_public = link_record.is_public,
            created_at = link_record.created_at,
            clicks_count = stats_data.total_clicks,
            last_clicked_at = stats_data.to_datetime(),
        )


    async def find_links(
        self, query_text: str, user_uuid: UUID, max_results: int = 10
    ) -> List[Link]:

        pattern = f"%{query_text}%"

        member_stmt = (
            select(Link)
            .where(
                Link.original_url.like("%" + query_text + "%"),
                Link.owner_id == user_uuid,
            )
            .limit(max_results)
        )

        member_result = await self.db_session.execute(member_stmt)
        user_links = member_result.scalars().all()

        member_stmt = (
            select(Link)
            .where(
                Link.original_url.like(pattern),
                Link.is_public == True,
                Link.owner_id != user_uuid,
            )
            .limit(max_results)
        )

        member_result = await self.db_session.execute(member_stmt)
        public_links = member_result.scalars().all()

        member_stmt = (
            select(Link)
            .join(project_members, Link.project_id == project_members.c.project_id)
            .where(
                Link.original_url.like(pattern),
                project_members.c.user_id == user_uuid,
                Link.owner_id != user_uuid,
            )
            .limit(max_results)
        )

        member_result = await self.db_session.execute(member_stmt)
        member_links = member_result.scalars().all()

        combined = user_links + public_links + member_links
        unique_links = list({link.id: link for link in combined}.values())

        return unique_links[:max_results]

    async def fetch_user_links(
        self, user_uuid: UUID, max_results: int = 50, skip: int = 0
    ) -> List[Link]:

        stmt = (
            select(Link)
            .where(Link.owner_id == user_uuid)
            .order_by(Link.created_at.desc())
            .offset(skip)
            .limit(max_results)
        )

        result = await self.db_session.execute(stmt)
        user_links = result.scalars().all()
        return user_links

    async def fetch_project_links(
        self, proj_id: int, user_uuid: UUID, max_results: int = 50, skip: int = 0
    ) -> List[Link]:

        await self._verify_user_project_access(proj_id, user_uuid)

        stmt = (
            select(Link)
            .where(Link.project_id == proj_id)
            .order_by(Link.created_at.desc())
            .offset(skip)
            .limit(max_results)
        )

        result = await self.db_session.execute(stmt)
        project_links = result.scalars().all()
        return project_links

    async def fetch_popular_links(
            self, max_results: int = 10
    ) -> List[Link]:

        cache_key = f"{self.cache_prefix}popular:{max_results}"
        cached_data = await app_cache.get_value(cache_key)
        
        if cached_data:
            logger.debug(
                f" >>> Получение популярных ссылок из кэша. Count: {len(cached_data)}"
            )
            return [
                CachedLinkInfo(**item).to_link_details()
                for item in cached_data
        ]

        logger.debug(f" >>> Получение популярных ссылок из базы данных")
        stmt = (
            select(Link)
            .where(Link.expires_at > datetime.now(timezone.utc))
            .order_by(Link.clicks_count.desc())
            .limit(max_results)
        )
        result = await self.db_session.execute(stmt)
        popular_links = result.scalars().all()

        logger.debug(f" >>> Найдено {len(popular_links)} популярных ссыло в датабазе")

        cache_payload = [
        CachedLinkInfo.from_link_details(link).model_dump()
        for link in popular_links
        ]

        await app_cache.set_value(
            cache_key,
            cache_payload,
            ttl_seconds=600,
        )

        return popular_links

    async def purge_expired_links(self) -> int:

        now_utc = datetime.now(timezone.utc)
        logger.debug(f" >>> Очистка: текущее время={now_utc}")

        stmt_select = select(Link).where(
        Link.expires_at.is_not(None),
        Link.expires_at < now_utc,
        )
        delete_result = await self.db_session.execute(stmt_select)
        expired_items = delete_result.scalars().all()
        logger.debug(f" >>> Найдено {len(expired_items)} ссылки с истекшим сроком действия")
        for item in expired_items:
            logger.debug(
                f" >>> Аннулировать кэш для {item}: истек срок годности в {item.expires_at} < {now_utc}"
            )
            await app_cache.delete_key(f"{self.cache_prefix}{item.short_code}")

        stmt_delete = delete(Link).where(
        Link.expires_at.is_not(None),
        Link.expires_at < now_utc,
        )
        delete_result = await self.db_session.execute(stmt_delete)
        await self.db_session.commit()

        logger.debug(" >>> Аннулировать кэш для популярных ссылок")
        await app_cache.delete_key(f"{self.cache_prefix}popular:*")

        removed_count = delete_result.rowcount
        logger.debug(f" >>> Очищено {removed_count} ссылок с истекшим сроком действия")
        return removed_count

    async def _create_unique_code(self, size: int = 7) -> str:
       
        alphabet = string.ascii_letters + string.digits

        while True:
            candidate = "".join(random.choices(alphabet, k=size))
            exists = await self._get_link_by_code(candidate)
            if not exists:
                return candidate

    async def _get_link_by_code(self, code: str) -> Optional[Link]:

        stmt = select(Link).where(Link.short_code == code)
        result = await self.db_session.execute(stmt)

        link_record = result.scalars().first()
        return link_record

    async def _fetch_project_or_fail(self, proj_id: int) -> ProjectEntity:

        stmt = select(ProjectEntity).where(ProjectEntity.id == proj_id)
        result = await self.db_session.execute(stmt)
        project_record = result.scalars().first()

        if not project_record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Проект с ID {proj_id} не найден",
            )

        return project_record

    async def _verify_user_project_access(self, proj_id: int, user_uuid: UUID) -> bool:

        project_record = await self._fetch_project_or_fail(proj_id)

        if project_record.owner_id == user_uuid:
            return True

        stmt = select(project_members).where(
            project_members.c.project_id == proj_id,
            project_members.c.user_id == user_uuid,
        )
        result = await self.db_session.execute(stmt)

        if not result.first():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="У вас нет доступа к этому проекту",
            )

        return True

    async def _verify_link_project_access(self, link_id: int, user_uuid: UUID) -> bool:

        stmt = select(Link).where(Link.id == link_id)
        result = await self.db_session.execute(stmt)
        link_record = result.scalars().first()

        if not link_record:
            return False

        stmt = select(project_members).where(
            (project_members.c.project_id == link_record.project_id)
            & (project_members.c.user_id == user_uuid)
        )
        result = await self.db_session.execute(stmt)
        membership = result.first()

        return membership is not None

    async def _verify_link_project_admin(self, link_id: int, user_uuid: UUID) -> bool:

        stmt = select(Link).where(Link.id == link_id)
        result = await self.db_session.execute(stmt)
        link_record = result.scalars().first()

        if not link_record:
            return False

        stmt = select(project_members).where(
            (project_members.c.project_id == link_record.project_id)
            & (project_members.c.user_id == user_uuid)
            & (project_members.c.is_admin == True)
        )
        result = await self.db_session.execute(stmt)
        admin_membership = result.first()

        return admin_membership is not None

    async def _fetch_link_by_id(self, link_identifier: int) -> Optional[Link]:
        stmt = select(Link).where(Link.id == link_identifier)
        result = await self.db_session.execute(stmt)
        link_record = result.scalars().first()
        return link_record

    async def _evaluate_link_access(
        self, code: str, user_uuid: UUID
    ) -> Tuple[bool, bool]:

        link_record = None
        acl_cache_key = f"{self.cache_prefix}{code}:acl:{user_uuid}"
        cached_acl = await app_cache.get_value(acl_cache_key)
        if cached_acl:
            return cached_acl

        stmt = (
            select(
                Link,
                Link.is_public.label("public_read"),
                (Link.owner_id == user_uuid).label("public_read"),
                (project_members.c.user_id.isnot(None)).label("project_member_flag"),
                (project_members.c.is_admin.is_(True)).label("project_admin_flag"),
                or_(
                    Link.is_public,
                    Link.owner_id == user_uuid,
                    project_members.c.user_id.isnot(None),
                ).label("can_read"),
                or_(
                    Link.owner_id == user_uuid, project_members.c.is_admin.is_(True)
                ).label("can_modify"),
            )
            .select_from(Link)
            .outerjoin(
                project_members,
                and_(
                    Link.project_id == project_members.c.project_id,
                    project_members.c.user_id == user_uuid,
                ),
            )
            .where(Link.short_code == code)
        )

        result = await self.db_session.execute(stmt)
        row = result.first()

        if not row:
            can_read, can_modify = False, False
            logger.debug(f" >>> Ссылка не найдена: {code}")
        else:

            (link_record, _, _, _, _, can_read, can_modify) = row
            logger.debug(f" >>> Ссылка: {link_record}")
            logger.debug(f" >>> Permissions: can_read={can_read}, can_modify={can_modify}")

        await app_cache.set_value(acl_cache_key, (can_read, can_modify), ttl_seconds=300)
        return can_read, can_modify
