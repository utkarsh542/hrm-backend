"""Candidates & Applications router."""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.models.candidate import Candidate, Application, ApplicationStatus
from app.models.job import Job
from app.schemas.schemas import (
    CandidateCreate, CandidateResponse,
    ApplicationCreate, ApplicationUpdate, ApplicationResponse
)
from app.services.ai_service import screen_resume

router = APIRouter(prefix="/api/candidates", tags=["Candidates"])


# ===== CANDIDATES =====
@router.get("/", response_model=list[CandidateResponse])
def list_candidates(search: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(Candidate)
    if search:
        query = query.filter(
            (Candidate.full_name.ilike(f"%{search}%")) |
            (Candidate.email.ilike(f"%{search}%")) |
            (Candidate.skills.ilike(f"%{search}%"))
        )
    return [CandidateResponse.model_validate(c) for c in query.order_by(Candidate.created_at.desc()).all()]


@router.post("/", response_model=CandidateResponse)
def create_candidate(request: CandidateCreate, db: Session = Depends(get_db)):
    existing = db.query(Candidate).filter(Candidate.email == request.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Candidate with this email already exists")
    
    candidate = Candidate(**request.model_dump())
    db.add(candidate)
    db.commit()
    db.refresh(candidate)
    return CandidateResponse.model_validate(candidate)


@router.get("/{candidate_id}", response_model=CandidateResponse)
def get_candidate(candidate_id: int, db: Session = Depends(get_db)):
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    return CandidateResponse.model_validate(candidate)


# ===== APPLICATIONS =====
@router.get("/applications/all", response_model=list[ApplicationResponse])
def list_applications(
    status: Optional[str] = None,
    job_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    query = db.query(Application)
    if status:
        query = query.filter(Application.status == ApplicationStatus(status))
    if job_id:
        query = query.filter(Application.job_id == job_id)
    
    applications = query.order_by(Application.applied_at.desc()).all()
    result = []
    for app in applications:
        candidate = db.query(Candidate).filter(Candidate.id == app.candidate_id).first()
        job = db.query(Job).filter(Job.id == app.job_id).first()
        resp = ApplicationResponse.model_validate(app)
        resp.candidate_name = candidate.full_name if candidate else ""
        resp.candidate_email = candidate.email if candidate else ""
        resp.job_title = job.title if job else ""
        result.append(resp)
    return result


@router.post("/applications/", response_model=ApplicationResponse)
def create_application(request: ApplicationCreate, db: Session = Depends(get_db)):
    # Verify candidate and job exist
    candidate = db.query(Candidate).filter(Candidate.id == request.candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    
    job = db.query(Job).filter(Job.id == request.job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Check if already applied
    existing = db.query(Application).filter(
        Application.candidate_id == request.candidate_id,
        Application.job_id == request.job_id
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Candidate has already applied for this job")
    
    application = Application(**request.model_dump())
    
    # Run AI screening
    screening = screen_resume(
        candidate_skills=candidate.skills or "",
        job_requirements=job.skills or job.requirements or "",
        experience_years=candidate.experience_years
    )
    application.ai_score = screening["score"]
    application.ai_summary = screening["summary"]
    
    db.add(application)
    db.commit()
    db.refresh(application)
    
    resp = ApplicationResponse.model_validate(application)
    resp.candidate_name = candidate.full_name
    resp.candidate_email = candidate.email
    resp.job_title = job.title
    return resp


@router.put("/applications/{app_id}", response_model=ApplicationResponse)
def update_application(app_id: int, request: ApplicationUpdate, db: Session = Depends(get_db)):
    application = db.query(Application).filter(Application.id == app_id).first()
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")
    
    update_data = request.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        if key == "status":
            value = ApplicationStatus(value)
        setattr(application, key, value)
    
    db.commit()
    db.refresh(application)
    
    candidate = db.query(Candidate).filter(Candidate.id == application.candidate_id).first()
    job = db.query(Job).filter(Job.id == application.job_id).first()
    resp = ApplicationResponse.model_validate(application)
    resp.candidate_name = candidate.full_name if candidate else ""
    resp.candidate_email = candidate.email if candidate else ""
    resp.job_title = job.title if job else ""
    return resp


@router.get("/applications/pipeline")
def get_pipeline(db: Session = Depends(get_db)):
    """Get all applications grouped by status for Kanban view."""
    statuses = [s.value for s in ApplicationStatus]
    pipeline = {}
    for status in statuses:
        apps = db.query(Application).filter(Application.status == ApplicationStatus(status)).all()
        items = []
        for app in apps:
            candidate = db.query(Candidate).filter(Candidate.id == app.candidate_id).first()
            job = db.query(Job).filter(Job.id == app.job_id).first()
            items.append({
                "id": app.id,
                "candidate_id": app.candidate_id,
                "candidate_name": candidate.full_name if candidate else "",
                "candidate_email": candidate.email if candidate else "",
                "job_id": app.job_id,
                "job_title": job.title if job else "",
                "ai_score": app.ai_score,
                "source": app.source.value if app.source else "website",
                "applied_at": app.applied_at.isoformat() if app.applied_at else "",
            })
        pipeline[status] = items
    return pipeline
