"""Router registry: every module router is mounted here under its API version."""

from fastapi import APIRouter

api_v1 = APIRouter(prefix="/v1")

API_ROUTERS = [api_v1]
