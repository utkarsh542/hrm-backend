"""Jobs router — CRUD for job postings."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.models.job import Job, JobStatus, JobType
from app.models.candidate import Application
from app.schemas.schemas import JobCreate, JobUpdate, JobResponse

router = APIRouter(prefix="/api/jobs", tags=["Jobs"])


@router.get("/", response_model=list[JobResponse])
def list_jobs(
    status: Optional[str] = None,
    department: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(Job)
    if status:
        query = query.filter(Job.status == JobStatus(status))
    if department:
        query = query.filter(Job.department == department)
    if search:
        query = query.filter(Job.title.ilike(f"%{search}%"))
    
    jobs = query.order_by(Job.created_at.desc()).all()
    result = []
    for job in jobs:
        count = db.query(Application).filter(Application.job_id == job.id).count()
        resp = JobResponse.model_validate(job)
        resp.applications_count = count
        result.append(resp)
    return result


@router.get("/{job_id}", response_model=JobResponse)
def get_job(job_id: int, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    count = db.query(Application).filter(Application.job_id == job.id).count()
    resp = JobResponse.model_validate(job)
    resp.applications_count = count
    return resp


@router.post("/", response_model=JobResponse)
def create_job(request: JobCreate, db: Session = Depends(get_db)):
    job = Job(**request.model_dump())
    db.add(job)
    db.commit()
    db.refresh(job)
    resp = JobResponse.model_validate(job)
    resp.applications_count = 0
    return resp


@router.put("/{job_id}", response_model=JobResponse)
def update_job(job_id: int, request: JobUpdate, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    update_data = request.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        if key == "status":
            value = JobStatus(value)
        elif key == "job_type":
            value = JobType(value)
        setattr(job, key, value)
    
    db.commit()
    db.refresh(job)
    count = db.query(Application).filter(Application.job_id == job.id).count()
    resp = JobResponse.model_validate(job)
    resp.applications_count = count
    return resp


@router.delete("/{job_id}")
def delete_job(job_id: int, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    db.delete(job)
    db.commit()
    return {"message": "Job deleted successfully"}


@router.get("/departments/list")
def list_departments_from_jobs(db: Session = Depends(get_db)):
    departments = db.query(Job.department).distinct().all()
    return [d[0] for d in departments if d[0]]


@router.post("/generate-jd")
def generate_jd_for_job(job_id: int, db: Session = Depends(get_db)):
    """Generate AI job description for an existing job posting."""
    from app.services.ai_service import generate_job_description
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    result = generate_job_description(
        title=job.title,
        department=job.department,
        experience_min=job.experience_min,
        experience_max=job.experience_max,
        skills=job.skills or "",
    )
    # Update job with AI-generated content
    if result.get("description"):
        job.description = result["description"]
    if result.get("requirements"):
        job.requirements = "\n".join(result["requirements"])
    db.commit()
    db.refresh(job)
    resp = JobResponse.model_validate(job)
    resp.applications_count = db.query(Application).filter(Application.job_id == job.id).count()
    return {"job": resp, "ai_content": result}
