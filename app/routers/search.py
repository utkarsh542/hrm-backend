"""Unified search across all entities."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.employee import Employee
from app.models.candidate import Candidate
from app.models.job import Job

router = APIRouter(prefix="/api/search", tags=["Search"])


@router.get("/")
def unified_search(q: str, db: Session = Depends(get_db)):
    if not q or len(q) < 2:
        return {"results": []}
    term = f"%{q}%"
    results = []

    for e in db.query(Employee).filter(
        (Employee.full_name.ilike(term)) | (Employee.email.ilike(term)) |
        (Employee.employee_id.ilike(term)) | (Employee.designation.ilike(term))
    ).limit(5).all():
        results.append({"type": "employee", "id": e.id, "title": e.full_name,
                         "subtitle": e.designation or "Employee", "link": f"/employees/{e.id}", "icon": "👤"})

    for c in db.query(Candidate).filter(
        (Candidate.full_name.ilike(term)) | (Candidate.email.ilike(term)) | (Candidate.skills.ilike(term))
    ).limit(5).all():
        results.append({"type": "candidate", "id": c.id, "title": c.full_name,
                         "subtitle": c.current_designation or "Candidate", "link": "/recruitment/candidates", "icon": "🎯"})

    for j in db.query(Job).filter(
        (Job.title.ilike(term)) | (Job.department.ilike(term)) | (Job.skills.ilike(term))
    ).limit(5).all():
        results.append({"type": "job", "id": j.id, "title": j.title,
                         "subtitle": f"{j.department}", "link": "/recruitment", "icon": "💼"})

    return {"results": results[:15]}
