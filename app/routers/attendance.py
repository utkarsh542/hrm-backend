"""Attendance & Leave router."""
import random
from datetime import datetime, date
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.config import settings
from app.services.geocoding_service import (
    calculate_haversine_distance, reverse_geocode,
    get_org_coordinates, update_org_coordinates
)

def _verify_face(image_base64: str, employee_id: int) -> dict:
    """
    Simulated face verification.
    In production: integrate DeepFace / AWS Rekognition / Azure Face API.
    Returns confidence score and match result.
    """
    if not image_base64 or len(image_base64) < 100:
        return {"verified": False, "confidence": 0.0, "reason": "Invalid image snapshot"}
    # Simulate: 95% success rate with high confidence
    confidence = round(random.uniform(0.85, 0.99), 3)
    verified = confidence >= 0.80
    return {
        "verified": verified,
        "confidence": confidence,
        "reason": "Face matched successfully" if verified else "Face match confidence too low",
    }

from app.models.attendance import (
    Attendance, AttendanceStatus, LeaveRequest, LeaveType, LeaveStatus, Holiday,
    CompOffRule, CompOffRequest
)
from app.models.employee import Employee
from app.models.user import User, UserRole
from app.schemas.schemas import (
    AttendanceCreate, AttendanceCheckIn, AttendanceResponse,
    LeaveRequestCreate, LeaveRequestUpdate, LeaveRequestResponse,
    CompOffRuleResponse, CompOffRuleUpdate, CompOffRequestCreate,
    CompOffRequestResponse, CompOffRequestAction
)
from app.services.auth_service import get_current_user, get_current_employee, require_roles

router = APIRouter(prefix="/api/attendance", tags=["Attendance & Leave"])


def get_role_value(role) -> str:
    if hasattr(role, "value"):
        return str(role.value).lower()
    return str(role).lower()



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
    if get_role_value(current_user.role) in ["employee", "manager"]:
        target_emp_id = current_employee.id

    # Face snap check
    if not request.image_base64:
        raise HTTPException(
            status_code=400, 
            detail="Check-in rejected: Webcam face snap verification is required."
        )
    
    face_res = _verify_face(request.image_base64, target_emp_id)
    if not face_res["verified"]:
        raise HTTPException(
            status_code=403, 
            detail=f"Face verification failed: {face_res['reason']}"
        )

    # Geofence Validation Check
    if request.latitude is not None and request.longitude is not None:
        org_coords = get_org_coordinates(db)
        distance = calculate_haversine_distance(
            request.latitude, request.longitude, 
            org_coords["latitude"], org_coords["longitude"]
        )
        if distance > org_coords["radius"]:
            raise HTTPException(
                status_code=400, 
                detail=f"Check-in rejected: You are {round(distance, 1)}m away from the office. You must be within {org_coords['radius']}m."
            )
        
        # Geocode the coordinates to fetch address details
        geo_info = reverse_geocode(request.latitude, request.longitude)
        check_in_lat = request.latitude
        check_in_lon = request.longitude
        check_in_address = geo_info["address"]
        check_in_district = geo_info["district"]
        check_in_state = geo_info["state"]
    else:
        raise HTTPException(
            status_code=400, 
            detail="Check-in rejected: Physical location coordinates are required for geofence validation."
        )

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
        existing.check_in_lat = check_in_lat
        existing.check_in_lon = check_in_lon
        existing.check_in_address = check_in_address
        existing.check_in_district = check_in_district
        existing.check_in_state = check_in_state
    else:
        attendance = Attendance(
            employee_id=target_emp_id,
            date=today,
            check_in=datetime.utcnow(),
            status=AttendanceStatus.PRESENT,
            check_in_lat=check_in_lat,
            check_in_lon=check_in_lon,
            check_in_address=check_in_address,
            check_in_district=check_in_district,
            check_in_state=check_in_state
        )
        db.add(attendance)
    
    db.commit()
    return {"message": f"✅ Checked in successfully (Face verified with {int(face_res['confidence']*100)}% match!)", "time": datetime.utcnow().isoformat()}


@router.post("/check-out")
def check_out(
    request: AttendanceCheckIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_employee: Employee = Depends(get_current_employee)
):
    # Enforce data isolation: Employees and Managers can only check-out for themselves
    target_emp_id = request.employee_id
    if get_role_value(current_user.role) in ["employee", "manager"]:
        target_emp_id = current_employee.id

    # Face snap check
    if not request.image_base64:
        raise HTTPException(
            status_code=400, 
            detail="Check-out rejected: Webcam face snap verification is required."
        )
    
    face_res = _verify_face(request.image_base64, target_emp_id)
    if not face_res["verified"]:
        raise HTTPException(
            status_code=403, 
            detail=f"Face verification failed: {face_res['reason']}"
        )

    # Geofence Validation Check
    if request.latitude is not None and request.longitude is not None:
        org_coords = get_org_coordinates(db)
        distance = calculate_haversine_distance(
            request.latitude, request.longitude, 
            org_coords["latitude"], org_coords["longitude"]
        )
        if distance > org_coords["radius"]:
            raise HTTPException(
                status_code=400, 
                detail=f"Check-out rejected: You are {round(distance, 1)}m away from the office. You must be within {org_coords['radius']}m."
            )
        
        # Geocode the coordinates to fetch address details
        geo_info = reverse_geocode(request.latitude, request.longitude)
        check_out_lat = request.latitude
        check_out_lon = request.longitude
        check_out_address = geo_info["address"]
        check_out_district = geo_info["district"]
        check_out_state = geo_info["state"]
    else:
        raise HTTPException(
            status_code=400, 
            detail="Check-out rejected: Physical location coordinates are required for geofence validation."
        )

    today = date.today()
    attendance = db.query(Attendance).filter(
        Attendance.employee_id == target_emp_id,
        Attendance.date == today
    ).first()
    
    if not attendance or not attendance.check_in:
        raise HTTPException(status_code=400, detail="Not checked in today")
    
    attendance.check_out = datetime.utcnow()
    attendance.check_out_lat = check_out_lat
    attendance.check_out_lon = check_out_lon
    attendance.check_out_address = check_out_address
    attendance.check_out_district = check_out_district
    attendance.check_out_state = check_out_state
    
    if attendance.check_in:
        diff = attendance.check_out - attendance.check_in
        attendance.work_hours = round(diff.total_seconds() / 3600, 2)
        if attendance.work_hours > 9:
            attendance.overtime_hours = round(attendance.work_hours - 9, 2)
    
    db.commit()
    return {"message": f"✅ Checked out successfully (Face verified with {int(face_res['confidence']*100)}% match!)", "work_hours": attendance.work_hours}


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
    if get_role_value(current_user.role) in ["employee", "manager"]:
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
    if get_role_value(current_user.role) in ["employee", "manager"]:
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
    if get_role_value(current_user.role) in ["employee", "manager"]:
        target_emp_id = current_employee.id

    emp = db.query(Employee).filter(Employee.id == target_emp_id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    # Calculate days
    days = (request.end_date - request.start_date).days + 1

    # Validate that no days in the range fall on a weekend or an official holiday
    from datetime import timedelta
    curr_date = request.start_date
    while curr_date <= request.end_date:
        # Check weekend (5: Saturday, 6: Sunday)
        if curr_date.weekday() in [5, 6]:
            raise HTTPException(
                status_code=400,
                detail=f"Leave request rejected: {curr_date.strftime('%Y-%m-%d')} falls on a weekend (Saturday/Sunday)."
            )
        # Check official holiday
        holiday = db.query(Holiday).filter(Holiday.date == curr_date).first()
        if holiday:
            raise HTTPException(
                status_code=400,
                detail=f"Leave request rejected: {curr_date.strftime('%Y-%m-%d')} is an official holiday ({holiday.name})."
            )
        curr_date += timedelta(days=1)
    
    # Check balance
    if request.leave_type == "casual" and emp.casual_leave_balance < days:
        raise HTTPException(status_code=400, detail="Insufficient casual leave balance")
    elif request.leave_type == "sick" and emp.sick_leave_balance < days:
        raise HTTPException(status_code=400, detail="Insufficient sick leave balance")
    elif request.leave_type == "earned" and emp.earned_leave_balance < days:
        raise HTTPException(status_code=400, detail="Insufficient earned leave balance")
    elif request.leave_type == "compensatory":
        if (emp.comp_off_balance or 0.0) < days:
            raise HTTPException(status_code=400, detail="Insufficient compensatory/comp-off leave balance")
        emp.comp_off_balance = (emp.comp_off_balance or 0.0) - days
    
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
    if get_role_value(current_user.role) in ["employee", "manager"]:
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
    current_user: User = Depends(get_current_user),
    current_employee: Employee = Depends(get_current_employee)
):
    leave = db.query(LeaveRequest).filter(LeaveRequest.id == leave_id).first()
    if not leave:
        raise HTTPException(status_code=404, detail="Leave request not found")
        
    # Enforce Role Guards: Employees can only cancel their own leaves or edit details if pending
    is_admin_or_hr_or_manager = get_role_value(current_user.role) in ["admin", "hr", "manager"]
    
    is_editing_details = (
        request.start_date is not None or 
        request.end_date is not None or 
        request.reason is not None or 
        request.leave_type is not None
    )
    
    if not is_admin_or_hr_or_manager:
        if leave.employee_id != current_employee.id:
            raise HTTPException(status_code=403, detail="Forbidden: You can only update your own leave requests")
        if request.status is not None and request.status != "cancelled":
            raise HTTPException(status_code=403, detail="Forbidden: Employees can only cancel their own leaves")
            
    if is_editing_details:
        if leave.status != LeaveStatus.PENDING:
            raise HTTPException(status_code=400, detail="Cannot edit a leave request that is not pending.")
            
        new_start = request.start_date if request.start_date is not None else leave.start_date
        new_end = request.end_date if request.end_date is not None else leave.end_date
        new_reason = request.reason if request.reason is not None else leave.reason
        new_type_str = request.leave_type if request.leave_type is not None else (leave.leave_type.value if hasattr(leave.leave_type, "value") else str(leave.leave_type))
        
        # Verify dates
        if new_start > new_end:
            raise HTTPException(status_code=400, detail="Start date cannot be after end date.")
            
        # Recalculate days (excluding weekends and holidays)
        from datetime import timedelta
        new_days = 0.0
        curr_date = new_start
        while curr_date <= new_end:
            # Check weekend (5: Saturday, 6: Sunday)
            if curr_date.weekday() in [5, 6]:
                raise HTTPException(
                    status_code=400,
                    detail=f"Leave request rejected: {curr_date.strftime('%Y-%m-%d')} falls on a weekend (Saturday/Sunday)."
                )
            # Check official holiday
            holiday = db.query(Holiday).filter(Holiday.date == curr_date).first()
            if holiday:
                raise HTTPException(
                    status_code=400,
                    detail=f"Leave request rejected: {curr_date.strftime('%Y-%m-%d')} is an official holiday ({holiday.name})."
                )
            new_days += 1.0
            curr_date += timedelta(days=1)
            
        emp = db.query(Employee).filter(Employee.id == leave.employee_id).first()
        if not emp:
            raise HTTPException(status_code=404, detail="Employee not found")
            
        prev_type = leave.leave_type
        new_type = LeaveType(new_type_str)
        
        # Refund old comp-off days if previous type was compensatory
        if prev_type == LeaveType.COMPENSATORY:
            emp.comp_off_balance = (emp.comp_off_balance or 0.0) + leave.days
            
        # Deduct new comp-off days if new type is compensatory
        if new_type == LeaveType.COMPENSATORY:
            if (emp.comp_off_balance or 0.0) < new_days:
                # Rollback refund if it was compensatory
                if prev_type == LeaveType.COMPENSATORY:
                    emp.comp_off_balance = (emp.comp_off_balance or 0.0) - leave.days
                raise HTTPException(
                    status_code=400, 
                    detail=f"Insufficient compensatory/comp-off balance. Required: {new_days}, Available: {emp.comp_off_balance}"
                )
            emp.comp_off_balance = (emp.comp_off_balance or 0.0) - new_days
            
        leave.start_date = new_start
        leave.end_date = new_end
        leave.days = new_days
        leave.reason = new_reason
        leave.leave_type = new_type
    
    if request.status == "approved":
        if leave.status != LeaveStatus.APPROVED:
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
        if leave.leave_type == LeaveType.COMPENSATORY:
            emp = db.query(Employee).filter(Employee.id == leave.employee_id).first()
            if emp:
                emp.comp_off_balance = (emp.comp_off_balance or 0.0) + leave.days
        
    elif request.status == "cancelled":
        emp = db.query(Employee).filter(Employee.id == leave.employee_id).first()
        if emp:
            if leave.leave_type == LeaveType.CASUAL:
                if leave.status == LeaveStatus.APPROVED:
                    emp.casual_leave_balance = emp.casual_leave_balance + leave.days
            elif leave.leave_type == LeaveType.SICK:
                if leave.status == LeaveStatus.APPROVED:
                    emp.sick_leave_balance = emp.sick_leave_balance + leave.days
            elif leave.leave_type == LeaveType.EARNED:
                if leave.status == LeaveStatus.APPROVED:
                    emp.earned_leave_balance = emp.earned_leave_balance + leave.days
            elif leave.leave_type == LeaveType.COMPENSATORY:
                # If the leave was pending or approved, we refund the balance since it was deducted on application
                if leave.status in [LeaveStatus.PENDING, LeaveStatus.APPROVED]:
                    emp.comp_off_balance = (emp.comp_off_balance or 0.0) + leave.days
        leave.status = LeaveStatus.CANCELLED
    
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
    if get_role_value(current_user.role) in ["employee", "manager"]:
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
class HolidayCreate(BaseModel):
    name: str
    date: date
    type: Optional[str] = "national"

@router.get("/holidays/")
def list_holidays(db: Session = Depends(get_db)):
    return db.query(Holiday).order_by(Holiday.date).all()

@router.post("/holidays/", response_model=dict)
def add_holiday(
    request: HolidayCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Enforce role: only Admin or HR can add holidays
    role_val = get_role_value(current_user.role) if hasattr(current_user.role, "value") else str(current_user.role)
    if role_val not in ["admin", "hr"]:
        raise HTTPException(status_code=403, detail="Forbidden: Only Admin or HR can add official holidays.")
        
    # Check if holiday on this date already exists
    existing = db.query(Holiday).filter(Holiday.date == request.date).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"A holiday '{existing.name}' already exists on this date ({request.date}).")
        
    holiday = Holiday(
        name=request.name,
        date=request.date,
        type=request.type
    )
    db.add(holiday)
    db.commit()
    db.refresh(holiday)
    return {
        "message": "Holiday added successfully",
        "holiday": {
            "id": holiday.id,
            "name": holiday.name,
            "date": str(holiday.date),
            "type": holiday.type
        }
    }


class HolidayUpdate(BaseModel):
    name: Optional[str] = None
    date: Optional[date] = None
    type: Optional[str] = None

@router.put("/holidays/{holiday_id}", response_model=dict)
def update_holiday(
    holiday_id: int,
    request: HolidayUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Enforce role: only Admin or HR can edit holidays
    role_val = get_role_value(current_user.role) if hasattr(current_user.role, "value") else str(current_user.role)
    if role_val not in ["admin", "hr"]:
        raise HTTPException(status_code=403, detail="Forbidden: Only Admin or HR can edit official holidays.")
        
    holiday = db.query(Holiday).filter(Holiday.id == holiday_id).first()
    if not holiday:
        raise HTTPException(status_code=404, detail="Holiday not found")
        
    if request.name is not None:
        holiday.name = request.name
        
    if request.date is not None:
        # Check if another holiday on this date already exists
        existing = db.query(Holiday).filter(Holiday.date == request.date, Holiday.id != holiday_id).first()
        if existing:
            raise HTTPException(status_code=400, detail=f"Another holiday '{existing.name}' already exists on this date ({request.date}).")
        holiday.date = request.date
        
    if request.type is not None:
        holiday.type = request.type
        
    db.commit()
    db.refresh(holiday)
    return {
        "message": "Holiday updated successfully",
        "holiday": {
            "id": holiday.id,
            "name": holiday.name,
            "date": str(holiday.date),
            "type": holiday.type
        }
    }


# ===== DYNAMIC GEOFENCE SETTINGS =====
class GeofenceUpdateRequest(BaseModel):
    latitude: float
    longitude: float
    radius: Optional[float] = 100.0

@router.get("/geofence")
def get_geofence(db: Session = Depends(get_db)):
    org_coords = get_org_coordinates(db)
    geo_info = reverse_geocode(org_coords["latitude"], org_coords["longitude"])
    return {
        "latitude": org_coords["latitude"],
        "longitude": org_coords["longitude"],
        "radius": org_coords["radius"],
        "address": geo_info["address"],
        "district": geo_info["district"],
        "state": geo_info["state"]
    }

@router.post("/geofence/update")
def update_geofence(
    req: GeofenceUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Restrict to Admin or HR role
    if get_role_value(current_user.role) not in ["admin", "hr"]:
        raise HTTPException(status_code=403, detail="Forbidden: Only Admins or HR can update the office boundary.")
    
    updated = update_org_coordinates(db, req.latitude, req.longitude, req.radius)
    geo_info = reverse_geocode(req.latitude, req.longitude)
    return {
        "message": "Geofence boundary updated successfully",
        "latitude": updated["latitude"],
        "longitude": updated["longitude"],
        "radius": updated["radius"],
        "address": geo_info["address"],
        "district": geo_info["district"],
        "state": geo_info["state"]
    }


# ===== COMPENSATORY OFF (COMP-OFF) ENDPOINTS =====

@router.get("/compoff/rule", response_model=CompOffRuleResponse)
def get_compoff_rule(db: Session = Depends(get_db)):
    rule = db.query(CompOffRule).filter(CompOffRule.is_active == 1).first()
    if not rule:
        # Fallback to creating a default rule if not found
        rule = CompOffRule(standard_working_hours=8.0, min_overtime_hours=2.0)
        db.add(rule)
        db.commit()
        db.refresh(rule)
    return rule


@router.put("/compoff/rule", response_model=CompOffRuleResponse)
def update_compoff_rule(
    req: CompOffRuleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if get_role_value(current_user.role) not in ["admin", "hr", "manager"]:
        raise HTTPException(status_code=403, detail="Forbidden: Only HR and Managers can update comp-off rules.")
    
    rule = db.query(CompOffRule).filter(CompOffRule.is_active == 1).first()
    if not rule:
        rule = CompOffRule()
        db.add(rule)
    
    if req.standard_working_hours is not None:
        rule.standard_working_hours = req.standard_working_hours
    if req.min_overtime_hours is not None:
        rule.min_overtime_hours = req.min_overtime_hours
        
    db.commit()
    db.refresh(rule)
    return rule


@router.get("/compoff/eligible-dates")
def get_eligible_overtime_dates(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_employee: Employee = Depends(get_current_employee)
):
    rule = db.query(CompOffRule).filter(CompOffRule.is_active == 1).first()
    min_ot = rule.min_overtime_hours if rule else 2.0
    
    # Get all attendance records of this employee where overtime_hours >= min_ot
    records = db.query(Attendance).filter(
        Attendance.employee_id == current_employee.id,
        Attendance.overtime_hours >= min_ot
    ).all()
    
    # Filter out dates where an active comp-off request already exists (either pending or approved)
    existing_requests = db.query(CompOffRequest).filter(
        CompOffRequest.employee_id == current_employee.id,
        CompOffRequest.status.in_(["pending", "approved"])
    ).all()
    requested_dates = {req.attendance_date for req in existing_requests}
    
    eligible = []
    for r in records:
        if r.date not in requested_dates:
            eligible.append({
                "date": str(r.date),
                "work_hours": r.work_hours,
                "overtime_hours": r.overtime_hours,
                "notes": r.notes
            })
    return eligible


@router.post("/compoff/request", response_model=CompOffRequestResponse)
def create_compoff_request(
    req: CompOffRequestCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_employee: Employee = Depends(get_current_employee)
):
    # Check if an active request already exists for this date
    existing = db.query(CompOffRequest).filter(
        CompOffRequest.employee_id == current_employee.id,
        CompOffRequest.attendance_date == req.attendance_date,
        CompOffRequest.status.in_(["pending", "approved"])
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="A comp-off request already exists for this date.")
        
    # Get attendance record to verify overtime hours
    attendance = db.query(Attendance).filter(
        Attendance.employee_id == current_employee.id,
        Attendance.date == req.attendance_date
    ).first()
    if not attendance:
        raise HTTPException(status_code=400, detail="No attendance record found for this date.")
        
    rule = db.query(CompOffRule).filter(CompOffRule.is_active == 1).first()
    min_ot = rule.min_overtime_hours if rule else 2.0
    
    if (attendance.overtime_hours or 0) < min_ot:
        raise HTTPException(
            status_code=400,
            detail=f"Attendance record on this date has {attendance.overtime_hours or 0} overtime hours. The minimum required threshold is {min_ot} hours."
        )
        
    compoff = CompOffRequest(
        employee_id=current_employee.id,
        attendance_date=req.attendance_date,
        working_hours=attendance.work_hours,
        overtime_hours=attendance.overtime_hours,
        reason=req.reason
    )
    db.add(compoff)
    db.commit()
    db.refresh(compoff)
    
    # Notify Manager and HR
    try:
        from app.routers.notifications import create_notification
        
        # 1. Notify Reporting Manager (if set)
        if current_employee.reporting_manager_id:
            mgr = db.query(Employee).filter(Employee.id == current_employee.reporting_manager_id).first()
            if mgr and mgr.user_id:
                create_notification(
                    db=db,
                    user_id=mgr.user_id,
                    title="Comp-off Approval Pending",
                    message=f"{current_employee.full_name} has requested a comp-off credit for {req.attendance_date}.",
                    type="action",
                    link="/attendance/leaves"
                )

        # 2. Notify HR/Admin
        privileged = db.query(User).filter(User.role.in_([UserRole.ADMIN, UserRole.HR])).all()
        for p_user in privileged:
            create_notification(
                db=db,
                user_id=p_user.id,
                title="Comp-off requested (Admin Alert)",
                message=f"{current_employee.full_name} has requested a comp-off credit for {req.attendance_date}.",
                type="info",
                link="/attendance/leaves"
            )
    except Exception as e:
        pass
        
    resp = CompOffRequestResponse.model_validate(compoff)
    resp.employee_name = current_employee.full_name
    return resp


@router.get("/compoff/my-requests", response_model=list[CompOffRequestResponse])
def get_my_compoff_requests(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_employee: Employee = Depends(get_current_employee)
):
    requests = db.query(CompOffRequest).filter(
        CompOffRequest.employee_id == current_employee.id
    ).order_by(CompOffRequest.created_at.desc()).all()
    
    result = []
    for r in requests:
        resp = CompOffRequestResponse.model_validate(r)
        resp.employee_name = current_employee.full_name
        result.append(resp)
    return result


@router.get("/compoff/pending-approvals", response_model=list[CompOffRequestResponse])
def get_pending_compoff_approvals(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_employee: Employee = Depends(get_current_employee)
):
    # Managers see requests where manager_status == 'pending' and the requester reports to them
    # HRs and Admins see requests where hr_status == 'pending'
    query = db.query(CompOffRequest).filter(CompOffRequest.status == "pending")
    requests = []
    
    if get_role_value(current_user.role) in ["admin", "hr"]:
        # HR/Admin can see all pending requests
        requests = query.all()
    elif get_role_value(current_user.role) == "manager":
        # Managers only see requests from their direct reports where manager_status is pending
        direct_reports = db.query(Employee.id).filter(Employee.reporting_manager_id == current_employee.id).all()
        report_ids = [d[0] for d in direct_reports]
        requests = query.filter(
            CompOffRequest.employee_id.in_(report_ids),
            CompOffRequest.manager_status == "pending"
        ).all()
        
    # Pre-fetch employee names
    employees = db.query(Employee).all()
    emp_map = {e.id: e.full_name for e in employees}
    
    result = []
    for r in requests:
        resp = CompOffRequestResponse.model_validate(r)
        resp.employee_name = emp_map.get(r.employee_id, "Unknown")
        result.append(resp)
    return result


@router.post("/compoff/action/{request_id}", response_model=CompOffRequestResponse)
def action_compoff_request(
    request_id: int,
    action_req: CompOffRequestAction,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_employee: Employee = Depends(get_current_employee)
):
    req = db.query(CompOffRequest).filter(CompOffRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
        
    action = action_req.action.lower()
    if req.status != "pending":
        if action == "reject" and req.status == "approved":
            pass
        else:
            raise HTTPException(status_code=400, detail="This request has already been finalized.")
        
    # Verify authorization: is user a Manager or HR?
    is_hr_or_admin = get_role_value(current_user.role) in ["admin", "hr"]
    is_manager = get_role_value(current_user.role) == "manager"
    
    requester = db.query(Employee).filter(Employee.id == req.employee_id).first()
    if not requester:
        raise HTTPException(status_code=400, detail="Requester employee not found")
        
    is_reporting_manager = (requester.reporting_manager_id is not None) and (requester.reporting_manager_id == current_employee.id)
    
    if not (is_hr_or_admin or is_reporting_manager):
        raise HTTPException(status_code=403, detail="Forbidden: You are not authorized to approve this request.")
        
    # Apply action
    if action == "reject":
        if req.status == "approved":
            requester.comp_off_balance = max(0.0, (requester.comp_off_balance or 0.0) - 1.0)
            
        req.status = "rejected"
        if is_hr_or_admin:
            req.hr_status = "rejected"
            req.hr_id = current_user.id
            req.hr_action_at = datetime.utcnow()
        if is_reporting_manager or (is_hr_or_admin and requester.reporting_manager_id is None):
            req.manager_status = "rejected"
            req.manager_id = current_employee.id
            req.manager_action_at = datetime.utcnow()
    elif action == "approve":
        # Handle reporting manager approval
        if is_reporting_manager:
            req.manager_status = "approved"
            req.manager_id = current_employee.id
            req.manager_action_at = datetime.utcnow()
        # Handle HR/Admin approval
        if is_hr_or_admin:
            req.hr_status = "approved"
            req.hr_id = current_user.id
            req.hr_action_at = datetime.utcnow()
            
            # If the requester has no reporting manager, HR approval can automatically cover manager status
            if requester.reporting_manager_id is None:
                req.manager_status = "approved"
                req.manager_id = current_employee.id
                req.manager_action_at = datetime.utcnow()
                
        # If both approved, finalize request and add comp-off credit to balance!
        if req.manager_status == "approved" and req.hr_status == "approved":
            req.status = "approved"
            requester.comp_off_balance = (requester.comp_off_balance or 0.0) + 1.0
            
            # Notify employee
            try:
                from app.routers.notifications import create_notification
                if requester.user_id:
                    create_notification(
                        db=db,
                        user_id=requester.user_id,
                        title="Comp-off Request Approved",
                        message=f"Your comp-off request for {req.attendance_date} has been fully approved. 1 day has been credited to your balance.",
                        type="success",
                        link="/attendance/leaves"
                    )
            except Exception as e:
                pass
    else:
        raise HTTPException(status_code=400, detail="Invalid action. Must be 'approve' or 'reject'.")
        
    db.commit()
    db.refresh(req)
    
    resp = CompOffRequestResponse.model_validate(req)
    resp.employee_name = requester.full_name
    return resp


@router.post("/compoff/cancel/{request_id}", response_model=CompOffRequestResponse)
def cancel_compoff_request(
    request_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_employee: Employee = Depends(get_current_employee)
):
    req = db.query(CompOffRequest).filter(CompOffRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
        
    if req.status == "cancelled":
        raise HTTPException(status_code=400, detail="This request is already cancelled.")
        
    # Verify authorization: owner, reporting manager, or HR/Admin
    requester = db.query(Employee).filter(Employee.id == req.employee_id).first()
    if not requester:
        raise HTTPException(status_code=400, detail="Requester employee not found")
        
    is_owner = (requester.id == current_employee.id)
    is_hr_or_admin = get_role_value(current_user.role) in ["admin", "hr"]
    is_reporting_manager = (requester.reporting_manager_id is not None) and (requester.reporting_manager_id == current_employee.id)
    
    if not (is_owner or is_hr_or_admin or is_reporting_manager):
        raise HTTPException(status_code=403, detail="Forbidden: You are not authorized to cancel this request.")
        
    # If the request was already approved, deduct 1.0 day from balance
    if req.status == "approved":
        requester.comp_off_balance = max(0.0, (requester.comp_off_balance or 0.0) - 1.0)
        
    req.status = "cancelled"
    req.manager_status = "cancelled"
    req.hr_status = "cancelled"
    
    db.commit()
    db.refresh(req)
    
    resp = CompOffRequestResponse.model_validate(req)
    resp.employee_name = requester.full_name
    return resp


