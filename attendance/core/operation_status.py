"""In-memory status tracking for local long-running QA operations."""
from __future__ import annotations

from datetime import datetime, timezone
from threading import RLock
from uuid import uuid4


class OperationStatusStore:
    def __init__(self) -> None:
        self._items: dict[str, dict] = {}
        self._lock = RLock()

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def create(self, operation: str, message: str) -> dict:
        job = {
            "id": uuid4().hex,
            "operation": operation,
            "state": "queued",
            "current": 0,
            "total": 0,
            "percent": 0,
            "message": message,
            "result": None,
            "error": None,
            "started_at": self._now(),
            "finished_at": None,
        }
        with self._lock:
            self._items[job["id"]] = job
        return dict(job)

    def update(self, job_id: str, *, current: int | None = None, total: int | None = None, message: str | None = None) -> None:
        with self._lock:
            job = self._items.get(job_id)
            if not job:
                return
            job["state"] = "running"
            if current is not None:
                job["current"] = current
            if total is not None:
                job["total"] = total
            if message is not None:
                job["message"] = message
            if job["total"]:
                job["percent"] = min(99, round((job["current"] / job["total"]) * 100))

    def complete(self, job_id: str, result: dict, message: str) -> None:
        with self._lock:
            job = self._items.get(job_id)
            if not job:
                return
            job.update({"state": "completed", "percent": 100, "message": message, "result": result, "finished_at": self._now()})
            if job["total"]:
                job["current"] = job["total"]

    def fail(self, job_id: str, error: str) -> None:
        with self._lock:
            job = self._items.get(job_id)
            if job:
                job.update({"state": "failed", "error": error, "message": error, "finished_at": self._now()})

    def get(self, job_id: str) -> dict | None:
        with self._lock:
            job = self._items.get(job_id)
            return dict(job) if job else None


operation_status = OperationStatusStore()
