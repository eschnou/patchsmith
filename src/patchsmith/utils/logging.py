"""Structured logging setup using structlog."""

import logging
import sys
from pathlib import Path
from typing import Any, Optional

import structlog


def setup_logging(verbose: bool = False, log_file: Optional[Path] = None) -> None:
    """
    Setup structured logging with console and file output.

    Args:
        verbose: If True, set log level to DEBUG, otherwise CRITICAL (silent)
        log_file: Optional path to log file, defaults to .patchsmith/audit.log
    """
    # By default, only show CRITICAL errors (effectively silent)
    # With --debug flag, show everything (DEBUG and above)
    log_level = logging.DEBUG if verbose else logging.CRITICAL

    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stderr,
        level=log_level,
    )

    # Configure structlog processors
    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.StackInfoRenderer(),
    ]

    # Console output processor (human-readable)
    console_processors = processors + [
        structlog.dev.ConsoleRenderer(colors=True),
    ]

    # Configure structlog
    structlog.configure(
        processors=console_processors,  # type: ignore[arg-type]
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Setup file logging if specified
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(log_level)

        # Create a separate logger for JSON file output
        file_logger = logging.getLogger("patchsmith.audit")
        file_logger.addHandler(file_handler)
        file_logger.setLevel(log_level)


def get_logger(name: Optional[str] = None) -> Any:
    """
    Get a structlog logger instance.

    Args:
        name: Optional logger name, defaults to None

    Returns:
        A structlog BoundLogger instance
    """
    if name:
        return structlog.get_logger(name)
    return structlog.get_logger()


def bind_context(**kwargs: Any) -> None:
    """
    Bind context variables to the logger that will appear in all subsequent log messages.

    Args:
        **kwargs: Key-value pairs to bind to the logger context
    """
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(**kwargs)


def clear_context() -> None:
    """Clear all bound context variables."""
    structlog.contextvars.clear_contextvars()
