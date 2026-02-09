"""
ARQ Worker Main Entry Point.
Run with: arq app.workers.main.WorkerSettings
"""

from arq import cron

from app.api.core.logging import get_logger
from app.workers.settings import REDIS_SETTINGS, JOB_TIMEOUT, MAX_TRIES

logger = get_logger(__name__, context="worker")
from app.workers.tasks.matching import (
    process_match_expirations,
    refresh_discovery_queues,
    recalculate_user_scores,
)
from app.workers.tasks.feedback import (
    request_feedback,
    process_feedback,
)
from app.workers.tasks.discovery import (
    cleanup_discovery_queues,
    cleanup_old_swipes,
    update_last_active,
)
from app.workers.tasks.chat import (
    invalidate_message_caches,
    update_sender_read_cursor,
)


async def startup(ctx: dict) -> None:
    """Initialize worker context."""

    logger.info("Worker starting up")
    # Could initialize database connections, etc.


async def shutdown(ctx: dict) -> None:
    """Cleanup worker context."""

    logger.info("Worker shutting down")
    # Could close database connections, etc.


class WorkerSettings:
    """ARQ Worker configuration."""

    # Redis connection
    redis_settings = REDIS_SETTINGS

    # Available functions (can be called on-demand)
    functions = [
        # Matching tasks
        process_match_expirations,
        refresh_discovery_queues,
        recalculate_user_scores,
        # Feedback tasks
        request_feedback,
        process_feedback,
        # Discovery tasks
        cleanup_discovery_queues,
        cleanup_old_swipes,
        update_last_active,
        # Chat tasks
        invalidate_message_caches,
        update_sender_read_cursor,
    ]

    # Scheduled jobs (cron)
    cron_jobs = [
        # Every hour: Check for expiring matches
        cron(
            process_match_expirations,
            hour=None,  # Every hour
            minute=0,
        ),
        # Every hour at :30: Refresh discovery queues
        cron(
            refresh_discovery_queues,
            hour=None,
            minute=30,
        ),
        # 4x daily: Request feedback for old matches
        cron(
            request_feedback,
            hour={0, 6, 12, 18},
            minute=0,
        ),
        # Daily at 3 AM: Full score recalculation
        cron(
            recalculate_user_scores,
            hour=3,
            minute=0,
        ),
        # Weekly on Sunday: Archive old swipes
        cron(
            cleanup_old_swipes,
            weekday=0,  # Sunday
            hour=4,
            minute=0,
        ),
    ]

    # Lifecycle hooks
    on_startup = startup
    on_shutdown = shutdown

    # Default job settings
    job_timeout = JOB_TIMEOUT
    max_tries = MAX_TRIES

    # Health check
    health_check_interval = 60  # seconds
