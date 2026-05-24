"""Skills, training, and succession planning router."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import date
from pydantic import BaseModel
from typing import Optional, List
from app.database import get_db
from app.models.skills import (Skill, SkillCategory, EmployeeSkill, TrainingProgram, TrainingEnrollment, SuccessionPlan, SuccessionCandidate)
from app.models.employee import Employee, Department
from app.services.ai_service import analyze_skill_gaps, assess_succession_readiness

router = APIRouter(prefix="/api/skills", tags=["Skills & Training"])


class SkillCreate(BaseModel):
    name: str
    category: str = "technical"
    description: Optional[str] = None

class EmployeeSkillCreate(BaseModel):
    employee_id: int
    skill_id: int
    proficiency: int = 3

class TrainingCreate(BaseModel):
    title: str
    description: Optional[str] = None
    category: Optional[str] = None
    provider: Optional[str] = None
    duration_hours: int = 0
    is_mandatory: bool = False
    skills_covered: Optional[List[str]] = None

class SuccessionPlanCreate(BaseModel):
    position: str
    department: Optional[str] = None
    current_holder_id: Optional[int] = None
    criticality: str = "medium"


# ─── Skills ───

@router.get("/")
def list_skills(db: Session = Depends(get_db)):
    skills = db.query(Skill).order_by(Skill.name).all()
    return [{"id": s.id, "name": s.name, "category": s.category.value if s.category else "technical",
             "description": s.description,
             "employee_count": db.query(EmployeeSkill).filter(EmployeeSkill.skill_id == s.id).count()} for s in skills]

@router.post("/")
def create_skill(data: SkillCreate, db: Session = Depends(get_db)):
    existing = db.query(Skill).filter(Skill.name == data.name).first()
    if existing:
        return {"id": existing.id, "message": "Skill already exists"}
    try:
        cat = SkillCategory(data.category)
    except ValueError:
        cat = SkillCategory.technical
    skill = Skill(name=data.name, category=cat, description=data.description)
    db.add(skill)
    db.commit()
    db.refresh(skill)
    return {"id": skill.id, "message": "Skill created"}

@router.get("/matrix")
def get_skills_matrix(db: Session = Depends(get_db)):
    departments = db.query(Department).all()
    skills = db.query(Skill).all()
    matrix = []
    for dept in departments:
        emp_ids = [e.id for e in db.query(Employee).filter(Employee.department_id == dept.id, Employee.is_active == True).all()]
        dept_skills = {}
        for skill in skills:
            if not emp_ids:
                continue
            records = db.query(EmployeeSkill).filter(EmployeeSkill.skill_id == skill.id, EmployeeSkill.employee_id.in_(emp_ids)).all()
            if records:
                avg = sum(es.proficiency for es in records) / len(records)
                dept_skills[skill.name] = {"count": len(records), "avg_proficiency": round(avg, 1)}
        matrix.append({"department": dept.name, "department_id": dept.id, "employee_count": len(emp_ids), "skills": dept_skills})
    return matrix

@router.get("/employee/{employee_id}")
def get_employee_skills(employee_id: int, db: Session = Depends(get_db)):
    emp = db.query(Employee).filter(Employee.id == employee_id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    emp_skills = db.query(EmployeeSkill).filter(EmployeeSkill.employee_id == employee_id).all()
    result = []
    for es in emp_skills:
        skill = db.query(Skill).filter(Skill.id == es.skill_id).first()
        if skill:
            result.append({"id": es.id, "skill_id": skill.id, "skill_name": skill.name,
                           "category": skill.category.value if skill.category else "technical",
                           "proficiency": es.proficiency, "verified": es.verified})
    return {"employee_name": emp.full_name, "skills": result}

@router.post("/employee")
def add_employee_skill(data: EmployeeSkillCreate, db: Session = Depends(get_db)):
    existing = db.query(EmployeeSkill).filter(EmployeeSkill.employee_id == data.employee_id, EmployeeSkill.skill_id == data.skill_id).first()
    if existing:
        existing.proficiency = data.proficiency
        db.commit()
        return {"message": "Skill updated"}
    es = EmployeeSkill(employee_id=data.employee_id, skill_id=data.skill_id, proficiency=max(1, min(5, data.proficiency)))
    db.add(es)
    db.commit()
    return {"message": "Skill added"}

@router.get("/gaps/{employee_id}")
def get_skill_gaps(employee_id: int, db: Session = Depends(get_db)):
    emp = db.query(Employee).filter(Employee.id == employee_id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    emp_skills = db.query(EmployeeSkill).filter(EmployeeSkill.employee_id == employee_id).all()
    skill_names = []
    for es in emp_skills:
        skill = db.query(Skill).filter(Skill.id == es.skill_id).first()
        if skill:
            skill_names.append(skill.name)
    role_requirements = ["Communication", "Problem Solving", "Leadership", "Teamwork"]
    desig = (emp.designation or "").lower()
    if any(kw in desig for kw in ["developer", "engineer", "architect"]):
        role_requirements.extend(["Python", "JavaScript", "SQL", "Git", "API Design"])
    elif any(kw in desig for kw in ["manager", "lead", "director"]):
        role_requirements.extend(["Strategic Planning", "People Management", "Budgeting"])
    elif "designer" in desig:
        role_requirements.extend(["Figma", "UI/UX", "Design Systems", "Prototyping"])
    return analyze_skill_gaps(skill_names, role_requirements, emp.designation or "Employee")


# ─── Training ───

@router.get("/training/programs")
def list_training_programs(db: Session = Depends(get_db)):
    programs = db.query(TrainingProgram).all()
    return [{"id": p.id, "title": p.title, "description": p.description, "category": p.category,
             "provider": p.provider, "duration_hours": p.duration_hours, "is_mandatory": p.is_mandatory,
             "skills_covered": p.skills_covered or [],
             "enrolled_count": db.query(TrainingEnrollment).filter(TrainingEnrollment.program_id == p.id).count()} for p in programs]

@router.post("/training/programs")
def create_training_program(data: TrainingCreate, db: Session = Depends(get_db)):
    program = TrainingProgram(title=data.title, description=data.description, category=data.category,
                              provider=data.provider, duration_hours=data.duration_hours,
                              is_mandatory=data.is_mandatory, skills_covered=data.skills_covered)
    db.add(program)
    db.commit()
    db.refresh(program)
    return {"id": program.id, "message": "Training program created"}

@router.post("/training/enroll")
def enroll_in_training(program_id: int, employee_id: int, db: Session = Depends(get_db)):
    existing = db.query(TrainingEnrollment).filter(TrainingEnrollment.program_id == program_id, TrainingEnrollment.employee_id == employee_id).first()
    if existing:
        return {"message": "Already enrolled"}
    enrollment = TrainingEnrollment(program_id=program_id, employee_id=employee_id)
    db.add(enrollment)
    db.commit()
    return {"message": "Enrolled successfully"}

@router.get("/training/employee/{employee_id}")
def get_employee_training(employee_id: int, db: Session = Depends(get_db)):
    enrollments = db.query(TrainingEnrollment).filter(TrainingEnrollment.employee_id == employee_id).all()
    result = []
    for en in enrollments:
        program = db.query(TrainingProgram).filter(TrainingProgram.id == en.program_id).first()
        if program:
            result.append({"enrollment_id": en.id, "program_id": program.id, "title": program.title,
                           "category": program.category, "provider": program.provider,
                           "duration_hours": program.duration_hours, "status": en.status,
                           "progress": en.progress,
                           "enrolled_at": en.enrolled_at.isoformat() if en.enrolled_at else None,
                           "completed_at": en.completed_at.isoformat() if en.completed_at else None})
    return result


# ─── Succession ───

@router.get("/succession/plans")
def list_succession_plans(db: Session = Depends(get_db)):
    plans = db.query(SuccessionPlan).all()
    result = []
    for p in plans:
        candidates = db.query(SuccessionCandidate).filter(SuccessionCandidate.plan_id == p.id).all()
        holder = db.query(Employee).filter(Employee.id == p.current_holder_id).first() if p.current_holder_id else None
        cand_list = []
        for c in candidates:
            emp = db.query(Employee).filter(Employee.id == c.employee_id).first()
            if emp:
                cand_list.append({"id": c.id, "employee_id": emp.id, "employee_name": emp.full_name,
                                  "designation": emp.designation, "readiness": c.readiness,
                                  "ai_score": c.ai_score, "gaps": c.gaps or [], "development_actions": c.development_actions or []})
        result.append({"id": p.id, "position": p.position, "department": p.department,
                       "criticality": p.criticality, "current_holder": holder.full_name if holder else None, "candidates": cand_list})
    return result

@router.post("/succession/plans")
def create_succession_plan(data: SuccessionPlanCreate, db: Session = Depends(get_db)):
    plan = SuccessionPlan(position=data.position, department=data.department,
                          current_holder_id=data.current_holder_id, criticality=data.criticality)
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return {"id": plan.id, "message": "Succession plan created"}

@router.post("/succession/plans/{plan_id}/assess")
def assess_candidate(plan_id: int, employee_id: int, db: Session = Depends(get_db)):
    plan = db.query(SuccessionPlan).filter(SuccessionPlan.id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    emp = db.query(Employee).filter(Employee.id == employee_id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    emp_skills_db = db.query(EmployeeSkill).filter(EmployeeSkill.employee_id == employee_id).all()
    skill_names = []
    for es in emp_skills_db:
        skill = db.query(Skill).filter(Skill.id == es.skill_id).first()
        if skill:
            skill_names.append(skill.name)
    from app.models.performance import PerformanceReview
    review = db.query(PerformanceReview).filter(PerformanceReview.employee_id == employee_id).order_by(PerformanceReview.created_at.desc()).first()
    rating = review.overall_rating if review and review.overall_rating else 3.5
    tenure_years = (date.today() - emp.joining_date).days / 365 if emp.joining_date else 1.0
    assessment = assess_succession_readiness(emp.full_name, emp.designation or "", plan.position, rating, tenure_years, skill_names)
    existing = db.query(SuccessionCandidate).filter(SuccessionCandidate.plan_id == plan_id, SuccessionCandidate.employee_id == employee_id).first()
    if existing:
        existing.readiness = assessment.get("readiness", "1-2_years")
        existing.ai_score = assessment.get("readiness_score", 50)
        existing.gaps = assessment.get("development_gaps", [])
        existing.development_actions = assessment.get("development_actions", [])
    else:
        candidate = SuccessionCandidate(plan_id=plan_id, employee_id=employee_id,
                                        readiness=assessment.get("readiness", "1-2_years"),
                                        ai_score=assessment.get("readiness_score", 50),
                                        gaps=assessment.get("development_gaps", []),
                                        development_actions=assessment.get("development_actions", []))
        db.add(candidate)
    db.commit()
    return assessment
