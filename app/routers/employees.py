"""Employees router — CRUD, directory, onboarding."""
from datetime import date
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.models.employee import Employee, Department, EmploymentStatus, EmploymentType, OnboardingStatus
from app.schemas.schemas import EmployeeCreate, EmployeeUpdate, EmployeeResponse
from app.services.payroll_service import calculate_salary_breakup

router = APIRouter(prefix="/api/employees", tags=["Employees"])


def _get_next_employee_id(db: Session) -> str:
    last = db.query(Employee).order_by(Employee.id.desc()).first()
    num = (last.id + 1) if last else 1
    return f"EMP{num:04d}"


@router.get("/", response_model=list[EmployeeResponse])
def list_employees(
    department_id: Optional[int] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(Employee)
    if department_id:
        query = query.filter(Employee.department_id == department_id)
    if status:
        query = query.filter(Employee.employment_status == EmploymentStatus(status))
    if search:
        query = query.filter(
            (Employee.full_name.ilike(f"%{search}%")) |
            (Employee.email.ilike(f"%{search}%")) |
            (Employee.employee_id.ilike(f"%{search}%"))
        )
    
    employees = query.order_by(Employee.full_name).all()
    result = []
    for emp in employees:
        dept = db.query(Department).filter(Department.id == emp.department_id).first()
        resp = EmployeeResponse.model_validate(emp)
        resp.department_name = dept.name if dept else "Unassigned"
        result.append(resp)
    return result


@router.get("/org-chart")
def get_org_chart(db: Session = Depends(get_db)):
    """Return all employees with manager relationships for org chart rendering."""
    employees = db.query(Employee).filter(Employee.is_active == True).all()
    result = []
    for emp in employees:
        dept = db.query(Department).filter(Department.id == emp.department_id).first()
        result.append({
            "id": emp.id,
            "employee_id": emp.employee_id,
            "full_name": emp.full_name,
            "designation": emp.designation,
            "department_name": dept.name if dept else "Unassigned",
            "reporting_manager_id": emp.reporting_manager_id,
            "employment_status": emp.employment_status.value,
        })
    return result


@router.get("/{employee_id}", response_model=EmployeeResponse)
def get_employee(employee_id: int, db: Session = Depends(get_db)):
    emp = db.query(Employee).filter(Employee.id == employee_id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    dept = db.query(Department).filter(Department.id == emp.department_id).first()
    resp = EmployeeResponse.model_validate(emp)
    resp.department_name = dept.name if dept else "Unassigned"
    return resp


@router.post("/", response_model=EmployeeResponse)
def create_employee(request: EmployeeCreate, db: Session = Depends(get_db)):
    emp_data = request.model_dump()
    
    # Generate employee ID
    emp_data["employee_id"] = _get_next_employee_id(db)
    
    # Calculate salary breakup from CTC
    if emp_data.get("ctc", 0) > 0:
        breakup = calculate_salary_breakup(emp_data["ctc"])
        emp_data["basic_salary"] = breakup["basic"]
        emp_data["hra"] = breakup["hra"]
        emp_data["da"] = breakup["da"]
        emp_data["special_allowance"] = breakup["special_allowance"]
        emp_data["pf_contribution"] = breakup["pf_employee"]
    
    # Auto-provision User account
    from app.models.user import User, UserRole
    from app.services.auth_service import hash_password

    existing_user = db.query(User).filter(User.email == emp_data["email"]).first()
    if not existing_user:
        # Determine role from designation
        designation = (emp_data.get("designation") or "").lower()
        role = UserRole.EMPLOYEE
        if "admin" in designation:
            role = UserRole.ADMIN
        elif any(k in designation for k in ["hr", "human resources", "talent"]):
            role = UserRole.HR
        elif any(k in designation for k in ["manager", "lead", "director", "vp", "head"]):
            role = UserRole.MANAGER
            
        new_user = User(
            email=emp_data["email"],
            hashed_password=hash_password("Welcome@123"),
            full_name=emp_data["full_name"],
            role=role,
            is_active=True
        )
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        emp_data["user_id"] = new_user.id
    else:
        emp_data["user_id"] = existing_user.id

    employee = Employee(**emp_data)
    db.add(employee)
    db.commit()
    db.refresh(employee)
    
    dept = db.query(Department).filter(Department.id == employee.department_id).first()
    resp = EmployeeResponse.model_validate(employee)
    resp.department_name = dept.name if dept else "Unassigned"
    return resp


@router.put("/{employee_id}", response_model=EmployeeResponse)
def update_employee(employee_id: int, request: EmployeeUpdate, db: Session = Depends(get_db)):
    emp = db.query(Employee).filter(Employee.id == employee_id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    update_data = request.model_dump(exclude_unset=True)
    
    # Recalculate salary if CTC changed
    if "ctc" in update_data and update_data["ctc"]:
        breakup = calculate_salary_breakup(update_data["ctc"])
        update_data["basic_salary"] = breakup["basic"]
        update_data["hra"] = breakup["hra"]
        update_data["da"] = breakup["da"]
        update_data["special_allowance"] = breakup["special_allowance"]
        update_data["pf_contribution"] = breakup["pf_employee"]
    
    for key, value in update_data.items():
        if key == "employment_status":
            value = EmploymentStatus(value)
            # If terminated or resigned, automatically deactivate employee and user login account
            if value in [EmploymentStatus.TERMINATED, EmploymentStatus.RESIGNED]:
                emp.is_active = False
                from app.models.user import User
                user = db.query(User).filter((User.id == emp.user_id) | (User.email == emp.email)).first()
                if user:
                    user.is_active = False
            else:
                emp.is_active = True
                from app.models.user import User
                user = db.query(User).filter((User.id == emp.user_id) | (User.email == emp.email)).first()
                if user:
                    user.is_active = True
        elif key == "employment_type":
            value = EmploymentType(value)
        setattr(emp, key, value)
    
    db.commit()
    db.refresh(emp)
    
    dept = db.query(Department).filter(Department.id == emp.department_id).first()
    resp = EmployeeResponse.model_validate(emp)
    resp.department_name = dept.name if dept else "Unassigned"
    return resp


@router.put("/{employee_id}/onboarding")
def update_onboarding(employee_id: int, status: str, db: Session = Depends(get_db)):
    emp = db.query(Employee).filter(Employee.id == employee_id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    emp.onboarding_status = OnboardingStatus(status)
    db.commit()
    return {"message": "Onboarding status updated"}


# ===== DEPARTMENTS =====
@router.get("/departments/all")
def list_departments(db: Session = Depends(get_db)):
    departments = db.query(Department).all()
    result = []
    for dept in departments:
        count = db.query(Employee).filter(Employee.department_id == dept.id, Employee.is_active == True).count()
        result.append({"id": dept.id, "name": dept.name, "description": dept.description, "employee_count": count})
    return result


@router.post("/departments/")
def create_department(name: str, description: str = "", db: Session = Depends(get_db)):
    dept = Department(name=name, description=description)
    db.add(dept)
    db.commit()
    db.refresh(dept)
    return {"id": dept.id, "name": dept.name, "description": dept.description}





@router.get("/{employee_id}/timeline")
def get_employee_timeline(employee_id: int, db: Session = Depends(get_db)):
    """Return key events in an employee's lifecycle."""
    from app.models.attendance import LeaveRequest, LeaveStatus
    from app.models.performance import PerformanceReview
    from app.models.payroll import Payslip

    emp = db.query(Employee).filter(Employee.id == employee_id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")

    events = []

    # Joining
    events.append({"date": str(emp.joining_date), "type": "joining", "title": "Joined the company", "detail": emp.designation})

    # Approved leaves
    leaves = db.query(LeaveRequest).filter(
        LeaveRequest.employee_id == employee_id,
        LeaveRequest.status == LeaveStatus.APPROVED
    ).order_by(LeaveRequest.start_date.desc()).limit(5).all()
    for l in leaves:
        events.append({"date": str(l.start_date), "type": "leave", "title": f"{l.leave_type.value.title()} Leave Approved", "detail": f"{l.days} day(s)"})

    # Performance reviews
    reviews = db.query(PerformanceReview).filter(
        PerformanceReview.employee_id == employee_id
    ).order_by(PerformanceReview.created_at.desc()).limit(3).all()
    for r in reviews:
        events.append({"date": str(r.created_at.date()), "type": "review", "title": f"{r.cycle.value.title()} Review — {r.status}", "detail": f"Rating: {r.overall_rating or 'Pending'}"})

    events.sort(key=lambda x: x["date"], reverse=True)
    return events
