from uuid import UUID
from fastapi_users import schemas


class UserCreate(schemas.BaseUserCreate):
    pass


class UserRead(schemas.BaseUser[UUID]):
    pass



