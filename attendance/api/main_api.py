import json
import os
import sys
import time
import uuid
from contextlib import asynccontextmanager

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from core.logging_config import setup_logging, get_logger, request_id_ctx
from core.limiter import limiter

# Initialize logging BEFORE importing routers
setup_logging()
logger = get_logger("api")

from api.routers import absences, auth, users, shifts, processed, movements, auth_users, importer, terminals, holidays, dashboard, reports, setup, control


@asynccontextmanager
async def lifespan(_app: FastAPI):
    from services.terminal_scheduler import start_scheduler, stop_scheduler
    start_scheduler()
    logger.info("SRTime API started", extra={"action": "startup"})
    yield
    stop_scheduler()
    logger.info("SRTime API stopped", extra={"action": "shutdown"})

app = FastAPI(
    title="Attendance System API",
    description="SRTime REST API — Attendance Management",
    version="0.9.0-beta.4",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# ── Request Logging Middleware ────────────────────────────────

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Logs every HTTP request with timing and correlation ID."""

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4())[:8])
        request_id_ctx.set(request_id)

        start = time.perf_counter()

        logger.info(
            f"REQUEST START {request.method} {request.url.path}",
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
            f"REQUEST END {request.method} {request.url.path} {response.status_code} ({duration_ms}ms)",
            extra={
                "method": request.method,
                "path": str(request.url.path),
                "status_code": response.status_code,
                "duration_ms": duration_ms,
            },
        )

        response.headers["X-Request-ID"] = request_id
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Agrega cabeceras HTTP de seguridad a todas las respuestas."""
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
            "script-src 'self' 'unsafe-inline'; connect-src 'self'"
        )
        if request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response

app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(SecurityHeadersMiddleware)


# ── CORS Policy Configuration ────────────────────────────────

_cors_env = os.getenv("CORS_ORIGINS", "[]")
origins = json.loads(_cors_env)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    expose_headers=["X-Request-ID"],
)


# ── Mount Sub-Routers ────────────────────────────────────────

app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(setup.router, prefix="/api/setup", tags=["Initial Setup"])
app.include_router(auth_users.router, prefix="/api/auth-users", tags=["Authorized Users"])
app.include_router(importer.router, prefix="/api/import", tags=["Import"])
app.include_router(users.router, prefix="/api/users", tags=["Employees Management"])
app.include_router(shifts.router, prefix="/api/shifts", tags=["Shifts"])
app.include_router(processed.router, prefix="/api/processed", tags=["Processed Attendance"])
app.include_router(absences.router, prefix="/api/absences", tags=["Absences"])
app.include_router(movements.router, prefix="/api/movements", tags=["Raw Movements"])
app.include_router(terminals.router, prefix="/api/terminals", tags=["Device Terminals"])
app.include_router(holidays.router, prefix="/api/holidays", tags=["Holidays"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["Dashboard"])
app.include_router(reports.router, prefix="/api/reports", tags=["Reports"])
app.include_router(control.router, prefix="/api/control", tags=["Control Center"])


@app.get("/api/health")
def health_check():
    """Endpoint for load balancers or monitoring to verify API is active."""
    return {"status": "ok", "message": "Attendance Web Backend running correctly"}


# Next.js se exporta como archivos estáticos. FastAPI los sirve desde el
# directorio configurado o desde web/out en desarrollo. El mount se registra
# al final para no interceptar rutas /api.
_default_web_dir = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "web", "out"
)
_web_dir = os.getenv("SRTIME_WEB_DIR", _default_web_dir)
if os.path.isdir(_web_dir):
    app.mount("/", StaticFiles(directory=_web_dir, html=True), name="web")
