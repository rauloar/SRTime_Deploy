"""
SRTime — Centralized Logging Configuration

Usage:
    from core.logging_config import get_logger
    logger = get_logger(__name__)
    logger.info("Message", extra={"user": "admin", "action": "login"})

Environment variables:
    LOG_LEVEL:    DEBUG | INFO | WARNING | ERROR  (default: INFO)
    LOG_FORMAT:   json  | text                    (default: json)
    LOG_DIR:      Directory for log files         (default: logs/ next to attendance/)
"""

import logging
import logging.handlers
import json
import os
import sys
from datetime import datetime, timezone
from contextvars import ContextVar
from pathlib import Path

# ── Context variable for request correlation ──────────────────
request_id_ctx: ContextVar[str] = ContextVar("request_id", default="-")

# ── Configuration from environment ────────────────────────────
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_FORMAT = os.getenv("LOG_FORMAT", "json")

# Default log directory: next to the attendance/ package
_DEFAULT_LOG_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "logs",
)
LOG_DIR = os.getenv("LOG_DIR", _DEFAULT_LOG_DIR)

# Extra keys that may be attached via `extra={...}`
_EXTRA_KEYS = (
    "user", "action", "detail", "method", "path",
    "status_code", "duration_ms", "client_ip",
)


# ── Formatters ────────────────────────────────────────────────

class JSONFormatter(logging.Formatter):
    """Structured JSON formatter — ideal for production log aggregation."""

    def format(self, record: logging.LogRecord) -> str:
        entry: dict = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": request_id_ctx.get("-"),
        }

        for key in _EXTRA_KEYS:
            val = getattr(record, key, None)
            if val is not None:
                entry[key] = val

        if record.exc_info and record.exc_info[0]:
            entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(entry, ensure_ascii=False, default=str)


class TextFormatter(logging.Formatter):
    """Human-readable formatter for local development."""

    def format(self, record: logging.LogRecord) -> str:
        rid = request_id_ctx.get("-")
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        base = f"{ts} [{record.levelname:<7}] [{rid[:8]}] {record.name}: {record.getMessage()}"

        extras = []
        for key in _EXTRA_KEYS:
            val = getattr(record, key, None)
            if val is not None:
                extras.append(f"{key}={val}")
        if extras:
            base += f"  | {', '.join(extras)}"

        if record.exc_info and record.exc_info[0]:
            base += "\n" + self.formatException(record.exc_info)

        return base


# ── Setup ─────────────────────────────────────────────────────

_initialized = False


def setup_logging() -> None:
    """
    Configure root logger with stdout + file handlers.
    Safe to call multiple times (only runs once).
    """
    global _initialized
    if _initialized:
        return
    _initialized = True

    level = getattr(logging, LOG_LEVEL, logging.INFO)
    formatter = JSONFormatter() if LOG_FORMAT == "json" else TextFormatter()

    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()

    # ── stdout handler (captured by systemd journald) ─────────
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setLevel(level)
    stdout_handler.setFormatter(formatter)
    root.addHandler(stdout_handler)

    # ── File handlers (rotated, 10 MB, keep 5 backups) ────────
    try:
        Path(LOG_DIR).mkdir(parents=True, exist_ok=True)

        # Main application log
        app_handler = logging.handlers.RotatingFileHandler(
            os.path.join(LOG_DIR, "api.log"),
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=5,
            encoding="utf-8",
        )
        app_handler.setLevel(level)
        app_handler.setFormatter(formatter)
        root.addHandler(app_handler)

        # Error-only log (for quick monitoring)
        err_handler = logging.handlers.RotatingFileHandler(
            os.path.join(LOG_DIR, "api-error.log"),
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        err_handler.setLevel(logging.ERROR)
        err_handler.setFormatter(formatter)
        root.addHandler(err_handler)

    except OSError:
        # If we can't write to the log directory, continue with stdout only
        root.warning(f"Cannot create log directory: {LOG_DIR}. Using stdout only.")

    # ── Quieten noisy libraries ───────────────────────────────
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("passlib").setLevel(logging.WARNING)
    logging.getLogger("multipart").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Get a named logger. Convention: pass ``__name__``."""
    return logging.getLogger(name)
