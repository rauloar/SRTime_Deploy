from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.routers import auth, users, shifts, processed, movements

app = FastAPI(
    title="Attendance System API",
    description="Secure REST API directly integrated with PySide6 PostgreSQL core models.",
    version="1.0.0",
)

# CORS Policy Configuration
origins = [
    "http://localhost",
    "http://localhost:3000", # Common React port
    "http://localhost:5173", # Common Vite port
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Sub-Routers
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(users.router, prefix="/api/users", tags=["Employees Management"])
app.include_router(shifts.router, prefix="/api/shifts", tags=["Shifts"])
app.include_router(processed.router, prefix="/api/processed", tags=["Processed Attendance"])
app.include_router(movements.router, prefix="/api/movements", tags=["Raw Movements"])

@app.get("/api/health")
def health_check():
    """Endpoint for load balancers or React tests to verify API is active."""
    return {"status": "ok", "message": "Attendance Web Backend running correctly"}
