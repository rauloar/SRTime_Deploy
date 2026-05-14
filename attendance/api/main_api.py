import json
import os
import sys
import time
import uuid

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from core.logging_config import setup_logging, get_logger, request_id_ctx

# Initialize logging BEFORE importing routers
setup_logging()
logger = get_logger("api")

# Limiter instances global
limiter = Limiter(key_func=get_remote_address)

from api.routers import auth, users, shifts, processed, movements, auth_users, importer, terminals, holidays, dashboard, reports

app = FastAPI(
    title="Attendance System API",
    description="SRTime REST API — Attendance Management",
    version="1.0.0",
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


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Agrega cabeceras HTTP de seguridad a todas las respuestas."""
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response

app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(SecurityHeadersMiddleware)


# ── CORS Policy Configuration ────────────────────────────────

_cors_env = os.getenv("CORS_ORIGINS", "")
origins = (
    json.loads(_cors_env)
    if _cors_env
    else [
        "http://localhost",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://192.168.1.35:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
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
app.include_router(terminals.router, prefix="/api/terminals", tags=["Device Terminals"])
app.include_router(holidays.router, prefix="/api/holidays", tags=["Holidays"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["Dashboard"])
app.include_router(reports.router, prefix="/api/reports", tags=["Reports"])


@app.get("/api/health")
def health_check():
    """Endpoint for load balancers or monitoring to verify API is active."""
    return {"status": "ok", "message": "Attendance Web Backend running correctly"}


@app.on_event("startup")
async def on_startup():
    logger.info("SRTime API started", extra={"action": "startup"})
