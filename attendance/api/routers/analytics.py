from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import ORJSONResponse
from sqlalchemy.orm import Session

from api.deps import get_current_user, get_db
from models.user import AuthUser
from services.analytics import AttendanceAnalytics


router = APIRouter()


def _analytics_filters(
    date_start: Optional[date] = Query(None),
    date_end: Optional[date] = Query(None),
    group_id: Optional[int] = Query(None),
    shift_id: Optional[int] = Query(None),
    terminal_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    employee: Optional[str] = Query(None),
    branch: Optional[str] = Query(None),
    sector: Optional[str] = Query(None),
    days: Optional[int] = Query(None, ge=1, le=365),
):
    return {
        "date_start": date_start,
        "date_end": date_end,
        "group_id": group_id,
        "shift_id": shift_id,
        "terminal_id": terminal_id,
        "status": status,
        "employee": employee,
        "branch": branch,
        "sector": sector,
        "days": days,
    }


@router.get("/dashboard", response_class=ORJSONResponse)
def get_analytics_dashboard(
    filters: dict = Depends(_analytics_filters),
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    return AttendanceAnalytics(db).dashboard(**filters)


@router.get("/overview", response_class=ORJSONResponse)
def get_analytics_overview(
    filters: dict = Depends(_analytics_filters),
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    service = AttendanceAnalytics(db)
    normalized = service._filters(**filters)
    return service.get_overview(normalized)


@router.get("/action-items", response_class=ORJSONResponse)
def get_analytics_action_items(
    filters: dict = Depends(_analytics_filters),
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    service = AttendanceAnalytics(db)
    normalized = service._filters(**filters)
    return service.get_action_items(normalized)


@router.get("/status-by-group", response_class=ORJSONResponse)
def get_analytics_status_by_group(
    filters: dict = Depends(_analytics_filters),
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    service = AttendanceAnalytics(db)
    normalized = service._filters(**filters)
    return service.get_status_by_group(normalized)


@router.get("/trends", response_class=ORJSONResponse)
def get_analytics_trends(
    filters: dict = Depends(_analytics_filters),
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    service = AttendanceAnalytics(db)
    normalized = service._filters(**filters)
    return service.get_trends(normalized)


@router.get("/recent-activity", response_class=ORJSONResponse)
def get_analytics_recent_activity(
    filters: dict = Depends(_analytics_filters),
    limit: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    service = AttendanceAnalytics(db)
    normalized = service._filters(**filters)
    return service.get_recent_activity(normalized, limit=limit)


@router.get("/data-quality", response_class=ORJSONResponse)
def get_analytics_data_quality(
    filters: dict = Depends(_analytics_filters),
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    service = AttendanceAnalytics(db)
    normalized = service._filters(**filters)
    return service.get_data_quality(normalized)


@router.get("/device-health", response_class=ORJSONResponse)
def get_analytics_device_health(
    filters: dict = Depends(_analytics_filters),
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    service = AttendanceAnalytics(db)
    normalized = service._filters(**filters)
    return service.get_device_health(normalized)
