"""
ConnectHub FastAPI Application Entry Point.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import router as api_router
from app.api.core.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Import Redis client functions (deferred to avoid import issues)
    from app.api.core.redis_client import close_redis, get_redis, ping_redis

    # Startup
    print(f"[STARTUP] Starting {settings.app_name} v{settings.app_version}")
    print(f"[ENV] Environment: {settings.environment}")

    # Initialize Redis
    try:
        await get_redis()
        redis_status = await ping_redis()
        if redis_status:
            print("[STARTUP] Redis connected successfully")
        else:
            print("[STARTUP] Warning: Redis connection failed")
    except Exception as e:
        print(f"[STARTUP] Warning: Redis initialization failed: {e}")

    yield

    # Shutdown
    print("[SHUTDOWN] Shutting down ConnectHub API")
    try:
        await close_redis()
        print("[SHUTDOWN] Redis connection closed")
    except Exception as e:
        print(f"[SHUTDOWN] Warning: Redis close failed: {e}")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="ConnectHub Dating App API - Supabase Hybrid Architecture",
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    lifespan=lifespan,
)

# Register exception handlers
from app.api.core.custom_exceptions.register import register_all_errors

register_all_errors(app)

# Custom OpenAPI schema
from app.api.core.custom_openapi_docs import custom_openapi

app.openapi = lambda: custom_openapi(app)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Health Check
@app.get("/health", tags=["System"])
async def health_check():
    """Health check endpoint."""
    from app.api.core.redis_client import ping_redis

    redis_status = "unknown"
    try:
        redis_healthy = await ping_redis()
        redis_status = "healthy" if redis_healthy else "unhealthy"
    except Exception as e:
        redis_status = f"error: {str(e)}"

    return {
        "status": "healthy",
        "app": settings.app_name,
        "version": settings.app_version,
        "redis": redis_status,
    }


# Include API routers
app.include_router(api_router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
    )
