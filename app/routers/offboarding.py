"""Offboarding router — resignations, exit interviews, document generation, final settlement."""
import os
from app.utils.timezone import get_ist_date
from datetime import date, timedelta
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.offboarding import Resignation, ResignationStatus
from app.models.employee import Employee, Department, EmploymentStatus
from app.schemas.schemas import ResignationCreate, ResignationUpdate, ResignationResponse
from app.services.pdf_service import generate_experience_letter_pdf, generate_relieving_letter_pdf
from app.config import settings
from app.services.auth_service import get_current_user
from app.models.user import User

router = APIRouter(prefix="/api/offboarding", tags=["Offboarding"])


@router.get("/resignations", response_model=list[ResignationResponse])
def list_resignations(
    current_user: "User" = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Resolve current employee record
    emp = db.query(Employee).filter(Employee.user_id == current_user.id).first()
    if not emp:
        emp = db.query(Employee).filter(Employee.email == current_user.email).first()

    # Isolate queries based on user role
    if current_user.role.value in ["admin", "hr"]:
        resignations = db.query(Resignation).order_by(Resignation.created_at.desc()).all()
    else:
        if emp:
            resignations = db.query(Resignation).filter(Resignation.employee_id == emp.id).order_by(Resignation.created_at.desc()).all()
        else:
            resignations = []

    result = []
    for r in resignations:
        emp_rec = db.query(Employee).filter(Employee.id == r.employee_id).first()
        dept = db.query(Department).filter(Department.id == emp_rec.department_id).first() if emp_rec else None
        resp = ResignationResponse.model_validate(r)
        resp.employee_name = emp_rec.full_name if emp_rec else ""
        resp.employee_code = emp_rec.employee_id if emp_rec else ""
        resp.department = dept.name if dept else ""
        resp.designation = emp_rec.designation if emp_rec else ""
        result.append(resp)
    return result


@router.post("/resignations", response_model=ResignationResponse)
def submit_resignation(request: ResignationCreate, db: Session = Depends(get_db)):
    emp = db.query(Employee).filter(Employee.id == request.employee_id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    # Calculate last working day
    lwd = get_ist_date() + timedelta(days=request.notice_period_days)
    
    resignation = Resignation(
        **request.model_dump(),
        last_working_day=lwd,
    )
    
    # Update employee status
    emp.employment_status = EmploymentStatus.ON_NOTICE
    
    db.add(resignation)
    db.commit()
    db.refresh(resignation)

    # Trigger Notifications & Email Alerts
    try:
        from app.services.email_service import send_resignation_notification
        from app.routers.notifications import create_notification
        from app.models.user import UserRole
        
        # 1. Notify reporting manager
        if emp.reporting_manager_id:
            mgr = db.query(Employee).filter(Employee.id == emp.reporting_manager_id).first()
            if mgr:
                # In-app notification for manager
                if mgr.user_id:
                    create_notification(
                        db=db,
                        user_id=mgr.user_id,
                        title="Resignation Submitted",
                        message=f"{emp.full_name} has submitted their resignation proposal.",
                        type="action",
                        link="/offboarding"
                    )
                # Email alert for manager
                if mgr.email:
                    send_resignation_notification(
                        to_email=mgr.email,
                        employee_name=emp.full_name,
                        notice_days=request.notice_period_days,
                        lwd=lwd.strftime("%Y-%m-%d"),
                        reason=request.reason
                    )
                    
        # 2. Notify all Admins and HR accounts
        admins_hrs = db.query(User).filter(User.role.in_([UserRole.ADMIN, UserRole.HR])).all()
        for user_acc in admins_hrs:
            # Prevent double notification if manager is also admin/hr
            if emp.reporting_manager_id:
                mgr = db.query(Employee).filter(Employee.id == emp.reporting_manager_id).first()
                if mgr and mgr.user_id == user_acc.id:
                    continue
            
            # In-app notification
            create_notification(
                db=db,
                user_id=user_acc.id,
                title="Resignation Alert",
                message=f"{emp.full_name} has submitted their resignation.",
                type="action",
                link="/offboarding"
            )
            # Email alert
            if user_acc.email:
                send_resignation_notification(
                    to_email=user_acc.email,
                    employee_name=emp.full_name,
                    notice_days=request.notice_period_days,
                    lwd=lwd.strftime("%Y-%m-%d"),
                    reason=request.reason
                )
    except Exception as e:
        from app.logger import logger
        logger.error(f"Error in resignation offboarding notification triggers: {e}")
    
    dept = db.query(Department).filter(Department.id == emp.department_id).first()
    resp = ResignationResponse.model_validate(resignation)
    resp.employee_name = emp.full_name
    resp.employee_code = emp.employee_id
    resp.department = dept.name if dept else ""
    resp.designation = emp.designation or ""
    return resp


@router.put("/resignations/{resignation_id}", response_model=ResignationResponse)
def update_resignation(resignation_id: int, request: ResignationUpdate, db: Session = Depends(get_db)):
    resignation = db.query(Resignation).filter(Resignation.id == resignation_id).first()
    if not resignation:
        raise HTTPException(status_code=404, detail="Resignation not found")
    
    update_data = request.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        if key == "status":
            value = ResignationStatus(value)
        setattr(resignation, key, value)
    
    # Handle exit interview completion
    if request.exit_feedback or request.exit_rating:
        resignation.exit_interview_done = True
    
    db.commit()
    db.refresh(resignation)
    
    emp = db.query(Employee).filter(Employee.id == resignation.employee_id).first()
    dept = db.query(Department).filter(Department.id == emp.department_id).first() if emp else None
    resp = ResignationResponse.model_validate(resignation)
    resp.employee_name = emp.full_name if emp else ""
    resp.employee_code = emp.employee_id if emp else ""
    resp.department = dept.name if dept else ""
    resp.designation = emp.designation if emp else ""
    return resp


@router.post("/resignations/{resignation_id}/calculate-settlement")
def calculate_settlement(resignation_id: int, db: Session = Depends(get_db)):
    resignation = db.query(Resignation).filter(Resignation.id == resignation_id).first()
    if not resignation:
        raise HTTPException(status_code=404, detail="Resignation not found")
    
    emp = db.query(Employee).filter(Employee.id == resignation.employee_id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    # Calculate final settlement
    monthly_salary = emp.basic_salary + emp.hra + emp.da + emp.special_allowance
    daily_salary = monthly_salary / 30
    
    # Leave encashment (earned leaves)
    leave_encashment = round(emp.earned_leave_balance * daily_salary, 2)
    
    # Gratuity (if > 5 years: 15 days salary per year)
    from datetime import date as d
    years_of_service = (d.today() - emp.joining_date).days / 365
    gratuity = round((15 * emp.basic_salary / 26) * years_of_service, 2) if years_of_service >= 5 else 0
    
    # Pending salary (remaining days in current month)
    pending_days = max(0, (d.today().day / 30) * 30 - d.today().day)
    pending_salary = round(daily_salary * 10, 2)  # Approximate
    
    resignation.pending_salary = pending_salary
    resignation.leave_encashment = leave_encashment
    resignation.gratuity = gratuity
    resignation.total_settlement = round(pending_salary + leave_encashment + gratuity, 2)
    
    db.commit()
    
    return {
        "pending_salary": pending_salary,
        "leave_encashment": leave_encashment,
        "gratuity": gratuity,
        "total_settlement": resignation.total_settlement,
    }


@router.post("/resignations/{resignation_id}/generate-experience-letter")
def generate_experience_letter(resignation_id: int, db: Session = Depends(get_db)):
    resignation = db.query(Resignation).filter(Resignation.id == resignation_id).first()
    if not resignation:
        raise HTTPException(status_code=404, detail="Resignation not found")
    
    emp = db.query(Employee).filter(Employee.id == resignation.employee_id).first()
    dept = db.query(Department).filter(Department.id == emp.department_id).first() if emp else None
    
    employee_data = {
        "full_name": emp.full_name,
        "employee_id": emp.employee_id,
        "designation": emp.designation,
        "department": dept.name if dept else "",
        "joining_date": emp.joining_date.strftime("%B %d, %Y"),
        "last_working_day": resignation.last_working_day.strftime("%B %d, %Y") if resignation.last_working_day else "",
    }
    
    output_path = os.path.join(settings.GENERATED_DIR, f"experience_letter_{emp.employee_id}.pdf")
    generate_experience_letter_pdf(employee_data, output_path)
    
    resignation.experience_letter_generated = True
    db.commit()
    
    return FileResponse(output_path, media_type="application/pdf", filename=f"Experience_Letter_{emp.employee_id}.pdf")


@router.post("/resignations/{resignation_id}/generate-relieving-letter")
def generate_relieving_letter(resignation_id: int, db: Session = Depends(get_db)):
    resignation = db.query(Resignation).filter(Resignation.id == resignation_id).first()
    if not resignation:
        raise HTTPException(status_code=404, detail="Resignation not found")
    
    emp = db.query(Employee).filter(Employee.id == resignation.employee_id).first()
    
    employee_data = {
        "full_name": emp.full_name,
        "employee_id": emp.employee_id,
        "designation": emp.designation,
        "last_working_day": resignation.last_working_day.strftime("%B %d, %Y") if resignation.last_working_day else "",
    }
    
    output_path = os.path.join(settings.GENERATED_DIR, f"relieving_letter_{emp.employee_id}.pdf")
    generate_relieving_letter_pdf(employee_data, output_path)
    
    resignation.relieving_letter_generated = True
    db.commit()
    
    return FileResponse(output_path, media_type="application/pdf", filename=f"Relieving_Letter_{emp.employee_id}.pdf")


@router.post("/resignations/{resignation_id}/complete")
def complete_offboarding(resignation_id: int, db: Session = Depends(get_db)):
    resignation = db.query(Resignation).filter(Resignation.id == resignation_id).first()
    if not resignation:
        raise HTTPException(status_code=404, detail="Resignation not found")
    
    resignation.status = ResignationStatus.COMPLETED
    
    # Update employee status
    emp = db.query(Employee).filter(Employee.id == resignation.employee_id).first()
    if emp:
        emp.employment_status = EmploymentStatus.RESIGNED
        emp.is_active = False
        
        # Suspend associated login User account
        from app.models.user import User
        user = db.query(User).filter((User.id == emp.user_id) | (User.email == emp.email)).first()
        if user:
            user.is_active = False
    
    db.commit()

    # Trigger offboarding complete email and notification
    if emp:
        try:
            from app.services.email_service import send_offboarding_completion_email
            from app.routers.notifications import create_notification
            
            # Send in-app notification to employee
            if emp.user_id:
                create_notification(
                    db=db,
                    user_id=emp.user_id,
                    title="Offboarding Complete",
                    message="Your offboarding process has been completed and final settlement cleared. Thank you for your service!",
                    type="success"
                )
            
            # Send completion email to employee
            lwd_str = resignation.last_working_day.strftime("%B %d, %Y") if resignation.last_working_day else "N/A"
            send_offboarding_completion_email(
                to_email=emp.email,
                name=emp.full_name,
                lwd=lwd_str,
                total_settlement=resignation.total_settlement or 0.0,
                exit_interview_done=bool(resignation.exit_interview_done)
            )
        except Exception as e:
            from app.logger import logger
            logger.error(f"Error in offboarding completion notification: {e}")
            
    return {"message": "Offboarding completed successfully"}
