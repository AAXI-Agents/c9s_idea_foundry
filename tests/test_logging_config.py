"""Tests for the centralized logging configuration."""

import logging
import os
from pathlib import Path
from unittest.mock import patch

import pytest

import crewai_productfeature_planner.scripts.logging_config as lc


@pytest.fixture(autouse=True)
def _reset_logging_state():
    """Reset the module-level _configured flag before each test.

    Teardown sets ``_configured = True`` so that ``setup_logging()``
    is a no-op for any subsequent test module that triggers
    ``get_logger()`` — preventing a new ``TimedRotatingFileHandler``
    from being added to the production log file.
    """
    lc._configured = False
    logger = logging.getLogger("crewai_productfeature_planner")
    logger.handlers.clear()
    logger.filters.clear()
    uvicorn_access = logging.getLogger("uvicorn.access")
    uvicorn_access.filters.clear()
    yield
    lc._configured = True
    logger.handlers.clear()
    logger.filters.clear()
    uvicorn_access.filters.clear()


def test_setup_logging_creates_log_dir(tmp_path, monkeypatch):
    """Log directory should be created if it doesn't exist."""
    log_dir = tmp_path / "test_logs"
    monkeypatch.setattr(lc, "_LOG_DIR", log_dir)
    monkeypatch.setenv("CREWAI_DEBUG", "false")
    monkeypatch.setenv("CREWAI_FLOW_DEBUG", "false")

    lc.setup_logging()

    assert log_dir.exists()


def test_setup_logging_idempotent(tmp_path, monkeypatch):
    """Calling setup_logging twice should not duplicate handlers."""
    monkeypatch.setattr(lc, "_LOG_DIR", tmp_path)
    monkeypatch.setenv("CREWAI_DEBUG", "false")
    monkeypatch.setenv("CREWAI_FLOW_DEBUG", "false")

    lc.setup_logging()
    lc.setup_logging()

    logger = logging.getLogger("crewai_productfeature_planner")
    assert len(logger.handlers) == 1  # file handler only


def test_debug_enabled_sets_debug_level(tmp_path, monkeypatch):
    """When CREWAI_DEBUG=true, root logger level should be DEBUG."""
    monkeypatch.setattr(lc, "_LOG_DIR", tmp_path)
    monkeypatch.setenv("CREWAI_DEBUG", "true")
    monkeypatch.setenv("CREWAI_FLOW_DEBUG", "false")

    logger = lc.setup_logging()

    assert logger.level == logging.DEBUG


def test_debug_disabled_sets_info_level(tmp_path, monkeypatch):
    """When CREWAI_DEBUG=false, root logger level should be INFO."""
    monkeypatch.setattr(lc, "_LOG_DIR", tmp_path)
    monkeypatch.setenv("CREWAI_DEBUG", "false")
    monkeypatch.setenv("CREWAI_FLOW_DEBUG", "false")

    logger = lc.setup_logging()

    assert logger.level == logging.INFO


def test_flow_debug_adds_console_handler(tmp_path, monkeypatch):
    """When CREWAI_FLOW_DEBUG=true, a StreamHandler should be added."""
    monkeypatch.setattr(lc, "_LOG_DIR", tmp_path)
    monkeypatch.setenv("CREWAI_DEBUG", "false")
    monkeypatch.setenv("CREWAI_FLOW_DEBUG", "true")

    lc.setup_logging()

    logger = logging.getLogger("crewai_productfeature_planner")
    handler_types = [type(h).__name__ for h in logger.handlers]
    assert "StreamHandler" in handler_types
    assert len(logger.handlers) == 2  # file + console


def test_flow_debug_off_no_console_handler(tmp_path, monkeypatch):
    """When CREWAI_FLOW_DEBUG=false, only file handler should exist."""
    monkeypatch.setattr(lc, "_LOG_DIR", tmp_path)
    monkeypatch.setenv("CREWAI_DEBUG", "false")
    monkeypatch.setenv("CREWAI_FLOW_DEBUG", "false")

    lc.setup_logging()

    logger = logging.getLogger("crewai_productfeature_planner")
    handler_types = [type(h).__name__ for h in logger.handlers]
    assert "StreamHandler" not in handler_types


def test_retention_days_from_env(tmp_path, monkeypatch):
    """Handler backupCount should reflect CREWAI_LOG_RETENTION_DAYS."""
    monkeypatch.setattr(lc, "_LOG_DIR", tmp_path)
    monkeypatch.setenv("CREWAI_DEBUG", "false")
    monkeypatch.setenv("CREWAI_FLOW_DEBUG", "false")
    monkeypatch.setenv("CREWAI_LOG_RETENTION_DAYS", "14")

    lc.setup_logging()

    logger = logging.getLogger("crewai_productfeature_planner")
    file_handler = logger.handlers[0]
    assert file_handler.backupCount == 14


def test_retention_days_default(tmp_path, monkeypatch):
    """Default retention should be 7 days."""
    monkeypatch.setattr(lc, "_LOG_DIR", tmp_path)
    monkeypatch.setenv("CREWAI_DEBUG", "false")
    monkeypatch.setenv("CREWAI_FLOW_DEBUG", "false")
    monkeypatch.delenv("CREWAI_LOG_RETENTION_DAYS", raising=False)

    lc.setup_logging()

    logger = logging.getLogger("crewai_productfeature_planner")
    file_handler = logger.handlers[0]
    assert file_handler.backupCount == 7


def test_get_logger_returns_child(tmp_path, monkeypatch):
    """get_logger should return a child of the project namespace."""
    monkeypatch.setattr(lc, "_LOG_DIR", tmp_path)
    monkeypatch.setenv("CREWAI_DEBUG", "false")
    monkeypatch.setenv("CREWAI_FLOW_DEBUG", "false")

    child = lc.get_logger("my_module")

    assert child.name == "crewai_productfeature_planner.my_module"


def test_log_file_written(tmp_path, monkeypatch):
    """An info message should appear in the log file."""
    monkeypatch.setattr(lc, "_LOG_DIR", tmp_path)
    monkeypatch.setenv("CREWAI_DEBUG", "false")
    monkeypatch.setenv("CREWAI_FLOW_DEBUG", "false")

    logger = lc.setup_logging()
    logger.info("test_log_entry_123")

    # Flush handlers
    for h in logger.handlers:
        h.flush()

    log_file = tmp_path / lc._LOG_FILENAME
    content = log_file.read_text()
    assert "test_log_entry_123" in content


def test_debug_messages_hidden_when_disabled(tmp_path, monkeypatch):
    """Debug messages should NOT appear when CREWAI_DEBUG=false."""
    monkeypatch.setattr(lc, "_LOG_DIR", tmp_path)
    monkeypatch.setenv("CREWAI_DEBUG", "false")
    monkeypatch.setenv("CREWAI_FLOW_DEBUG", "false")

    logger = lc.setup_logging()
    logger.debug("secret_debug_msg_999")

    for h in logger.handlers:
        h.flush()

    log_file = tmp_path / lc._LOG_FILENAME
    content = log_file.read_text()
    assert "secret_debug_msg_999" not in content


def test_debug_messages_visible_when_enabled(tmp_path, monkeypatch):
    """Debug messages should appear when CREWAI_DEBUG=true."""
    monkeypatch.setattr(lc, "_LOG_DIR", tmp_path)
    monkeypatch.setenv("CREWAI_DEBUG", "true")
    monkeypatch.setenv("CREWAI_FLOW_DEBUG", "false")

    logger = lc.setup_logging()
    logger.debug("visible_debug_msg_777")

    for h in logger.handlers:
        h.flush()

    log_file = tmp_path / lc._LOG_FILENAME
    content = log_file.read_text()
    assert "visible_debug_msg_777" in content


def test_is_truthy_variants():
    """Various truthy string values should be recognised."""
    assert lc._is_truthy("true") is True
    assert lc._is_truthy("True") is True
    assert lc._is_truthy("TRUE") is True
    assert lc._is_truthy("1") is True
    assert lc._is_truthy("yes") is True
    assert lc._is_truthy("false") is False
    assert lc._is_truthy("0") is False
    assert lc._is_truthy("") is False
    assert lc._is_truthy(None) is False


# ── is_verbose tests ─────────────────────────────────────────


def test_is_verbose_defaults_to_false(monkeypatch):
    """Without CREWAI_VERBOSE set, is_verbose() returns False."""
    monkeypatch.delenv("CREWAI_VERBOSE", raising=False)
    assert lc.is_verbose() is False


def test_is_verbose_true(monkeypatch):
    """CREWAI_VERBOSE=true should return True."""
    monkeypatch.setenv("CREWAI_VERBOSE", "true")
    assert lc.is_verbose() is True


def test_is_verbose_false_explicit(monkeypatch):
    """CREWAI_VERBOSE=false should return False."""
    monkeypatch.setenv("CREWAI_VERBOSE", "false")
    assert lc.is_verbose() is False


def test_is_verbose_one(monkeypatch):
    """CREWAI_VERBOSE=1 should return True."""
    monkeypatch.setenv("CREWAI_VERBOSE", "1")
    assert lc.is_verbose() is True


# ── Token redaction filter tests ─────────────────────────────


def test_token_redact_filter_strips_jwt_from_websocket_url():
    """Token query params must be redacted from log messages."""
    f = lc._TokenRedactFilter()
    record = logging.LogRecord(
        name="uvicorn.access",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg='127.0.0.1:53490 - "WebSocket /ws/ideation/abc123?token=eyJhbGciOiJSUz.payload.sig" [accepted]',
        args=None,
        exc_info=None,
    )
    f.filter(record)
    assert "eyJhbGciOiJSUz" not in record.msg
    assert "?token=[REDACTED]" in record.msg
    assert "[accepted]" in record.msg


def test_token_redact_filter_handles_multiple_params():
    """Token param in the middle of a query string must be redacted."""
    f = lc._TokenRedactFilter()
    record = logging.LogRecord(
        name="uvicorn.access",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg='/ws/session?foo=bar&token=secret_value&baz=qux',
        args=None,
        exc_info=None,
    )
    f.filter(record)
    assert "secret_value" not in record.msg
    assert "&token=[REDACTED]" in record.msg
    assert "foo=bar" in record.msg
    assert "baz=qux" in record.msg


def test_token_redact_filter_no_token_unchanged():
    """Messages without token params should pass through unchanged."""
    f = lc._TokenRedactFilter()
    original = '127.0.0.1 - "GET /health" 200'
    record = logging.LogRecord(
        name="uvicorn.access",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg=original,
        args=None,
        exc_info=None,
    )
    f.filter(record)
    assert record.msg == original


def test_token_redact_filter_with_args():
    """Filter must redact tokens embedded in string args."""
    f = lc._TokenRedactFilter()
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg='WS connected: %s',
        args=("/ws/ideation/abc?token=my_secret_jwt_token",),
        exc_info=None,
    )
    f.filter(record)
    assert "my_secret_jwt_token" not in record.getMessage()
    assert "?token=[REDACTED]" in record.getMessage()


def test_token_redact_filter_uvicorn_tuple_args():
    """Uvicorn access records use tuple args; token in full_path must be redacted."""
    f = lc._TokenRedactFilter()
    # Uvicorn access log: args = (client_addr, method, full_path, http_version, status_code)
    record = logging.LogRecord(
        name="uvicorn.access",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg='%s - "%s %s HTTP/%s" %s',
        args=(
            "127.0.0.1:58515",
            "GET",
            "/ws/ideation/abc123?token=eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.payload.sig",
            "1.1",
            403,
        ),
        exc_info=None,
    )
    f.filter(record)
    # Token must be redacted from the tuple arg
    assert "eyJhbGciOiJSUzI1Ni" not in str(record.args)
    assert "?token=[REDACTED]" in str(record.args)
    # Non-token args must survive
    assert record.args[0] == "127.0.0.1:58515"
    assert record.args[1] == "GET"
    assert record.args[3] == "1.1"
    assert record.args[4] == 403
    # getMessage() must produce a redacted string
    msg = record.getMessage()
    assert "eyJhbGciOiJSUzI1Ni" not in msg
    assert "?token=[REDACTED]" in msg


def test_token_redact_filter_dict_args():
    """Dict-style %-formatting args must also be redacted."""
    f = lc._TokenRedactFilter()
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg='%(path)s connected',
        args=({"path": "/ws/ideation/abc?token=secret_jwt"},),
        exc_info=None,
    )
    # LogRecord stores single-dict as the dict itself
    # Our filter handles both tuple and dict shapes
    f.filter(record)
    msg = record.getMessage()
    assert "secret_jwt" not in msg
    assert "?token=[REDACTED]" in msg


def test_uvicorn_access_logger_gets_redact_filter(tmp_path, monkeypatch):
    """setup_logging must attach the redact filter to uvicorn.access."""
    monkeypatch.setattr(lc, "_LOG_DIR", tmp_path)
    monkeypatch.setenv("CREWAI_DEBUG", "false")
    monkeypatch.setenv("CREWAI_FLOW_DEBUG", "false")

    lc.setup_logging()

    uvicorn_access = logging.getLogger("uvicorn.access")
    filter_types = [type(f).__name__ for f in uvicorn_access.filters]
    assert "_TokenRedactFilter" in filter_types


def test_get_uvicorn_log_config_has_token_filter():
    """get_uvicorn_log_config must embed the token redact filter in both handlers."""
    cfg = lc.get_uvicorn_log_config()
    assert "token_redact" in cfg["filters"]
    assert cfg["filters"]["token_redact"]["()"] is lc._TokenRedactFilter
    assert "token_redact" in cfg["handlers"]["default"]["filters"]
    assert "token_redact" in cfg["handlers"]["access"]["filters"]


def test_get_uvicorn_log_config_produces_valid_dictconfig():
    """The returned config must be accepted by logging.config.dictConfig."""
    import logging.config
    cfg = lc.get_uvicorn_log_config()
    # Should not raise
    logging.config.dictConfig(cfg)
