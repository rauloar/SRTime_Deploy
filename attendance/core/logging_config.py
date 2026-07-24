"""Configuración de logs estructurados para FastAPI mediante ``dictConfig``.

La aplicación no expone archivos de log por API. Los operadores los consultan
directamente en el directorio configurado por entorno. Las rutas, formato y
retención se configuran con ``LOG_*`` en el archivo de entorno activo.
"""

from __future__ import annotations

import json
import logging
import logging.config
import os
import sys
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

request_id_ctx: ContextVar[str] = ContextVar("request_id", default="-")

_ATTENDANCE_DIR = Path(__file__).resolve().parents[1]
_initialized = False

_EXTRA_KEYS = (
    "user", "action", "detail", "method", "path",
    "status_code", "duration_ms", "client_ip",
)


class JSONFormatter(logging.Formatter):
    """Formato JSON apto para journald y herramientas de observabilidad."""

    def format(self, record: logging.LogRecord) -> str:
        entry: dict[str, object] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": request_id_ctx.get("-"),
        }
        for key in _EXTRA_KEYS:
            value = getattr(record, key, None)
            if value is not None:
                entry[key] = value
        if record.exc_info and record.exc_info[0]:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry, ensure_ascii=False, default=str)


class TextFormatter(logging.Formatter):
    """Formato legible para ejecución local."""

    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        message = (
            f"{timestamp} [{record.levelname:<7}] [{request_id_ctx.get('-')[:8]}] "
            f"{record.name}: {record.getMessage()}"
        )
        extras = [
            f"{key}={getattr(record, key)}"
            for key in _EXTRA_KEYS
            if getattr(record, key, None) is not None
        ]
        if extras:
            message += f"  | {', '.join(extras)}"
        if record.exc_info and record.exc_info[0]:
            message += "\n" + self.formatException(record.exc_info)
        return message


@dataclass(frozen=True)
class LogSettings:
    level: str
    format_name: str
    directory: Path
    app_file: str
    error_file: str
    max_bytes: int
    backup_count: int


def _load_active_environment() -> None:
    """Carga el entorno elegido por el launcher antes de leer ``LOG_*``."""
    env_path = Path(os.getenv("SRTIME_ENV_FILE", _ATTENDANCE_DIR / ".env"))
    load_dotenv(env_path, override=False)


def _positive_int(name: str, default: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        return default
    return value if value > 0 else default


def _settings_from_environment() -> LogSettings:
    _load_active_environment()
    configured_dir = Path(os.getenv("LOG_DIR", "logs"))
    directory = configured_dir if configured_dir.is_absolute() else _ATTENDANCE_DIR / configured_dir
    return LogSettings(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format_name=os.getenv("LOG_FORMAT", "json").lower(),
        directory=directory,
        app_file=os.getenv("LOG_APP_FILE", "api.log"),
        error_file=os.getenv("LOG_ERROR_FILE", "api-error.log"),
        max_bytes=_positive_int("LOG_MAX_BYTES", 10 * 1024 * 1024),
        backup_count=_positive_int("LOG_BACKUP_COUNT", 5),
    )


def _dict_config(settings: LogSettings, include_files: bool) -> dict:
    formatter = "text" if settings.format_name == "text" else "json"
    handlers: dict[str, dict] = {
        "console": {
            "class": "logging.StreamHandler",
            "level": settings.level,
            "formatter": formatter,
            "stream": "ext://sys.stdout",
        }
    }
    root_handlers = ["console"]
    if include_files:
        common = {
            "class": "logging.handlers.RotatingFileHandler",
            "formatter": formatter,
            "maxBytes": settings.max_bytes,
            "backupCount": settings.backup_count,
            "encoding": "utf-8",
        }
        handlers["application_file"] = {
            **common,
            "level": settings.level,
            "filename": str(settings.directory / settings.app_file),
        }
        handlers["error_file"] = {
            **common,
            "level": "ERROR",
            "filename": str(settings.directory / settings.error_file),
        }
        root_handlers.extend(["application_file", "error_file"])
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "json": {"()": JSONFormatter},
            "text": {"()": TextFormatter},
        },
        "handlers": handlers,
        "root": {"level": settings.level, "handlers": root_handlers},
    }


def setup_logging() -> None:
    """Configura stdout y archivos rotativos antes de instanciar FastAPI."""
    global _initialized
    if _initialized:
        return

    settings = _settings_from_environment()
    try:
        settings.directory.mkdir(parents=True, exist_ok=True)
        logging.config.dictConfig(_dict_config(settings, include_files=True))
    except OSError:
        logging.config.dictConfig(_dict_config(settings, include_files=False))
        logging.getLogger(__name__).warning(
            "Cannot create configured log directory; using stdout only",
            extra={"action": "logging_fallback"},
        )

    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("passlib").setLevel(logging.WARNING)
    logging.getLogger("multipart").setLevel(logging.WARNING)
    _initialized = True


def get_logger(name: str) -> logging.Logger:
    """Obtiene un logger con el formato y handlers configurados por entorno."""
    return logging.getLogger(name)
