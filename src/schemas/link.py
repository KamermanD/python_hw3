from datetime import datetime, timezone
from src.core.logger import logger
from typing import Optional
from uuid import UUID
from src.utils.utils import localize_datetime
from pydantic import BaseModel, Field, HttpUrl


class ShortLinkBaseModel(BaseModel):

    url_original: HttpUrl
    code_short: Optional[str] = Field(None, min_length=3, max_length=15)
    expires_on: Optional[datetime] = Field(
        None,
        description="Дата и время истечения действия ссылки",
    )


class LinkInfoModel(ShortLinkBaseModel):

    created_on: datetime
    project_ref: Optional[int] = None
    owner_ref: Optional[UUID] = None
    public_flag: Optional[bool] = False


class LinkDetailsModel(LinkInfoModel):

    link_id: int
    code: str
    public_flag: bool
    click_counter: int = 0
    last_click_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class LinkAnalyticsModel(ShortLinkBaseModel):

    total_clicks: int
    last_click_time: Optional[datetime] = None

    class Config:
        from_attributes = True


class LinkNewModel(ShortLinkBaseModel):

    project_ref: Optional[int] = None
    public_access: Optional[bool] = False


class LinkResponse(ShortLinkBaseModel):

    clicks_count: Optional[int] = 0


class LinkModifyModel(BaseModel):

    new_url: Optional[HttpUrl] = Field(None, description="Новый URL ссылки")
    expiration: Optional[datetime] = Field(None, description="Время истечения ссылки")
    public_flag: Optional[bool] = Field(None, description="Флаг публичности ссылки")


class CachedLinkClicks(BaseModel):

    total_clicks: int = 0
    last_click_time: Optional[str] = None

    @classmethod
    def from_link_details(cls, link: LinkDetailsModel) -> "CachedLinkClicks":
        return cls(
            clicks_count=link.click_counter,
            last_clicked_at=link.last_click_at.replace(
                tzinfo=timezone.utc
            ).isoformat()
            if link.last_click_at
            else None,
        )

    def to_datetime(self) -> Optional[datetime]:
        if self.last_click_time:
            return datetime.fromisoformat(self.last_click_time).replace(
                tzinfo=timezone.utc
            )
        return None


class CachedLinkInfo(LinkDetailsModel):

    expiration_time: str
    owner_identifier: str
    creation_time: str
    last_click_time: Optional[str] = None
    total_clicks: int = 0

    @classmethod
    def from_link_details(cls, link_obj: LinkDetailsModel) -> "CachedLinkInfo":
        return cls(
            id=link_obj.link_id,
            original_url=link_obj.url_original,
            short_code=link_obj.code,
            owner_id=str(link_obj.owner_ref),
            project_id=link_obj.project_ref,
            is_public=link_obj.public_flag,
            created_at=link_obj.created_on.replace(tzinfo=timezone.utc).isoformat(),
            expires_at=link_obj.expires_on.replace(tzinfo=timezone.utc).isoformat(),
            last_clicked_at=link_obj.last_click_at.replace(
                tzinfo=timezone.utc
            ).isoformat() if link_obj.last_click_at else None,
            clicks_count=link_obj.click_counter,
        )

    def to_link_details(self) -> LinkDetailsModel:
        return LinkDetailsModel(
            id=self.link_id,
            original_url=self.url_original,
            short_code=self.code,
            project_id=self.project_ref,
            owner_id=UUID(self.owner_identifier) if self.owner_identifier else None,
            is_public=self.public_flag,
            expires_at=datetime.fromisoformat(self.expiration_time).replace(
                tzinfo=timezone.utc
            ) if self.expiration_time else None,
            created_at=datetime.fromisoformat(self.creation_time).replace(
                tzinfo=timezone.utc
            ),
            last_clicked_at=datetime.fromisoformat(self.last_click_time).replace(
                tzinfo=timezone.utc
            ) if self.last_click_time else None,
            clicks_count=self.total_clicks,
        )


class CacheLinkSnapshot(LinkDetailsModel):

    link_id: int
    url_original: str
    short_ref: str
    owner_key: str
    project_ref: int
    public_flag: bool = False
    created_time: str
    expire_time: str

    @classmethod
    def from_link_details(cls, link: LinkDetailsModel) -> "CacheLinkSnapshot":
        snapshot = cls(
            id=link.link_id,
            original_url=link.url_original,
            short_code=link.code,
            owner_id=str(link.owner_ref),
            project_id=link.project_ref,
            is_public=link.public_flag,
            created_at=localize_datetime(link.created_on).isoformat(),
            expires_at=localize_datetime(link.expires_on).isoformat(),
        )
        logger.debug(f" >>> CacheLinkSnapshot.from_link: {snapshot}")
        return snapshot

    def to_link_details(
        self, clicks_count: int = 0, last_clicked_at: Optional[datetime] = None
    ) -> LinkDetailsModel:
        return LinkDetailsModel(
            id=self.link_id,
            original_url=self.url_original,
            short_code=self.short_ref,
            owner_id=UUID(self.owner_key),
            project_id=self.project_ref,
            is_public=self.public_flag,
            expires_at=datetime.fromisoformat(self.expire_time).replace(
                tzinfo=timezone.utc
            ),
            created_at=datetime.fromisoformat(self.created_time).replace(
                tzinfo=timezone.utc
            ),
            clicks_count=clicks_count,
            last_clicked_at=last_clicked_at,
        )


