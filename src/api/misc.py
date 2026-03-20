from fastapi import APIRouter, Depends
from fastapi_cache.decorator import cache
from src.auth.users import current_user_active 
from src.models.user import AppUser


router = APIRouter(prefix="/misc", tags=["Service utils"])


@router.get("/unprotected")
def get_service_status():
    return "Сервис работает корректно"


@router.get("/cache")
@cache(expire=60)
def get_cached_info():
    return "Этот ответ кэшируется в течение 60 секунд"


@router.get("/protected")
def get_current_user_info(user: AppUser = Depends(current_user_active )):
    return f"Привет, добро пожаловать {user.email} !"