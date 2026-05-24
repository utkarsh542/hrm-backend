"""Advanced analytics and AI insights."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import date
from app.database import get_db
from app.models.employee import Employee, Department
from app.models.job import Job, JobStatus
from app.models.candidate import Application
from app.models.attendance import LeaveRequest
from app.models.offboarding import Resignation
from app.services.ai_service import generate_workforce_insights

router = APIRouter(prefix="/api/analytics", tags=["Analytics"])


@router.get("/workforce")
def get_workforce_analytics(db: Session = Depends(get_db)):
    total = db.query(Employee).count()
    active = db.query(Employee).filter(Employee.is_active == True).count()
    male = db.query(Employee).filter(Employee.gender == "M", Employee.is_active == True).count()
    female = db.query(Employee).filter(Employee.gender == "F", Employee.is_active == True).count()

    departments = db.query(Department).all()
    dept_dist = []
    for dept in departments:
        count = db.query(Employee).filter(Employee.department_id == dept.id, Employee.is_active == True).count()
        if count > 0:
            dept_dist.append({"name": dept.name, "count": count})

    tenure_buckets = {"<1 year": 0, "1-2 years": 0, "2-5 years": 0, "5+ years": 0}
    for emp in db.query(Employee).filter(Employee.is_active == True).all():
        if emp.joining_date:
            years = (date.today() - emp.joining_date).days / 365
            if years < 1: tenure_buckets["<1 year"] += 1
            elif years < 2: tenure_buckets["1-2 years"] += 1
            elif years < 5: tenure_buckets["2-5 years"] += 1
            else: tenure_buckets["5+ years"] += 1

    employees = db.query(Employee).filter(Employee.is_active == True, Employee.ctc > 0).all()
    avg_ctc = sum(e.ctc for e in employees) / len(employees) if employees else 0
    month_start = date.today().replace(day=1)
    new_hires = db.query(Employee).filter(Employee.joining_date >= month_start).count()
    quarter_start = date.today().replace(month=((date.today().month - 1) // 3) * 3 + 1, day=1)
    resignations = db.query(Resignation).filter(Resignation.resignation_date >= quarter_start).count()
    attrition_rate = round((resignations / max(active, 1)) * 100, 1)

    return {
        "total_employees": total, "active_employees": active,
        "gender_distribution": {"male": male, "female": female, "other": active - male - female},
        "department_distribution": dept_dist, "tenure_distribution": tenure_buckets,
        "avg_ctc": round(avg_ctc), "new_hires_this_month": new_hires,
        "resignations_this_quarter": resignations, "attrition_rate": attrition_rate,
    }


@router.get("/hiring")
def get_hiring_analytics(db: Session = Depends(get_db)):
    open_jobs = db.query(Job).filter(Job.status == JobStatus.OPEN).count()
    total_apps = db.query(Application).count()
    sources = {}
    for app in db.query(Application).all():
        src = app.source.value if hasattr(app.source, 'value') else str(app.source)
        sources.setdefault(src, {"total": 0, "hired": 0})
        sources[src]["total"] += 1
        status_val = app.status.value if hasattr(app.status, 'value') else str(app.status)
        if status_val == "hired":
            sources[src]["hired"] += 1
    source_data = [
        {"source": k, "applications": v["total"], "hired": v["hired"],
         "conversion_rate": round((v["hired"] / v["total"]) * 100, 1) if v["total"] > 0 else 0}
        for k, v in sources.items()
    ]
    return {"open_positions": open_jobs, "total_applications": total_apps, "source_effectiveness": source_data}


@router.get("/ai-insights")
def get_ai_insights(db: Session = Depends(get_db)):
    active = db.query(Employee).filter(Employee.is_active == True).count()
    pending_leaves = db.query(LeaveRequest).filter(LeaveRequest.status == "pending").count()
    open_positions = db.query(Job).filter(Job.status == JobStatus.OPEN).count()
    total_apps = db.query(Application).count()
    stats = {"total_employees": active, "open_positions": open_positions,
             "total_applications": total_apps, "pending_leaves": pending_leaves}
    return generate_workforce_insights(stats)


@router.get("/compensation")
def get_compensation_analytics(db: Session = Depends(get_db)):
    departments = db.query(Department).all()
    dept_comp = []
    for dept in departments:
        emps = db.query(Employee).filter(Employee.department_id == dept.id, Employee.is_active == True, Employee.ctc > 0).all()
        if emps:
            ctcs = [e.ctc for e in emps]
            dept_comp.append({"department": dept.name, "avg_ctc": round(sum(ctcs) / len(ctcs)),
                              "min_ctc": min(ctcs), "max_ctc": max(ctcs),
                              "headcount": len(ctcs), "total_cost": sum(ctcs)})
    return {"department_compensation": dept_comp}
