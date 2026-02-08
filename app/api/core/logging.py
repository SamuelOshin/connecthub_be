"""
Centralized logging configuration using Loguru.
Import `logger` from this module throughout the application.

Usage:
    from app.api.core.logging import logger
    
    logger.info("Message")
    logger.warning("Warning message")
    logger.error("Error message")
    logger.debug("Debug message")
"""

import sys
from pathlib import Path

from loguru import logger


# Remove default handler
logger.remove()


def setup_logging(
    log_level: str = "INFO",
    log_to_file: bool = True,
    log_dir: str = "logs",
    json_logs: bool = False,
) -> None:
    """
    Configure application logging.
    
    Args:
        log_level: Minimum log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_to_file: Whether to write logs to file
        log_dir: Directory for log files
        json_logs: Whether to use JSON format for logs
    """
    
    # Console format - colored and readable
    console_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
        "<level>{message}</level>"
    )
    
    # File format - more detailed
    file_format = (
        "{time:YYYY-MM-DD HH:mm:ss.SSS} | "
        "{level: <8} | "
        "{name}:{function}:{line} | "
        "{message}"
    )
    
    # JSON format for production log aggregation
    json_format = "{message}"
    
    # Add console handler
    logger.add(
        sys.stdout,
        format=console_format,
        level=log_level,
        colorize=True,
        backtrace=True,
        diagnose=True,
    )
    
    if log_to_file:
        log_path = Path(log_dir)
        log_path.mkdir(parents=True, exist_ok=True)
        
        # Main application log (rotated daily, kept 7 days)
        logger.add(
            log_path / "app_{time:YYYY-MM-DD}.log",
            format=file_format if not json_logs else json_format,
            level=log_level,
            rotation="00:00",  # New file at midnight
            retention="7 days",
            compression="zip",
            serialize=json_logs,
        )
        
        # Error log (errors only, kept 30 days)
        logger.add(
            log_path / "error_{time:YYYY-MM-DD}.log",
            format=file_format if not json_logs else json_format,
            level="ERROR",
            rotation="00:00",
            retention="30 days",
            compression="zip",
            serialize=json_logs,
        )
        
        # Worker log (for background tasks)
        logger.add(
            log_path / "worker_{time:YYYY-MM-DD}.log",
            format=file_format,
            level=log_level,
            rotation="00:00",
            retention="7 days",
            compression="zip",
            filter=lambda record: "worker" in record["extra"].get("context", ""),
        )


def get_logger(name: str = None, context: str = None):
    """
    Get a logger instance with optional name binding.
    
    Args:
        name: Module or component name
        context: Additional context (e.g., "worker", "api")
    
    Returns:
        Bound logger instance
    """
    bound_logger = logger
    
    if name:
        bound_logger = bound_logger.bind(name=name)
    if context:
        bound_logger = bound_logger.bind(context=context)
    
    return bound_logger


# Initialize with defaults on import
# This will be reconfigured by main.py with actual settings
setup_logging()


__all__ = ["logger", "get_logger", "setup_logging"]
