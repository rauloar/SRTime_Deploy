"""Operational diagnostics and PostgreSQL backups for the SRTime Control Center."""
from __future__ import annotations

import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import text

from core.logging_config import get_logger

logger = get_logger(__name__)


def _runtime_root() -> Path:
    env_file = os.getenv("SRTIME_ENV_FILE")
    if env_file:
        path = Path(env_file).resolve()
        return path.parent.parent if path.parent.name == "config" else path.parent
    return Path(__file__).resolve().parents[2]


def backup_directory() -> Path:
    configured = os.getenv("SRTIME_BACKUP_DIR", "backups")
    directory = Path(configured)
    return directory if directory.is_absolute() else _runtime_root() / directory


def _latest_backup() -> dict | None:
    directory = backup_directory()
    if not directory.is_dir():
        return None
    candidates = sorted(directory.glob("srtime_*.dump"), key=lambda item: item.stat().st_mtime, reverse=True)
    if not candidates:
        return None
    latest = candidates[0]
    stat = latest.stat()
    return {"name": latest.name, "created_at": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(), "size_bytes": stat.st_size}


def get_status() -> dict:
    """Return a safe, read-only operational snapshot."""
    database_ok = False
    try:
        # ``configure_database`` replaces the engine during initial setup;
        # import it at call time so the Control Center follows that switch.
        from core.database import engine
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        database_ok = True
    except Exception:
        pass
    from services.terminal_scheduler import is_scheduler_running
    return {
        "application": {"status": "running"},
        "database": {"status": "ok" if database_ok else "unavailable", "engine": os.getenv("DB_ENGINE", "sqlite").lower(), "error": None if database_ok else "No se pudo establecer conexión con PostgreSQL."},
        "scheduler": {"status": "running" if is_scheduler_running() else "stopped"},
        "backup": {"enabled": bool(os.getenv("SRTIME_PG_DUMP_PATH") or shutil.which("pg_dump")), "latest": _latest_backup()},
        "service": {"status": "managed_externally", "name": os.getenv("SRTIME_SERVICE_NAME", "SRTimeWeb")},
    }


def create_postgres_backup() -> dict:
    """Create a custom-format PostgreSQL dump without persisting credentials."""
    if os.getenv("DB_ENGINE", "sqlite").lower() != "postgres":
        raise RuntimeError("Los backups operativos requieren PostgreSQL.")
    executable = os.getenv("SRTIME_PG_DUMP_PATH") or shutil.which("pg_dump")
    if not executable:
        raise RuntimeError("No se encontró pg_dump. Configure SRTIME_PG_DUMP_PATH.")
    directory = backup_directory()
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"srtime_{datetime.now().strftime('%Y%m%d_%H%M%S')}.dump"
    command = [executable, "--format=custom", "--no-owner", "--no-privileges", "--file", str(target), "--host", os.getenv("DB_HOST", "localhost"), "--port", os.getenv("DB_PORT", "5432"), "--username", os.getenv("DB_USER", "postgres"), os.getenv("DB_NAME", "srtime_db")]
    process_env = os.environ.copy()
    process_env["PGPASSWORD"] = os.getenv("DB_PASS", "")
    try:
        result = subprocess.run(command, env=process_env, capture_output=True, text=True, timeout=int(os.getenv("SRTIME_BACKUP_TIMEOUT_SECONDS", "600")), check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        target.unlink(missing_ok=True)
        raise RuntimeError("No se pudo ejecutar el backup de PostgreSQL.") from exc
    if result.returncode != 0:
        target.unlink(missing_ok=True)
        logger.warning("PostgreSQL backup failed", extra={"action": "backup_failed"})
        raise RuntimeError("PostgreSQL no pudo crear el backup. Revise los logs del servidor.")
    stat = target.stat()
    logger.info("PostgreSQL backup created", extra={"action": "backup_created", "detail": target.name})
    return {"name": target.name, "created_at": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(), "size_bytes": stat.st_size}
