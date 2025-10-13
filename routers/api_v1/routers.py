from fastapi import APIRouter
from routers.api_v1.endpoints.user import router as user_router
from routers.api_v1.endpoints.order import router as order_router
from routers.api_v1.endpoints.auth import router as auth_router
from routers.api_v1.endpoints.admin import router as admin_router
from routers.api_v1.endpoints.driver import router as driver_router
from routers.api_v1.endpoints.route import router as route_router

router = APIRouter()

router.include_router(user_router, prefix="/user")
router.include_router(order_router, prefix="/order")
router.include_router(auth_router, prefix="/auth")
router.include_router(admin_router, prefix="/admin")
router.include_router(driver_router, prefix="/driver")
router.include_router(route_router, prefix="/route")