"""Structured JSON logging configuration.

Configures structlog with JSON output for production and colored console
output for development.

Reference: docs/07-implementation-plan.md § P1-1.6
"""

from __future__ import annotations

import logging
import sys

import structlog


def setup_logging(log_level: str = "INFO", log_format: str = "json") -> None:
    """Configure structured logging for the application.

    Args:
        log_level: Python logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        log_format: Output format — 'json' for production, 'console' for development.
    """
    # Shared processors for both formats
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    if log_format == "console":
        # Development: colored console output
        renderer: structlog.types.Processor = structlog.dev.ConsoleRenderer(colors=True)
    else:
        # Production: JSON output
        renderer = structlog.processors.JSONRenderer()

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Configure standard logging to use structlog formatter
    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(getattr(logging, log_level.upper()))

    # Quiet noisy third-party loggers
    for noisy_logger in ["uvicorn.access", "aio_pika", "aiormq"]:
        logging.getLogger(noisy_logger).setLevel(logging.WARNING)


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Get a structlog bound logger.

    Args:
        name: Logger name (usually __name__).

    Returns:
        BoundLogger: A structlog logger with structured context support.
    """
    logger: structlog.stdlib.BoundLogger = structlog.get_logger(name)
    return logger
