import uuid
from fastapi_users.db import SQLAlchemyUserDatabase
from typing import Optional
from fastapi_users.authentication import (
    AuthenticationBackend,
    BearerTransport,
    JWTStrategy,
)
from fastapi import Depends, Request
from fastapi_users import BaseUserManager, FastAPIUsers, UUIDIDMixin, models
from src.core.logger import logger
from src.core.config import settings 
from src.models.user import AppUser, init_user_db


class MyUserManager(UUIDIDMixin, BaseUserManager[AppUser, uuid.UUID]):
    reset_password_token_secret = settings .JWT_SECRET.get_secret_value()
    verification_token_secret = settings .JWT_SECRET.get_secret_value()

    async def after_register(self, user: AppUser, request: Optional[Request] = None):
        logger.info(f"User {user.id} has registered.")

    async def after_forgot_password(
        self, user: AppUser, token: str, request: Optional[Request] = None
    ):
        logger.info(f"User {user.id} has forgot their password. Reset token: {token}")

    async def after_forgot_password(
        self, user: AppUser, token: str, request: Optional[Request] = None
    ):
        logger.info(
            f"Verification requested for user {user.id}. Verification token: {token}"
        )


async def provide_user_manager(user_db: SQLAlchemyUserDatabase = Depends(init_user_db)):
    yield MyUserManager(user_db)


jwt_transport = BearerTransport(tokenUrl="/auth/jwt/login")


def provide_jwt_strategy() -> JWTStrategy[models.UP, models.ID]:
    return JWTStrategy(secret=settings .JWT_SECRET.get_secret_value(), lifetime_seconds=3600)


auth_backend = AuthenticationBackend(
    name="jwt",
    transport=jwt_transport ,
    get_strategy=provide_jwt_strategy,
)

my_fastapi_users  = FastAPIUsers[AppUser, uuid.UUID](provide_user_manager, [auth_backend])

current_user_active  = my_fastapi_users .current_user(active=True)
current_user_optional  = my_fastapi_users .current_user(active=True, optional=True)
