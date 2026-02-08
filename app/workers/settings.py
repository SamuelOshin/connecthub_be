"""
ARQ Worker Settings.
Configuration for background task processing.
"""

from arq.connections import RedisSettings

from app.api.core.config import settings


def get_redis_settings() -> RedisSettings:
    """Get Redis connection settings from environment."""
    redis_url = settings.redis_broker_url

    # Parse Redis URL
    if redis_url.startswith("redis://"):
        redis_url = redis_url[8:]
    elif redis_url.startswith("rediss://"):
        redis_url = redis_url[9:]

    # Split host:port
    if "@" in redis_url:
        # Has authentication
        auth, host_port = redis_url.rsplit("@", 1)
        if ":" in auth:
            password, _ = auth.split(":", 1)
        else:
            password = auth
    else:
        password = None
        host_port = redis_url

    if "/" in host_port:
        host_port, db = host_port.split("/", 1)
        database = int(db) if db else 0
    else:
        database = 0

    if ":" in host_port:
        host, port_str = host_port.split(":", 1)
        port = int(port_str)
    else:
        host = host_port
        port = 6379

    return RedisSettings(
        host=host,
        port=port,
        password=password,
        database=database,
    )


# Default settings
REDIS_SETTINGS = get_redis_settings()

# Job retry settings
MAX_TRIES = 3
JOB_TIMEOUT = 300  # 5 minutes

# Queue names
QUEUE_DEFAULT = "default"
QUEUE_MATCHING = "matching"
QUEUE_NOTIFICATIONS = "notifications"
