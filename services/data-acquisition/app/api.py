"""Router registry: every module router is mounted here under its API version."""

from fastapi import APIRouter

from app.modules.source_registry.router import router as source_registry_router

api_v1 = APIRouter(prefix="/v1")
api_v1.include_router(source_registry_router)

API_ROUTERS = [api_v1]
