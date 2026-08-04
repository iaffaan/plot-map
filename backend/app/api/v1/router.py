from fastapi import APIRouter

from app.api.v1.endpoints import compile, health

api_router = APIRouter()

api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(compile.router, prefix="/compile", tags=["compile"])
