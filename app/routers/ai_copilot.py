"""AI Copilot router — chat, JD generator, attrition risk, review writer."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from app.database import get_db
from app.models.user import User, UserRole
from app.models.employee import Employee, EmploymentStatus
from app.models.attendance import LeaveRequest, LeaveStatus
from app.models.performance import PerformanceReview
from app.models.attendance import Attendance
from app.services.auth_service import get_current_user, get_current_employee
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
def copilot_chat(
    request: CopilotRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_employee: Employee = Depends(get_current_employee)
):
    """Natural language HR assistant with live DB context and secure RAG document querying."""
    from app.services.ai_service import search_documents_rag
    
    # 1. Retrieve RAG context from uploaded corporate/employee files (strictly isolated by role!)
    # Standard roles are restricted to searching only their own private documents or company public policy files
    rag_context = search_documents_rag(
        query=request.message,
        db=db,
        employee_id=current_employee.id if current_user.role.value in ["employee", "manager"] else None
    )

    # 2. Build a compact database context snapshot for the LLM
    employees = db.query(Employee).all()
    from app.models.employee import Department
    dept_map = {d.id: d.name for d in db.query(Department).all()}
    mgr_map = {e.id: e.full_name for e in employees}
    
    pending_leaves = db.query(LeaveRequest).filter(LeaveRequest.status == LeaveStatus.PENDING).all()
    active_count = db.query(Employee).filter(
        Employee.employment_status == EmploymentStatus.ACTIVE,
        Employee.is_active == True
    ).count()
    on_notice = db.query(Employee).filter(
        Employee.employment_status == EmploymentStatus.ON_NOTICE,
        Employee.is_active == True
    ).all()
    
    # Personal context for the logged-in user
    personal_leaves = db.query(LeaveRequest).filter(
        LeaveRequest.employee_id == current_employee.id
    ).order_by(LeaveRequest.created_at.desc()).limit(10).all()
    
    # 3. Retrieve today's attendance logs and personal attendance history
    from datetime import date, timedelta
    today = date.today()
    today_attendance = db.query(Attendance).filter(Attendance.date == today).all()
    today_checkins = []
    for att in today_attendance:
        emp = db.query(Employee).filter(Employee.id == att.employee_id).first()
        emp_name = emp.full_name if emp else f"ID {att.employee_id}"
        today_checkins.append({
            "employee_name": emp_name,
            "status": att.status.value if hasattr(att.status, "value") else str(att.status),
            "check_in": att.check_in.strftime('%I:%M %p') if att.check_in else None,
            "check_out": att.check_out.strftime('%I:%M %p') if att.check_out else None,
            "work_hours": att.work_hours,
        })
        
    personal_attendance = db.query(Attendance).filter(
        Attendance.employee_id == current_employee.id
    ).order_by(Attendance.date.desc()).limit(10).all()

    # 4. Dialect-independent python grouping for 3 months (90 days) historical attendance data
    three_months_ago = today - timedelta(days=90)
    history_records = db.query(Attendance.date, Attendance.status, Attendance.employee_id)\
        .filter(Attendance.date >= three_months_ago).all()
        
    unique_emps = set()
    monthly_counts = {}
    for r_date, r_status, r_emp_id in history_records:
        if r_date:
            unique_emps.add(r_emp_id)
            year_month = (r_date.year, r_date.month)
            status_str = r_status.value if hasattr(r_status, "value") else str(r_status)
            key = (year_month, status_str)
            monthly_counts[key] = monthly_counts.get(key, 0) + 1
            
    historical_summary = [
        {
            "year": k[0][0],
            "month": k[0][1],
            "status": k[1],
            "count": v
        }
        for k, v in monthly_counts.items()
    ]
    unique_emp_count = len(unique_emps)

    # 5. Build employee_list securely and dynamically based on caller role
    employee_list = []
    user_role = current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)
    
    for e in employees:
        is_self = (e.id == current_employee.id)
        is_direct_report = (e.reporting_manager_id == current_employee.id)
        has_sensitive_access = (
            user_role in ["admin", "hr"] or
            (user_role == "manager" and (is_self or is_direct_report)) or
            is_self
        )
        
        emp_data = {
            "employee_code": e.employee_id,
            "name": e.full_name,
            "email": e.email,
            "phone": e.phone if is_self or user_role in ["admin", "hr", "manager"] else "N/A",
            "gender": e.gender if is_self or user_role in ["admin", "hr", "manager"] else "N/A",
            "designation": e.designation,
            "department": dept_map.get(e.department_id, "N/A"),
            "reporting_manager": mgr_map.get(e.reporting_manager_id, "None"),
            "joining_date": str(e.joining_date) if e.joining_date else "N/A",
            "status": e.employment_status.value if hasattr(e.employment_status, "value") else str(e.employment_status),
            "employment_type": e.employment_type.value if hasattr(e.employment_type, "value") else str(e.employment_type),
            "is_active": e.is_active,
        }
        
        if has_sensitive_access:
            emp_data.update({
                "casual_leave_balance": e.casual_leave_balance,
                "sick_leave_balance": e.sick_leave_balance,
                "earned_leave_balance": e.earned_leave_balance,
            })
        employee_list.append(emp_data)

    context = {
        "current_user": {
            "name": current_user.full_name,
            "email": current_user.email,
            "role": user_role,
            "employee_id": current_employee.employee_id,
            "designation": current_employee.designation,
            "casual_leave_balance": current_employee.casual_leave_balance,
            "sick_leave_balance": current_employee.sick_leave_balance,
            "earned_leave_balance": current_employee.earned_leave_balance,
            "status": current_employee.employment_status.value if hasattr(current_employee.employment_status, "value") else str(current_employee.employment_status),
        },
        "current_user_leave_requests": [
            {
                "id": l.id,
                "type": l.leave_type.value if hasattr(l.leave_type, "value") else str(l.leave_type),
                "days": l.days,
                "start_date": str(l.start_date),
                "end_date": str(l.end_date),
                "status": l.status.value if hasattr(l.status, "value") else str(l.status),
                "reason": l.reason,
            }
            for l in personal_leaves
        ],
        "current_user_recent_attendance": [
            {
                "date": str(att.date),
                "status": att.status.value if hasattr(att.status, "value") else str(att.status),
                "check_in": att.check_in.strftime('%Y-%m-%d %I:%M %p') if att.check_in else None,
                "check_out": att.check_out.strftime('%Y-%m-%d %I:%M %p') if att.check_out else None,
                "work_hours": att.work_hours,
            }
            for att in personal_attendance
        ],
        "today_checkins": today_checkins,
        "total_employees_registered": len(employees),
        "total_active_employees": active_count,
        "employees_on_notice": [{"name": e.full_name, "designation": e.designation} for e in on_notice],
        "pending_leave_requests": len(pending_leaves),
        "pending_leaves_detail": [
            {
                "employee": mgr_map.get(l.employee_id, "Unknown"),
                "type": l.leave_type.value if hasattr(l.leave_type, "value") else str(l.leave_type),
                "days": l.days,
                "from": str(l.start_date),
            }
            for l in pending_leaves[:10]
        ],
        "employee_list": employee_list,
        "historical_attendance_summary_3_months": historical_summary,
        "total_unique_employees_checked_in_last_90_days": unique_emp_count,
        "retrieved_corporate_documents_context": rag_context
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
    """Calculate attrition risk for all active employees in an optimized way."""
    from app.services.ai_service import _chat, _AI_ENABLED
    from sqlalchemy import func
    from app.models.employee import Department
    
    employees = db.query(Employee).filter(
        Employee.employment_status == EmploymentStatus.ACTIVE,
        Employee.is_active == True,
    ).all()

    if not employees:
        return []

    emp_ids = [emp.id for emp in employees]

    # 1. Pre-fetch departments
    dept_map = {d.id: d.name for d in db.query(Department).all()}

    # 2. Pre-fetch performance reviews for active employees
    reviews_list = db.query(PerformanceReview).filter(
        PerformanceReview.employee_id.in_(emp_ids)
    ).all()
    emp_reviews = {}
    for r in reviews_list:
        emp_reviews.setdefault(r.employee_id, []).append(r)
    # Sort reviews desc by created_at and slice to 3
    for eid in emp_reviews:
        emp_reviews[eid].sort(key=lambda x: x.created_at or datetime.min, reverse=True)
        emp_reviews[eid] = emp_reviews[eid][:3]

    # 3. Pre-fetch leave requests
    leaves_list = db.query(LeaveRequest).filter(
        LeaveRequest.employee_id.in_(emp_ids)
    ).all()
    emp_leaves = {}
    for l in leaves_list:
        emp_leaves.setdefault(l.employee_id, []).append(l)

    # 4. Pre-fetch attendance counts
    attendance_counts = db.query(Attendance.employee_id, func.count(Attendance.id))\
        .filter(Attendance.employee_id.in_(emp_ids))\
        .group_by(Attendance.employee_id).all()
    emp_attendance = {emp_id: count for emp_id, count in attendance_counts}

    results = []
    for emp in employees:
        reviews = emp_reviews.get(emp.id, [])
        leaves = emp_leaves.get(emp.id, [])
        attendance_count = emp_attendance.get(emp.id, 0)

        # Calculate local score immediately (skip slow single LLM calls)
        risk = calculate_attrition_risk(emp, reviews, leaves, attendance_count, skip_llm=True)

        results.append({
            "employee_id": emp.id,
            "employee_code": emp.employee_id,
            "full_name": emp.full_name,
            "designation": emp.designation,
            "department": dept_map.get(emp.department_id, "—"),
            "tenure_months": ((__import__('datetime').date.today() - emp.joining_date).days // 30) if emp.joining_date else 0,
            **risk,
        })

    # 5. Bulk AI recommendations for employees with high or medium risk in a single OpenRouter request!
    target_employees = [e for e in results if e.get("risk_level") in ["high", "medium"]]
    if _AI_ENABLED and target_employees:
        emp_bullets = []
        for e in target_employees:
            emp_bullets.append(
                f"- ID {e['employee_id']}: {e['full_name']} ({e['designation']}), "
                f"Risk Score: {e['risk_score']}/100, Factors: {'; '.join(e['factors'])}"
            )
        joined_bullets = "\n".join(emp_bullets)
        prompt = f"""We have calculated employee attrition risks. Write a tailored, highly professional 1 to 2-sentence HR retention recommendation for each.
Return a JSON object mapping Employee IDs (as string keys) to recommendations.
Example:
{{
  "1": "Schedule a compensation review...",
  "2": "Discuss workload balance..."
}}

Employees list:
{joined_bullets}"""
        
        try:
            bulk_result = _chat(prompt)
            if isinstance(bulk_result, dict):
                for e in results:
                    emp_key = str(e["employee_id"])
                    if emp_key in bulk_result:
                        e["recommendation"] = bulk_result[emp_key]
        except Exception as ex:
            import logging
            logger = logging.getLogger("uvicorn")
            logger.error(f"Error in bulk attrition AI recommendation: {ex}")

    # Fill in defaults if any recommendation is missing
    for e in results:
        if not e.get("recommendation"):
            if e["risk_level"] == "high":
                e["recommendation"] = "Immediate manager check-in and compensation review recommended."
            elif e["risk_level"] == "medium":
                e["recommendation"] = "Schedule a career development conversation within 30 days."
            else:
                e["recommendation"] = "Employee appears stable. Continue regular engagement."

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


# ─── AI Policy & Document RAG Query ───────────────────────────────────────
class DocQueryRequest(BaseModel):
    query: str

@router.post("/query-docs")
def query_documents(
    request: DocQueryRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_employee: Employee = Depends(get_current_employee)
):
    """Secure RAG document query specifically for the Documents page, isolating files by employee role."""
    from app.services.ai_service import search_documents_rag, _call_openrouter
    
    # 1. Retrieve isolated document context matching employee permissions
    employee_id = current_employee.id if current_user.role.value in ["employee", "manager"] else None
    rag_context = search_documents_rag(
        query=request.query,
        db=db,
        employee_id=employee_id
    )
    
    if not rag_context:
        return {
            "answer": "No relevant company documents or policies could be found matching your query. Please make sure the documents are uploaded and that you have permission to view them.",
            "references": []
        }
        
    # 2. Structure an LLM query using the RAG context
    system_prompt = (
        "You are TechCorp's HR AI Assistant. Your task is to answer employee queries using strictly the "
        "retrieved corporate document context provided below. Be precise, professional, and helpful. "
        "If the answer cannot be found in the context, state that clearly. "
        "Always cite the source document name if you use facts from it."
    )
    
    user_prompt = f"Employee Question: {request.query}\n\nRetrieved Document Context:\n{rag_context}"
    
    # Call OpenRouter (re-uses cache / fallback handling)
    try:
        answer = _call_openrouter(user_prompt, system_prompt)
    except Exception as e:
        answer = f"Error processing query: {str(e)}"
        
    # Format matching references from the rag_context text block
    references = []
    for block in rag_context.split("\n\n"):
        if block.startswith("[Source Document:"):
            # Parse header "[Source Document: Title (Filename)]"
            header = block.split("]")[0].replace("[Source Document:", "").strip()
            # Title is before open paren, filename is inside
            title = header
            file_name = ""
            if "(" in header and header.endswith(")"):
                parts = header.rsplit("(", 1)
                title = parts[0].strip()
                file_name = parts[1][:-1].strip()
            
            content = block.split("]", 1)[1].strip() if "]" in block else block
            references.append({
                "title": title,
                "file_name": file_name,
                "snippet": content[:200] + "..." if len(content) > 200 else content
            })
            
    return {
        "answer": answer,
        "references": references
    }
