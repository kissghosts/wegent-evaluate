"""
API router configuration.
"""
from fastapi import APIRouter

from app.api.endpoints import analytics, config, daily, evaluation, health, reports, sync, version

api_router = APIRouter()

# Health check endpoints
api_router.include_router(health.router, tags=["health"])

# Daily report endpoints (new)
api_router.include_router(daily.router, prefix="/daily", tags=["daily"])

# Sync endpoints
api_router.include_router(sync.router, prefix="/sync", tags=["sync"])

# Evaluation endpoints
api_router.include_router(evaluation.router, prefix="/evaluation", tags=["evaluation"])

# Analytics endpoints
api_router.include_router(analytics.router, prefix="/analytics", tags=["analytics"])

# Config endpoints
api_router.include_router(config.router, prefix="/settings", tags=["settings"])

# Version endpoints
api_router.include_router(version.router, prefix="/versions", tags=["versions"])

# Report endpoints
api_router.include_router(reports.router, prefix="/reports", tags=["reports"])
