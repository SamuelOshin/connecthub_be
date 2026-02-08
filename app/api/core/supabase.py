"""
Supabase client initialization.
Provides both anon (user-scoped) and service role (admin) clients.
"""

from functools import lru_cache

from supabase import create_client, Client
from supabase.lib.client_options import ClientOptions

from app.api.core.config import settings


@lru_cache
def get_supabase_client() -> Client:
    """
    Get Supabase client with anon key.
    Use for user-scoped operations (respects RLS).
    """
    return create_client(
        settings.supabase_url,
        settings.supabase_anon_key,
    )


@lru_cache
def get_supabase_admin_client() -> Client:
    """
    Get Supabase client with service role key.
    Use for admin operations (bypasses RLS).
    
    WARNING: Only use for background jobs and admin operations.
    """
    return create_client(
        settings.supabase_url,
        settings.supabase_service_role_key,
        options=ClientOptions(
            auto_refresh_token=False,
            persist_session=False,
        ),
    )


def get_supabase_user_client(access_token: str) -> Client:
    """
    Get Supabase client authenticated as a specific user.
    Use for user-scoped operations with the user's JWT.
    """
    client = create_client(
        settings.supabase_url,
        settings.supabase_anon_key,
    )
    client.auth.set_session(access_token, "")
    return client
