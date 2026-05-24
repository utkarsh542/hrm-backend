"""AI Copilot router — chat, JD generator, attrition risk, review writer."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from app.database import get_db
from app.models.employee import Employee, EmploymentStatus
from app.models.attendance import LeaveRequest, LeaveStatus
from app.models.performance import PerformanceReview
from app.models.attendance import Attendance
from app.services.ai_service import (
    hr_copilot_chat,
    generate_job_description,
    calculate_attrition_risk,
    generate_performance_review,
)

router = APIRouter(prefix="/api/ai", tags=["AI"])


# ─── Schemas ───────────────────────────────────────────────────────────────
class CopilotRequest(BaseModel):
    message: str

class JDRequest(BaseModel):
    title: str
    department: str
    experience_min: int = 2
    experience_max: int = 5
    skills: str = ""

class ReviewWriterRequest(BaseModel):
    employee_id: int
    bullet_points: str
    technical_rating: Optional[float] = None
    communication_rating: Optional[float] = None
    leadership_rating: Optional[float] = None


# ─── HR Copilot Chat ────────────────────────────────────────────────────────
@router.post("/chat")
def copilot_chat(request: CopilotRequest, db: Session = Depends(get_db)):
    """Natural language HR assistant with live DB context."""
    # Build a compact context snapshot for the LLM
    employees = db.query(Employee).filter(Employee.is_active == True).all()
    pending_leaves = db.query(LeaveRequest).filter(LeaveRequest.status == LeaveStatus.PENDING).all()
    active_count = db.query(Employee).filter(Employee.employment_status == EmploymentStatus.ACTIVE).count()
    on_notice = db.query(Employee).filter(Employee.employment_status == EmploymentStatus.ON_NOTICE).all()

    context = {
        "total_employees": len(employees),
        "active_employees": active_count,
        "employees_on_notice": [{"name": e.full_name, "designation": e.designation} for e in on_notice],
        "pending_leave_requests": len(pending_leaves),
        "pending_leaves_detail": [
            {
                "employee": db.query(Employee).filter(Employee.id == l.employee_id).first().full_name
                if db.query(Employee).filter(Employee.id == l.employee_id).first() else "Unknown",
                "type": l.leave_type.value,
                "days": l.days,
                "from": str(l.start_date),
            }
            for l in pending_leaves[:10]
        ],
        "employee_list": [
            {
                "name": e.full_name,
                "designation": e.designation,
                "department": e.department_id,
                "ctc": e.ctc,
                "casual_leave_balance": e.casual_leave_balance,
                "sick_leave_balance": e.sick_leave_balance,
                "earned_leave_balance": e.earned_leave_balance,
                "status": e.employment_status.value,
            }
            for e in employees[:20]
        ],
    }

    answer = hr_copilot_chat(request.message, context)
    return {"answer": answer, "ai_enabled": bool(answer and "GROQ_API_KEY" not in answer)}


# ─── Job Description Generator ─────────────────────────────────────────────
@router.post("/generate-jd")
def generate_jd(request: JDRequest):
    """Generate a full job description using AI."""
    result = generate_job_description(
        title=request.title,
        department=request.department,
        experience_min=request.experience_min,
        experience_max=request.experience_max,
        skills=request.skills,
    )
    return result


# ─── Attrition Risk Dashboard ───────────────────────────────────────────────
@router.get("/attrition-risk")
def get_attrition_risk(db: Session = Depends(get_db)):
    """Calculate attrition risk for all active employees."""
    employees = db.query(Employee).filter(
        Employee.employment_status == EmploymentStatus.ACTIVE,
        Employee.is_active == True,
    ).all()

    results = []
    for emp in employees:
        reviews = db.query(PerformanceReview).filter(
            PerformanceReview.employee_id == emp.id
        ).order_by(PerformanceReview.created_at.desc()).limit(3).all()

        leaves = db.query(LeaveRequest).filter(
            LeaveRequest.employee_id == emp.id
        ).all()

        attendance_count = db.query(Attendance).filter(
            Attendance.employee_id == emp.id
        ).count()

        risk = calculate_attrition_risk(emp, reviews, leaves, attendance_count)

        from app.models.employee import Department
        dept = db.query(Department).filter(Department.id == emp.department_id).first()

        results.append({
            "employee_id": emp.id,
            "employee_code": emp.employee_id,
            "full_name": emp.full_name,
            "designation": emp.designation,
            "department": dept.name if dept else "—",
            "tenure_months": ((__import__('datetime').date.today() - emp.joining_date).days // 30) if emp.joining_date else 0,
            **risk,
        })

    results.sort(key=lambda x: x["risk_score"], reverse=True)
    return results


# ─── AI Performance Review Writer ──────────────────────────────────────────
@router.post("/write-review")
def write_review(request: ReviewWriterRequest, db: Session = Depends(get_db)):
    """AI expands manager bullet points into a full professional review."""
    emp = db.query(Employee).filter(Employee.id == request.employee_id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")

    ratings = {
        "technical": request.technical_rating,
        "communication": request.communication_rating,
        "leadership": request.leadership_rating,
    }

    result = generate_performance_review(
        employee_name=emp.full_name,
        designation=emp.designation or "Employee",
        bullet_points=request.bullet_points,
        ratings=ratings,
    )
    return result
