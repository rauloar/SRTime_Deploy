from collections import defaultdict
from datetime import datetime, date, timedelta
from sqlalchemy.orm import Session
from models.attendance import AttendanceLog
from models.employee import User
from models.shift import Shift
from models.processed_attendance import ProcessedAttendance

class AttendanceEngine:
    def __init__(self, session: Session):
        self.session = session

    def process_all(self, progress_callback=None, force_all=False):
        """
        Processes raw AttendanceLog records, calculates hours, tardiness, etc.,
        and upserts the results into the ProcessedAttendance table.
        """
        # Fetch raw logs
        query = self.session.query(AttendanceLog)
        if not force_all:
            query = query.filter(AttendanceLog.is_processed == False)
            
        logs = query.order_by(
            AttendanceLog.employee_id, 
            AttendanceLog.date, 
            AttendanceLog.time
        ).all()

        if not logs:
            return 0 # Nothing to process

        # Group by (employee_id, date)
        grouped_logs = defaultdict(list)
        for log in logs:
            if log.employee_id: # Ignore logs not linked to an employee yet
                grouped_logs[(log.employee_id, log.date)].append(log)

        processed_count = 0
        total_days = len(grouped_logs)

        # Process each day for each employee
        for (emp_id, day), daily_logs in grouped_logs.items():
            if not daily_logs:
                continue

            employee = self.session.query(User).filter_by(id=emp_id).first()
            if not employee: 
                continue
            
            # Check if this day is already manually justified, skip calculation
            existing = self.session.query(ProcessedAttendance).filter_by(
                employee_id=emp_id, date=day
            ).first()
            
            if existing and existing.status == "JUSTIFICADO":
                processed_count += 1
                if progress_callback and processed_count % 10 == 0:
                    progress_callback(processed_count, total_days)
                continue
            
            shift = self.session.query(Shift).filter_by(id=employee.shift_id).first() if employee.shift_id else None
            
            # Simple pairing heuristic: First punch is IN, last is OUT.
            # In a robust system, you would iterate and find pairs (In, Out, In, Out) summing times.
            first_log_time = daily_logs[0].time
            last_log_time = daily_logs[-1].time if len(daily_logs) > 1 else None
            
            total_hours = 0.0
            if first_log_time and last_log_time:
                dt_in = datetime.combine(day, first_log_time)
                dt_out = datetime.combine(day, last_log_time)
                
                # If for some reason OUT < IN (e.g. overnight shift handled poorly), avoid negative hours
                if dt_out > dt_in:
                    total_hours = (dt_out - dt_in).total_seconds() / 3600.0
            
            tardiness = 0
            early_departure = 0
            overtime = 0
            status = "OK"
            if not last_log_time:
                status = "INCOMPLETO" # Missing clock out
                
            # Apply Business Rules if Shift exists
            if shift and first_log_time:
                expected_in_dt = datetime.combine(day, shift.expected_in)
                actual_in_dt = datetime.combine(day, first_log_time)
                
                diff_minutes = (actual_in_dt - expected_in_dt).total_seconds() / 60.0
                if diff_minutes > shift.grace_period_minutes:
                    tardiness = int(diff_minutes)
                    
                # Check early departure and overtime
                if last_log_time:
                    expected_out_dt = datetime.combine(day, shift.expected_out)
                    actual_out_dt = datetime.combine(day, last_log_time)
                    
                    if actual_out_dt < expected_out_dt:
                        diff = (expected_out_dt - actual_out_dt).total_seconds() / 60.0
                        early_departure = int(diff)
                    elif actual_out_dt > expected_out_dt:
                        diff = (actual_out_dt - expected_out_dt).total_seconds() / 60.0
                        overtime = int(diff)
            
            # Upsert logic
            if not existing:
                existing = ProcessedAttendance(employee_id=emp_id, date=day)
                self.session.add(existing)
                
            existing.first_in = first_log_time
            existing.last_out = last_log_time
            existing.total_hours = round(total_hours, 2)
            existing.tardiness_minutes = tardiness
            existing.early_departure_minutes = early_departure
            existing.overtime_minutes = overtime
            existing.status = status
            
            # Mark raw logs as processed
            for log in daily_logs:
                log.is_processed = True
            
            processed_count += 1
            if progress_callback and processed_count % 10 == 0:
                progress_callback(processed_count, total_days)
            
        self.session.commit()
        return processed_count
