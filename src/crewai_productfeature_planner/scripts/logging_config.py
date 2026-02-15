"""Centralised logging configuration.

Reads environment variables to control behaviour:
    CREWAI_DEBUG            – set to "true" to emit DEBUG-level messages to the log file.
    CREWAI_FLOW_DEBUG       – set to "true" to also stream flow-execution logs to the console.
    CREWAI_LOG_RETENTION_DAYS – number of daily log files to keep (default 7).

Log files are stored in the ``logs/`` directory with the naming pattern
``crewai_YYYY-MM-DD.log`` and automatically rotated at midnight.
"""

import logging
import os
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

_LOG_DIR = Path("logs")
_LOG_FILENAME = "crewai.log"
_DATE_FMT = "%Y-%m-%d %H:%M:%S"
_LOG_FMT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"

_configured = False


def _is_truthy(value: str | None) -> bool:
    """Return True for common truthy env-var strings."""
    return (value or "").strip().lower() in ("true", "1", "yes")


def setup_logging() -> logging.Logger:
    """Configure and return the root project logger.

    Safe to call multiple times — subsequent calls are no-ops.
    """
    global _configured
    if _configured:
        return logging.getLogger("crewai_productfeature_planner")

    debug_enabled = _is_truthy(os.environ.get("CREWAI_DEBUG"))
    flow_debug = _is_truthy(os.environ.get("CREWAI_FLOW_DEBUG"))
    retention_days = int(os.environ.get("CREWAI_LOG_RETENTION_DAYS", "7"))

    root_level = logging.DEBUG if debug_enabled else logging.INFO

    # ── Root project logger ───────────────────────────────────
    logger = logging.getLogger("crewai_productfeature_planner")
    logger.setLevel(root_level)
    logger.propagate = False

    formatter = logging.Formatter(_LOG_FMT, datefmt=_DATE_FMT)

    # ── File handler (daily rotation) ─────────────────────────
    _LOG_DIR.mkdir(parents=True, exist_ok=True)
    file_handler = TimedRotatingFileHandler(
        filename=str(_LOG_DIR / _LOG_FILENAME),
        when="midnight",
        interval=1,
        backupCount=retention_days,
        encoding="utf-8",
        utc=False,
    )
    file_handler.suffix = "%Y-%m-%d"
    file_handler.setLevel(root_level)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # ── Console handler (only when flow debug is on) ──────────
    if flow_debug:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(root_level)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    _configured = True
    logger.info("Logging initialised (debug=%s, flow_debug=%s, retention=%d days)",
                debug_enabled, flow_debug, retention_days)
    return logger


def get_logger(name: str) -> logging.Logger:
    """Return a child logger under the project namespace.

    Ensures ``setup_logging()`` has been called first.

    Usage::

        from crewai_productfeature_planner.logging_config import get_logger
        logger = get_logger(__name__)
        logger.info("Something happened")
    """
    setup_logging()
    return logging.getLogger(f"crewai_productfeature_planner.{name}")
