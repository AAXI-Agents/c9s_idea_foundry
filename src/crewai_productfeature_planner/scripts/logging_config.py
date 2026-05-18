"""Centralised logging configuration.

Reads environment variables to control behaviour:
    CREWAI_DEBUG            – set to "true" to emit DEBUG-level messages to the log file.
    CREWAI_FLOW_DEBUG       – set to "true" to also stream flow-execution logs to the console.
    CREWAI_LOG_RETENTION_DAYS – number of daily log files to keep (default 7).
    CREWAI_VERBOSE          – set to "true" to enable verbose CrewAI agent/crew output
                              on the console (default "false").
    LOG_TARGET              – logging target: "file" (default, file-based rotation),
                              "stdout" (structured JSON to stdout for GCP Cloud Logging),
                              "both" (file + stdout JSON).

Log files are stored in the ``logs/`` directory with the naming pattern
``crewai_YYYY-MM-DD.log`` and automatically rotated at midnight.
"""

import json
import logging
import os
import re
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

_LOG_DIR = Path("logs")
_LOG_FILENAME = "crewai.log"
_DATE_FMT = "%Y-%m-%d %H:%M:%S"
_LOG_FMT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"

_configured = False

# Regex patterns to redact sensitive tokens / secrets / signed headers from log
# messages (e.g. WebSocket ?token=..., OAuth callback ?code=..., webhook
# Authorization: Bearer ..., X-Hub-Signature-256 in payload dumps, etc.).
_SENSITIVE_PATTERNS = (
    re.compile(r"([\?&]token=)[^\s&\"']+", re.IGNORECASE),
    re.compile(r"([\?&]access_token=)[^\s&\"']+", re.IGNORECASE),
    re.compile(r"([\?&]refresh_token=)[^\s&\"']+", re.IGNORECASE),
    re.compile(r"([\?&]ticket=)[^\s&\"']+", re.IGNORECASE),
    re.compile(r"([\?&]api[-_]?key=)[^\s&\"']+", re.IGNORECASE),
    re.compile(r"([\?&](?:secret|signature)=)[^\s&\"']+", re.IGNORECASE),
    re.compile(r"(Authorization:\s*Bearer\s+)[^\s\"']+", re.IGNORECASE),
    re.compile(r"(X-(?:Api-Key|Auth-Token|Hub-Signature(?:-256)?)\s*[:=]\s*)[^\s,\"']+", re.IGNORECASE),
    re.compile(r"([\?&]code=)[^\s&\"']+", re.IGNORECASE),
    re.compile(r"([\?&]client_secret=)[^\s&\"']+", re.IGNORECASE),
)

# Kept for backwards-compat; some callers / tests import this symbol directly.
_TOKEN_REDACT_RE = _SENSITIVE_PATTERNS[0]


def _redact(text: str) -> str:
    """Apply every sensitive-data pattern to ``text``."""
    for pattern in _SENSITIVE_PATTERNS:
        text = pattern.sub(r"\1[REDACTED]", text)
    return text


class _TokenRedactFilter(logging.Filter):
    """Redact JWT/auth tokens and other secrets from log messages.

    Handles two formats:
    - Standard log records: token in ``record.msg`` or ``%(s)`` args.
    - Uvicorn access records: args is a tuple
      ``(client_addr, method, full_path, http_version, status_code)``
      where ``full_path`` may contain ``?token=...``.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        # ── Redact inside uvicorn-style tuple args ────────────
        if isinstance(record.args, tuple):
            record.args = tuple(
                _redact(str(a)) if isinstance(a, str) else a
                for a in record.args
            )
        elif isinstance(record.args, dict):
            record.args = {
                k: _redact(str(v)) if isinstance(v, str) else v
                for k, v in record.args.items()
            }

        # ── Redact the message itself ─────────────────────────
        record.msg = _redact(str(record.msg))
        return True

# Mapping from Python log levels to GCP Cloud Logging severity names.
_GCP_SEVERITY = {
    logging.DEBUG: "DEBUG",
    logging.INFO: "INFO",
    logging.WARNING: "WARNING",
    logging.ERROR: "ERROR",
    logging.CRITICAL: "CRITICAL",
}


class _JSONFormatter(logging.Formatter):
    """Emit structured JSON log lines compatible with GCP Cloud Logging.

    GCP automatically parses JSON lines on stdout and picks up the
    ``severity``, ``message``, and ``time`` fields.
    """

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "severity": _GCP_SEVERITY.get(record.levelno, "DEFAULT"),
            "message": record.getMessage(),
            "logger": record.name,
            "time": self.formatTime(record, _DATE_FMT),
        }
        if record.exc_info and record.exc_info[1]:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry, ensure_ascii=False)


def _is_truthy(value: str | None) -> bool:
    """Return True for common truthy env-var strings."""
    return (value or "").strip().lower() in ("true", "1", "yes")


def setup_logging() -> logging.Logger:
    """Configure and return the root project logger.

    Safe to call multiple times — subsequent calls are no-ops.

    Honours the ``LOG_TARGET`` env var:

    * ``"file"`` (default) — daily-rotated log files in ``logs/``.
    * ``"stdout"`` — structured JSON to stdout (for GCP Cloud Logging).
    * ``"both"`` — file + stdout JSON simultaneously.
    """
    global _configured
    if _configured:
        return logging.getLogger("crewai_productfeature_planner")

    debug_enabled = _is_truthy(os.environ.get("CREWAI_DEBUG"))
    flow_debug = _is_truthy(os.environ.get("CREWAI_FLOW_DEBUG"))
    retention_days = int(os.environ.get("CREWAI_LOG_RETENTION_DAYS", "7"))
    log_target = os.environ.get("LOG_TARGET", "file").strip().lower()

    root_level = logging.DEBUG if debug_enabled else logging.INFO

    # ── Token redaction filter (applies to all handlers) ─────
    redact_filter = _TokenRedactFilter()

    # ── Root project logger ───────────────────────────────────
    logger = logging.getLogger("crewai_productfeature_planner")
    logger.setLevel(root_level)
    logger.propagate = False
    logger.addFilter(redact_filter)

    # ── Apply redaction to Uvicorn loggers ──────────────────
    # Uvicorn logs full WebSocket URLs including ?token= query params and may
    # surface webhook payload errors with secrets via uvicorn.error.
    for uvi_name in ("uvicorn", "uvicorn.access", "uvicorn.error"):
        logging.getLogger(uvi_name).addFilter(redact_filter)

    formatter = logging.Formatter(_LOG_FMT, datefmt=_DATE_FMT)

    use_file = log_target in ("file", "both")
    use_stdout = log_target in ("stdout", "both")

    # ── File handler (daily rotation) ─────────────────────────
    if use_file:
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

    # ── Stdout JSON handler (for GCP Cloud Logging) ───────────
    if use_stdout:
        json_handler = logging.StreamHandler()
        json_handler.setLevel(root_level)
        json_handler.setFormatter(_JSONFormatter())
        logger.addHandler(json_handler)

    # ── Console handler (only when flow debug is on) ──────────
    if flow_debug and not use_stdout:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(root_level)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    _configured = True
    logger.info(
        "Logging initialised (debug=%s, flow_debug=%s, retention=%d days, target=%s)",
        debug_enabled, flow_debug, retention_days, log_target,
    )
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


def get_uvicorn_log_config() -> dict:
    """Return a uvicorn-compatible log config with token redaction.

    Uvicorn calls ``logging.config.dictConfig()`` on startup, which
    replaces any filters we previously attached to ``uvicorn.access``.
    By embedding the filter class directly in the config dict, the
    filter survives uvicorn's logger reconfiguration.
    """
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "filters": {
            "token_redact": {
                "()": _TokenRedactFilter,
            },
        },
        "formatters": {
            "default": {
                "()": "uvicorn.logging.DefaultFormatter",
                "fmt": "%(levelprefix)s %(message)s",
                "use_colors": None,
            },
            "access": {
                "()": "uvicorn.logging.AccessFormatter",
                "fmt": '%(levelprefix)s %(client_addr)s - "%(request_line)s" %(status_code)s',
            },
        },
        "handlers": {
            "default": {
                "formatter": "default",
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stderr",
                "filters": ["token_redact"],
            },
            "access": {
                "formatter": "access",
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stdout",
                "filters": ["token_redact"],
            },
        },
        "loggers": {
            "uvicorn": {
                "handlers": ["default"],
                "level": "INFO",
                "propagate": False,
            },
            "uvicorn.error": {
                "level": "INFO",
            },
            "uvicorn.access": {
                "handlers": ["access"],
                "level": "INFO",
                "propagate": False,
            },
        },
    }


def is_verbose() -> bool:
    """Return ``True`` when ``CREWAI_VERBOSE`` is set to a truthy value.

    Controls whether CrewAI agents and crews emit verbose console output.
    Defaults to ``False`` so that internal prompt scaffolding (e.g.
    *"you MUST return the actual complete content …"*) is suppressed.
    """
    return _is_truthy(os.environ.get("CREWAI_VERBOSE"))
