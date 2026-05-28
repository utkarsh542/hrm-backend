"""Attendance & Leave router."""
from datetime import datetime, date
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.models.attendance import Attendance, AttendanceStatus, LeaveRequest, LeaveType, LeaveStatus, Holiday
from app.models.employee import Employee
from app.models.user import User, UserRole
from app.schemas.schemas import (
    AttendanceCreate, AttendanceCheckIn, AttendanceResponse,
    LeaveRequestCreate, LeaveRequestUpdate, LeaveRequestResponse
)
from app.services.auth_service import get_current_user, get_current_employee, require_roles

router = APIRouter(prefix="/api/attendance", tags=["Attendance & Leave"])


# ===== ATTENDANCE =====
@router.post("/check-in")
def check_in(
    request: AttendanceCheckIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_employee: Employee = Depends(get_current_employee)
):
    # Enforce data isolation: Employees and Managers can only check-in for themselves
    target_emp_id = request.employee_id
    if current_user.role.value in ["employee", "manager"]:
        target_emp_id = current_employee.id

    today = date.today()
    existing = db.query(Attendance).filter(
        Attendance.employee_id == target_emp_id,
        Attendance.date == today
    ).first()
    
    if existing and existing.check_in:
        raise HTTPException(status_code=400, detail="Already checked in today")
    
    if existing:
        existing.check_in = datetime.utcnow()
        existing.status = AttendanceStatus.PRESENT
    else:
        attendance = Attendance(
            employee_id=target_emp_id,
            date=today,
            check_in=datetime.utcnow(),
            status=AttendanceStatus.PRESENT,
        )
        db.add(attendance)
    
    db.commit()
    return {"message": "Checked in successfully", "time": datetime.utcnow().isoformat()}


@router.post("/check-out")
def check_out(
    request: AttendanceCheckIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_employee: Employee = Depends(get_current_employee)
):
    # Enforce data isolation: Employees and Managers can only check-out for themselves
    target_emp_id = request.employee_id
    if current_user.role.value in ["employee", "manager"]:
        target_emp_id = current_employee.id

    today = date.today()
    attendance = db.query(Attendance).filter(
        Attendance.employee_id == target_emp_id,
        Attendance.date == today
    ).first()
    
    if not attendance or not attendance.check_in:
        raise HTTPException(status_code=400, detail="Not checked in today")
    
    attendance.check_out = datetime.utcnow()
    if attendance.check_in:
        diff = attendance.check_out - attendance.check_in
        attendance.work_hours = round(diff.total_seconds() / 3600, 2)
        if attendance.work_hours > 9:
            attendance.overtime_hours = round(attendance.work_hours - 9, 2)
    
    db.commit()
    return {"message": "Checked out successfully", "work_hours": attendance.work_hours}


@router.get("/records", response_model=list[AttendanceResponse])
def get_attendance_records(
    employee_id: Optional[int] = None,
    month: Optional[int] = None,
    year: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_employee: Employee = Depends(get_current_employee)
):
    # Enforce data isolation
    if current_user.role.value in ["employee", "manager"]:
        employee_id = current_employee.id

    query = db.query(Attendance)
    if employee_id:
        query = query.filter(Attendance.employee_id == employee_id)
    if month and year:
        from sqlalchemy import extract
        query = query.filter(
            extract('month', Attendance.date) == month,
            extract('year', Attendance.date) == year
        )
    
    records = query.order_by(Attendance.date.desc()).all()
    
    # Pre-fetch all employees to avoid N+1 queries in loop
    employees = db.query(Employee).all()
    emp_map = {e.id: e.full_name for e in employees}
    
    result = []
    for r in records:
        resp = AttendanceResponse.model_validate(r)
        resp.employee_name = emp_map.get(r.employee_id, "")
        result.append(resp)
    return result


@router.get("/summary/{employee_id}")
def get_attendance_summary(
    employee_id: int,
    month: int,
    year: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_employee: Employee = Depends(get_current_employee)
):
    # Enforce data isolation
    if current_user.role.value in ["employee", "manager"]:
        if employee_id != current_employee.id:
            raise HTTPException(status_code=403, detail="Forbidden: You can only query your own data")

    from sqlalchemy import extract
    records = db.query(Attendance).filter(
        Attendance.employee_id == employee_id,
        extract('month', Attendance.date) == month,
        extract('year', Attendance.date) == year
    ).all()
    
    present = sum(1 for r in records if r.status == AttendanceStatus.PRESENT)
    absent = sum(1 for r in records if r.status == AttendanceStatus.ABSENT)
    wfh = sum(1 for r in records if r.status == AttendanceStatus.WORK_FROM_HOME)
    half_days = sum(1 for r in records if r.status == AttendanceStatus.HALF_DAY)
    total_hours = sum(r.work_hours or 0 for r in records)
    overtime = sum(r.overtime_hours or 0 for r in records)
    
    return {
        "present": present,
        "absent": absent,
        "work_from_home": wfh,
        "half_days": half_days,
        "total_hours": round(total_hours, 2),
        "overtime_hours": round(overtime, 2),
        "total_records": len(records),
    }


# ===== LEAVES =====
@router.post("/leaves/", response_model=LeaveRequestResponse)
def apply_leave(
    request: LeaveRequestCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_employee: Employee = Depends(get_current_employee)
):
    # Enforce data isolation
    target_emp_id = request.employee_id
    if current_user.role.value in ["employee", "manager"]:
        target_emp_id = current_employee.id

    emp = db.query(Employee).filter(Employee.id == target_emp_id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    # Calculate days
    days = (request.end_date - request.start_date).days + 1
    
    # Check balance
    if request.leave_type == "casual" and emp.casual_leave_balance < days:
        raise HTTPException(status_code=400, detail="Insufficient casual leave balance")
    elif request.leave_type == "sick" and emp.sick_leave_balance < days:
        raise HTTPException(status_code=400, detail="Insufficient sick leave balance")
    elif request.leave_type == "earned" and emp.earned_leave_balance < days:
        raise HTTPException(status_code=400, detail="Insufficient earned leave balance")
    
    leave_data = request.model_dump()
    leave_data["employee_id"] = target_emp_id

    leave = LeaveRequest(
        **leave_data,
        days=days,
    )
    db.add(leave)
    db.commit()
    db.refresh(leave)

    # Trigger Leave Pending Notifications for Managers & HR
    try:
        from app.routers.notifications import create_notification
        from app.services.email_service import send_leave_notification
        
        # 1. Notify Reporting Manager (if set)
        if emp.reporting_manager_id:
            mgr = db.query(Employee).filter(Employee.id == emp.reporting_manager_id).first()
            if mgr and mgr.user_id:
                create_notification(
                    db=db,
                    user_id=mgr.user_id,
                    title="Leave Request Pending Action",
                    message=f"{emp.full_name} has requested {days} day(s) of {request.leave_type} leave. Review required.",
                    type="action",
                    link="/approvals"
                )
                # Send email notification
                send_leave_notification(
                    to_email=mgr.email,
                    employee_name=emp.full_name,
                    leave_type=request.leave_type,
                    start_date=str(request.start_date),
                    end_date=str(request.end_date),
                    days=days,
                    reason=request.reason or "No reason provided."
                )

        # 2. Notify all HR & Admin accounts in database
        from app.models.user import User, UserRole
        privileged_users = db.query(User).filter(User.role.in_([UserRole.ADMIN, UserRole.HR])).all()
        for p_user in privileged_users:
            # Avoid duplicate manager alerts
            if emp.reporting_manager_id and mgr and p_user.id == mgr.user_id:
                continue
            create_notification(
                db=db,
                user_id=p_user.id,
                title="Leave Applied (Admin Alert)",
                message=f"{emp.full_name} has submitted a leave request for {days} day(s). Review required.",
                type="info",
                link="/approvals"
            )
    except Exception as e:
        import logging
        logger = logging.getLogger("uvicorn")
        logger.error(f"Error in leave application notifications: {e}")
        
    resp = LeaveRequestResponse.model_validate(leave)
    resp.employee_name = emp.full_name
    return resp


@router.get("/leaves/", response_model=list[LeaveRequestResponse])
def list_leaves(
    employee_id: Optional[int] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_employee: Employee = Depends(get_current_employee)
):
    # Enforce data isolation
    if current_user.role.value in ["employee", "manager"]:
        employee_id = current_employee.id

    query = db.query(LeaveRequest)
    if employee_id:
        query = query.filter(LeaveRequest.employee_id == employee_id)
    if status:
        query = query.filter(LeaveRequest.status == LeaveStatus(status))
    
    leaves = query.order_by(LeaveRequest.created_at.desc()).all()
    
    # Pre-fetch all employees to avoid N+1 queries in loop
    employees = db.query(Employee).all()
    emp_map = {e.id: e.full_name for e in employees}
    
    result = []
    for l in leaves:
        resp = LeaveRequestResponse.model_validate(l)
        resp.employee_name = emp_map.get(l.employee_id, "")
        result.append(resp)
    return result


@router.put("/leaves/{leave_id}", response_model=LeaveRequestResponse)
def update_leave(
    leave_id: int,
    request: LeaveRequestUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "hr", "manager")) # Leave approval enforcement!
):
    leave = db.query(LeaveRequest).filter(LeaveRequest.id == leave_id).first()
    if not leave:
        raise HTTPException(status_code=404, detail="Leave request not found")
    
    if request.status == "approved":
        leave.status = LeaveStatus.APPROVED
        leave.approved_at = datetime.utcnow()
        
        # Deduct leave balance
        emp = db.query(Employee).filter(Employee.id == leave.employee_id).first()
        if emp:
            if leave.leave_type == LeaveType.CASUAL:
                emp.casual_leave_balance = max(0, emp.casual_leave_balance - leave.days)
            elif leave.leave_type == LeaveType.SICK:
                emp.sick_leave_balance = max(0, emp.sick_leave_balance - leave.days)
            elif leave.leave_type == LeaveType.EARNED:
                emp.earned_leave_balance = max(0, emp.earned_leave_balance - leave.days)
    
    elif request.status == "rejected":
        leave.status = LeaveStatus.REJECTED
        leave.rejection_reason = request.rejection_reason
    
    db.commit()
    db.refresh(leave)
    
    emp = db.query(Employee).filter(Employee.id == leave.employee_id).first()
    
    # Trigger Status Update Notifications for the Employee
    try:
        from app.routers.notifications import create_notification
        from app.services.email_service import send_leave_status_update
        
        status_str = leave.status.value
        remarks = leave.rejection_reason if status_str == "rejected" else "Leave request approved."
        
        if emp:
            # 1. Send in-app notification
            if emp.user_id:
                create_notification(
                    db=db,
                    user_id=emp.user_id,
                    title=f"Leave Request {status_str.title()}",
                    message=f"Your {leave.leave_type.value} leave request for {leave.days} day(s) has been {status_str}. Remarks: \"{remarks}\"",
                    type="success" if status_str == "approved" else "warning",
                    link="/attendance/leaves"
                )
            
            # 2. Send email notification
            send_leave_status_update(
                to_email=emp.email,
                employee_name=emp.full_name,
                leave_type=leave.leave_type.value,
                status=status_str,
                comments=remarks
            )
    except Exception as e:
        import logging
        logger = logging.getLogger("uvicorn")
        logger.error(f"Error in leave status update notifications: {e}")
        
    resp = LeaveRequestResponse.model_validate(leave)
    resp.employee_name = emp.full_name if emp else ""
    return resp


@router.get("/leaves/balance/{employee_id}")
def get_leave_balance(
    employee_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_employee: Employee = Depends(get_current_employee)
):
    # Enforce data isolation
    if current_user.role.value in ["employee", "manager"]:
        if employee_id != current_employee.id:
            raise HTTPException(status_code=403, detail="Forbidden: You can only query your own data")

    emp = db.query(Employee).filter(Employee.id == employee_id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    return {
        "casual": emp.casual_leave_balance,
        "sick": emp.sick_leave_balance,
        "earned": emp.earned_leave_balance,
        "total_available": emp.casual_leave_balance + emp.sick_leave_balance + emp.earned_leave_balance,
    }


# ===== HOLIDAYS =====
@router.get("/holidays/")
def list_holidays(db: Session = Depends(get_db)):
    return db.query(Holiday).order_by(Holiday.date).all()
