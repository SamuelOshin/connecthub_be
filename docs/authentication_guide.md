# Authentication Implementation Guide - ConnectHub Backend

> **Supabase Hybrid Architecture**: FastAPI validates Supabase-issued JWT tokens

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Supabase Auth Setup](#supabase-auth-setup)
3. [Backend JWT Validation](#backend-jwt-validation)
4. [Dependency Injection](#dependency-injection)
5. [Protected Endpoints](#protected-endpoints)
6. [Row-Level Security (RLS)](#row-level-security-rls)
7. [Error Handling](#error-handling)
8. [Testing Authentication](#testing-authentication)

---

## Architecture Overview

### Authentication Flow

```mermaid
sequenceDiagram
    participant User
    participant Frontend
    participant SupabaseAuth
    participant FastAPI
    participant PostgreSQL

    User->>Frontend: Click "Sign in with Google"
    Frontend->>SupabaseAuth: OAuth request
    SupabaseAuth->>User: Redirect to Google
    User->>SupabaseAuth: Authorize
    SupabaseAuth->>Frontend: JWT token + session
    Frontend->>Frontend: Store in cookies
    
    Frontend->>FastAPI: API request + JWT token
    FastAPI->>FastAPI: Validate JWT
    FastAPI->>PostgreSQL: Query with user_id
    PostgreSQL->>PostgreSQL: Apply RLS policies
    PostgreSQL->>FastAPI: Filtered results
    FastAPI->>Frontend: Response
```

### Key Principles

- **Supabase handles authentication**: Login, OAuth, password hashing, token issuance
- **FastAPI validates tokens**: Verifies JWT signature and extracts user identity
- **PostgreSQL enforces permissions**: Row-Level Security based on JWT claims
- **Stateless**: No session storage in FastAPI, JWT contains all needed info

---

## Supabase Auth Setup

### 1. Environment Variables

```bash
# .env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...  # Public key
SUPABASE_SERVICE_ROLE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...  # Secret key
SUPABASE_JWT_SECRET=your-jwt-secret  # For local JWT verification
```

### 2. Supabase Client Initialization

```python
# app/core/supabase.py
import os
from supabase import create_client, Client
from functools import lru_cache

@lru_cache()
def get_supabase_client() -> Client:
    """
    Create Supabase client with service role key.
    Use for server-side operations that bypass RLS.
    """
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    
    if not url or not key:
        raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")
    
    return create_client(url, key)

@lru_cache()
def get_supabase_anon_client() -> Client:
    """
    Create Supabase client with anon key.
    Use for user-scoped operations (respects RLS).
    """
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_ANON_KEY")
    
    if not url or not key:
        raise ValueError("SUPABASE_URL and SUPABASE_ANON_KEY must be set")
    
    return create_client(url, key)
```

### 3. Configuration

```python
# app/core/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    SUPABASE_URL: str
    SUPABASE_ANON_KEY: str
    SUPABASE_SERVICE_ROLE_KEY: str
    SUPABASE_JWT_SECRET: str
    
    # JWT settings
    JWT_ALGORITHM: str = "HS256"
    JWT_AUDIENCE: str = "authenticated"
    
    class Config:
        env_file = ".env"

settings = Settings()
```

---

## Backend JWT Validation

### Option A: Verify with Supabase API (Recommended for MVP)

```python
# app/core/auth.py
from supabase import Client
from app.core.supabase import get_supabase_anon_client
from app.api.core.custom_exceptions.exceptions import (
    InvalidTokenError,
    TokenExpiredError,
    AuthenticationError
)

async def verify_token_with_supabase(token: str) -> dict:
    """
    Verify JWT token by calling Supabase Auth API.
    
    Pros: Simple, always up-to-date with Supabase changes
    Cons: Network call on every request (slower)
    """
    try:
        supabase: Client = get_supabase_anon_client()
        
        # Set the auth token for this request
        supabase.auth.set_session(token, token)
        
        # Verify and get user
        response = supabase.auth.get_user(token)
        
        if not response.user:
            raise InvalidTokenError("Invalid or expired token")
        
        return {
            "user_id": response.user.id,
            "email": response.user.email,
            "role": response.user.role,
            "metadata": response.user.user_metadata
        }
        
    except Exception as e:
        if "expired" in str(e).lower():
            raise TokenExpiredError()
        raise InvalidTokenError(f"Token validation failed: {str(e)}")
```

### Option B: Decode JWT Locally (Recommended for Production)

```python
# app/core/auth.py
import jwt
from datetime import datetime
from app.core.config import settings
from app.api.core.custom_exceptions.exceptions import (
    InvalidTokenError,
    TokenExpiredError
)

def decode_jwt_token(token: str) -> dict:
    """
    Decode and verify JWT token locally.
    
    Pros: Fast, no network call
    Cons: Requires JWT secret, must handle token refresh
    """
    try:
        payload = jwt.decode(
            token,
            settings.SUPABASE_JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
            audience=settings.JWT_AUDIENCE
        )
        
        # Check expiration
        exp = payload.get("exp")
        if exp and datetime.fromtimestamp(exp) < datetime.now():
            raise TokenExpiredError()
        
        return {
            "user_id": payload.get("sub"),  # Subject = user ID
            "email": payload.get("email"),
            "role": payload.get("role"),
            "metadata": payload.get("user_metadata", {})
        }
        
    except jwt.ExpiredSignatureError:
        raise TokenExpiredError()
    except jwt.InvalidTokenError as e:
        raise InvalidTokenError(f"Invalid token: {str(e)}")
```

---

## Dependency Injection

### 1. User Model

```python
# app/models/user.py
from pydantic import BaseModel, UUID4
from typing import Optional

class CurrentUser(BaseModel):
    """Authenticated user from JWT token"""
    id: UUID4
    email: str
    role: str = "authenticated"
    metadata: dict = {}
    
    class Config:
        from_attributes = True
```

### 2. Auth Dependency

```python
# app/core/dependencies.py
from fastapi import Depends, Header, HTTPException
from typing import Annotated
from app.models.user import CurrentUser
from app.core.auth import verify_token_with_supabase  # or decode_jwt_token
from app.api.core.custom_exceptions.exceptions import (
    InvalidTokenError,
    AuthenticationError
)

async def get_current_user(
    authorization: Annotated[str, Header()] = None
) -> CurrentUser:
    """
    Extract and validate JWT token from Authorization header.
    
    Usage:
        @router.get("/me")
        async def get_profile(user: CurrentUser = Depends(get_current_user)):
            return {"user_id": user.id}
    """
    if not authorization:
        raise AuthenticationError("Missing Authorization header")
    
    # Extract token from "Bearer <token>"
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise InvalidTokenError("Invalid Authorization header format. Expected: Bearer <token>")
    
    token = parts[1]
    
    try:
        # Verify token (choose one method)
        user_data = await verify_token_with_supabase(token)
        # OR: user_data = decode_jwt_token(token)
        
        return CurrentUser(**user_data)
        
    except (InvalidTokenError, TokenExpiredError) as e:
        raise e
    except Exception as e:
        raise AuthenticationError(f"Authentication failed: {str(e)}")


async def get_optional_user(
    authorization: Annotated[str, Header()] = None
) -> CurrentUser | None:
    """
    Optional authentication - returns None if no token provided.
    
    Usage:
        @router.get("/public-profile/{user_id}")
        async def get_profile(
            user_id: UUID,
            current_user: CurrentUser | None = Depends(get_optional_user)
        ):
            # Show different data based on auth status
            if current_user:
                return full_profile
            return public_profile
    """
    if not authorization:
        return None
    
    try:
        return await get_current_user(authorization)
    except:
        return None
```

### 3. Role-Based Access Control

```python
# app/core/dependencies.py
from functools import wraps
from app.api.core.custom_exceptions.exceptions import PermissionDeniedError

def require_role(*allowed_roles: str):
    """
    Decorator to require specific roles.
    
    Usage:
        @router.delete("/admin/users/{user_id}")
        @require_role("admin", "superadmin")
        async def delete_user(
            user_id: UUID,
            current_user: CurrentUser = Depends(get_current_user)
        ):
            ...
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, current_user: CurrentUser, **kwargs):
            if current_user.role not in allowed_roles:
                raise PermissionDeniedError(
                    f"This action requires one of: {', '.join(allowed_roles)}"
                )
            return await func(*args, current_user=current_user, **kwargs)
        return wrapper
    return decorator
```

---

## Protected Endpoints

### Example 1: Get Current User Profile

```python
# app/api/v1/profiles/routes.py
from fastapi import APIRouter, Depends
from app.models.user import CurrentUser
from app.core.dependencies import get_current_user
from app.core.supabase import get_supabase_anon_client

router = APIRouter(prefix="/profiles", tags=["profiles"])

@router.get("/me")
async def get_my_profile(
    current_user: CurrentUser = Depends(get_current_user)
):
    """
    Get authenticated user's profile.
    
    Headers:
        Authorization: Bearer <jwt_token>
    """
    supabase = get_supabase_anon_client()
    
    # Query will automatically apply RLS (only returns user's own profile)
    response = supabase.table("profiles").select("*").eq("id", current_user.id).single().execute()
    
    if not response.data:
        raise NotFoundError("Profile not found")
    
    return response.data
```

### Example 2: Update Profile

```python
@router.patch("/me")
async def update_my_profile(
    updates: ProfileUpdate,
    current_user: CurrentUser = Depends(get_current_user)
):
    """
    Update authenticated user's profile.
    
    RLS policy ensures users can only update their own profile.
    """
    supabase = get_supabase_anon_client()
    
    response = supabase.table("profiles").update(
        updates.model_dump(exclude_unset=True)
    ).eq("id", current_user.id).execute()
    
    return response.data
```

### Example 3: Swipe Action (Match Engine)

```python
# app/api/v1/discovery/routes.py
from pydantic import BaseModel, UUID4

class SwipeRequest(BaseModel):
    liked_id: UUID4
    direction: str  # "LEFT", "RIGHT", "SUPER_LIKE"

@router.post("/swipe")
async def swipe_on_profile(
    swipe: SwipeRequest,
    current_user: CurrentUser = Depends(get_current_user)
):
    """
    Record a swipe and check for mutual match.
    """
    supabase = get_supabase_anon_client()
    
    # Record swipe
    swipe_data = {
        "liker_id": str(current_user.id),
        "liked_id": str(swipe.liked_id),
        "direction": swipe.direction
    }
    
    supabase.table("swipes").insert(swipe_data).execute()
    
    # Check for mutual match
    if swipe.direction in ("RIGHT", "SUPER_LIKE"):
        reciprocal = supabase.table("swipes").select("*").match({
            "liker_id": str(swipe.liked_id),
            "liked_id": str(current_user.id),
            "direction": "RIGHT"
        }).execute()
        
        if reciprocal.data:
            # Create match
            match_data = {
                "user1_id": str(current_user.id),
                "user2_id": str(swipe.liked_id),
                "status": "ACTIVE"
            }
            match = supabase.table("matches").insert(match_data).execute()
            
            return {
                "swiped": True,
                "matched": True,
                "match_id": match.data[0]["id"]
            }
    
    return {"swiped": True, "matched": False}
```

---

## Row-Level Security (RLS)

### Enable RLS on Tables

```sql
-- Enable RLS on all user-facing tables
ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE photos ENABLE ROW LEVEL SECURITY;
ALTER TABLE swipes ENABLE ROW LEVEL SECURITY;
ALTER TABLE matches ENABLE ROW LEVEL SECURITY;
ALTER TABLE messages ENABLE ROW LEVEL SECURITY;
```

### Profile Policies

> [!IMPORTANT]
> **RLS Performance Optimization**: Always wrap `auth.uid()` in a SELECT subquery for 100x+ performance improvement on large tables. Without this, `auth.uid()` is called for every row!

```sql
-- ✅ CORRECT: Users can view their own profile (optimized)
CREATE POLICY "Users can view own profile"
ON profiles FOR SELECT
USING ((SELECT auth.uid()) = id);  -- Wrapped in SELECT, called once

-- ✅ CORRECT: Users can update their own profile (optimized)
CREATE POLICY "Users can update own profile"
ON profiles FOR UPDATE
USING ((SELECT auth.uid()) = id);  -- Wrapped in SELECT, called once

-- ✅ CORRECT: Users can view verified profiles (for discovery)
CREATE POLICY "Users can view discoverable profiles"
ON profiles FOR SELECT
USING (
    is_verified = true 
    AND id != (SELECT auth.uid())  -- Wrapped in SELECT
    AND NOT EXISTS (
        SELECT 1 FROM blocked_users 
        WHERE blocker_id = (SELECT auth.uid()) AND blocked_id = id
    )
);

-- ⚠️ CRITICAL: Add indexes on columns used in RLS policies
CREATE INDEX profiles_id_idx ON profiles (id);  -- For auth.uid() = id
CREATE INDEX blocked_users_blocker_idx ON blocked_users (blocker_id, blocked_id);
```

### Message Policies

```sql
-- ✅ CORRECT: Users can read messages in their matches (optimized)
CREATE POLICY "Users can read own messages"
ON messages FOR SELECT
USING (
    sender_id = (SELECT auth.uid())  -- Wrapped in SELECT
    OR match_id IN (
        SELECT id FROM matches 
        WHERE user1_id = (SELECT auth.uid()) OR user2_id = (SELECT auth.uid())
    )
);

-- ✅ CORRECT: Users can send messages in their matches (optimized)
CREATE POLICY "Users can send messages"
ON messages FOR INSERT
WITH CHECK (
    sender_id = (SELECT auth.uid())  -- Wrapped in SELECT
    AND match_id IN (
        SELECT id FROM matches 
        WHERE user1_id = (SELECT auth.uid()) OR user2_id = (SELECT auth.uid())
        AND status = 'ACTIVE'
    )
);

-- ⚠️ CRITICAL: Add indexes for message queries
CREATE INDEX messages_sender_id_idx ON messages (sender_id);
CREATE INDEX messages_match_id_idx ON messages (match_id, created_at DESC);
CREATE INDEX matches_users_idx ON matches (user1_id, user2_id);
```

### Swipe Policies

```sql
-- ✅ CORRECT: Users can create their own swipes (optimized)
CREATE POLICY "Users can create swipes"
ON swipes FOR INSERT
WITH CHECK (liker_id = (SELECT auth.uid()));  -- Wrapped in SELECT

-- ✅ CORRECT: Users can view their own swipes (optimized)
CREATE POLICY "Users can view own swipes"
ON swipes FOR SELECT
USING (liker_id = (SELECT auth.uid()) OR liked_id = (SELECT auth.uid()));  -- Wrapped in SELECT

-- ⚠️ CRITICAL: Add indexes for swipe queries
CREATE INDEX swipes_liker_id_idx ON swipes (liker_id, liked_id);
CREATE INDEX swipes_liked_id_idx ON swipes (liked_id, direction);  -- For match detection
```

### Advanced RLS Patterns

#### Security Definer Functions for Complex Checks

For complex authorization logic, use security definer functions to avoid per-row function calls:

```sql
-- Create helper function (runs as definer, bypasses RLS)
CREATE OR REPLACE FUNCTION is_match_participant(p_match_id UUID)
RETURNS BOOLEAN
LANGUAGE SQL
SECURITY DEFINER
SET search_path = ''
AS $$
  SELECT EXISTS (
    SELECT 1 FROM public.matches
    WHERE id = p_match_id 
    AND (user1_id = (SELECT auth.uid()) OR user2_id = (SELECT auth.uid()))
    AND status = 'ACTIVE'
  );
$$;

-- Use in policy (indexed lookup, not per-row check)
CREATE POLICY "Users can access match data"
ON match_data FOR SELECT
USING ((SELECT is_match_participant(match_id)));
```

#### Force RLS Even for Table Owners

```sql
-- Prevent bypassing RLS even with elevated privileges
ALTER TABLE profiles FORCE ROW LEVEL SECURITY;
ALTER TABLE messages FORCE ROW LEVEL SECURITY;
ALTER TABLE swipes FORCE ROW LEVEL SECURITY;
ALTER TABLE matches FORCE ROW LEVEL SECURITY;
```

---

## Connection Pooling

> [!IMPORTANT]
> **Connection Pooling is CRITICAL**: Without pooling, applications exhaust database connections under load. Postgres connections consume 1-3MB RAM each.

### Supabase Connection Pooler

Supabase provides built-in connection pooling via PgBouncer:

```python
# app/core/config.py
class Settings(BaseSettings):
    # Direct connection (for migrations, admin tasks)
    SUPABASE_DB_URL: str  # postgresql://postgres:[password]@db.[project].supabase.co:5432/postgres
    
    # Pooled connection (for application queries) - USE THIS
    SUPABASE_POOLER_URL: str  # postgresql://postgres:[password]@db.[project].supabase.co:6543/postgres
    
    # Pool configuration
    DB_POOL_SIZE: int = 10  # (CPU cores * 2) + spindle_count
    DB_MAX_OVERFLOW: int = 20
```

### FastAPI Database Connection

```python
# app/core/database.py
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

# Use POOLER URL for application queries
engine = create_async_engine(
    settings.SUPABASE_POOLER_URL.replace("postgresql://", "postgresql+asyncpg://"),
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_pre_ping=True,  # Verify connections before using
    pool_recycle=3600,   # Recycle connections after 1 hour
)

AsyncSessionLocal = sessionmaker(
    engine, 
    class_=AsyncSession, 
    expire_on_commit=False
)

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
```

### Connection Pool Modes

- **Transaction mode** (recommended): Connection returned after each transaction
  - Best for most applications
  - Supabase default: port 6543
- **Session mode**: Connection held for entire session
  - Needed for prepared statements, temp tables
  - Supabase: port 5432 (direct connection)

### Monitoring Connections

```sql
-- Check current active connections
SELECT count(*) FROM pg_stat_activity WHERE state = 'active';

-- View connections by database
SELECT datname, count(*) 
FROM pg_stat_activity 
GROUP BY datname;

-- Identify long-running queries
SELECT pid, now() - query_start AS duration, query
FROM pg_stat_activity
WHERE state = 'active'
ORDER BY duration DESC;
```

---

## Error Handling

### Global Exception Handler

```python
# app/api/core/exception_handlers.py
from fastapi import Request, status
from fastapi.responses import JSONResponse
from app.api.core.custom_exceptions.exceptions import CustomDomainException
from app.api.core.custom_exceptions.error_status_code_mapper import ERROR_STATUS_MAP

async def custom_exception_handler(request: Request, exc: CustomDomainException):
    """
    Handle all custom domain exceptions.
    Maps error codes to HTTP status codes.
    """
    status_code = ERROR_STATUS_MAP.get(exc.code, status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message
            }
        }
    )

# Register in main.py
from fastapi import FastAPI
from app.api.core.custom_exceptions.exceptions import CustomDomainException
from app.api.core.exception_handlers import custom_exception_handler

app = FastAPI()
app.add_exception_handler(CustomDomainException, custom_exception_handler)
```

### Auth Error Responses

```python
# Example error responses

# 401 Unauthorized - Missing/invalid token
{
    "error": {
        "code": "INVALID_TOKEN",
        "message": "Your session is invalid. Please log in again."
    }
}

# 401 Unauthorized - Expired token
{
    "error": {
        "code": "TOKEN_EXPIRED",
        "message": "Your session has expired. Please log in again to continue."
    }
}

# 403 Forbidden - Insufficient permissions
{
    "error": {
        "code": "PERMISSION_DENIED",
        "message": "You do not have permission to access this resource."
    }
}

# 403 Forbidden - Inactive account
{
    "error": {
        "code": "ACCOUNT_INACTIVE",
        "message": "Your account has been deactivated. Please contact support."
    }
}
```

---

## Testing Authentication

### 1. Get Test JWT Token

```python
# tests/conftest.py
import pytest
from supabase import create_client
import os

@pytest.fixture
def supabase_client():
    return create_client(
        os.getenv("SUPABASE_URL"),
        os.getenv("SUPABASE_ANON_KEY")
    )

@pytest.fixture
async def test_user_token(supabase_client):
    """
    Create test user and return JWT token.
    """
    # Sign up test user
    response = supabase_client.auth.sign_up({
        "email": "test@example.com",
        "password": "testpassword123"
    })
    
    return response.session.access_token

@pytest.fixture
async def auth_headers(test_user_token):
    """
    Return authorization headers for testing.
    """
    return {"Authorization": f"Bearer {test_user_token}"}
```

### 2. Test Protected Endpoints

```python
# tests/test_profiles.py
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_get_profile_authenticated(client: AsyncClient, auth_headers):
    """Test getting profile with valid token"""
    response = await client.get("/api/v1/profiles/me", headers=auth_headers)
    
    assert response.status_code == 200
    assert "id" in response.json()
    assert "email" in response.json()

@pytest.mark.asyncio
async def test_get_profile_unauthenticated(client: AsyncClient):
    """Test getting profile without token"""
    response = await client.get("/api/v1/profiles/me")
    
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTHENTICATION_ERROR"

@pytest.mark.asyncio
async def test_get_profile_invalid_token(client: AsyncClient):
    """Test getting profile with invalid token"""
    headers = {"Authorization": "Bearer invalid_token"}
    response = await client.get("/api/v1/profiles/me", headers=headers)
    
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_TOKEN"
```

### 3. Test RLS Policies

```python
# tests/test_rls.py
@pytest.mark.asyncio
async def test_user_cannot_update_other_profile(
    client: AsyncClient,
    auth_headers,
    other_user_id
):
    """Test that RLS prevents updating other users' profiles"""
    response = await client.patch(
        f"/api/v1/profiles/{other_user_id}",
        headers=auth_headers,
        json={"bio": "Hacked!"}
    )
    
    # Should fail due to RLS policy
    assert response.status_code == 403
```

---

## Quick Reference

### Environment Setup

```bash
# Required environment variables
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=eyJ...
SUPABASE_SERVICE_ROLE_KEY=eyJ...
SUPABASE_JWT_SECRET=your-secret
```

### Protected Endpoint Template

```python
from fastapi import APIRouter, Depends
from app.models.user import CurrentUser
from app.core.dependencies import get_current_user

router = APIRouter()

@router.get("/protected")
async def protected_endpoint(
    current_user: CurrentUser = Depends(get_current_user)
):
    """
    This endpoint requires authentication.
    current_user.id contains the authenticated user's ID.
    """
    return {"user_id": current_user.id}
```

### Frontend Integration

```typescript
// Frontend sends JWT token in Authorization header
const response = await fetch('https://api.connecthub.com/v1/profiles/me', {
  headers: {
    'Authorization': `Bearer ${session.access_token}`,
    'Content-Type': 'application/json'
  }
})
```

---

## Next Steps

1. ✅ Set up Supabase project and configure OAuth providers
2. ✅ Implement JWT validation in `app/core/auth.py`
3. ✅ Create auth dependencies in `app/core/dependencies.py`
4. ✅ Add RLS policies to database tables
5. ✅ Protect endpoints with `Depends(get_current_user)`
6. ✅ Test authentication flow end-to-end
7. ✅ Monitor JWT token expiration and refresh logic

---

**Last Updated**: 2026-02-01  
**Architecture**: Supabase Hybrid (Auth + FastAPI)
