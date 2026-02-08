# AGENTS.md - ConnectHub Dating App Backend

> A comprehensive guide for AI coding agents working on the ConnectHub FastAPI backend.
> This file serves as an **operating manual** for automated coding assistants, defining conventions, patterns, and boundaries.

---

## Project Overview

**Application:** ConnectHub Dating App - FastAPI Backend with Supabase Hybrid Architecture

**Tech Stack:**
- Python 3.12+ with FastAPI 0.115+
- Supabase 2.0+ (Auth, Database, Storage, RLS)
- Pydantic 2.0+ / Pydantic-Settings for validation and config
- PostgreSQL with PostGIS (via Supabase)
- Redis 5.0+ for caching
- ARQ 0.26+ for background jobs (Redis-based)
- GeoAlchemy2 / Shapely for geospatial operations
- UV for dependency management
- Ruff for linting and formatting

**Architecture Pattern:** Supabase-First Hybrid with Modular Service Layer

**Key Design Principles:**
- Supabase handles Auth, RLS, and direct database operations via REST API
- FastAPI provides additional business logic, custom endpoints, and background jobs
- Row Level Security (RLS) enforced at database layer via user JWT
- Service layer pattern for business logic separation

---

## Setup Commands

```bash
# Install dependencies
uv sync

# Install with dev dependencies
uv sync --dev

# Activate virtual environment
.venv\Scripts\Activate  # Windows (PowerShell)
source .venv/bin/activate  # Linux/macOS

# Run application
uv run python main.py

# Run tests
pytest
pytest --cov=app  # with coverage

# Linting & Formatting
uv run ruff check .
uv run ruff format --check .
uv run ruff check . --fix  # auto-fix

# Run ARQ worker (background jobs)
arq app.workers.main.WorkerSettings

# Docker development
docker-compose up -d  # Start Redis & worker
docker-compose down   # Stop services
```

---

## Project Structure

```
connecthub_be/
├── main.py                    # FastAPI app entry point with lifespan
├── app/
│   └── api/
│       ├── __init__.py
│       ├── core/              # Core utilities & config
│       │   ├── config.py      # Pydantic Settings (env-based)
│       │   ├── supabase.py    # Supabase client initialization
│       │   ├── dependencies.py # FastAPI Depends() - auth, clients
│       │   └── custom_exceptions/
│       │       ├── exceptions.py      # CustomDomainException classes
│       │       ├── handlers.py        # Exception handlers
│       │       ├── register.py        # Registration to FastAPI
│       │       └── error_status_code_mapper.py
│       ├── db/
│       │   └── database.py    # Direct DB connection (if needed)
│       ├── utils/
│       │   └── response_payloads.py  # success_response, error_response
│       └── modules/
│           └── v1/            # API version 1
│               ├── __init__.py    # Router aggregation
│               ├── profiles/      # Profile module
│               │   ├── router.py      # FastAPI routes
│               │   ├── service.py     # Business logic
│               │   └── schemas.py     # Pydantic models
│               ├── photos/        # Photos module
│               │   ├── router.py
│               │   ├── service.py
│               │   └── schemas.py
│               └── <module>/      # Feature modules
│                   ├── router.py
│                   ├── service.py
│                   └── schemas.py
├── docs/                      # Documentation
├── tests/                     # Pytest test suite
├── docker-compose.yml         # Redis + Worker setup
└── pyproject.toml             # Project config & deps
```

---

## Code Style & Conventions

### Naming Conventions
- **Functions/Methods:** `snake_case` (`get_my_profile`, `create_profile`)
- **Classes:** `PascalCase` (`ProfileService`, `ProfileResponse`)
- **Constants:** `UPPER_SNAKE_CASE` (`DEFAULT_DISCOVERY_RADIUS_KM`)
- **File Names:** `snake_case.py` (`profile_service.py`, `response_payloads.py`)
- **Modules:** Pluralized for collections (`profiles/`, `photos/`)

### Code Formatting
- Line length: 100 characters (Ruff default)
- Double quotes for strings
- Imports sorted: stdlib → third-party → local (Ruff handles this)
- No trailing whitespace

---

## Service Layer Pattern

Services contain all business logic. Routes should be thin and delegate to services.

### ✅ Good - Service Class Pattern:
```python
# service.py
from supabase import Client
from uuid import UUID

class ProfileService:
    """Service for profile operations."""

    def __init__(self, supabase: Client, user_id: UUID):
        """
        Initialize profile service.

        Args:
            supabase: Authenticated Supabase client (respects RLS)
            user_id: Current authenticated user's ID
        """
        self.supabase = supabase
        self.user_id = user_id

    async def get_my_profile(self) -> Optional[dict]:
        """
        Get the current user's profile.

        Returns:
            dict: Profile data with computed fields, or None if not found.
        """
        response = self.supabase.table("profiles").select(
            "*, photos(id, storage_path, order_index, is_primary)"
        ).eq("id", str(self.user_id)).single().execute()

        if not response.data:
            return None

        profile = response.data
        profile["age"] = self._calculate_age(profile.get("birthdate"))
        return profile
```

### ✅ Good - Route Handler:
```python
# router.py
from fastapi import APIRouter, HTTPException, status
from app.api.core.dependencies import CurrentUserId, AuthenticatedClient

router = APIRouter(prefix="/profiles", tags=["Profiles"])

@router.get("/me", response_model=ProfileResponse)
async def get_my_profile(
    user_id: CurrentUserId,
    supabase: AuthenticatedClient,
):
    """Get the current user's profile."""
    service = ProfileService(supabase, user_id)
    profile = await service.get_my_profile()

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found. Please complete onboarding.",
        )

    return profile
```

### ❌ Bad - Business logic in routes:
```python
@router.get("/me")
async def get_my_profile(user_id: CurrentUserId, supabase: AuthenticatedClient):
    # ❌ Direct Supabase calls in routes
    response = supabase.table("profiles").select("*").eq("id", str(user_id)).execute()
    # ❌ Business logic in routes
    if response.data:
        profile = response.data[0]
        profile["age"] = calculate_age(profile["birthdate"])
        return profile
```

---

## Supabase Integration

### Client Types

```python
# app/api/core/supabase.py

# Anon client - for user-scoped operations (respects RLS)
get_supabase_client() -> Client

# Admin client - bypasses RLS (background jobs only!)
get_supabase_admin_client() -> Client

# User-authenticated client - for specific user context
get_supabase_user_client(access_token: str) -> Client
```

### Dependency Injection

```python
# app/api/core/dependencies.py

# Type aliases for clean injection
CurrentUserId = Annotated[UUID, Depends(get_current_user_id)]
AuthenticatedClient = Annotated[Client, Depends(get_authenticated_supabase_client)]

# Usage in routes:
@router.get("/me")
async def get_profile(
    user_id: CurrentUserId,           # Extracted from JWT
    supabase: AuthenticatedClient,    # Client with user's token
):
    ...
```

### Supabase Query Patterns

```python
# SELECT with joins
response = supabase.table("profiles").select(
    "*, photos(id, storage_path, order_index)"
).eq("id", str(user_id)).single().execute()

# INSERT
response = supabase.table("profiles").insert({
    "id": str(user_id),
    "display_name": data.display_name,
}).execute()

# UPDATE
response = supabase.table("profiles").update({
    "bio": data.bio
}).eq("id", str(user_id)).execute()

# RPC (stored procedures)
response = supabase.rpc("update_profile_location", {
    "user_id": str(user_id),
    "location_wkt": point_wkt,
}).execute()

# Storage
url = supabase.storage.from_("photos").create_signed_url(path, 3600)
```

---

## Custom Exceptions

All domain exceptions inherit from `CustomDomainException` and are auto-registered.

### Creating New Exceptions:
```python
# app/api/core/custom_exceptions/exceptions.py

class CustomDomainException(Exception):
    """Base exception for all domain-specific errors."""

    def __init__(self, message: str, code: str):
        self.message = message
        self.code = code
        super().__init__(message)


class NotFoundError(CustomDomainException):
    """Raised when a requested resource is not found."""

    def __init__(self, message: str = ""):
        message = "The requested resource was not found." if not message else message
        super().__init__(message=message, code="NOT_FOUND")


class PermissionDeniedError(CustomDomainException):
    """Raised when a user lacks permission."""

    def __init__(self, message: str = ""):
        message = "You do not have permission to access this resource." if not message else message
        super().__init__(message=message, code="PERMISSION_DENIED")
```

### Exception Hierarchy:
```
CustomDomainException
├── NotFoundError (404)
├── PermissionDeniedError (403)
├── AlreadyExistsError (409)
├── InvalidCredentialsError (401)
├── InvalidTokenError (401)
├── TokenExpiredError (401)
├── AccountInactiveError (403)
├── RateLimitExceededError (429)
├── ProcessingError (500)
├── ValidationError (400)
└── OAuth-related exceptions
    ├── OAuthFlowError
    ├── OAuthStateInvalidError
    └── OAuthTokenInvalidError
```

### Standard Error-Handling Pattern (MANDATORY)

Use domain exceptions for ALL service-layer errors. Never raise raw `HTTPException` inside services. Services should:

1. **Validate inputs** → raise `ValidationError` / `BadRequestError`
2. **Enforce access control** → raise `ForbiddenError` / `PermissionDeniedError`
3. **Handle missing data** → raise `NotFoundError`
4. **Wrap external dependencies** (Supabase, Redis, Storage) → raise a specific CustomDomainException

Controllers (routes) should be thin and let the global exception handler map errors to response codes.

#### ✅ Good Service Pattern
```python
from app.api.core.custom_exceptions.exceptions import (
    NotFoundError,
    ForbiddenError,
    RedisConnectionError,
    RedisCacheError,
)

class ExampleService:
    async def get_resource(self, user_id: UUID, resource_id: UUID) -> dict:
        # Access control
        if not self._has_access(user_id, resource_id):
            raise ForbiddenError(message="Access denied", code="FORBIDDEN")

        # External dependency (Redis cache)
        try:
            cached = await get_cached_resource(str(resource_id))
        except RedisCacheError:
            cached = None

        if cached:
            return cached

        # DB lookup
        result = self.supabase.table("resources").select("*").eq("id", str(resource_id)).single().execute()
        if not result.data:
            raise NotFoundError(message="Resource not found", code="NOT_FOUND")

        return result.data
```

#### ❌ Bad Pattern
```python
from fastapi import HTTPException

if not result.data:
    raise HTTPException(status_code=404, detail="Not found")
```

### Dependency Error Mapping Rules

When interacting with external systems, always map failures to custom exceptions:

- **Supabase/Auth/DB failures** → `ProcessingError` or `DependencyError`
- **Redis connection failures** → `RedisConnectionError`
- **Redis cache operation failures** → `RedisCacheError`
- **Storage failures** → `ProcessingError`

These exceptions are mapped in `error_status_code_mapper.py` and should always be used instead of raw exceptions.

---

## Response Payloads

ALWAYS use standardized response functions from `app/api/utils/response_payloads.py`.

### Success Response:
```python
from app.api.utils.response_payloads import success_response

return success_response(
    status_code=200,
    message="Profile retrieved successfully",
    data={"id": str(profile.id), "display_name": profile.display_name},
)
# Output:
# {
#     "status": "SUCCESS",
#     "status_code": 200,
#     "message": "Profile retrieved successfully",
#     "data": {"id": "...", "display_name": "..."}
# }
```

### Auth Response (with token):
```python
from app.api.utils.response_payloads import auth_response

return auth_response(
    status_code=200,
    message="Login successful",
    access_token=token,
    data={"user_id": str(user.id)},
)
```

### Error Response:
```python
from app.api.utils.response_payloads import error_response

return error_response(
    status_code=400,
    message="Invalid request data",
    error_code="VALIDATION_ERROR",
    errors={"email": ["Invalid email format"]},
)
```

---

## Pydantic Schemas

### Request/Response Schemas:
```python
# schemas.py
from datetime import date, datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field, field_validator


class ProfileCreate(BaseModel):
    """Profile creation request."""
    display_name: Optional[str] = Field(None, max_length=50)
    birthdate: date
    gender: Optional[str] = Field(None, pattern="^(male|female|non-binary|other)$")
    looking_for: list[str] = Field(default_factory=list)
    bio: Optional[str] = Field(None, max_length=500)

    @field_validator("birthdate")
    @classmethod
    def validate_age(cls, v: date) -> date:
        """Ensure user is at least 18 years old."""
        today = date.today()
        age = today.year - v.year - ((today.month, today.day) < (v.month, v.day))
        if age < 18:
            raise ValueError("Must be at least 18 years old")
        return v


class ProfileResponse(BaseModel):
    """Profile response with all fields."""
    id: UUID
    display_name: Optional[str]
    age: Optional[int]
    is_verified: bool
    created_at: datetime

    class Config:
        from_attributes = True
```

---

## PostGIS / Geospatial

This project uses PostGIS for location-based features.

### Location Update Pattern:
```python
# Create PostGIS POINT geometry
point_wkt = f"SRID=4326;POINT({longitude} {latitude})"

# Use RPC for PostGIS operations
response = supabase.rpc(
    "update_profile_location",
    {
        "user_id": str(user_id),
        "location_wkt": point_wkt,
    }
).execute()
```

### Location Schema:
```python
class LocationUpdate(BaseModel):
    """Location update request."""
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
```

---

## ARQ Background Jobs

This project uses **ARQ** (not Celery) for background jobs with Redis.

```python
# Running worker
arq app.workers.main.WorkerSettings

# Docker
docker-compose up -d  # Starts Redis + Worker
```

### ARQ Task Pattern:
```python
# app/workers/tasks.py
async def send_notification(ctx, user_id: str, message: str):
    """Send push notification to user."""
    # Access Redis from context
    redis = ctx["redis"]
    # Task implementation
    ...

# Worker settings
class WorkerSettings:
    functions = [send_notification]
    redis_settings = RedisSettings.from_dsn(settings.redis_broker_url)
```

---

## OpenAPI Documentation Pattern

This project uses a custom OpenAPI schema generator (`app/api/core/custom_openapi_docs.py`) that automatically injects standardized success and error responses.

### Custom Endpoint Attributes:

```python
# routes/profile_router.py

@router.get("/me", response_model=ProfileResponse)
async def get_my_profile(
    user_id: CurrentUserId,
    supabase: AuthenticatedClient,
):
    """Get the current user's profile."""
    service = ProfileService(supabase, user_id)
    profile = await service.get_my_profile()
    return profile

# Attach custom OpenAPI markers
get_my_profile._custom_errors = ["400", "401", "404", "500"]
get_my_profile._custom_success = {
    "status_code": 200,
    "description": "Profile retrieved successfully.",
}
```

### Default Error Codes by Method:

| Method | Default Error Codes |
|--------|---------------------|
| GET | 400, 401, 422, 404, 500 |
| POST | 400, 401, 403, 422, 500 |
| PATCH | 400, 401, 404, 422, 500 |
| PUT | 400, 401, 404, 422, 500 |
| DELETE | 400, 401, 404, 500 |

### Default Success Codes by Method:

| Method | Default Status |
|--------|----------------|
| GET | 200 |
| POST | 201 |
| PATCH | 200 |
| PUT | 200 |
| DELETE | 204 |

### Response Schemas:

All responses use standardized schemas:
- `SuccessResponseModel` - from `app/api/core/schemas/success_schema.py`
- `ErrorResponseModel` - from `app/api/core/schemas/error_schema.py`

---

## Docstring Standards

Use Google-style docstrings with Args, Returns, and Raises.

```python
async def create_profile(self, data: ProfileCreate) -> dict:
    """
    Create a new profile during onboarding.

    Args:
        data: Profile creation data with display_name, birthdate, etc.

    Returns:
        dict: The newly created profile data.

    Raises:
        AlreadyExistsError: If profile already exists for this user.
        ProcessingError: If database operation fails.
    """
```

---

## Testing Standards

```bash
# Run all tests
pytest

# Run specific module
pytest tests/api/modules/v1/profiles/

# Run with coverage
pytest --cov=app --cov-report=html

# Run single test
pytest -k "test_get_profile"
```

### Test Structure:
```
tests/
└── api/
    └── modules/
        └── v1/
            └── profiles/
                ├── test_router.py
                ├── test_service.py
                └── conftest.py  # Fixtures
```

---

## Environment Variables

Required environment variables (see `.env.example`):

```env
# App Settings
DEBUG=true
ENVIRONMENT=development

# Supabase (required)
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_ANON_KEY=eyJ...
SUPABASE_SERVICE_ROLE_KEY=eyJ...

# Optional: Direct database connection
DATABASE_URL=postgresql://...

# Redis
REDIS_BROKER_URL=redis://localhost:6379/0
REDIS_BACKEND_URL=redis://localhost:6379/1

# CORS
APP_URL=https://app.connecthub.com
DEV_URL=http://localhost:3000

# JWT (optional, Supabase handles this)
JWT_SECRET_KEY=your-secret-key
JWT_ALGORITHM=HS256
```

---

## Boundaries

### ✅ Always Do:
- Use `success_response()`, `auth_response()`, and `error_response()` for all API responses
- Use Supabase client through dependency injection (`AuthenticatedClient`)
- Put business logic in service classes, not routes
- Inherit custom exceptions from `CustomDomainException`
- Add comprehensive docstrings with Args/Returns/Raises
- Use UUID for user IDs
- Run `ruff check` and `ruff format` before commits
- Respect Row Level Security (RLS) - use authenticated client in routes

### ⚠️ Ask First:
- Database schema changes (managed via Supabase Dashboard/migrations)
- Adding new dependencies to `pyproject.toml`
- Modifying `main.py` or core configuration
- Creating new exception types
- Changes to authentication flow
- Modifying Supabase RLS policies
- PostGIS stored procedures

### 🚫 Never Do:
- Return raw dicts instead of `success_response`/`error_response`
- Use admin client in regular API routes (breaks RLS!)
- Commit `.env` files or secrets
- Skip docstrings for public functions/classes
- Use mutable default arguments
- Ignore type hints
- Hardcode user IDs or bypass authentication
- Make direct database connections when Supabase client suffices

---

## ARQ Workers

```bash
# Development
arq app.workers.main.WorkerSettings

# Docker (auto-starts with compose)
docker-compose up -d worker

# Check Redis
docker-compose exec redis redis-cli ping
```

---

## Quick Reference - New Feature Checklist

1. [ ] Create module directory: `app/api/modules/v1/<feature>/`
2. [ ] Add files: `__init__.py`, `router.py`, `service.py`, `schemas.py`
3. [ ] Define Pydantic schemas in `schemas.py`
4. [ ] Implement service class in `service.py`
5. [ ] Create routes in `router.py`
6. [ ] Register router in `app/api/modules/v1/__init__.py`
7. [ ] Add custom exceptions if needed
8. [ ] Write tests in `tests/api/modules/v1/<feature>/`
9. [ ] Run linting: `uv run ruff check . --fix && uv run ruff format .`
10. [ ] Update Supabase tables/RLS policies if needed (via Dashboard)

---

## API Documentation

- **Swagger UI:** `http://localhost:8000/docs` (debug mode only)
- **ReDoc:** `http://localhost:8000/redoc` (debug mode only)
- **Health Check:** `GET /health`

---

*This AGENTS.md follows the [AGENTS.md standard](https://agents.md) and is compatible with GitHub Copilot, Cursor, Codex, Jules, Gemini CLI, and other AI coding agents.*
