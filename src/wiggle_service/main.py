"""
Main FastAPI application for Wiggle Service.

Core API and database service for the Wiggle multi-exchange arbitrage system.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
import uvicorn
import structlog
import time

from wiggle_service.core.config import get_settings
from wiggle_service.db import init_database, close_database
from wiggle_service.api.routes import (
    opportunities,
    tokens,
    exchanges,
    analytics,
    health,
)

# Configure structured logging
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer()
    ],
    wrapper_class=structlog.make_filtering_bound_logger(30),  # INFO level
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    
    Handles startup and shutdown of database connections and other resources.
    """
    settings = get_settings()
    
    # Startup
    logger.info("Starting Wiggle Service", version=app.version)
    
    try:
        # Initialize database
        logger.info("Initializing database connection")
        await init_database()
        logger.info("Database initialized successfully")
        
        # Add any other startup tasks here
        
        yield
        
    except Exception as e:
        logger.error("Failed to start application", error=str(e))
        raise
    
    finally:
        # Shutdown
        logger.info("Shutting down Wiggle Service")
        
        try:
            await close_database()
            logger.info("Database connection closed")
        except Exception as e:
            logger.error("Error during shutdown", error=str(e))


def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application.
    
    Returns:
        FastAPI: Configured application instance
    """
    settings = get_settings()
    
    app = FastAPI(
        title=settings.api.api_title,
        version=settings.api.api_version,
        description=settings.api.api_description,
        lifespan=lifespan,
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
    )
    
    # Add middleware
    setup_middleware(app, settings)
    
    # Add routes
    setup_routes(app)
    
    # Add exception handlers
    setup_exception_handlers(app)
    
    return app


def setup_middleware(app: FastAPI, settings) -> None:
    """Configure application middleware"""
    
    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.api.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )
    
    # Trusted host middleware (for production)
    if settings.is_production:
        app.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=["*.wiggle.dev", "localhost"]
        )
    
    # Request timing middleware
    @app.middleware("http")
    async def add_process_time_header(request: Request, call_next):
        start_time = time.time()
        response = await call_next(request)
        process_time = time.time() - start_time
        response.headers["X-Process-Time"] = str(process_time)
        return response
    
    # Request logging middleware
    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        start_time = time.time()
        
        # Log request
        logger.info(
            "Request started",
            method=request.method,
            url=str(request.url),
            client_ip=request.client.host if request.client else None,
        )
        
        response = await call_next(request)
        
        # Log response
        duration = time.time() - start_time
        logger.info(
            "Request completed",
            method=request.method,
            url=str(request.url),
            status_code=response.status_code,
            duration=duration,
        )
        
        return response


def setup_routes(app: FastAPI) -> None:
    """Configure application routes"""
    
    # Health check routes
    app.include_router(health.router, prefix="/health", tags=["Health"])
    
    # Core API routes
    app.include_router(opportunities.router, prefix="/api/v1/opportunities", tags=["Opportunities"])
    app.include_router(tokens.router, prefix="/api/v1/tokens", tags=["Tokens"])
    app.include_router(exchanges.router, prefix="/api/v1/exchanges", tags=["Exchanges"])
    app.include_router(analytics.router, prefix="/api/v1/analytics", tags=["Analytics"])
    
    # Root endpoint
    @app.get("/", summary="Root endpoint", tags=["Root"])
    async def root():
        """Root endpoint with service information"""
        settings = get_settings()
        return {
            "service": "Wiggle Service",
            "version": settings.api.api_version,
            "description": settings.api.api_description,
            "status": "healthy",
            "environment": settings.environment,
            "docs_url": "/docs" if settings.debug else "disabled",
        }


def setup_exception_handlers(app: FastAPI) -> None:
    """Configure global exception handlers"""
    
    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError):
        logger.error("ValueError occurred", error=str(exc), url=str(request.url))
        return JSONResponse(
            status_code=400,
            content={
                "error": "Bad Request",
                "message": str(exc),
                "type": "ValueError"
            }
        )
    
    @app.exception_handler(ConnectionError)
    async def connection_error_handler(request: Request, exc: ConnectionError):
        logger.error("ConnectionError occurred", error=str(exc), url=str(request.url))
        return JSONResponse(
            status_code=503,
            content={
                "error": "Service Unavailable",
                "message": "Database connection error",
                "type": "ConnectionError"
            }
        )
    
    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        logger.error("Unexpected error occurred", error=str(exc), url=str(request.url))
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal Server Error",
                "message": "An unexpected error occurred",
                "type": type(exc).__name__
            }
        )


# Create the app instance
app = create_app()


def cli():
    """Command-line interface for running the service"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Wiggle Service")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind to")
    parser.add_argument("--workers", type=int, default=1, help="Number of workers")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload")
    parser.add_argument("--log-level", default="info", help="Log level")
    
    args = parser.parse_args()
    
    # Run the server
    uvicorn.run(
        "wiggle_service.main:app",
        host=args.host,
        port=args.port,
        workers=args.workers,
        reload=args.reload,
        log_level=args.log_level,
        access_log=True,
    )


if __name__ == "__main__":
    cli()