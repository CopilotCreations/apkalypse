"""
Structured logging configuration for APKalypse.

Uses structlog for structured, context-rich logging that supports both human-readable
console output and JSON format for production/CI environments.
"""

from __future__ import annotations

import logging
import sys
from typing import TYPE_CHECKING

import structlog
from rich.console import Console
from rich.logging import RichHandler

if TYPE_CHECKING:
    from .config import Config


def setup_logging(config: Config | None = None) -> None:
    """Configure structured logging for the application.

    Args:
        config: Optional configuration. If None, uses INFO level.
    """
    log_level = config.log_level if config else "INFO"
    level = getattr(logging, log_level, logging.INFO)

    # Configure standard library logging
    console = Console(stderr=True)
    handler = RichHandler(
        console=console,
        show_path=False,
        rich_tracebacks=True,
        tracebacks_show_locals=log_level == "DEBUG",
    )

    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[handler],
    )

    # Configure structlog
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.dev.set_exc_info,
        structlog.processors.TimeStamper(fmt="iso"),
    ]

    if sys.stderr.isatty():
        # Human-readable format for development
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer(colors=True),
        ]
    else:
        # JSON format for CI/production
        processors = shared_processors + [
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer(),
        ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Get a structured logger instance.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Configured bound logger
    """
    return structlog.get_logger(name)


def bind_context(**kwargs: object) -> None:
    """Bind context variables to all subsequent log entries in this context.

    Args:
        **kwargs: Context key-value pairs to bind
    """
    structlog.contextvars.bind_contextvars(**kwargs)


def clear_context() -> None:
    """Clear all bound context variables."""
    structlog.contextvars.clear_contextvars()
