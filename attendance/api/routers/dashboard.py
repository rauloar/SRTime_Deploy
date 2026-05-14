from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import date, timedelta

from core.logging_config import get_logger
logger = get_logger(__name__)

from api.deps import get_db, get_current_user
from models.user import AuthUser

router = APIRouter()


@router.get("/summary")
def get_dashboard_summary(
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user)
):
    from models.employee import User
    from models.processed_attendance import ProcessedAttendance
    from models.holiday import Holiday

    today = date.today()
    month_start = today.replace(day=1)
    week_start = today - timedelta(days=6)
    next30 = today + timedelta(days=30)

    # Employees
    active = db.query(User).filter(User.is_active == True).count()
    inactive = db.query(User).filter(User.is_active == False).count()

    # Current month
    month_recs = db.query(ProcessedAttendance).filter(
        ProcessedAttendance.date >= month_start,
        ProcessedAttendance.date <= today
    ).all()
    month_by_status = {"OK": 0, "INCOMPLETO": 0, "JUSTIFICADO": 0}
    total_tard = total_ot = 0
    for r in month_recs:
        month_by_status[r.status] = month_by_status.get(r.status, 0) + 1
        total_tard += r.tardiness_minutes or 0
        total_ot += r.overtime_minutes or 0

    # Last 7 days
    week_recs = db.query(ProcessedAttendance).filter(
        ProcessedAttendance.date >= week_start,
        ProcessedAttendance.date <= today
    ).all()
    week_incomplete = sum(1 for r in week_recs if r.status == "INCOMPLETO")

    # Upcoming holidays (next 30 days)
    holidays = db.query(Holiday).all()
    upcoming = []
    for h in holidays:
        if h.is_recurring:
            candidate = h.date.replace(year=today.year)
            if candidate < today:
                candidate = candidate.replace(year=today.year + 1)
        else:
            candidate = h.date
        if today <= candidate <= next30:
            upcoming.append({"date": str(candidate), "name": h.name, "is_recurring": h.is_recurring})

    return {
        "employees": {"active": active, "inactive": inactive, "total": active + inactive},
        "current_month": {
            "month": today.month,
            "year": today.year,
            "total_records": len(month_recs),
            "by_status": month_by_status,
            "total_tardiness_minutes": total_tard,
            "total_overtime_minutes": total_ot,
        },
        "last_7_days": {
            "total_records": len(week_recs),
            "incomplete": week_incomplete,
        },
        "upcoming_holidays": sorted(upcoming, key=lambda x: x["date"]),
    }
