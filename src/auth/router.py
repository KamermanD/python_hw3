from src.schemas.user import UserRead, UserCreate
from src.auth.users import auth_backend, my_fastapi_users 
from fastapi import APIRouter

router = APIRouter(prefix="/auth", tags=["Auth"])

router.include_router(my_fastapi_users .get_register_router(UserRead, UserCreate))
router.include_router(my_fastapi_users .get_auth_router(auth_backend), prefix="/jwt")

