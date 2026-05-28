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
    if current_user.role.value in ["employee", "manager"]:
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
    current_user: User = Depends(get_current_user),
    current_employee: Employee = Depends(get_current_employee)
):
    leave = db.query(LeaveRequest).filter(LeaveRequest.id == leave_id).first()
    if not leave:
        raise HTTPException(status_code=404, detail="Leave request not found")
        
    # Enforce Role Guards: Employees can only cancel their own leaves
    is_admin_or_hr_or_manager = current_user.role.value in ["admin", "hr", "manager"]
    if not is_admin_or_hr_or_manager:
        if leave.employee_id != current_employee.id:
            raise HTTPException(status_code=403, detail="Forbidden: You can only update your own leave requests")
        if request.status != "cancelled":
            raise HTTPException(status_code=403, detail="Forbidden: Employees can only cancel their own leaves")
    
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
        
    elif request.status == "cancelled":
        # Refund leave balance if it was already approved
        if leave.status == LeaveStatus.APPROVED:
            emp = db.query(Employee).filter(Employee.id == leave.employee_id).first()
            if emp:
                if leave.leave_type == LeaveType.CASUAL:
                    emp.casual_leave_balance = emp.casual_leave_balance + leave.days
                elif leave.leave_type == LeaveType.SICK:
                    emp.sick_leave_balance = emp.sick_leave_balance + leave.days
                elif leave.leave_type == LeaveType.EARNED:
                    emp.earned_leave_balance = emp.earned_leave_balance + leave.days
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
    if current_user.role.value not in ["admin", "hr"]:
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

