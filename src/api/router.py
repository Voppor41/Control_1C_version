from fastapi import APIRouter

from src.api.routers import auth, checks, clients, configurations, installations, notifications, planning, reports, users

api_router = APIRouter(prefix="/api")
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(clients.router)
api_router.include_router(configurations.router)
api_router.include_router(installations.nested)
api_router.include_router(installations.router)
api_router.include_router(checks.router)
api_router.include_router(notifications.router)
api_router.include_router(planning.slots)
api_router.include_router(planning.updates)
api_router.include_router(reports.router)
