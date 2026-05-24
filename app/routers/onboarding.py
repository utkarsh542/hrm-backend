"""Onboarding router — AI-powered employee onboarding."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
from app.database import get_db
from app.models.onboarding import OnboardingPlan, OnboardingTask, OnboardingTaskStatus, OnboardingTaskCategory
from app.models.employee import Employee, Department
from app.services.ai_service import generate_onboarding_plan

router = APIRouter(prefix="/api/onboarding", tags=["Onboarding"])


@router.get("/plans")
def list_plans(employee_id: int = None, db: Session = Depends(get_db)):
    query = db.query(OnboardingPlan)
    if employee_id:
        query = query.filter(OnboardingPlan.employee_id == employee_id)
    plans = query.order_by(OnboardingPlan.created_at.desc()).all()
    result = []
    for p in plans:
        tasks = db.query(OnboardingTask).filter(OnboardingTask.plan_id == p.id).all()
        total = len(tasks)
        completed = len([t for t in tasks if t.status == OnboardingTaskStatus.completed])
        emp = db.query(Employee).filter(Employee.id == p.employee_id).first()
        result.append({
            "id": p.id, "employee_id": p.employee_id,
            "employee_name": emp.full_name if emp else "",
            "plan_name": p.plan_name, "department": p.department,
            "role": p.role, "status": p.status, "ai_generated": p.ai_generated,
            "total_tasks": total, "completed_tasks": completed,
            "progress": round((completed / total) * 100) if total > 0 else 0,
            "created_at": p.created_at.isoformat() if p.created_at else None,
        })
    return result


@router.get("/plans/{plan_id}")
def get_plan(plan_id: int, db: Session = Depends(get_db)):
    plan = db.query(OnboardingPlan).filter(OnboardingPlan.id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    tasks = db.query(OnboardingTask).filter(OnboardingTask.plan_id == plan_id).order_by(OnboardingTask.due_day, OnboardingTask.order).all()
    emp = db.query(Employee).filter(Employee.id == plan.employee_id).first()
    return {
        "id": plan.id, "employee_id": plan.employee_id,
        "employee_name": emp.full_name if emp else "",
        "plan_name": plan.plan_name, "department": plan.department,
        "role": plan.role, "status": plan.status, "ai_generated": plan.ai_generated,
        "created_at": plan.created_at.isoformat() if plan.created_at else None,
        "tasks": [
            {"id": t.id, "title": t.title, "description": t.description,
             "category": t.category.value if t.category else "training",
             "due_day": t.due_day, "status": t.status.value if t.status else "pending",
             "priority": t.priority, "notes": t.notes,
             "completed_at": t.completed_at.isoformat() if t.completed_at else None}
            for t in tasks
        ],
    }


@router.post("/generate-plan")
def generate_plan(employee_id: int, db: Session = Depends(get_db)):
    emp = db.query(Employee).filter(Employee.id == employee_id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    dept_name = ""
    if emp.department_id:
        dept = db.query(Department).filter(Department.id == emp.department_id).first()
        dept_name = dept.name if dept else ""

    ai_plan = generate_onboarding_plan(emp.full_name, emp.designation or "Employee", dept_name)
    plan = OnboardingPlan(
        employee_id=employee_id,
        plan_name=ai_plan.get("plan_name", f"Onboarding: {emp.full_name}"),
        department=dept_name, role=emp.designation, ai_generated=True,
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)

    for i, td in enumerate(ai_plan.get("tasks", [])):
        cat_val = td.get("category", "training")
        try:
            cat = OnboardingTaskCategory(cat_val)
        except ValueError:
            cat = OnboardingTaskCategory.training
        task = OnboardingTask(
            plan_id=plan.id, title=td.get("title", f"Task {i+1}"),
            description=td.get("description", ""), category=cat,
            due_day=td.get("day", i + 1), priority=td.get("priority", "medium"), order=i,
        )
        db.add(task)
    db.commit()
    return {"id": plan.id, "message": "AI onboarding plan generated successfully"}


@router.put("/tasks/{task_id}")
def update_task(task_id: int, status: str, notes: str = None, db: Session = Depends(get_db)):
    task = db.query(OnboardingTask).filter(OnboardingTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    try:
        task.status = OnboardingTaskStatus(status)
    except ValueError:
        task.status = OnboardingTaskStatus.pending
    if status == "completed":
        task.completed_at = datetime.utcnow()
    if notes:
        task.notes = notes
    db.commit()

    # Auto-complete plan if all tasks done
    plan = db.query(OnboardingPlan).filter(OnboardingPlan.id == task.plan_id).first()
    if plan:
        all_tasks = db.query(OnboardingTask).filter(OnboardingTask.plan_id == plan.id).all()
        if all(t.status == OnboardingTaskStatus.completed for t in all_tasks):
            plan.status = "completed"
            plan.completed_at = datetime.utcnow()
            db.commit()
    return {"success": True}
