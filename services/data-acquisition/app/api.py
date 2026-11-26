"""Router registry: every module router is mounted here under its API version."""

from fastapi import APIRouter

from app.modules.scraping_jobs.router import router as scraping_jobs_router

api_v1 = APIRouter(prefix="/v1")
api_v1.include_router(scraping_jobs_router)

API_ROUTERS = [api_v1]
