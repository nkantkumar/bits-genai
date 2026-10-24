"""
Common Structured Logging Configuration using structlog.

Configuration can be controlled via:
1. Environment variables (or .env file):
   - LOG_LEVEL: DEBUG, INFO, WARNING, ERROR, CRITICAL (default: INFO)
   - LOG_FORMAT: console or json (default: console)
   - LOG_TIMESTAMPS: true or false (default: true)

2. Direct function call:
   from common.logger import configure_logging, get_logger

   configure_logging(log_level="DEBUG", log_format="json")
   logger = get_logger("my_module")
"""

import os
import sys
import logging
from typing import Optional, Dict, Any
from dotenv import load_dotenv
import structlog

# Load environment variables if .env exists
load_dotenv()

_CONFIGURED = False


def _get_env_config() -> Dict[str, Any]:
    """Retrieve logging configuration from environment variables."""
    return {
        "level": os.getenv("LOG_LEVEL", "INFO").upper(),
        "format": os.getenv("LOG_FORMAT", "console").lower(),
        "timestamps": os.getenv("LOG_TIMESTAMPS", "true").lower() in ("true", "1", "yes"),
    }


def configure_logging(
    log_level: Optional[str] = None,
    log_format: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None,
    force: bool = False,
) -> None:
    """
    Configure structlog and standard library logging.

    Args:
        log_level: DEBUG, INFO, WARNING, ERROR, CRITICAL (overrides env)
        log_format: 'console' (pretty colors) or 'json' (structured machine output)
        config: Optional dict with 'level', 'format', and 'timestamps'
        force: If True, reconfigures even if already configured
    """
    global _CONFIGURED
    if _CONFIGURED and not force:
        return

    env_config = _get_env_config()
    cfg = {**env_config, **(config or {})}
    if log_level:
        cfg["level"] = log_level.upper()
    if log_format:
        cfg["format"] = log_format.lower()

    # Determine Python logging level
    numeric_level = getattr(logging, cfg["level"], logging.INFO)

    # Base processors applied to every log entry
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]

    # Timestamp processor
    if cfg.get("timestamps", True):
        if cfg["format"] == "json":
            shared_processors.insert(2, structlog.processors.TimeStamper(fmt="iso"))
        else:
            shared_processors.insert(2, structlog.processors.TimeStamper(fmt="%H:%M:%S"))

    # Choose renderer based on format
    if cfg["format"] == "json":
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(
            colors=sys.stderr.isatty() or os.getenv("FORCE_COLOR", "0") == "1" or True,
            pad_event=25,
        )

    # Configure structlog
    structlog.configure(
        processors=shared_processors + [renderer],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Redirect standard library logging (e.g. uvicorn, requests, httpx) through structlog
    logging.basicConfig(
        format="%(message)s",
        level=numeric_level,
        handlers=[logging.StreamHandler(sys.stdout)],
        force=True,
    )

    _CONFIGURED = True


def get_logger(name: Optional[str] = None, **initial_values: Any) -> structlog.stdlib.BoundLogger:
    """
    Get a configured structlog logger instance.
    Automatically configures logging with defaults if not already done.

    Args:
        name: Name of the logger (defaults to caller's module name if None)
        initial_values: Key-value context to bind permanently to this logger instance

    Returns:
        structlog BoundLogger
    """
    if not _CONFIGURED:
        configure_logging()

    logger = structlog.get_logger(name or __name__)
    if initial_values:
        logger = logger.bind(**initial_values)
    return logger
