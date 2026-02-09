"""
Redis client for caching.
Provides connection pooling and helper methods for cache operations.
"""

import json
from typing import Any

from redis.asyncio import ConnectionPool, Redis

from app.api.core.config import settings
from app.api.core.custom_exceptions.exceptions import (
    RedisCacheError,
    RedisConnectionError,
)
from app.api.core.logging import get_logger

logger = get_logger(__name__)


# Global connection pool
_redis_pool: ConnectionPool | None = None
_redis_client: Redis | None = None


# Cache TTL constants (in seconds)
CACHE_TTL_PROFILE = 300  # 5 minutes - user profile/avatar data
CACHE_TTL_MATCH = 600  # 10 minutes - match data
CACHE_TTL_READ_CURSOR = 30  # 30 seconds - read cursor data
CACHE_TTL_CONVERSATION_LIST = 60  # 1 minute - conversation list
CACHE_TTL_MATCH_STATS = 60  # 1 minute - match statistics (badges)


# Cache key prefixes
KEY_PREFIX_PROFILE = "profile"
KEY_PREFIX_MATCH = "match"
KEY_PREFIX_READ_CURSOR = "read_cursor"
KEY_PREFIX_CONVERSATION = "conversation"
KEY_PREFIX_MATCH_STATS = "match_stats"


def get_redis_pool() -> ConnectionPool:
    """Get or create Redis connection pool."""
    global _redis_pool

    if _redis_pool is None:
        # Parse Redis URL from settings
        redis_url = settings.redis_backend_url
        try:
            _redis_pool = ConnectionPool.from_url(
                redis_url,
                encoding="utf-8",
                decode_responses=True,
                max_connections=10,
            )
            logger.info(f"Redis connection pool created: {redis_url}")
        except Exception as e:
            logger.error(f"Redis connection pool creation failed: {e}")
            raise RedisConnectionError()

    return _redis_pool


async def get_redis() -> Redis:
    """Get Redis client from connection pool."""
    global _redis_client

    if _redis_client is None:
        try:
            pool = get_redis_pool()
            _redis_client = Redis(connection_pool=pool)
            logger.info("Redis client initialized")
        except Exception as e:
            logger.error(f"Redis client initialization failed: {e}")
            raise RedisConnectionError()

    return _redis_client


async def close_redis():
    """Close Redis connection pool."""
    global _redis_pool, _redis_client

    if _redis_client:
        await _redis_client.aclose()
        _redis_client = None
        logger.info("Redis client closed")

    if _redis_pool:
        await _redis_pool.aclose()
        _redis_pool = None
        logger.info("Redis connection pool closed")


async def ping_redis() -> bool:
    """Check if Redis is available."""
    try:
        redis = await get_redis()
        result = await redis.ping()
        return result
    except Exception as e:
        logger.error(f"Redis ping failed: {e}")
        raise RedisConnectionError()


# ==========================================
# Cache Helper Functions
# ==========================================


async def cache_set(
    key: str,
    value: Any,
    ttl: int,
    prefix: str = "",
) -> bool:
    """
    Set a value in cache with TTL.

    Args:
        key: Cache key
        value: Value to cache (will be JSON serialized)
        ttl: Time to live in seconds
        prefix: Optional key prefix

    Returns:
        True if successful, False otherwise
    """
    try:
        redis = await get_redis()
        full_key = f"{prefix}:{key}" if prefix else key

        # Serialize value to JSON
        serialized = json.dumps(value, default=str)

        await redis.setex(full_key, ttl, serialized)
        logger.debug(f"Cache set: {full_key} (TTL: {ttl}s)")
        return True
    except Exception as e:
        logger.error(f"Cache set failed for {key}: {e}")
        raise RedisCacheError()


async def cache_get(
    key: str,
    prefix: str = "",
) -> Any | None:
    """
    Get a value from cache.

    Args:
        key: Cache key
        prefix: Optional key prefix

    Returns:
        Cached value or None if not found
    """
    try:
        redis = await get_redis()
        full_key = f"{prefix}:{key}" if prefix else key

        value = await redis.get(full_key)

        if value is None:
            logger.debug(f"Cache miss: {full_key}")
            return None

        # Deserialize JSON
        result = json.loads(value)
        logger.debug(f"Cache hit: {full_key}")
        return result
    except Exception as e:
        logger.error(f"Cache get failed for {key}: {e}")
        raise RedisCacheError()


async def cache_delete(
    key: str,
    prefix: str = "",
) -> bool:
    """
    Delete a key from cache.

    Args:
        key: Cache key
        prefix: Optional key prefix

    Returns:
        True if key was deleted, False otherwise
    """
    try:
        redis = await get_redis()
        full_key = f"{prefix}:{key}" if prefix else key

        result = await redis.delete(full_key)
        logger.debug(f"Cache delete: {full_key}")
        return result > 0
    except Exception as e:
        logger.error(f"Cache delete failed for {key}: {e}")
        raise RedisCacheError()


async def cache_delete_pattern(pattern: str) -> int:
    """
    Delete all keys matching a pattern.

    Args:
        pattern: Pattern to match (e.g., "profile:*")

    Returns:
        Number of keys deleted
    """
    try:
        redis = await get_redis()

        # Find all matching keys
        keys = []
        async for key in redis.scan_iter(match=pattern):
            keys.append(key)

        if not keys:
            return 0

        # Delete all matching keys
        result = await redis.delete(*keys)
        logger.debug(f"Cache delete pattern: {pattern} ({result} keys)")
        return result
    except Exception as e:
        logger.error(f"Cache delete pattern failed for {pattern}: {e}")
        raise RedisCacheError()


async def cache_set_multiple(
    items: dict[str, Any],
    ttl: int,
    prefix: str = "",
) -> bool:
    """
    Set multiple values in cache with same TTL.

    Args:
        items: Dictionary of key-value pairs
        ttl: Time to live in seconds
        prefix: Optional key prefix

    Returns:
        True if all successful, False otherwise
    """
    try:
        redis = await get_redis()
        pipe = redis.pipeline()

        for key, value in items.items():
            full_key = f"{prefix}:{key}" if prefix else key
            serialized = json.dumps(value, default=str)
            pipe.setex(full_key, ttl, serialized)

        await pipe.execute()
        logger.debug(f"Cache set multiple: {len(items)} items (TTL: {ttl}s)")
        return True
    except Exception as e:
        logger.error(f"Cache set multiple failed: {e}")
        raise RedisCacheError()


# ==========================================
# Domain-Specific Cache Functions
# ==========================================


async def cache_profile(user_id: str, profile_data: dict) -> bool:
    """Cache user profile data."""
    return await cache_set(
        key=user_id,
        value=profile_data,
        ttl=CACHE_TTL_PROFILE,
        prefix=KEY_PREFIX_PROFILE,
    )


async def get_cached_profile(user_id: str) -> dict | None:
    """Get cached user profile data."""
    return await cache_get(
        key=user_id,
        prefix=KEY_PREFIX_PROFILE,
    )


async def invalidate_profile_cache(user_id: str) -> bool:
    """Invalidate cached profile for a user."""
    return await cache_delete(
        key=user_id,
        prefix=KEY_PREFIX_PROFILE,
    )


async def cache_match(match_id: str, match_data: dict) -> bool:
    """Cache match data."""
    return await cache_set(
        key=match_id,
        value=match_data,
        ttl=CACHE_TTL_MATCH,
        prefix=KEY_PREFIX_MATCH,
    )


async def get_cached_match(match_id: str) -> dict | None:
    """Get cached match data."""
    return await cache_get(
        key=match_id,
        prefix=KEY_PREFIX_MATCH,
    )


async def invalidate_match_cache(match_id: str) -> bool:
    """Invalidate cached match data."""
    return await cache_delete(
        key=match_id,
        prefix=KEY_PREFIX_MATCH,
    )


async def cache_read_cursor(match_id: str, user_id: str, cursor_data: dict) -> bool:
    """Cache read cursor data."""
    key = f"{match_id}:{user_id}"
    return await cache_set(
        key=key,
        value=cursor_data,
        ttl=CACHE_TTL_READ_CURSOR,
        prefix=KEY_PREFIX_READ_CURSOR,
    )


async def get_cached_read_cursor(match_id: str, user_id: str) -> dict | None:
    """Get cached read cursor data."""
    key = f"{match_id}:{user_id}"
    return await cache_get(
        key=key,
        prefix=KEY_PREFIX_READ_CURSOR,
    )


async def invalidate_read_cursor_cache(match_id: str, user_id: str) -> bool:
    """Invalidate cached read cursor for a user in a match."""
    key = f"{match_id}:{user_id}"
    return await cache_delete(
        key=key,
        prefix=KEY_PREFIX_READ_CURSOR,
    )


async def cache_conversation_list(user_id: str, conversations: list) -> bool:
    """Cache conversation list for a user."""
    return await cache_set(
        key=user_id,
        value=conversations,
        ttl=CACHE_TTL_CONVERSATION_LIST,
        prefix=KEY_PREFIX_CONVERSATION,
    )


async def get_cached_conversation_list(user_id: str) -> list | None:
    """Get cached conversation list."""
    return await cache_get(
        key=user_id,
        prefix=KEY_PREFIX_CONVERSATION,
    )


async def invalidate_conversation_cache(user_id: str) -> bool:
    """Invalidate conversation list cache for a user."""
    return await cache_delete(
        key=user_id,
        prefix=KEY_PREFIX_CONVERSATION,
    )


async def cache_match_stats(user_id: str, stats: dict) -> bool:
    """Cache match statistics for a user (for sidebar badges)."""
    return await cache_set(
        key=user_id,
        value=stats,
        ttl=CACHE_TTL_MATCH_STATS,
        prefix=KEY_PREFIX_MATCH_STATS,
    )


async def get_cached_match_stats(user_id: str) -> dict | None:
    """Get cached match statistics."""
    return await cache_get(
        key=user_id,
        prefix=KEY_PREFIX_MATCH_STATS,
    )


async def invalidate_match_stats(user_id: str) -> bool:
    """Invalidate match stats cache for a user."""
    return await cache_delete(
        key=user_id,
        prefix=KEY_PREFIX_MATCH_STATS,
    )
