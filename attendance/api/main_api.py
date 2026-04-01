import json
import os
import sys
import time
import uuid

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from core.logging_config import setup_logging, get_logger, request_id_ctx

# Initialize logging BEFORE importing routers
setup_logging()
logger = get_logger("api")

from api.routers import auth, users, shifts, processed, movements, auth_users, importer

app = FastAPI(
    title="Attendance System API",
    description="SRTime REST API — Attendance Management",
    version="1.0.0",
)


# ── Request Logging Middleware ────────────────────────────────

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Logs every HTTP request with timing and correlation ID."""

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4())[:8])
        request_id_ctx.set(request_id)

        start = time.perf_counter()

        logger.info(
            f"→ {request.method} {request.url.path}",
            extra={
                "method": request.method,
                "path": str(request.url.path),
                "client_ip": request.client.host if request.client else "-",
            },
        )

        try:
            response = await call_next(request)
        except Exception:
            logger.exception("Unhandled exception during request")
            raise

        duration_ms = round((time.perf_counter() - start) * 1000, 1)

        logger.info(
            f"← {request.method} {request.url.path} {response.status_code} ({duration_ms}ms)",
            extra={
                "method": request.method,
                "path": str(request.url.path),
                "status_code": response.status_code,
                "duration_ms": duration_ms,
            },
        )

        response.headers["X-Request-ID"] = request_id
        return response


app.add_middleware(RequestLoggingMiddleware)


# ── CORS Policy Configuration ────────────────────────────────

_cors_env = os.getenv("CORS_ORIGINS", "")
origins = (
    json.loads(_cors_env)
    if _cors_env
    else [
        "http://localhost",
        "http://localhost:3000",
        "http://localhost:5173",
    ]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
)


# ── Mount Sub-Routers ────────────────────────────────────────

app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(auth_users.router, prefix="/api/auth-users", tags=["Authorized Users"])
app.include_router(importer.router, prefix="/api/import", tags=["Import"])
app.include_router(users.router, prefix="/api/users", tags=["Employees Management"])
app.include_router(shifts.router, prefix="/api/shifts", tags=["Shifts"])
app.include_router(processed.router, prefix="/api/processed", tags=["Processed Attendance"])
app.include_router(movements.router, prefix="/api/movements", tags=["Raw Movements"])


@app.get("/api/health")
def health_check():
    """Endpoint for load balancers or monitoring to verify API is active."""
    return {"status": "ok", "message": "Attendance Web Backend running correctly"}


@app.on_event("startup")
async def on_startup():
    logger.info("SRTime API started", extra={"action": "startup"})
