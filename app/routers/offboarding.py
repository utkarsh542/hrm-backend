"""Offboarding router — resignations, exit interviews, document generation, final settlement."""
import os
from datetime import date, timedelta
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.offboarding import Resignation, ResignationStatus, Document
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
    lwd = date.today() + timedelta(days=request.notice_period_days)
    
    resignation = Resignation(
        **request.model_dump(),
        last_working_day=lwd,
    )
    
    # Update employee status
    emp.employment_status = EmploymentStatus.ON_NOTICE
    
    db.add(resignation)
    db.commit()
    db.refresh(resignation)
    
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
    return {"message": "Offboarding completed successfully"}
