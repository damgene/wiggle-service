"""
Health check endpoints for Wiggle Service.

Provides health checks and monitoring endpoints.
"""

from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
import structlog

from wiggle_service.db import db_manager
from wiggle_service.core.config import get_settings

logger = structlog.get_logger(__name__)

router = APIRouter()


class HealthResponse(BaseModel):
    """Health check response model"""
    status: str
    timestamp: datetime
    version: str
    environment: str
    uptime_seconds: float


class DetailedHealthResponse(BaseModel):
    """Detailed health check response"""
    status: str
    timestamp: datetime
    version: str
    environment: str
    uptime_seconds: float
    components: dict
    database: dict


@router.get("/", response_model=HealthResponse, summary="Basic health check")
async def health_check():
    """
    Basic health check endpoint.
    
    Returns basic service status and information.
    """
    settings = get_settings()
    
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now(),
        version=settings.api.api_version,
        environment=settings.environment,
        uptime_seconds=0.0  # TODO: Implement actual uptime tracking
    )


@router.get("/detailed", response_model=DetailedHealthResponse, summary="Detailed health check")
async def detailed_health_check():
    """
    Detailed health check with component status.
    
    Includes database connection status and other component health.
    """
    settings = get_settings()
    
    # Check database health
    db_healthy = await db_manager.health_check()
    db_stats = await db_manager.get_database_stats() if db_healthy else {}
    
    components = {
        "database": {
            "status": "healthy" if db_healthy else "unhealthy",
            "connected": db_manager.is_connected,
        }
    }
    
    # Overall status based on components
    overall_status = "healthy" if db_healthy else "degraded"
    
    return DetailedHealthResponse(
        status=overall_status,
        timestamp=datetime.now(),
        version=settings.api.api_version,
        environment=settings.environment,
        uptime_seconds=0.0,  # TODO: Implement actual uptime tracking
        components=components,
        database=db_stats
    )


@router.get("/readiness", summary="Readiness probe")
async def readiness_check():
    """
    Readiness probe for Kubernetes/container orchestration.
    
    Returns 200 if service is ready to accept traffic.
    """
    # Check if database is connected
    if not await db_manager.health_check():
        raise HTTPException(status_code=503, detail="Database not ready")
    
    return {"status": "ready", "timestamp": datetime.now()}


@router.get("/liveness", summary="Liveness probe")
async def liveness_check():
    """
    Liveness probe for Kubernetes/container orchestration.
    
    Returns 200 if service is alive.
    """
    return {"status": "alive", "timestamp": datetime.now()}