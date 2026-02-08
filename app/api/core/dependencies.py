"""
FastAPI dependencies for authentication and authorization.
Validates Supabase JWTs and provides current user context.
"""

from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from supabase import Client

from app.api.core.supabase import get_supabase_client, get_supabase_user_client


# HTTP Bearer token extractor
security = HTTPBearer(auto_error=False)


async def get_current_user_id(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
) -> UUID:
    """
    Extract and validate user ID from Supabase JWT.
    Raises 401 if token is missing or invalid.
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    client = get_supabase_client()

    try:
        # Verify token with Supabase Auth
        # Retry up to 3 times to handle transient SSL/Network timeouts
        for attempt in range(3):
            try:
                user_response = client.auth.get_user(token)
                break
            except Exception as e:
                # If it's the last attempt, re-raise
                if attempt == 2:
                    raise e
                # Otherwise loop to try again
                continue
                
        if not user_response.user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return UUID(user_response.user.id)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token validation failed: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_authenticated_supabase_client(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
) -> Client:
    """
    Get Supabase client authenticated with user's token.
    Use for operations that should respect RLS policies.
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        return get_supabase_user_client(credentials.credentials)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentication failed: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )


# Type aliases for dependency injection
CurrentUserId = Annotated[UUID, Depends(get_current_user_id)]
AuthenticatedClient = Annotated[Client, Depends(get_authenticated_supabase_client)]
